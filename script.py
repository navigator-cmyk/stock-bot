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
    print("データ取得開始...")
    # 1. データ取得
    data = yf.download(tickers, period="2y")['Close']
    
    # タイムゾーン処理（安全策）
    if data.index.tz is None:
        data.index = data.index.tz_localize('UTC').tz_convert(pytz.timezone('Asia/Tokyo')).tz_localize(None)
    else:
        data.index = data.index.tz_convert(pytz.timezone('Asia/Tokyo')).tz_localize(None)

    data = data.ffill() # 欠損値補完

    print("CSVデータ生成開始...")
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

    print("チャート画像生成開始...")
    # 4. チャート画像生成 (3種類)
    # 休場日を詰めるため、Integer Indexプロット用の関数を使用
    
    # 週次チャート (5営業日)
    generate_compressed_chart(data.tail(5), "Weekly Performance (5 Trading Days)", "weekly_chart.png", tick_format='%m/%d')
    
    # 3ヶ月チャート (65営業日)
    generate_compressed_chart(data.tail(65), "Quarterly Performance (3 Months)", "quarterly_chart.png", tick_format='%Y/%m')
    
    # 1年チャート (255営業日)
    generate_compressed_chart(data.tail(255), "Yearly Performance (1 Year)", "yearly_chart.png", tick_format='%Y/%m')

def generate_compressed_chart(df, title, filename, tick_format):
    """休場日を詰めて、凡例重なりを防ぐプロット関数"""
    # 正規化
    base_prices = df.iloc[0]
    # 初日が0の場合の安全策
    if (base_prices == 0).any():
        base_prices = base_prices.replace(0, 1)
    normalized = (df / base_prices) - 1
    
    # プロット領域作成
    # 凡例用のスペースを上部に確保するためにsubplot調整を行う
    fig, ax = plt.figure(figsize=(10, 6)), plt.gca()
    
    # --- 修正点2: 休場日を詰める (Integer Indexプロット) ---
    # 日付ではなく、0, 1, 2... という数字に対してプロットする
    indices = range(len(df))
    dates = df.index
    
    colors = ['#1f77b4', '#2ca02c', '#ff7f0e', '#d62728', '#7f7f7f'] # IXICはグレー
    for i, t in enumerate(tickers):
        label = t.replace("^IXIC", ".IXIC")
        # 時間軸(df.index)ではなく、連番(indices)でプロット
        ax.plot(indices, normalized[t], label=label, color=colors[i], linewidth=2 if t=="^IXIC" else 1.5)
    
    # --- 修正点1: タイトルと凡例の重なり防止 ---
    # タイトルのパディング（余白）を大きく取る
    ax.set_title(title, fontsize=16, pad=35) 
    
    # 縦軸設定
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    # 0%線を強調
    ax.axhline(0, color='black', linewidth=1)
    # グリッド
    ax.grid(True, linestyle='--', alpha=0.6)
    
    # --- X軸設定 (連番に対応する日付ラベルを貼る) ---
    # データ量に応じてラベルの間隔を調整
    N = len(df)
    if N <= 10: gap = 1
    elif N <= 70: gap = 10
    else: gap = 40
    
    tick_indices = list(range(0, N, gap))
    # 最後の日付は必ず表示
    if (N-1) not in tick_indices: tick_indices.append(N-1)
    
    tick_labels = [dates[i].strftime(tick_format) for i in tick_indices]
    
    ax.set_xticks(tick_indices)
    ax.set_xticklabels(tick_labels, fontsize=10)
    
    # --- 凡例設定 (重なり防止のため位置を微調整) ---
    display_labels = [t.replace("^IXIC", ".IXIC") for t in tickers]
    # bbox_to_anchorのy値を少し上げる(1.1 ➔ 1.13)
    ax.legend(display_labels, loc='upper center', bbox_to_anchor=(0.5, 1.13), 
               ncol=len(tickers), frameon=False, fontsize=10)
    
    # レイアウト調整 (保存時に凡例が切れないようにする)
    plt.tight_layout()
    
    # 保存 (bbox_inches='tight' で外側にはみ出した凡例も含めて保存)
    plt.savefig(filename, bbox_inches='tight')
    plt.close()
    print(f"  チャート画像保存しました: {filename}")

if __name__ == "__main__":
    run()
