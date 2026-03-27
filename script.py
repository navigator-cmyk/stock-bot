import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pytz
import japanize_matplotlib
import os
import feedparser
import requests
import time
from datetime import datetime

# --- 設定エリア ---
USER_AGENT = "YourName your-email@example.com"
TICKERS = ["IONQ", "RGTI", "QBTS", "QUBT"]
NASDAQ_SYMBOL = "^IXIC"  # ナスダックを追加
CIK_MAP = {
    "IONQ": "0001824920",
    "RGTI": "0001838359",
    "QBTS": "0001907982",
    "QUBT": "0001758009"
}

def get_sec_info(ticker):
    """SECから最新書類と現金残高を取得"""
    if ticker == NASDAQ_SYMBOL: return "N/A", "N/A"
    cik = CIK_MAP[ticker]
    headers = {'User-Agent': USER_AGENT}
    
    # 1. 最新の書類
    feed_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&output=atom"
    latest_filing = "N/A"
    try:
        response = requests.get(feed_url, headers=headers, timeout=10)
        feed = feedparser.parse(response.text)
        if feed.entries:
            entry = feed.entries[0]
            f_type = entry.title.split('-')[0].strip() if '-' in entry.title else "Filing"
            f_date = entry.updated[:10].replace('-', '/')
            latest_filing = f"{f_type} ({f_date})"
    except: pass
    
    time.sleep(0.2)

    # 2. 現金残高
    cash = "N/A"
    api_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    try:
        data = requests.get(api_url, headers=headers, timeout=10).json()
        for tag in ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"]:
            try:
                values = data['facts']['us-gaap'][tag]['units']['USD']
                latest_val = values[-1]['val']
                cash = f"${latest_val / 1_000_000:,.1f}M"
                break
            except: continue
    except: pass

    return latest_filing, cash

def generate_charts(data):
    """騰落率チャート (1W, 3M, 1Y) を生成"""
    periods = [
        {"name": "1週間の値動き", "file": "weekly_chart.png", "days": 5, "fmt": "%m/%d"},
        {"name": "3ヶ月間の値動き", "file": "quarterly_chart.png", "days": 65, "fmt": "%m/%d"},
        {"name": "1年間の値動き", "file": "yearly_chart.png", "days": 255, "fmt": "%Y/%m"}
    ]
    
    for p in periods:
        df = data.tail(p["days"])
        if df.empty: continue
        base = df.iloc[0].replace(0, 1)
        normalized = (df / base) - 1
        
        fig, ax = plt.subplots(figsize=(10, 6))
        indices = range(len(df))
        
        # 量子銘柄のプロット
        colors = ['#1f77b4', '#2ca02c', '#ff7f0e', '#d62728']
        for i, t in enumerate(TICKERS):
            ax.plot(indices, normalized[t], label=t, color=colors[i], linewidth=2)
        
        # ナスダックのプロット（グレー表示）
        if NASDAQ_SYMBOL in normalized.columns:
            ax.plot(indices, normalized[NASDAQ_SYMBOL], label="Nasdaq", color='gray', linewidth=1.5, linestyle='--', alpha=0.7)
        
        ax.set_title(p["name"], fontsize=18, pad=20)
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
        ax.axhline(0, color='black', linewidth=1)
        ax.grid(True, linestyle='--', alpha=0.6)
        
        step = max(1, len(df) // 5)
        ax.set_xticks(list(range(0, len(df), step)) + [len(df)-1])
        ax.set_xticklabels([df.index[i].strftime(p["fmt"]) for i in ax.get_xticks()])
        
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), ncol=5, frameon=False, fontsize=12)
        plt.subplots_adjust(bottom=0.2)
        plt.savefig(p["file"], bbox_inches='tight')
        plt.close()

def run():
    print("データ取得開始...")
    download_list = TICKERS + [NASDAQ_SYMBOL, "JPY=X"]
    all_data = yf.download(download_list, period="2y")['Close']
    all_data.index = all_data.index.tz_localize(None)
    
    # --- 修正箇所：未確定データの排除ロジック ---
    # 米国東部時間（ET）を基準に判定を行う
    tz_ny = pytz.timezone('America/New_York')
    now_ny = datetime.now(tz_ny)
    today_ny = pd.Timestamp(now_ny.date())
    
    # 最終行の日付を取得
    last_date = all_data.index[-1]
    
    if last_date > today_ny:
        # 未来の日付データが存在する場合は削除（異常値対応）
        print(f"未来の未確定データ（{last_date.date()}）を除外します。")
        all_data = all_data.iloc[:-1]
    elif last_date == today_ny:
        # 最終行が「現地時間の今日」の場合、市場閉場（16:00 ET）前なら削除
        if now_ny.hour < 16:
            print(f"本日の未確定データ（{last_date.date()}）を除外します。")
            all_data = all_data.iloc[:-1]
        else:
            print(f"本日の確定済みデータ（{last_date.date()}）を保持します。")
    # ------------------------------------------
    
    stock_data = all_data[TICKERS + [NASDAQ_SYMBOL]].ffill()
    usdjpy_data = all_data["JPY=X"].ffill()

    # 1. チャート生成 (修正後の stock_data を使用)
    generate_charts(stock_data)

    # 3. GAS用：最新株価CSVの作成 (latest_prices.csv)
    latest_date_str = stock_data.index[-1].strftime('%Y/%m/%d')
    latest_price_rows = []
    for t in TICKERS + [NASDAQ_SYMBOL]:
        latest_close = stock_data[t].iloc[-1]
        prev_close = stock_data[t].iloc[-2]
        latest_price_rows.append([latest_date_str, t, latest_close, prev_close])
    
    pd.DataFrame(latest_price_rows, columns=["Date", "Ticker", "LatestClose", "PrevClose"]).to_csv("latest_prices.csv", index=False)

    # 4. 評価テーブルと決算カレンダーの作成
    valuation_rows = []
    earnings_rows = []
    for t in TICKERS:
        print(f"{t} の詳細データを取得中...")
        info = yf.Ticker(t)
        price = stock_data[t].iloc[-1]
        mkt_cap = info.info.get('marketCap', 0)
        mkt_cap_str = f"${mkt_cap / 1_000_000_000:.2f}B" if mkt_cap > 0 else "N/A"
        
        filing, cash = get_sec_info(t)
        
        e_date = "N/A"
        try:
            cal = info.calendar
            if not cal.empty and 'Earnings Date' in cal.index:
                e_date = cal.loc['Earnings Date'][0].strftime('%Y/%m/%d')
        except: pass

        valuation_rows.append([t, f"{price:.2f}", mkt_cap_str, cash, filing])
        earnings_rows.append([t, e_date])

    pd.DataFrame(valuation_rows, columns=["銘柄", "株価($)", "時価総額", "現金残高", "直近の重要開示(SEC)"]).to_csv("valuation_table.csv", index=False)
    pd.DataFrame(earnings_rows, columns=["銘柄", "次回決算予定日"]).to_csv("earnings_calendar.csv", index=False)

    print("すべてのファイル生成が完了しました。")

if __name__ == "__main__":
    run()
