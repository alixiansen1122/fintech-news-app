import os
import time
import feedparser
import google.generativeai as genai
from newspaper import Article, Config
from supabase import create_client, Client

# ================= ☁️ 云端版配置 (无代理) ☁️ =================

# 1. 直接从环境变量读取 Keys (GitHub 会自动注入)
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# 2. 新闻源
RSS_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html" # 添加了CNBC
]

# ================= 初始化 =================
if not GOOGLE_API_KEY or not SUPABASE_KEY:
    raise ValueError("❌ 错误：未找到 API Key，请检查 GitHub Secrets 配置！")

genai.configure(api_key=GOOGLE_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
MODEL_NAME = 'gemini-2.0-flash'

# ================= 核心函数 (保持不变) =================

def check_if_exists(url):
    try:
        response = supabase.table("news").select("id").eq("url", url).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"⚠️ DB Check Error: {e}")
        return False

def get_article_content(url):
    config = Config()
    config.browser_user_agent = 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36' # 伪装成手机
    config.request_timeout = 10
    try:
        article = Article(url, config=config)
        article.download()
        article.parse()
        return article.title, article.text
    except Exception:
        return None, None

def ai_summarize(title, content):
    system_instruction = """
    你是一位金融科技情报官。请将新闻总结为Markdown格式：
    ### ⚡ 一句话核心
    ### 📉 关键数据
    ### 🐂 熊/牛 评级
    ### 🏷️ 标签
    """
    model = genai.GenerativeModel(model_name=MODEL_NAME, system_instruction=system_instruction)
    try:
        response = model.generate_content(f"标题：{title}\n\n内容：{content[:8000]}")
        return response.text
    except Exception as e:
        print(f"❌ AI Error: {e}")
        return None

def save_to_supabase(title, url, summary, source):
    data = {"title": title, "url": url, "content_summary": summary, "original_source": source}
    try:
        supabase.table("news").insert(data).execute()
        print(f"✅ Saved: {title[:20]}...")
    except Exception as e:
        print(f"❌ Save Error: {e}")

# ================= 主循环 =================

def run_pipeline():
    print(f"🚀 Starting Cloud Pipeline...")
    for feed_url in RSS_FEEDS:
        print(f"🌊 Reading RSS: {feed_url}")
        try:
            feed = feedparser.parse(feed_url)
            # 每次只取最新的 5 条，防止超时
            for entry in feed.entries[:5]:
                url = entry.link
                if check_if_exists(url):
                    print("   ⏭️ Skipped (Exists)")
                    continue
                
                print("   📥 Downloading...")
                title, content = get_article_content(url)
                if content:
                    print("   🧠 Analyzing...")
                    summary = ai_summarize(title, content)
                    if summary:
                        source = "TechCrunch" if "techcrunch" in feed_url else "Other"
                        save_to_supabase(title, url, summary, source)
                        time.sleep(2) # 礼貌爬虫
        except Exception as e:
            print(f"⚠️ RSS Parse Error: {e}")

if __name__ == "__main__":
    run_pipeline()