import feedparser
import pandas as pd
import requests
from datetime import datetime
import re
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# --- ソース定義 ---
RSS_SOURCES = {
    "IBM": "https://research.ibm.com/blog/rss.xml",
    "Google": "https://blog.google/technology/ai/rss/",
    "Microsoft": "https://azure.microsoft.com/en-us/blog/feed/",
    "NVIDIA": "https://blogs.nvidia.com/feed/",
    "Reuters": "https://www.reutersagency.com/feed/?best-topics=technology",
    "SeekingAlpha": "https://seekingalpha.com/market_currents.xml"
}

ARXIV_API = "http://export.arxiv.org/api/query?search_query=cat:quant-ph&max_results=20&sortBy=submittedDate&sortOrder=descending"

# --- フィルタ強化 ---
INCLUDE_KEYWORDS = [
    "quantum computing", "qubit", "quantum processor",
    "superconducting qubit", "ion trap", "quantum annealing"
]

COMPANY_KEYWORDS = [
    "ionq", "rigetti", "d-wave", "qbts", "quantinuum",
    "xanadu", "psiquantum"
]

EXCLUDE_KEYWORDS = ["crypto", "bitcoin", "blockchain"]

def is_target_news(title, summary):
    text = (title + " " + summary).lower()

    if any(k in text for k in EXCLUDE_KEYWORDS):
        return False

    # 強条件：quantum computing系
    if any(k in text for k in INCLUDE_KEYWORDS):
        return True

    # 弱条件：企業＋quantum
    if "quantum" in text and any(k in text for k in COMPANY_KEYWORDS):
        return True

    return False

# --- RSS取得 ---
def fetch_rss(source_name, url):
    rows = []
    try:
        feed = feedparser.parse(url)

        for entry in feed.entries:
            title = getattr(entry, "title", "")
            link = getattr(entry, "link", "")
            summary = getattr(entry, "summary", "")
            pub_date = getattr(entry, "published", datetime.now().strftime("%Y/%m/%d"))

            if not is_target_news(title, summary):
                continue

            rows.append([
                pub_date,
                "",
                "",
                source_name,
                "",
                title,
                link,
                summary[:300],
                ""
            ])

    except Exception as e:
        print(f"{source_name} error: {e}")

    return rows

# --- arXiv ---
def fetch_arxiv():
    rows = []
    try:
        res = requests.get(ARXIV_API, headers=HEADERS, timeout=15)
        feed = feedparser.parse(res.text)

        for entry in feed.entries:
            title = entry.title
            summary = entry.summary
            link = entry.link
            pub_date = entry.published

            if not is_target_news(title, summary):
                continue

            rows.append([
                pub_date,
                "",
                "Paper",   # Categoryのみ使用（構造は維持）
                "arXiv",
                "",
                title,
                link,
                summary[:300],
                ""
            ])

    except Exception as e:
        print(f"arXiv error: {e}")

    return rows

# --- メイン ---
def fetch_news():
    all_rows = []

    # RSS
    for name, url in RSS_SOURCES.items():
        all_rows.extend(fetch_rss(name, url))
        time.sleep(1)

    # arXiv
    all_rows.extend(fetch_arxiv())

    if not all_rows:
        print("No matching news found.")
        return

    df = pd.DataFrame(all_rows, columns=[
        "Date", "Flag", "Category", "Source", "Target",
        "Title", "URL", "Summary", "Summary_X"
    ])

    # --- URL正規化重複除去 ---
    df['URL_norm'] = df['URL'].str.replace(r'/$', '', regex=True).str.lower()
    df = df.drop_duplicates(subset=['URL_norm']).drop(columns=['URL_norm'])

    df.to_csv("quantum_news.csv", index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} items")

if __name__ == "__main__":
    fetch_news()
