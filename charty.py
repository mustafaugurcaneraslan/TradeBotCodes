import time
from datetime import datetime
import pandas as pd
import ta
import matplotlib.pyplot as plt
from binance.um_futures import UMFutures
from binance.error import ClientError
from xconfig import BINANCE_API_KEY, BINANCE_SECRET_KEY

client = UMFutures(key=BINANCE_API_KEY, secret=BINANCE_SECRET_KEY)

def klines(symbol, interval):
    try:
        resp = pd.DataFrame(client.klines(symbol, interval))
        resp = resp.iloc[:, :6]
        resp.columns = ['open_time', 'open', 'high', 'low', 'close', 'volume']
        resp = resp.set_index('open_time')
        resp.index = pd.to_datetime(resp.index, unit='ms')
        resp = resp.astype(float)
        return resp
    except ClientError as error:
        print(f"Error: {error.error_message}")
        return None

def calculate_signal(df):
    # EMA ve VWAP hesapla
    df['ema_50'] = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator()
    df['ema_200'] = ta.trend.EMAIndicator(df['close'], window=200).ema_indicator()

    # VWAP hesaplama
    df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
    df['vwap'] = (df['typical_price'] * df['volume']).cumsum() / df['volume'].cumsum()

    # Hacim analizi: Ortalama hacmi al
    df['avg_volume'] = df['volume'].rolling(window=20).mean()

    signals = []
    
    for i in range(1, len(df)):
        # Alım sinyali: Fiyat EMA50'nin üzerinde, EMA50 > EMA200, fiyat VWAP'ı geçti, hacim ortalamanın üzerinde
        if (df['close'].iloc[i] > df['ema_50'].iloc[i] and
            df['ema_50'].iloc[i] > df['ema_200'].iloc[i] and
            df['close'].iloc[i] > df['vwap'].iloc[i] and
            df['volume'].iloc[i] > df['avg_volume'].iloc[i]):
            signals.append(('buy', df.index[i], df['close'].iloc[i]))

        # Satım sinyali: Fiyat EMA50'nin altında, EMA50 < EMA200, fiyat VWAP'ın altında, hacim ortalamanın üzerinde
        elif (df['close'].iloc[i] < df['ema_50'].iloc[i] and
              df['ema_50'].iloc[i] < df['ema_200'].iloc[i] and
              df['close'].iloc[i] < df['vwap'].iloc[i] and
              df['volume'].iloc[i] > df['avg_volume'].iloc[i]):
            signals.append(('sell', df.index[i], df['close'].iloc[i]))

    return signals

def backtest(symbol, interval='5m', initial_balance=1000, trade_size_usd=50, leverage=20):
    df = klines(symbol, interval)
    if df is None:
        return
    
    balance = initial_balance
    position = 0  # Pozisyon (pozitif: long, negatif: short)
    entry_price = 0  # İşleme giriş fiyatı
    trades = []
    
    tp_percent = 0.02  # Take profit %2
    sl_percent = 0.01  # Stop loss %1
    
    signals = calculate_signal(df)
    
    if not signals:  # Eğer sinyal yoksa uyarı ver
        print("No signals generated! Check your strategy or data.")
        return
    
    for signal in signals:
        signal_type, time, price = signal
        trade_size = trade_size_usd / price  # Dolar bazlı pozisyon boyutu hesapla
        
        if signal_type == 'buy' and position == 0:
            position = trade_size * leverage
            entry_price = price
            tp_price = entry_price * (1 + tp_percent)
            sl_price = entry_price * (1 - sl_percent)
            trades.append(('buy', time, entry_price))
        
        if position > 0:
            if price >= tp_price:  # Take Profit (TP)
                profit = (tp_price - entry_price) * trade_size * leverage
                balance += profit
                position = 0
                trades.append(('sell_tp', time, tp_price, profit))
            elif price <= sl_price:  # Stop Loss (SL)
                loss = (entry_price - sl_price) * trade_size * leverage
                balance -= loss
                position = 0
                trades.append(('sell_sl', time, sl_price, -loss))
    
    print(f"Final Balance: {balance:.2f} USDT")
    return trades, balance

backtest('BTCUSDT', '5m')
