import os
import time
import json
import re
import feedparser
import google.generativeai as genai
from newspaper import Article, Config
from supabase import create_client, Client

# ================= 配置区域 =================
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

RSS_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html"
]

if not GOOGLE_API_KEY or not SUPABASE_KEY:
    raise ValueError("❌ API Key 缺失")

genai.configure(api_key=GOOGLE_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
MODEL_NAME = 'gemini-2.0-flash'

# ================= 辅助函数 =================

def clean_json_text(text):
    """清理 AI 可能返回的 Markdown 格式符号，提取纯 JSON"""
    # 移除 ```json 和 ``` 
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    return text.strip()

def check_if_exists(url):
    try:
        response = supabase.table("news").select("id").eq("url", url).execute()
        return len(response.data) > 0
    except Exception:
        return False

def get_article_content(url):
    config = Config()
    config.browser_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    config.request_timeout = 10
    try:
        article = Article(url, config=config)
        article.download()
        article.parse()
        return article.title, article.text
    except Exception:
        return None, None

def ai_summarize_structured(title, content):
    """
    让 AI 返回严格的 JSON 格式
    """
    # 强制 AI 输出 JSON 的 Prompt
    system_instruction = """
    你是一位金融数据分析引擎。不要输出任何 Markdown 格式或废话。
    请阅读新闻，返回且仅返回一个符合 Python 解析标准的 JSON 字符串。
    
    JSON 结构要求：
    {
        "summary": "30字以内的中文一句话核心摘要",
        "key_stats": "关键数据（如金额、百分比），如果没有则填'无'",
        "sentiment_score": 一个整数 (-10 代表极度利空, 0 代表中性, 10 代表极度利好),
        "tags": ["标签1", "标签2", "标签3"]
    }
    """
    
    model = genai.GenerativeModel(model_name=MODEL_NAME, system_instruction=system_instruction)
    
    try:
        # 截取前 6000 字符防止 Token 溢出
        response = model.generate_content(f"新闻标题：{title}\n\n内容：{content[:6000]}")
        raw_text = response.text
        
        # 清理并解析 JSON
        json_str = clean_json_text(raw_text)
        data = json.loads(json_str)
        return data
        
    except Exception as e:
        print(f"❌ JSON 解析失败: {e}")
        # 如果解析失败，返回 None，跳过这条新闻
        return None

def save_to_supabase(title, url, ai_data, source):
    """
    现在 ai_data 是一个字典，我们把它拆解存入不同列
    """
    # 组合一下 summary 内容，保留之前的格式习惯，把关键数据拼在后面
    full_summary = f"{ai_data['summary']}\n\n**关键数据:** {ai_data['key_stats']}"
    
    data = {
        "title": title,
        "url": url,
        "content_summary": full_summary, # 保持兼容
        "original_source": source,
        "sentiment_score": ai_data['sentiment_score'], # 新增：分数
        "tags": ai_data['tags'] # 新增：标签数组
    }
    
    try:
        supabase.table("news").insert(data).execute()
        print(f"✅ 入库成功: {title[:20]}... [分数: {ai_data['sentiment_score']}]")
    except Exception as e:
        print(f"❌ 入库失败: {e}")

# ================= 主循环 =================

def run_pipeline():
    print("🚀 启动结构化数据抓取...")
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]: # 限制每次每个源抓5条
                url = entry.link
                
                if check_if_exists(url):
                    print("   ⏭️ 跳过 (已存在)")
                    continue
                
                print("   📥 下载中...")
                title, content = get_article_content(url)
                
                if content:
                    print("   🧠 AI 分析中 (JSON模式)...")
                    # 调用新的结构化分析函数
                    ai_data = ai_summarize_structured(title, content)
                    
                    if ai_data:
                        source = "TechCrunch" if "techcrunch" in feed_url else "CoinDesk"
                        save_to_supabase(title, url, ai_data, source)
                        time.sleep(2)
                        
        except Exception as e:
            print(f"⚠️ RSS 错误: {e}")

if __name__ == "__main__":
    run_pipeline()