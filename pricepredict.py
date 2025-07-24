import pandas as pd
import numpy as np
from binance.um_futures import UMFutures
from ta.trend import MACD, EMAIndicator,adx
from ta.momentum import StochRSIIndicator, rsi
from sklearn.ensemble import RandomForestRegressor
from xconfig import BINANCE_API_KEY, BINANCE_SECRET_KEY

# Binance client for historical data
client = UMFutures(key=BINANCE_API_KEY, secret=BINANCE_SECRET_KEY)

def get_historical_data(symbol, interval='5m', limit=1000):
    raw_data = client.klines(symbol=symbol, interval=interval, limit=limit)
    data = pd.DataFrame(raw_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', '_', '_', '_', '_', '_', '_'])
    data = data[['timestamp', 'open', 'high', 'low', 'close', 'volume']].astype(float)
    data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
    data.set_index('timestamp', inplace=True)
    return data

def create_target_variable(data):
    data['next_close'] = data['close'].shift(-1)
    data = data.dropna()
    return data

def compute_macd(data):
    macd = MACD(close=data['close'], window_slow=26, window_fast=12, window_sign=9)
    data['macd'] = macd.macd()
    data['macd_signal'] = macd.macd_signal()
    data['macd_histogram'] = data['macd'] - data['macd_signal']
    return data

def compute_stoch_rsi(data):
    stoch_rsi = StochRSIIndicator(close=data['close'], window=14, smooth1=3, smooth2=3)
    data['stoch_rsi'] = stoch_rsi.stochrsi()
    data['stoch_rsi_d'] = stoch_rsi.stochrsi_d()
    data['stoch_rsi_k'] = stoch_rsi.stochrsi_k()
    data['rsi'] = rsi(close=data['close'], window=14)
    data['adx'] = adx(high=data['high'], low=data['low'], close=data['close'], window=14)
    return data

def compute_ema(data):
    ema_50 = EMAIndicator(close=data['close'], window=50)
    ema_200 = EMAIndicator(close=data['close'], window=200)

    sma_10 = data['close'].rolling(window=10).mean()
    sma_5 = data['close'].rolling(window=5).mean()
    sma_15 = data['close'].rolling(window=15).mean()
    data['ema_50'] = ema_50.ema_indicator()
    data['ema_200'] = ema_200.ema_indicator()
    data['sma_5'] = sma_5
    data['sma_10'] = sma_10
    data['sma_15'] = sma_15
    return data

def prepare_features(data):
    features = data[['open', 'high', 'low', 'close', 'volume', 
                     'macd', 'macd_signal', 'macd_histogram', 'stoch_rsi', 
                     'ema_50', 'ema_200','stoch_rsi_k','stoch_rsi_d','rsi','adx','sma_5','sma_10','sma_15']].values
    return features

def train_random_forest(data):
    features = prepare_features(data)
    target = data['next_close'].values
    rf = RandomForestRegressor(n_estimators=100, random_state=42)
    rf.fit(features, target)
    return rf

def make_prediction(rf, data):
    latest_features = data[['open', 'high', 'low', 'close', 'volume', 
                            'macd', 'macd_signal', 'macd_histogram', 'stoch_rsi', 
                            'ema_50', 'ema_200','stoch_rsi_k','stoch_rsi_d','rsi','adx','sma_5','sma_10','sma_15']].iloc[-1:].values
    prediction = rf.predict(latest_features)
    return prediction[0]

def analyze_and_predict_close(symbol, interval='4h'):
    try:
        data = get_historical_data(symbol, interval)
        data = create_target_variable(data)
        data = compute_macd(data)
        data = compute_stoch_rsi(data)
        data = compute_ema(data)
        data = data.dropna()
        rf = train_random_forest(data)
        predicted_close = make_prediction(rf, data)
        return predicted_close
    except Exception as e:
        return f"Error: {e}"
