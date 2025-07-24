import pandas as pd
import numpy as np
from binance.um_futures import UMFutures
from ta.trend import MACD, EMAIndicator, adx
from ta.momentum import StochRSIIndicator, rsi
from ta.volatility import AverageTrueRange
from xgboost import XGBRegressor
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

def create_target_variable(data):
    data['next_close'] = data['close'].shift(-1)
    data.dropna(inplace=True)
    return data

def compute_volume_profile(data, bins=20):
    price_range = np.linspace(data['low'].min(), data['high'].max(), bins)
    volume_profile = np.zeros(bins - 1)
    
    for i in range(len(price_range) - 1):
        mask = (data['close'] >= price_range[i]) & (data['close'] < price_range[i + 1])
        volume_profile[i] = data.loc[mask, 'volume'].sum()
    
    data['vp_high_volume'] = np.interp(data['close'], price_range[:-1], volume_profile)
    return data

def compute_indicators(data):
    macd = MACD(close=data['close'], window_slow=26, window_fast=12, window_sign=9)
    stoch_rsi = StochRSIIndicator(close=data['close'], window=14, smooth1=3, smooth2=3)
    ema_50 = EMAIndicator(close=data['close'], window=50)
    ema_200 = EMAIndicator(close=data['close'], window=200)
    
    data['macd'] = macd.macd()
    data['macd_signal'] = macd.macd_signal()
    data['macd_histogram'] = data['macd'] - data['macd_signal']
    data['stoch_rsi'] = stoch_rsi.stochrsi()
    data['stoch_rsi_k'] = stoch_rsi.stochrsi_k()
    data['stoch_rsi_d'] = stoch_rsi.stochrsi_d()
    data['rsi'] = rsi(close=data['close'], window=14)
    data['adx'] = adx(high=data['high'], low=data['low'], close=data['close'], window=14)
    data['ema_50'] = ema_50.ema_indicator()
    data['ema_200'] = ema_200.ema_indicator()
    data['ema_crossover'] = (data['ema_50'] > data['ema_200']).astype(int)
    data['roc'] = data['close'].pct_change(periods=5) * 100
    data['price_change'] = data['close'].diff()
    data['obv'] = (data['price_change'] * data['volume']).cumsum()

    data['rsi3'] = rsi(close=data['close'], window=3)
    data['rsi5'] = rsi(close=data['close'], window=5)
    data['rsi10'] = rsi(close=data['close'], window=10)
    data['rsi14'] = rsi(close=data['close'], window=14)
    data['rsi20'] = rsi(close=data['close'], window=20)
    data['rsi30'] = rsi(close=data['close'], window=30)

    data['atr'] = AverageTrueRange(high=data['high'], low=data['low'], close=data['close'], window=14).average_true_range()
    data = compute_volume_profile(data)
    data.dropna(inplace=True)
    return data

def prepare_features(data):
    features = data[['close',
                     'obv']]
    return features, data['next_close']

def train_xgboost(data):
    X, y = prepare_features(data)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    xgb_model = XGBRegressor(n_estimators=200, learning_rate=0.05, max_depth=3)
    xgb_model.fit(X_train, y_train)
    return xgb_model

def make_prediction(model, data):
    latest_features = prepare_features(data)[0].iloc[-1:].values
    prediction = model.predict(latest_features)
    return prediction[0]

def analyze_and_predict_close(symbol, interval='4h'):
    try:
        data = get_historical_data(symbol, interval)
        data = create_target_variable(data)
        data = compute_indicators(data)
        model = train_xgboost(data)
        predicted_close = make_prediction(model, data)
        return float(predicted_close)
    except Exception as e:
        return f"Error: {e}"
