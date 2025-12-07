import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timedelta
import os

# 1. 页面配置
st.set_page_config(page_title="AI 金融情报局", page_icon="📈", layout="wide")

# 2. 从 Streamlit Secrets 读取 Key (安全！)
# 待会儿我会教你在网页上填这些 Key，不用写在代码里
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

# 3. 连接数据库
@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_connection()

# 4. 获取数据函数
def get_news():
    try:
        response = supabase.table("news").select("*").order("created_at", desc=True).limit(20).execute()
        return response.data
    except Exception as e:
        st.error(f"无法连接数据库: {e}")
        return []

# ================= 网页布局 (UI) =================

# 1. 侧边栏 (Sidebar)
with st.sidebar:
    st.header("🔍 筛选与控制")
    st.write("这就是你的个人彭博终端雏形。")
    
    # 刷新按钮
    if st.button("🔄 刷新数据"):
        st.rerun() # 重新运行整个脚本，相当于F5
    
    st.divider()
    st.info("数据来源：Supabase Cloud")
    st.caption("Powered by Gemini 2.0")

# 2. 主页面 (Main)
st.title("📈 AI 金融情报局 (Alpha)")
st.markdown("### 每日全球市场核心简报")

# 获取数据
news_list = get_news()

if not news_list:
    st.warning("数据库里还没有新闻，请先运行 `news_auto.py` 抓取一些数据！")
else:
    # 3. 循环渲染每一条新闻
    for news in news_list:
        # 使用 Expander (折叠卡片) 让界面更整洁
        # 卡片标题显示：[来源] 新闻标题
        source_label = news.get('original_source', 'Unknown')
        
        # 处理时间 (把 UTC 时间转得好看点)
        raw_time = news['created_at']
        try:
            # 简单截取日期部分，或者你可以用 datetime 库转换时区
            date_str = raw_time.split('T')[0]
        except:
            date_str = "刚刚"

        with st.expander(f"🗓️ {date_str} | {news['title']}", expanded=True):
            
            # 分两列：左边主要内容，右边原文链接
            col1, col2 = st.columns([3, 1])
            
            with col1:
                # 渲染 AI 生成的 Markdown 简报
                st.markdown(news['content_summary'])
                
                # 情绪标签 (这里简单模拟，如果你的AI输出了标签)
                # st.caption("#AI #Nvidia #Bullish")
                
            with col2:
                st.write("---")
                st.write("**来源:**", source_label)
                # 显示一个漂亮的跳转按钮
                st.link_button("🔗 阅读原文", news['url'])