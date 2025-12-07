import streamlit as st
from supabase import create_client, Client
import pandas as pd 
import google.generativeai as genai
import re
import time
import random

# --- 1. 多语言配置 ---
TRANSLATIONS = {
    "CN": {
        "page_title": "AI 金融情报局",
        "section_finance": "💰 金融市场",
        "section_tech": "🤖 科技前沿",
        "tab_all": "🔥 全部动态",
        "tab_ai": "🤖 AI & Tech",
        "tab_crypto": "₿ Crypto",
        "tab_macro": "💰 Macro & Market",
        "tab_consumer_tech": "📱 Gadgets & Tech",
        "no_news": "📭 该板块暂无最新消息",
        "original_title": "**原标题**",
        "read_more": "🔗 阅读原文",
        "expand_details": "展开详情",
        "latest_count": "最新收录",
        "market_sentiment": "当前市场情绪",
        "sentiment_trend": "情绪走势 (近30条)",
        "chatbot_title": "🤖 AI 分析师 (Beta)",
        "chatbot_placeholder": "问我关于最近新闻的问题... (例如: 最近加密货币市场怎么样?)",
        "settings_title": "⚙️ 设置",
        "language_label": "语言 / Language",
        "view_mode_label": "显示模式 / View Mode",
        "view_mode_compact": "精简 (Compact)",
        "view_mode_expanded": "展开 (Full Details)",
        "theme_label": "主题 / Theme",
        "theme_info": "💡 Streamlit 限制：请点击右上角 '⋮' -> 'Settings' -> 'Theme' 切换深色/浅色模式。",
        "key_stats": "**关键数据:**",
        "loading": "暂无数据，正在抓取中...",
        "db_error": "数据库连接失败: ",
        "ai_error": "AI 思考超时或出错: ",
        "user_role": "用户",
        "assistant_role": "AI 助手",
        "prompt_template": """
        你是一个基于以下新闻数据的{role_type}助手。请用{language}回答。
        
        【新闻数据库】：
        {context_text}
        
        【用户问题】：{prompt}
        
        请根据数据库里的新闻回答。如果新闻里没提到，就说不知道，不要编造。
        """
    },
    "EN": {
        "page_title": "AI Financial Intelligence",
        "section_finance": "💰 Finance Market",
        "section_tech": "🤖 Tech Frontier",
        "tab_all": "🔥 All News",
        "tab_ai": "🤖 AI & Tech",
        "tab_crypto": "₿ Crypto",
        "tab_macro": "💰 Macro & Market",
        "tab_consumer_tech": "📱 Gadgets & Tech",
        "no_news": "📭 No recent news in this section",
        "original_title": "**Original Title**",
        "read_more": "🔗 Read More",
        "expand_details": "Expand Details",
        "latest_count": "Latest News",
        "market_sentiment": "Market Sentiment",
        "sentiment_trend": "Sentiment Trend (Last 30)",
        "chatbot_title": "🤖 AI Analyst (Beta)",
        "chatbot_placeholder": "Ask me about recent news... (e.g., How is the crypto market?)",
        "settings_title": "⚙️ Settings",
        "language_label": "Language",
        "view_mode_label": "View Mode",
        "view_mode_compact": "Compact",
        "view_mode_expanded": "Full Details",
        "theme_label": "Theme",
        "theme_info": "💡 Note: Switch Dark/Light mode in top-right menu '⋮' -> 'Settings' -> 'Theme'.",
        "key_stats": "**Key Stats:**",
        "loading": "No data, fetching...",
        "db_error": "Database connection failed: ",
        "ai_error": "AI Error: ",
        "user_role": "User",
        "assistant_role": "AI Assistant",
        "prompt_template": """
        You are a financial assistant based on the following news data. Please answer in {language}.
        
        【News Database】：
        {context_text}
        
        【User Question】：{prompt}
        
        Answer based on the database. If not mentioned, say you don't know.
        """
    }
}

# 页面配置
st.set_page_config(page_title="AI Financial Intelligence", page_icon="📈", layout="wide")

# --- Sidebar Settings ---
with st.sidebar:
    st.title("⚙️ Settings")
    
    # Section Selector (Finance vs Tech)
    # We use radio but style it or just standard radio
    # To access translations, we need to know the current language first.
    # But language is selected below. Let's move Language Selector up or default to CN.
    pass 

# Language Selector Logic needs to be early
# We'll use session state to persist language choice if needed, but for now standard radio is fine.
# But we need 't' to define labels.

# Default to CN labels for the first render before 't' is defined?
# Or just put Language Selector first.

with st.sidebar:
    # Language Selector First
    lang_choice = st.radio("Language / 语言", ["中文", "English"])
    lang_code = "CN" if lang_choice == "中文" else "EN"
    t = TRANSLATIONS[lang_code] # Current translation dict
    
    st.divider()

    # Section Selector
    section_choice = st.radio(
        "板块选择 / Section",
        [t["section_finance"], t["section_tech"]]
    )
    is_finance = (section_choice == t["section_finance"])
    
    st.divider()
    
    # View Mode Selector
    view_mode = st.radio(
        t["view_mode_label"], 
        [t["view_mode_compact"], t["view_mode_expanded"]]
    )
    is_expanded = (view_mode == t["view_mode_expanded"])
    
    st.divider()
    
    # Theme Info (Mock Settings)
    st.write(f"**{t['theme_label']}**")
    st.info(t["theme_info"])

# 从 Secrets 读取 Google Key (记得去 Streamlit 后台添加 GOOGLE_API_KEY)
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except:
    pass # 如果没配 Key，对话功能就用不了，但不影响主程序

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
        st.error(f"{t['db_error']}{e}")
        return []
# 获取数据
news_list = get_news()
if not news_list:
    st.info(t["loading"])
    st.stop()
# --- UI 逻辑 ---

st.title(f"📈 {t['page_title']}")

# 1. 定义标签页
# 根据 Section 动态定义 Tabs
if is_finance:
    tabs = st.tabs([t["tab_all"], t["tab_crypto"], t["tab_macro"]])
else:
    # Tech Mode
    tabs = st.tabs([t["tab_all"], t["tab_ai"], t["tab_consumer_tech"]])

# ... (translate_text function remains here) ...

def render_news_list(news):
    for n in news:
        title = n.get('title')
        url = n.get('url')
        full_summary = n.get('content_summary')
        created_at = n.get('created_at')
        date_str = created_at.split('T')[0] if created_at else ""
        score = n.get('sentiment_score')
        tags = n.get('tags')
        
        # 颜色逻辑
        emoji = "⚪"
        if score is not None:
            if score >= 4: emoji = "🟢"
            elif score <= -4: emoji = "🔴"

        # 1. 提取摘要和详情
        short_summary = title # 默认回退
        details_text = full_summary
        
        if full_summary:
            if "**关键数据:**" in full_summary:
                parts = full_summary.split("**关键数据:**", 1)
                short_summary = parts[0].strip()
                details_text = f"{t['key_stats']} {parts[1].strip()}"
            elif len(full_summary) > 0:
                short_summary = full_summary
                details_text = "" # 如果没有关键数据，详情区暂时为空，或者可以放其他信息

        # 2. 翻译摘要 (根据当前语言设置)
        display_summary = translate_text(short_summary, lang_code)
        
        # 3. 处理标签
        tags_str = ""
        if tags:
            tags_str = " ".join([f"#{tag}" for tag in tags])

        # 4. 渲染卡片
        with st.container(border=True):
            # 第一行：表情 + 日期
            st.caption(f"{emoji} {date_str}")
            
            # 主文本：显示翻译后的核心摘要 (替代原来的 Title 位置)
            st.markdown(f"**{display_summary}**")
            
            # 标签
            if tags_str:
                st.markdown(f"`{tags_str}`")
            
            # 详情折叠区
            with st.expander(t["expand_details"], expanded=is_expanded):
                # 里面显示原标题 (带链接)
                st.markdown(f"{t['original_title']}: [{title}]({url})")
                
                # 渲染 Key Stats (支持高亮)
                if details_text:
                    # 替换 {{...}} 为 HTML 高亮样式 (橙黄色背景)
                    highlighted_details = re.sub(
                        r"\{\{(.*?)\}\}", 
                        r"<span style='background-color: #FFC107; color: black; padding: 2px 6px; border-radius: 4px; font-weight: bold;'>\1</span>", 
                        details_text
                    )
                    st.markdown(highlighted_details, unsafe_allow_html=True)
                
                st.link_button(t["read_more"], url)

# 2. 在不同的 Tab 里筛选并显示数据
# 逻辑拆分
if is_finance:
    with tabs[0]: # All Finance
        # Filter for all finance related categories
        finance_cats = ["₿ Crypto", "💰 Macro & Market"]
        finance_news = [n for n in news_list if n.get('category') in finance_cats]
        render_news_list(finance_news)
        
    with tabs[1]: # Crypto
        crypto_news = [n for n in news_list if n.get('category') == "₿ Crypto"]
        render_news_list(crypto_news)
        
    with tabs[2]: # Macro
        macro_news = [n for n in news_list if n.get('category') == "💰 Macro & Market"]
        render_news_list(macro_news)

else: # Tech Mode
    with tabs[0]: # All Tech
        tech_cats = ["🤖 AI & Tech", "📱 Gadgets & Tech"]
        tech_news = [n for n in news_list if n.get('category') in tech_cats]
        render_news_list(tech_news)
        
    with tabs[1]: # AI
        ai_news = [n for n in news_list if n.get('category') == "🤖 AI & Tech"]
        render_news_list(ai_news)
        
    with tabs[2]: # Consumer Tech
        consumer_news = [n for n in news_list if n.get('category') == "📱 Gadgets & Tech"]
        render_news_list(consumer_news)


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
        st.metric(t["latest_count"], f"{len(df)}")
    with col2:
        # 计算平均情绪
        avg_score = df['sentiment_score'].mean()
        delta_color = "normal"
        if avg_score > 2: delta_color = "inverse" # 绿色
        elif avg_score < -2: delta_color = "off" # 红色
        st.metric(t["market_sentiment"], f"{avg_score:.1f}", delta=f"{avg_score:.1f}", delta_color=delta_color)
    with col3:
        st.write(t["sentiment_trend"])
        # 画一个简单折线图
        st.line_chart(df[['created_at', 'sentiment_score']].set_index('created_at'), height=100)

    st.divider()
    # ... (新闻列表渲染完毕后) ...

st.divider()
st.header(t["chatbot_title"])

# 初始化聊天记录
if "messages" not in st.session_state:
    st.session_state.messages = []

# 显示历史聊天记录
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 接收用户输入
if prompt := st.chat_input(t["chatbot_placeholder"]):
    # 1. 显示用户问题
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 2. 准备上下文 (把最近的 10 条新闻标题和摘要拼起来)
    # 这里的 news_list 是我们之前从数据库查出来的
    context_text = ""
    for n in news_list[:10]: # 只给AI看最近10条，省流量
        context_text += f"- {n['created_at']}: {n['title']} (Summary: {n['content_summary']})\n"

    # 3. 调用 Gemini 回答
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # 核心 Prompt (Inject Language)
        language_name = "Chinese" if lang_code == "CN" else "English"
        role_type = "金融" if is_finance else "科技" # Default to Finance/Tech
        if lang_code == "EN":
             role_type = "Financial" if is_finance else "Technology"
        
        full_prompt = t["prompt_template"].format(
            role_type=role_type,
            language=language_name,
            context_text=context_text,
            prompt=prompt
        )
        
        with st.chat_message("assistant"):
            stream = model.generate_content(full_prompt, stream=True)
            response = st.write_stream(stream)
            
        st.session_state.messages.append({"role": "assistant", "content": response})
        
    except Exception as e:
        st.error(f"{t['ai_error']}{e}")