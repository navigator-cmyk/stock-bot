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
USER_AGENT = "YourName your-email@example.com" # SECルール：名前とメールアドレスを記載
TICKERS = ["IONQ", "RGTI", "QBTS", "QUBT"]
CIK_MAP = {
    "IONQ": "0001824920",
    "RGTI": "0001838359",
    "QBTS": "0001907982",
    "QUBT": "0001758009"
}

def get_sec_info(ticker):
    """SECから最新書類と現金残高を取得"""
    cik = CIK_MAP[ticker]
    headers = {'User-Agent': USER_AGENT}
    
    # 1. 最新の書類（Atom Feed）
    feed_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&output=atom"
    latest_filing = "N/A"
    try:
        feed = feedparser.parse(requests.get(feed_url, headers=headers).text)
        if feed.entries:
            entry = feed.entries[0]
            # "8-K" などの種別を抽出
            f_type = entry.title.split('-')[0].strip() if '-' in entry.title else "Filing"
            f_date = entry.updated[:10].replace('-', '/')
            latest_filing = f"{f_type} ({f_date})"
    except: pass
    
    time.sleep(0.2) # SECレート制限対策

    # 2. 現金残高（Company Facts API）
    cash = "N/A"
    api_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    try:
        data = requests.get(api_url, headers=headers).json()
        # 主要な現金タグを検索
        for tag in ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"]:
            try:
                values = data['facts']['us-gaap'][tag]['units']['USD']
                latest_val = values[-1]['val']
                cash = f"${latest_val / 1_000_000:,.1f}M"
                break
            except: continue
    except: pass

    return latest_filing, cash

def generate_charts(data, usdjpy_data):
    """チャート画像4枚を生成"""
    # 1. 騰落率チャート (1W, 3M, 1Y)
    periods = [
        {"name": "1週間の値動き", "file": "weekly_chart.png", "days": 5, "fmt": "%m/%d"},
        {"name": "3ヶ月間の値動き", "file": "quarterly_chart.png", "days": 65, "fmt": "%m/%d"},
        {"name": "1年間の値動き", "file": "yearly_chart.png", "days": 255, "fmt": "%Y/%m"}
    ]
    
    for p in periods:
        df = data.tail(p["days"])
        base = df.iloc[0].replace(0, 1)
        normalized = (df / base) - 1
        
        fig, ax = plt.subplots(figsize=(10, 6))
        indices = range(len(df))
        colors = ['#1f77b4', '#2ca02c', '#ff7f0e', '#d62728']
        for i, t in enumerate(TICKERS):
            ax.plot(indices, normalized[t], label=t, color=colors[i], linewidth=2)
        
        ax.set_title(p["name"], fontsize=18, pad=20)
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
        ax.axhline(0, color='black', linewidth=1)
        ax.grid(True, linestyle='--', alpha=0.6)
        
        # X軸
        step = max(1, len(df) // 5)
        ax.set_xticks(list(range(0, len(df), step)) + [len(df)-1])
        ax.set_xticklabels([df.index[i].strftime(p["fmt"]) for i in ax.get_xticks()])
        
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), ncol=4, frameon=False, fontsize=12)
        plt.subplots_adjust(bottom=0.2)
        plt.savefig(p["file"], bbox_inches='tight')
        plt.close()

    # 2. ドル円3ヶ月チャート
    df_fx = usdjpy_data.tail(65)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(range(len(df_fx)), df_fx.values, color='#888888', linewidth=2)
    ax.set_title("ドル円（3ヶ月）", fontsize=18, pad=20)
    ax.grid(True, linestyle='--', alpha=0.6)
    
    step = 10
    ax.set_xticks(list(range(0, len(df_fx), step)) + [len(df_fx)-1])
    ax.set_xticklabels([df_fx.index[i].strftime('%m/%d') for i in ax.get_xticks()])
    
    plt.savefig("usdjpy_3m_chart.png", bbox_inches='tight')
    plt.close()

def run():
    print("データ取得開始...")
    all_data = yf.download(TICKERS + ["JPY=X"], period="2y")['Close']
    all_data.index = all_data.index.tz_localize(None)
    
    stock_data = all_data[TICKERS].ffill()
    usdjpy_data = all_data["JPY=X"].ffill()

    # 1. チャート生成
    generate_charts(stock_data, usdjpy_data)

    # 2. 比較評価テーブルと決算日の作成
    valuation_rows = []
    earnings_rows = []

    for t in TICKERS:
        print(f"{t} の詳細データを取得中...")
        info = yf.Ticker(t)
        
        # 基本情報
        price = stock_data[t].iloc[-1]
        mkt_cap = info.info.get('marketCap', 0)
        mkt_cap_str = f"${mkt_cap / 1_000_000_000:.2f}B" if mkt_cap > 0 else "N/A"
        
        # SEC情報
        filing, cash = get_sec_info(t)
        
        # 決算予定日
        e_date = "N/A"
        try:
            cal = info.calendar
            if not cal.empty and 'Earnings Date' in cal.index:
                e_date = cal.loc['Earnings Date'][0].strftime('%Y/%m/%d')
        except: pass

        valuation_rows.append([t, f"{price:.2f}", mkt_cap_str, cash, filing])
        earnings_rows.append([t, e_date])

    # CSV保存
    pd.DataFrame(valuation_rows, columns=["銘柄", "株価($)", "時価総額", "現金残高", "直近の重要開示(SEC)"]).to_csv("valuation_table.csv", index=False)
    pd.DataFrame(earnings_rows, columns=["銘柄", "次回決算予定日"]).to_csv("earnings_calendar.csv", index=False)

    print("すべてのファイル生成が完了しました。")

if __name__ == "__main__":
    run()
