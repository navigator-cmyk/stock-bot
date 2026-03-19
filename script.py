import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pytz
import japanize_matplotlib  # 日本語化ライブラリを追加
import os

# 銘柄設定
tickers = ["IONQ", "RGTI", "QBTS", "QUBT", "^IXIC"]
tasks = [
    {"target": "Graph_1W", "limit": 5, "label_gap": 1},
    {"target": "Graph_3M", "limit": 65, "label_gap": 5},
    {"target": "Graph_1Y", "limit": 255, "label_gap": 20}
]

def run():
    print("データ取得開始...")
    data = yf.download(tickers, period="2y")['Close']
    
    # タイムゾーン処理
    if data.index.tz is None:
        data.index = data.index.tz_localize('UTC').tz_convert(pytz.timezone('Asia/Tokyo')).tz_localize(None)
    else:
        data.index = data.index.tz_convert(pytz.timezone('Asia/Tokyo')).tz_localize(None)

    data = data.ffill()

    print("CSVデータ生成開始 (実際の株価を保存)...")
    for task in tasks:
        df = data.tail(task["limit"]).copy()
        
        # ラベル間引き処理
        labels = df.index.strftime('%Y/%m/%d').tolist()
        formatted_labels = [l if (i == len(labels)-1 or i % task["label_gap"] == 0) else "" for i, l in enumerate(labels)]
        
        # 騰落率ではなく「実際の株価 (df)」をそのままCSVに保存
        csv_df = df.reset_index()
        csv_df.columns = ["Date"] + tickers
        csv_df["Date"] = formatted_labels
        csv_df.to_csv(f"stock_data_{task['target']}.csv", index=False)

    print("最新価格CSV生成開始...")
    latest_2d = data.tail(2)
    latest_prices = latest_2d.T
    latest_prices.columns = ["Prev", "Latest"]
    latest_prices = latest_prices.reset_index()
    latest_prices.columns = ["Ticker", "Prev_Close", "Latest_Close"]
    latest_prices["Date"] = latest_2d.index[-1].strftime('%Y/%m/%d')
    latest_prices[["Date", "Ticker", "Latest_Close", "Prev_Close"]].to_csv("stock_data_latest_prices.csv", index=False)

    print("チャート画像生成開始...")
    # チャート生成 (日本語タイトルに変更)
    generate_compressed_chart(data.tail(5), "1週間の値動き", "weekly_chart.png", tick_format='%m/%d')
    generate_compressed_chart(data.tail(65), "3ヶ月間の値動き", "quarterly_chart.png", tick_format='%m/%d')
    generate_compressed_chart(data.tail(255), "1年間の値動き", "yearly_chart.png", tick_format='%Y/%m')

def generate_compressed_chart(df, title, filename, tick_format):
    # グラフ描画用に「メモリ上だけで」騰落率を計算 (CSVには影響しません)
    base_prices = df.iloc[0].replace(0, 1) # 0割防止
    normalized = (df / base_prices) - 1
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    indices = range(len(df))
    dates = df.index
    colors = ['#1f77b4', '#2ca02c', '#ff7f0e', '#d62728', '#7f7f7f']
    
    for i, t in enumerate(tickers):
        label = t.replace("^IXIC", ".IXIC")
        ax.plot(indices, normalized[t], label=label, color=colors[i], linewidth=2 if t=="^IXIC" else 1.5)
    
    # タイトル (日本語)
    ax.set_title(title, fontsize=18, pad=20)
    
    # 縦軸設定
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    ax.axhline(0, color='black', linewidth=1)
    ax.grid(True, linestyle='--', alpha=0.6)
    
    # X軸設定
    N = len(df)
    if N <= 10: gap = 1
    elif N <= 70: gap = 10
    else: gap = 40
    
    tick_indices = list(range(0, N, gap))
    if (N-1) not in tick_indices: tick_indices.append(N-1)
    tick_labels = [dates[i].strftime(tick_format) for i in tick_indices]
    
    ax.set_xticks(tick_indices)
    ax.set_xticklabels(tick_labels, fontsize=10)
    
    # --- 修正点: 凡例をグラフの「下」に配置 ---
    # bbox_to_anchorのY座標をマイナスにして枠外下部に置く
    display_labels = [t.replace("^IXIC", ".IXIC") for t in tickers]
    ax.legend(display_labels, loc='upper center', bbox_to_anchor=(0.5, -0.12), 
               ncol=len(tickers), frameon=False, fontsize=12)
    
    # グラフ下部に凡例用の余白を作る
    plt.subplots_adjust(bottom=0.2)
    
    plt.savefig(filename, bbox_inches='tight')
    plt.close()

if __name__ == "__main__":
    run()
