import feedparser
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time

HEADERS = {"User-Agent": "Mozilla/5.0"}

# --- RSSソース ---
RSS_SOURCES = {
    "IBM": "https://research.ibm.com/blog/rss.xml",
    "Google": "https://blog.google/technology/ai/rss/",
    "Microsoft": "https://azure.microsoft.com/en-us/blog/feed/",
    "NVIDIA": "https://blogs.nvidia.com/feed/",
    "Reuters": "https://www.reutersagency.com/feed/?best-topics=technology",
    "SeekingAlpha": "https://seekingalpha.com/market_currents.xml",
    "Nature": "https://www.nature.com/nature.rss",
    "Science": "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=science",
    "QCR": "https://quantumcomputingreport.com/feed/",
    "QuantumInsider": "https://thequantuminsider.com/feed/",
    "IQT": "https://www.insidequantumtechnology.com/feed/",
    "Bloomberg": "https://feeds.bloomberg.com/technology/news.rss"
}

ARXIV_API = "http://export.arxiv.org/api/query?search_query=cat:quant-ph&max_results=30&sortBy=submittedDate&sortOrder=descending"

IONQ_URL = "https://ionq.com/news"

def is_quantum(text):
    return "quantum" in text.lower()

# --- RSS ---
def fetch_rss(name, url):
    rows = []
    try:
        feed = feedparser.parse(url)

        print(f"[{name}] entries={len(feed.entries)} bozo={feed.bozo}")

        for e in feed.entries:
            title = getattr(e, "title", "")
            summary = getattr(e, "summary", "")
            link = getattr(e, "link", "")
            date = getattr(e, "published", datetime.now().strftime("%Y/%m/%d"))

            if not is_quantum(title + summary):
                continue

            rows.append([
                date, "", "", name, "", title, link, summary[:300], ""
            ])

    except Exception as e:
        print(f"[ERROR][{name}] {e}")

    return rows

# --- arXiv ---
def fetch_arxiv():
    rows = []
    try:
        res = requests.get(ARXIV_API, headers=HEADERS, timeout=15)
        feed = feedparser.parse(res.text)

        print(f"[arXiv] entries={len(feed.entries)}")

        for e in feed.entries:
            rows.append([
                e.published, "", "Paper", "arXiv", "",
                e.title, e.link, e.summary[:300], ""
            ])

    except Exception as e:
        print(f"[ERROR][arXiv] {e}")

    return rows

# --- IonQ（HTMLスクレイピング） ---
def fetch_ionq():
    rows = []
    try:
        res = requests.get(IONQ_URL, headers=HEADERS, timeout=15)
        print(f"[IonQ] status={res.status_code}")

        soup = BeautifulSoup(res.text, "html.parser")

        articles = soup.find_all("a")

        for a in articles:
            title = a.get_text(strip=True)
            link = a.get("href")

            if not title or not link:
                continue

            if "news" not in link:
                continue

            if not is_quantum(title):
                continue

            if not link.startswith("http"):
                link = "https://ionq.com" + link

            rows.append([
                datetime.now().strftime("%Y/%m/%d"),
                "", "", "IonQ", "",
                title, link, "", ""
            ])

    except Exception as e:
        print(f"[ERROR][IonQ] {e}")

    return rows

# --- メイン ---
def fetch_all():
    all_rows = []

    for name, url in RSS_SOURCES.items():
        all_rows.extend(fetch_rss(name, url))
        time.sleep(1)

    all_rows.extend(fetch_arxiv())
    all_rows.extend(fetch_ionq())

    if not all_rows:
        print("No data collected")
        return

    df = pd.DataFrame(all_rows, columns=[
        "Date","Flag","Category","Source","Target",
        "Title","URL","Summary","Summary_X"
    ])

    # 重複除去
    df["URL_norm"] = df["URL"].str.lower().str.rstrip("/")
    df = df.drop_duplicates(subset=["URL_norm"]).drop(columns=["URL_norm"])

    df.to_csv("news_list.csv", index=False, encoding="utf-8-sig")
    print(f"Saved: {len(df)} rows")

if __name__ == "__main__":
    fetch_all()
