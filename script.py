import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pytz
import os

# 銘柄設定
tickers = ["IONQ", "RGTI", "QBTS", "QUBT", "^IXIC"]
tasks = [
    {"target": "Graph_1W", "limit": 5, "label_gap": 1},
    {"target": "Graph_3M", "limit": 65, "label_gap": 5},
    {"target": "Graph_1Y", "limit": 255, "label_gap": 20}
]

def run():
    # 1. データ取得
    data = yf.download(tickers, period="2y")['Close']
    data.index = data.index.tz_convert(pytz.timezone('Asia/Tokyo')).tz_localize(None)
    data = data.ffill()

    # 2. 各期間のCSV生成 (GASロジック再現)
    for task in tasks:
        df = data.tail(task["limit"]).copy()
        base_prices = df.iloc[0]
        normalized_df = (df / base_prices) - 1
        
        labels = normalized_df.index.strftime('%Y/%m/%d').tolist()
        formatted_labels = [l if (i == len(labels)-1 or i % task["label_gap"] == 0) else "" for i, l in enumerate(labels)]
        
        csv_df = normalized_df.reset_index()
        csv_df.columns = ["Date"] + tickers
        csv_df["Date"] = formatted_labels
        csv_df.to_csv(f"stock_data_{task['target']}.csv", index=False)

    # 3. 最新価格CSV (GASポスト生成用)
    latest_2d = data.tail(2)
    latest_prices = latest_2d.T
    latest_prices.columns = ["Prev", "Latest"]
    latest_prices = latest_prices.reset_index()
    latest_prices.columns = ["Ticker", "Prev_Close", "Latest_Close"]
    latest_prices["Date"] = latest_2d.index[-1].strftime('%Y/%m/%d')
    latest_prices[["Date", "Ticker", "Latest_Close", "Prev_Close"]].to_csv("stock_data_latest_prices.csv", index=False)

    # 4. チャート画像生成 (1W用)
    generate_chart(data.tail(7))

def generate_chart(df):
    normalized = (df / df.iloc[0]) - 1
    plt.figure(figsize=(10, 6))
    colors = ['#1f77b4', '#2ca02c', '#ff7f0e', '#d62728', '#7f7f7f']
    for i, t in enumerate(tickers):
        label = t.replace("^IXIC", ".IXIC")
        plt.plot(normalized[t], label=label, color=colors[i], linewidth=2 if t=="^IXIC" else 1.5)
    
    plt.title("Weekly Performance (7 Days)", fontsize=14, pad=20)
    plt.gca().yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    plt.xticks(df.index, df.index.strftime('%m/%d'))
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.axhline(0, color='black', linewidth=1)
    plt.legend([t.replace("^IXIC", ".IXIC") for t in tickers], loc='upper center', bbox_to_anchor=(0.5, 1.1), ncol=5, frameon=False)
    plt.tight_layout()
    plt.savefig("weekly_chart.png")

if __name__ == "__main__":
    run()
