import feedparser
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time

# --- 設定 ---
OUTPUT_FILE = "news_list.csv"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}

# 取得対象の範囲（今日と昨日）
TODAY = datetime.now().date()
YESTERDAY = TODAY - timedelta(days=1)

def is_target_date(published_struct):
    """feedparserの日付構造体が今日か昨日か判定"""
    if not published_struct:
        return False
    # struct_timeをdateオブジェクトに変換
    dt = datetime(*published_struct[:3]).date()
    return dt == TODAY or dt == YESTERDAY

def is_quantum(text):
    """キーワードチェック"""
    keywords = ["quantum", "量子", "qubit", "ionq", "rigetti", "d-wave", "computing"]
    text_lower = text.lower()
    return any(k in text_lower for k in keywords)

# --- RSS取得 ---
def fetch_rss(name, url):
    """RSSからデータを取得し [日付, ソース, タイトル, URL, サマリー] のリストを返す"""
    rows = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        feed = feedparser.parse(res.text)
        
        for e in feed.entries:
            # 日付チェック
            pub_struct = getattr(e, "published_parsed", None)
            if not is_target_date(pub_struct):
                continue
            
            title = getattr(e, "title", "")
            summary = getattr(e, "summary", "")
            link = getattr(e, "link", "")
            date_str = datetime(*pub_struct[:3]).strftime("%Y-%m-%d")

            if is_quantum(title + summary):
                # GAS用にSummaryも保持（最大300文字）
                clean_summary = BeautifulSoup(summary, "html.parser").get_text()[:300]
                rows.append([date_str, name, title, link, clean_summary])
    except Exception as e:
        print(f"[ERROR][{name}] {e}")
    return rows

# --- arXiv ---
def fetch_arxiv():
    url = "http://export.arxiv.org/api/query?search_query=cat:quant-ph&max_results=30&sortBy=submittedDate&sortOrder=descending"
    return fetch_rss("arXiv", url)

# --- IonQ (HTMLスクレイピング) ---
def fetch_ionq():
    rows = []
    url = "https://ionq.com/news"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        articles = soup.find_all("a", href=True)
        
        for a in articles:
            title = a.get_text(strip=True)
            href = a["href"]
            if not is_quantum(title) or len(title) < 20:
                continue

            full_url = href if href.startswith("http") else "https://ionq.com" + href
            # スクレイピングサイトは日付判定が難しいため、実行日の日付を入れる
            # (毎日実行前提ならこれで昨日の重複チェックにかからずGASへ送れる)
            rows.append([TODAY.strftime("%Y-%m-%d"), "IonQ", title, full_url, ""])
            
        return rows[:5] # 最新の数件に絞る
    except Exception as e:
        print(f"[ERROR][IonQ] {e}")
    return rows

# --- メイン処理 ---
def main():
    collected_data = []

    RSS_SOURCES = {
        "IBM": "https://research.ibm.com/blog/rss.xml",
        "Google": "https://blog.google/technology/ai/rss/",
        "NVIDIA": "https://blogs.nvidia.com/feed/",
        "QuantumInsider": "https://thequantuminsider.com/feed/",
        "QCR": "https://quantumcomputingreport.com/feed/",
        "Microsoft": "https://azure.microsoft.com/en-us/blog/feed/",
        "Nature": "https://www.nature.com/nature.rss"
    }

    # 各サイトから収集
    for name, url in RSS_SOURCES.items():
        print(f"Fetching RSS: {name}...")
        collected_data.extend(fetch_rss(name, url))
        time.sleep(1)

    print("Fetching arXiv...")
    collected_data.extend(fetch_arxiv())
    
    print("Fetching IonQ...")
    collected_data.extend(fetch_ionq())

    # --- GASの列順に合わせて整形 ---
    # GAS要求: [1]=Source, [5]=Title, [6]=URL, [7]=Summary
    final_rows = []
    for item in collected_data:
        # item = [Date, Source, Title, URL, Summary]
        final_rows.append([
            item[0], # 0: Date
            item[1], # 1: Source (GAS csvRow[1])
            "",      # 2: Flag
            "",      # 3: Category
            "",      # 4: Target
            item[2], # 5: Title (GAS csvRow[5])
            item[3], # 6: URL (GAS csvRow[6])
            item[4]  # 7: Summary (GAS csvRow[7])
        ])

    # DataFrame作成
    df = pd.DataFrame(final_rows, columns=[
        "Date", "Source", "Flag", "Category", "Target", "Title", "URL", "Summary"
    ])
    
    if df.empty:
        print("No new articles for today/yesterday.")
        # 空でもヘッダーだけは出力してGAS側のエラーを防ぐ
        df = pd.DataFrame(columns=["Date", "Source", "Flag", "Category", "Target", "Title", "URL", "Summary"])
    else:
        # URLで重複排除
        df = df.drop_duplicates(subset=["URL"])

    # 保存（上書き）
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"Successfully saved {len(df)} articles to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
