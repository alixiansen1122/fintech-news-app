import streamlit as st
from supabase import create_client, Client
import pandas as pd 
# 页面配置
st.set_page_config(page_title="AI 金融情报局", page_icon="📈", layout="wide")

# 读取 Secrets
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except:
    st.error("请在 Streamlit Cloud 配置 Secrets")
    st.stop()

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_connection()

def get_news():
    try:
        # 记得获取 tags 和 sentiment_score
        response = supabase.table("news").select("*").order("created_at", desc=True).limit(30).execute()
        return response.data
    except Exception as e:
        st.error(f"数据库连接失败: {e}")
        return []

# --- UI 逻辑 ---

with st.sidebar:
    st.header("🔍 筛选")
    if st.button("🔄 刷新数据"):
        st.rerun()
    st.info("🟢 绿色 = 利好\n🔴 红色 = 利空\n⚪ 灰色 = 中性/旧数据")

st.title("📈 AI 金融情报局 Pro")
st.markdown("### 实时结构化金融数据流")

news_list = get_news()

if not news_list:
    st.info("暂无数据")
else:
    for news in news_list:
        # 1. 提取数据
        title = news['title']
        summary = news['content_summary']
        url = news['url']
        date_str = news['created_at'].split('T')[0]
        
        # 处理分数 (旧数据可能是 None)
        score = news.get('sentiment_score')
        tags = news.get('tags')
        
        # 2. 决定颜色图标
        # 默认灰色
        emoji = "⚪" 
        score_display = ""
        border_color = None # Streamlit目前还不支持动态边框颜色，但我们可以用emoji区分
        
        if score is not None:
            score_display = f" [情绪分: {score}]"
            if score >= 4:
                emoji = "🟢" # 利好
            elif score <= -4:
                emoji = "🔴" # 利空
        
        # 3. 渲染卡片
        with st.expander(f"{emoji} {date_str} | {title} {score_display}", expanded=True):
            # 显示标签
            if tags:
                # 这种写法会生成漂亮的胶囊标签 [AI] [Nvidia]
                st.markdown(" ".join([f"`#{tag}`" for tag in tags]))
            
            st.markdown(summary)
            
            # 按钮
            st.link_button("🔗 阅读原文", url)
st.title("📈 AI 金融情报局 Pro")

# --- 新增功能 1: 市场情绪看板 ---

news_list = get_news() # 获取最新的30-50条数据

if news_list:
    # 1. 将数据转换为 Pandas DataFrame (表格处理神器)
    df = pd.DataFrame(news_list)
    
    # 2. 处理时间格式
    df['created_at'] = pd.to_datetime(df['created_at'])
    df['date'] = df['created_at'].dt.date # 只取日期
    
    # 3. 处理分数 (有些旧数据是 None，填充为 0)
    df['sentiment_score'] = df['sentiment_score'].fillna(0)
    
    # 4. 界面布局：上图下文
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("最新收录", f"{len(df)} 条")
    with col2:
        # 计算平均情绪
        avg_score = df['sentiment_score'].mean()
        delta_color = "normal"
        if avg_score > 2: delta_color = "inverse" # 绿色
        elif avg_score < -2: delta_color = "off" # 红色
        st.metric("当前市场情绪", f"{avg_score:.1f}", delta=f"{avg_score:.1f} 分", delta_color=delta_color)
    with col3:
        st.write("情绪走势 (近30条)")
        # 画一个简单折线图
        st.line_chart(df[['created_at', 'sentiment_score']].set_index('created_at'), height=100)

    st.divider()