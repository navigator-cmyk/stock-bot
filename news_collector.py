import feedparser
import pandas as pd
import requests
from datetime import datetime
import re

# --- 設定：RSSソース ---
# GASのソースに Google News と GlobeNewswire を加えて補強しています
RSS_SOURCES = {
    "QCR": "https://quantumcomputingreport.com/feed",
    "PRN": "https://www.prnewswire.com/rss/news-releases-list.rss",
    "GNEWS": "https://news.google.com/rss/search?q=Quantum+Computing+when:24h&hl=en-US&gl=US&ceid=US:en",
    "GLOBE": "https://www.globenewswire.com/rss-feed/subject/Quantum%20Computing"
}

# --- フィルタ設定（GASの isTargetNews を踏襲） ---
TARGET_KEYWORDS = ["ibm", "google", "microsoft", "nvidia", "ionq", "rigetti", "d-wave", "xanadu", "quantinuum"]
ACTION_KEYWORDS = ["announce", "launch", "funding", "partnership", "breakthrough", "results", "collaborate"]
EXCLUDE_KEYWORDS = ["crypto", "blockchain", "bitcoin"]

def strip_cdata(text):
    if not text: return ""
    return re.sub(r'<!\[CDATA\[|\]\]>', '', text).strip()

def is_target_news(title, summary, source_id):
    # QCRは専門サイトなので無条件でパス、それ以外はフィルタをかける
    if source_id == "QCR":
        return True
    
    combined_text = (title + " " + summary).lower()
    
    # 基本条件：quantumが含まれていること
    if "quantum" not in combined_text:
        return False
    
    # 除外条件
    if any(k in combined_text for k in EXCLUDE_KEYWORDS):
        return False
    
    # ターゲット銘柄 または 重要アクションが含まれていること
    has_target = any(k in combined_text for k in TARGET_KEYWORDS)
    has_action = any(k in combined_text for k in ACTION_KEYWORDS)
    
    return has_target or has_action

def fetch_news():
    all_rows = []
    
    for source_id, url in RSS_SOURCES.items():
        print(f"Fetching from {source_id}...")
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = getattr(entry, 'title', '')
                link = getattr(entry, 'link', '')
                summary = strip_cdata(getattr(entry, 'summary', getattr(entry, 'description', '')))
                pub_date = getattr(entry, 'published', datetime.now().strftime('%Y/%m/%d'))
                
                # フィルタリング
                if is_target_news(title, summary, source_id):
                    # GASの BlogSource シート（9列構成）に完全対応
                    row = [
                        pub_date,    # A: Date
                        "",          # B: Flag
                        "",          # C: Category (Gemini用)
                        source_id,   # D: Source
                        "",          # E: Target (Gemini用)
                        title,       # F: Title
                        link,        # G: URL
                        summary[:300], # H: Summary (長すぎるとGASでエラーになるため制限)
                        ""           # I: Summary_X (Gemini用)
                    ]
                    all_rows.append(row)
        except Exception as e:
            print(f"Error fetching {source_id}: {e}")

    # DataFrame作成
    df = pd.DataFrame(all_rows, columns=[
        "Date", "Flag", "Category", "Source", "Target", "Title", "URL", "Summary", "Summary_X"
    ])

    # URL重複排除
    df['URL_norm'] = df['URL'].str.replace(r'/$', '', regex=True).str.lower()
    df = df.drop_duplicates(subset=['URL_norm']).drop(columns=['URL_norm'])

    # CSV出力
    df.to_csv("news_list.csv", index=False, encoding='utf-8-sig')
    print(f"Saved {len(df)} news items to news_list.csv")

if __name__ == "__main__":
    fetch_news()
