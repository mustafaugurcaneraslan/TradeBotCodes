import requests
import pandas as pd
import numpy as np
import ta

def get_binance_futures_klines(symbol="BTCUSDT", interval="1h", limit=1000):
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
    response = requests.get(url)
    data = response.json()
    df = pd.DataFrame(data, columns=[
        "Open time", "Open", "High", "Low", "Close", "Volume",
        "Close time", "Quote asset volume", "Number of trades",
        "Taker buy base asset volume", "Taker buy quote asset volume", "Ignore"
    ])
    df["Close"] = df["Close"].astype(float)
    df["High"] = df["High"].astype(float)
    df["Low"] = df["Low"].astype(float)
    df["Volume"] = df["Volume"].astype(float)
    df["Open time"] = pd.to_datetime(df["Open time"], unit='ms')
    return df

def EFI(close, volume, period=13):
    price_change = close.diff()
    volume_sign = volume.copy()
    volume_sign[price_change > 0] = volume[price_change > 0]
    volume_sign[price_change < 0] = -volume[price_change < 0]
    volume_sign[price_change == 0] = 0
    efi = volume_sign.rolling(window=period).sum() / volume.rolling(window=period).sum()
    return efi

df = get_binance_futures_klines()

df['EFI_13'] = EFI(df['Close'], df['Volume'], 13)

macd = ta.trend.MACD(df['Close'])
df['MACD'] = macd.macd()
df['MACD_signal'] = macd.macd_signal()

df['long_signal'] = (df['EFI_13'] > 0) & (df['MACD'] > df['MACD_signal']) & (df['MACD'].shift(1) <= df['MACD_signal'].shift(1))
df['short_signal'] = (df['EFI_13'] < 0) & (df['MACD'] < df['MACD_signal']) & (df['MACD'].shift(1) >= df['MACD_signal'].shift(1))

position = 0
entry_price = 0
stop_loss = 0
take_profit = 0
trades = []

for idx, row in df.iterrows():
    if position == 0:
        if row['long_signal']:
            position = 1
            entry_price = row['Close']
            stop_loss = entry_price * (1 - 0.02)  # %2 stop loss
            take_profit = entry_price * (1 + 0.02)  # %2 take profit
            trades.append({
                "Type": "LONG_ENTRY",
                "Time": row["Open time"],
                "Price": entry_price
            })
    elif position == 1:
        # Stop loss ya da take profit gerçekleştiyse pozisyonu kapat
        if row['Low'] <= stop_loss:
            exit_price = stop_loss
            result = "lose"
            trades.append({
                "Type": "LONG_EXIT_STOP_LOSS",
                "Time": row["Open time"],
                "Price": exit_price,
                "Result": result
            })
            position = 0
        elif row['High'] >= take_profit:
            exit_price = take_profit
            result = "win"
            trades.append({
                "Type": "LONG_EXIT_TAKE_PROFIT",
                "Time": row["Open time"],
                "Price": exit_price,
                "Result": result
            })
            position = 0
        # Eğer stop loss ya da take profit gerçekleşmediyse, çıkış sinyali varsa kapat
        elif row['short_signal']:
            exit_price = row['Close']
            result = "win" if exit_price > entry_price else "lose"
            trades.append({
                "Type": "LONG_EXIT_SIGNAL",
                "Time": row["Open time"],
                "Price": exit_price,
                "Result": result
            })
            position = 0

trades_df = pd.DataFrame(trades)
trades_df.to_csv("backtest_trades_with_sl_tp.csv", index=False)

print("İşlem kayıtları 'backtest_trades_with_sl_tp.csv' dosyasına kaydedildi.")
