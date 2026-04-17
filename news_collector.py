import feedparser
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
import calendar

# --- 設定 ---
OUTPUT_FILE = "news_list.csv"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# 取得対象の範囲（今日と昨日）
TODAY = datetime.now().date()
YESTERDAY = TODAY - timedelta(days=1)

def is_target_date(published_struct):
    """feedparserの日付構造体が今日か昨日か判定"""
    if not published_struct:
        return False
    dt = datetime(*published_struct[:3]).date()
    return dt == TODAY or dt == YESTERDAY

def is_quantum(text):
    keywords = ["quantum", "量子", "qubit", "ionq", "rigetti", "d-wave"]
    return any(k in text.lower() for k in keywords)

# --- RSS取得 ---
def fetch_rss(name, url):
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
                rows.append([date_str, name, title, link])
    except Exception as e:
        print(f"[ERROR][{name}] {e}")
    return rows

# --- arXiv ---
def fetch_arxiv():
    # arXivは量が多いので、API側で今日・昨日のフィルタは難しいが、取得後にフィルタする
    url = "http://export.arxiv.org/api/query?search_query=cat:quant-ph&max_results=30&sortBy=submittedDate&sortOrder=descending"
    return fetch_rss("arXiv", url)

# --- IonQ (HTMLスクレイピング) ---
def fetch_ionq():
    rows = []
    url = "https://ionq.com/news"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        
        # IonQのニュースリスト（構造に合わせて調整が必要な場合があります）
        # 各記事が <article> や特定のクラスに囲まれていると想定
        articles = soup.find_all("a", href=True)
        
        for a in articles:
            title = a.get_text(strip=True)
            href = a["href"]
            
            if not is_quantum(title) or len(title) < 20:
                continue

            # IonQのようなサイトはaタグの近くに日付テキストがあることが多い
            # 日付が見つからない場合は「最新情報」として今日の日付で処理
            # ※本来は詳細ページへ行くか、前後の要素から日付を抽出します
            
            full_url = href if href.startswith("http") else "https://ionq.com" + href
            
            # 今回は「中継用」なので、URLが新しいものを拾う
            # 日付判別が難しい場合は、実行日の日付を入れる
            rows.append([TODAY.strftime("%Y-%m-%d"), "IonQ", title, full_url])
            
        # IonQなどは件数が多いので上位5件程度に絞る（過去ログ混入防止）
        return rows[:5]
    except Exception as e:
        print(f"[ERROR][IonQ] {e}")
    return rows

# --- メイン処理 ---
def main():
    all_data = []

    # RSSソースの巡回
    RSS_SOURCES = {
        "IBM": "https://research.ibm.com/blog/rss.xml",
        "Google": "https://blog.google/technology/ai/rss/",
        "NVIDIA": "https://blogs.nvidia.com/feed/",
        "QuantumInsider": "https://thequantuminsider.com/feed/",
        "QCR": "https://quantumcomputingreport.com/feed/"
    }

    for name, url in RSS_SOURCES.items():
        print(f"Fetching {name}...")
        all_data.extend(fetch_rss(name, url))
        time.sleep(1)

    print("Fetching arXiv...")
    all_data.extend(fetch_arxiv())
    
    print("Fetching IonQ...")
    all_data.extend(fetch_ionq())

    # CSV作成
    df = pd.DataFrame(all_data, columns=["Date", "Source", "Title", "URL"])
    
    if df.empty:
        # データが空の場合、GAS側がエラーにならないよう空のヘッダーだけ作成するか、
        # 処理を中断するか選べます。ここではヘッダーのみ作成します。
        df = pd.DataFrame(columns=["Date", "Source", "Title", "URL"])

    # 重複削除
    df = df.drop_duplicates(subset=["URL"])
    
    # 上書き保存（encodingはスプレッドシートが読みやすいようutf-8-sig）
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} articles to {OUTPUT_FILE} (Filtered for Today/Yesterday)")

if __name__ == "__main__":
    main()
