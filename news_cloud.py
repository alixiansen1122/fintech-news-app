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

RSS_CONFIGS = [
    {
        "category": "🤖 AI & Tech",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/"
    },
    {
        "category": "₿ Crypto",
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"
    },
    {
        "category": "💰 Macro & Market", # 宏观与市场
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664" # CNBC Finance
    },
    {
        "category": "💰 Macro & Market", 
        "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories" # MarketWatch
    },
    {
        "category": "📱 Gadgets & Tech", 
        "url": "https://www.theverge.com/rss/index.xml" # The Verge
    }
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
        "summary": "30字以内的中文核心摘要",
        "key_stats": "关键数据列表（字符串，换行分隔）。请使用自然语言描述每条数据背景，并将核心数值（如金额、百分比、时间等）用双大括号包裹 {{...}}。例如：'xLight从美国商务部获得的初步交易金额上限为 {{$1.5亿}}'。不要使用 '数值: 描述' 的格式，必须是完整的句子。",
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

# ================= 2. 升级入库函数 =================
# 增加 category 参数
def save_to_supabase(title, url, ai_data, source, category):
    full_summary = f"{ai_data['summary']}\n\n**关键数据:** {ai_data['key_stats']}"
    
    data = {
        "title": title,
        "url": url,
        "content_summary": full_summary,
        "original_source": source,
        "sentiment_score": ai_data['sentiment_score'],
        "tags": ai_data['tags'],
        "category": category  # <--- 新增这一行
    }
    
    try:
        supabase.table("news").insert(data).execute()
        print(f"✅ [{category}] 入库成功: {title[:15]}...")
    except Exception as e:
        print(f"❌ 入库失败: {e}")

# ================= 主循环 =================

def run_pipeline():
    print("🚀 启动分频道抓取...")
    
    # 遍历我们配置好的字典列表
    for config in RSS_CONFIGS:
        category = config['category']
        feed_url = config['url']
        
        print(f"\n🌊 正在读取频道: {category} ...")
        
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:3]: # 每个源抓3条，保持轻量
                url = entry.link
                
                if check_if_exists(url):
                    print("   ⏭️ 跳过 (已存在)")
                    continue
                
                print("   📥 下载中...")
                title, content = get_article_content(url)
                
                if content:
                    print(f"   🧠 AI 分析中 ({category})...")
                    ai_data = ai_summarize_structured(title, content)
                    
                    if ai_data:
                        # 简单的来源名称提取
                        if "cnbc" in feed_url: source = "CNBC"
                        elif "techcrunch" in feed_url: source = "TechCrunch"
                        elif "coindesk" in feed_url: source = "CoinDesk"
                        elif "dowjones" in feed_url: source = "MarketWatch"
                        else: source = "Web"
                        
                        # 传入 category
                        save_to_supabase(title, url, ai_data, source, category)
                        time.sleep(2)
                        
        except Exception as e:
            print(f"⚠️ RSS 错误: {e}")

if __name__ == "__main__":
    run_pipeline()