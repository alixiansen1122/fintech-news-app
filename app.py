import streamlit as st
from supabase import create_client, Client
import pandas as pd 
import google.generativeai as genai
import re

# --- 1. 多语言配置 ---
TRANSLATIONS = {
    "CN": {
        "page_title": "AI 金融情报局",
        "tab_all": "🔥 全部动态",
        "tab_ai": "🤖 AI & Tech",
        "tab_crypto": "₿ Crypto",
        "tab_macro": "💰 Macro & Market",
        "no_news": "📭 该板块暂无最新消息",
        "original_title": "**原标题**",
        "read_more": "🔗 阅读原文",
        "expand_details": "🔽 展开详情",
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
        你是一个基于以下新闻数据的金融助手。请用{language}回答。
        
        【新闻数据库】：
        {context_text}
        
        【用户问题】：{prompt}
        
        请根据数据库里的新闻回答。如果新闻里没提到，就说不知道，不要编造。
        """
    },
    "EN": {
        "page_title": "AI Financial Intelligence",
        "tab_all": "🔥 All News",
        "tab_ai": "🤖 AI & Tech",
        "tab_crypto": "₿ Crypto",
        "tab_macro": "💰 Macro & Market",
        "no_news": "📭 No recent news in this section",
        "original_title": "**Original Title**",
        "read_more": "🔗 Read More",
        "expand_details": "🔽 Expand Details",
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
    
    # Language Selector
    lang_choice = st.radio("Language / 语言", ["中文", "English"])
    lang_code = "CN" if lang_choice == "中文" else "EN"
    t = TRANSLATIONS[lang_code] # Current translation dict
    
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
# 第一个是“全部”，后面对应我们在 Python 脚本里写的 category
tabs = st.tabs([t["tab_all"], t["tab_ai"], t["tab_crypto"], t["tab_macro"]])

@st.cache_data(show_spinner=False)
def translate_text(text, target_lang_code):
    """
    使用 Gemini 翻译文本，并缓存结果以提高性能。
    自动检测源语言：
    - 如果目标是 CN，但文本不包含中文 -> 翻译成中文
    - 如果目标是 EN，但文本包含中文 -> 翻译成英文
    """
    if not text:
        return ""
        
    # 简单的语言检测：检查是否包含中文字符
    has_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
    
    prompt = None
    
    if target_lang_code == "CN":
        # 目标是中文
        if has_chinese:
            return text # 已经是中文，直接返回
        # 否则翻译成中文
        prompt = f"Translate the following text to Simplified Chinese (Keep it concise). Output only the translated text:\n\n{text}"
    
    else: # EN
        # 目标是英文
        if not has_chinese:
            return text # 已经是英文（或非中文），直接返回
        # 否则翻译成英文
        prompt = f"Translate the following text to English (Keep it concise). Output only the translated text:\n\n{text}"
    
    if prompt:
        try:
            model = genai.GenerativeModel('gemini-2.0-flash')
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception:
            return text
    
    return text

# 定义一个渲染函数，避免代码重复
def render_news_list(news_items):
    if not news_items:
        st.caption(t["no_news"])
        return

    # 使用 2 列布局 (Grid Layout)
    cols = st.columns(2)

    for index, news in enumerate(news_items):
        with cols[index % 2]: # 奇偶交替
            title = news['title']
            full_summary = news['content_summary']
            url = news['url']
            date_str = news['created_at'].split('T')[0]
            score = news.get('sentiment_score')
            tags = news.get('tags')
            
            # 颜色逻辑
            emoji = "⚪"
            if score is not None:
                if score >= 4: emoji = "🟢"
                elif score <= -4: emoji = "🔴"
            
            # 尝试提取一句话摘要（AI生成摘要）
            short_summary = title # 默认使用标题
            details = full_summary
            
            if "\n\n**关键数据:**" in full_summary:
                parts = full_summary.split("\n\n**关键数据:**", 1)
                short_summary = parts[0].strip()
                details = f"{t['key_stats']} {parts[1].strip()}"
            
            # 翻译摘要 (核心修改：总是尝试根据当前语言进行适配)
            # translate_text 函数内部会自动判断是否需要翻译
            display_summary = translate_text(short_summary, lang_code)

            # 标签处理
            tags_str = ""
            if tags:
                tags_str = " ".join([f"#{tag}" for tag in tags])
            
            # 卡片式布局 (Rectangle)
            with st.container(border=True):
                # 标题行: 表情 日期
                st.caption(f"{emoji} {date_str}")
                
                # 核心摘要 (Bold)
                st.markdown(f"**{display_summary}**")
                
                # 标签
                if tags_str:
                    st.markdown(f"`{tags_str}`")
                
                # 详情折叠区
                # 这里的 expanded 由 sidebar 控制
                with st.expander(t["expand_details"], expanded=is_expanded):
                    st.markdown(f"{t['original_title']}: [{title}]({url})")
                    st.markdown(details)
                    st.link_button(t["read_more"], url)

# 2. 在不同的 Tab 里筛选并显示数据
# Pandas 也可以做 filtering，但这里用列表推导式更直观

with tabs[0]: # 全部
    render_news_list(news_list)

with tabs[1]: # AI
    # 筛选 category 包含 "AI" 的新闻
    ai_news = [n for n in news_list if n.get('category') == "🤖 AI & Tech"]
    render_news_list(ai_news)

with tabs[2]: # Crypto
    crypto_news = [n for n in news_list if n.get('category') == "₿ Crypto"]
    render_news_list(crypto_news)

with tabs[3]: # Macro
    macro_news = [n for n in news_list if n.get('category') == "💰 Macro & Market"]
    render_news_list(macro_news)

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
        full_prompt = t["prompt_template"].format(
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