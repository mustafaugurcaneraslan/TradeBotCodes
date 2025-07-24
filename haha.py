import pandas as pd
import numpy as np
import ta
import time
from datetime import datetime
from binance.um_futures import UMFutures
from binance.error import ClientError
from xconfig import BINANCE_API_KEY, BINANCE_SECRET_KEY

client = UMFutures(key=BINANCE_API_KEY, secret=BINANCE_SECRET_KEY)

# Binance API'den veri çekme

def fetch_binance_data(symbol='BTCUSDT', interval='5m', limit=1000):
    try:
        klines = client.klines(symbol=symbol, interval=interval, limit=limit)
        df = pd.DataFrame(klines, columns=['open_time', 'open', 'high', 'low', 'close', 'volume', 
                                            'close_time', 'quote_asset_volume', 'trades', 'taker_buy_base_asset_volume', 
                                            'taker_buy_quote_asset_volume', 'ignore'])
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df.set_index('open_time', inplace=True)
        df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
        return df
    except ClientError as e:
        print(f"Binance API Error: {e}")
        return None

# MACD fiyat pattern stratejisi
def macd_hist(df):
    df['buy_signal'] = (df['high'].shift(1) > df['close'].shift(1)) & \
                       (df['close'].shift(1) > df['high'].shift(3)) & \
                       (df['high'].shift(3) > df['high'].shift(2)) & \
                       (df['high'].shift(2) > df['low'].shift(1)) & \
                       (df['low'].shift(1) > df['low'].shift(3)) & \
                       (df['low'].shift(2) > df['low'].shift(2))
    
    df['sell_signal'] = (df['low'].shift(1) < df['open'].shift(1)) & \
                        (df['open'].shift(1) < df['low'].shift(3)) & \
                        (df['low'].shift(3) < df['low'].shift(2)) & \
                        (df['low'].shift(2) < df['high'].shift(1)) & \
                        (df['high'].shift(1) < df['high'].shift(3)) & \
                        (df['high'].shift(2) < df['high'].shift(2))
    return df

# Backtest fonksiyonu
def backtest(df, initial_balance=1000, risk=0.01, price_change=0.01):
    balance = initial_balance
    position = 0
    entry_price = 0
    df = macd_hist(df)
    
    for i in range(len(df)):
        if position == 0:
            if df['buy_signal'].iloc[i]:
                entry_price = df['close'].iloc[i]
                sl = entry_price * (1 - price_change)
                tp = entry_price * (1 + price_change)
                position = 1
                print(f"BUY: {entry_price} | TP: {tp} | SL: {sl}")
            elif df['sell_signal'].iloc[i]:
                entry_price = df['close'].iloc[i]
                sl = entry_price * (1 + price_change)
                tp = entry_price * (1 - price_change)
                position = -1
                print(f"SELL: {entry_price} | TP: {tp} | SL: {sl}")
        
        if position != 0:
            if (position == 1 and df['high'].iloc[i] >= tp) or (position == -1 and df['low'].iloc[i] <= tp):
                balance += balance * risk
                position = 0
                print(f"Take Profit Hit | Balance: {balance}")
            elif (position == 1 and df['low'].iloc[i] <= sl) or (position == -1 and df['high'].iloc[i] >= sl):
                balance -= balance * risk
                position = 0
                print(f"Stop Loss Hit | Balance: {balance}")
    
    print(f"Final Balance: {balance}")
    return balance

# Örnek kullanım
data = fetch_binance_data('BTCUSDT', '1h', 100)
if data is not None:
    backtest(data)
