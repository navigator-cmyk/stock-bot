import feedparser
import pandas as pd
import requests
from datetime import datetime
import re
import time

# --- 設定：ソースはGNEWSのみ ---
# クエリ: "Quantum Computing" に関する過去24時間のニュース
GNEWS_RSS_URL = "https://news.google.com/rss/search?q=Quantum+Computing+when:24h&hl=en-US&gl=US&ceid=US:en"

# --- フィルタ設定：GNEWS内のノイズ（無関係なテック記事）を排除 ---
TARGET_KEYWORDS = ["ionq", "rigetti", "d-wave", "qbts", "qubt", "xanadu", "quantinuum", "google", "ibm", "microsoft", "nvidia", "psiquantum"]
ACTION_KEYWORDS = ["announce", "launch", "funding", "partnership", "results", "deal", "collaborate", "unveil", "report"]
EXCLUDE_KEYWORDS = ["crypto", "blockchain", "bitcoin"]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def strip_cdata(text):
    if not text: return ""
    return re.sub(r'<!\[CDATA\[|\]\]>', '', text).strip()

def is_target_news(title, summary):
    combined_text = (title + " " + summary).lower()
    
    # 1. 除外ワードが含まれる場合は即却下
    if any(k in combined_text for k in EXCLUDE_KEYWORDS):
        return False
    
    # 2. 基本ワード "quantum" が含まれていること
    if "quantum" not in combined_text:
        return False
        
    # 3. 特定銘柄名、または重要アクションが含まれていること（精度向上）
    has_target = any(k in combined_text for k in TARGET_KEYWORDS)
    has_action = any(k in combined_text for k in ACTION_KEYWORDS)
    
    return has_target or has_action

def fetch_news():
    print(f"Fetching news from GNEWS...")
    all_rows = []
    
    try:
        response = requests.get(GNEWS_RSS_URL, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            print(f"Failed to fetch GNEWS: Status {response.status_code}")
            return
            
        feed = feedparser.parse(response.text)
        
        for entry in feed.entries:
            title = getattr(entry, 'title', '')
            link = getattr(entry, 'link', '')
            # description または summary を取得
            summary = strip_cdata(getattr(entry, 'summary', getattr(entry, 'description', '')))
            # 日付フォーマットの正規化
            pub_date = getattr(entry, 'published', datetime.now().strftime('%Y/%m/%d'))
            
            if is_target_news(title, summary):
                # GASの BlogSource シート（9列構成）に完全準拠
                row = [
                    pub_date,    # A: Date
                    "",          # B: Flag
                    "",          # C: Category
                    "GNEWS",     # D: Source
                    "",          # E: Target
                    title,       # F: Title
                    link,        # G: URL
                    summary[:300], # H: Summary (文字数制限)
                    ""           # I: Summary_X
                ]
                all_rows.append(row)
                
    except Exception as e:
        print(f"Error: {e}")

    if not all_rows:
        print("No matching news found today.")
        # 空のファイルを作らず終了
        return

    # DataFrame作成
    df = pd.DataFrame(all_rows, columns=[
        "Date", "Flag", "Category", "Source", "Target", "Title", "URL", "Summary", "Summary_X"
    ])

    # 重複排除（URL基準）
    df['URL_norm'] = df['URL'].str.replace(r'/$', '', regex=True).str.lower()
    df = df.drop_duplicates(subset=['URL_norm']).drop(columns=['URL_norm'])

    # CSV出力 (UTF-8 with BOM)
    df.to_csv("news_list.csv", index=False, encoding='utf-8-sig')
    print(f"Success: Saved {len(df)} items to news_list.csv")

if __name__ == "__main__":
    fetch_news()
