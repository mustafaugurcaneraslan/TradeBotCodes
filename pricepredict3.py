import pandas as pd
import numpy as np
from binance.um_futures import UMFutures
import ta
from ta.trend import MACD, EMAIndicator
from ta.momentum import StochRSIIndicator, rsi
from ta.volatility import AverageTrueRange
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from xconfig import BINANCE_API_KEY, BINANCE_SECRET_KEY

# Binance client
client = UMFutures(key=BINANCE_API_KEY, secret=BINANCE_SECRET_KEY)

def get_historical_data(symbol, interval='5m', limit=1000):
    raw_data = client.klines(symbol=symbol, interval=interval, limit=limit)
    data = pd.DataFrame(raw_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', '_', '_', '_', '_', '_', '_'])
    data = data[['timestamp', 'open', 'high', 'low', 'close', 'volume']].astype(float)
    data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
    data.set_index('timestamp', inplace=True)
    return data

# Hedef değişkeni oluşturma

def create_target_variable(data):
    data['target'] = 0
    threshold = 0.01  # %1 hareket eşiği

    for i in range(len(data) - 1):
        future_data = data.iloc[i+1:i+20]

        high_times = future_data[future_data['high'] >= data['close'].iloc[i] * (1 + threshold)].index
        low_times = future_data[future_data['low'] <= data['close'].iloc[i] * (1 - threshold)].index

        if not high_times.empty and not low_times.empty:
            # Hangisi önce gerçekleşti?
            if high_times[0] < low_times[0]:
                data.at[data.index[i], 'target'] = 1  # Önce yükseldiyse
            else:
                data.at[data.index[i], 'target'] = 0  # Önce düştüyse
        elif not high_times.empty:
            data.at[data.index[i], 'target'] = 1  # Sadece yükselme olduysa
        elif not low_times.empty:
            data.at[data.index[i], 'target'] = 0  # Sadece düşüş olduysa

    data.dropna(inplace=True)
    return data

# Teknik göstergeleri hesaplama

def compute_indicators(data):
    # OBV
    data['obv'] = ta.volume.OnBalanceVolumeIndicator(data['close'], data['volume']).on_balance_volume()

    # RSI
    data['rsi'] = ta.momentum.RSIIndicator(data['close'], window=14).rsi()

    # EMA
    data['ema_50'] = ta.trend.EMAIndicator(data['close'], window=50).ema_indicator()
    data['ema_200'] = ta.trend.EMAIndicator(data['close'], window=200).ema_indicator()

    # ATR
    data['atr'] = ta.volatility.AverageTrueRange(data['high'], data['low'], data['close'], window=14).average_true_range()

    # High, Low, Close, Open Tabanlı Feature'lar
    data['return'] = data['close'].pct_change()
    data['open_close_diff'] = (data['close'] - data['open']) / data['open']
    data['high_low_range'] = (data['high'] - data['low']) / data['low']
    data['close_change'] = data['close'].diff()
    data['close_ema50_ratio'] = data['close'] / data['ema_50']
    data['ema_diff'] = data['ema_50'] - data['ema_200']

    data.dropna(inplace=True)
    return data

def prepare_features(data):
    features = data[[
                     'return', 'open_close_diff', 'high_low_range', 'close_change',
                     'close_ema50_ratio', 'ema_diff']]
    return features, data['target']


# XGBoost eğitimi

def train_xgboost(data):
    X, y = prepare_features(data)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    xgb_model = XGBClassifier(n_estimators=300, learning_rate=0.01, max_depth=3, subsample=0.7, colsample_bytree=0.7)
    xgb_model.fit(X_train, y_train)
    return xgb_model

# Tahmin yapma

def make_prediction(model, data):
    latest_features = prepare_features(data)[0].iloc[-1:].values
    prediction = model.predict_proba(latest_features)
    return prediction[0]

def analyze_and_predict(symbol, interval='1h'):
    try:
        data = get_historical_data(symbol, interval)
        data = create_target_variable(data)
        data = compute_indicators(data)
        model = train_xgboost(data)
        probabilities = make_prediction(model, data)
        
        return probabilities[1], probabilities[0]  # Yukarı ve aşağı olasılıkları
    except Exception as e:
        return f"Error: {e}"
