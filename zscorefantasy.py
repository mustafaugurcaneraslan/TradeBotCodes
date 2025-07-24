import pandas as pd
import numpy as np
from binance.um_futures import UMFutures
from xconfig import BINANCE_API_KEY, BINANCE_SECRET_KEY

# Binance client
client = UMFutures(key=BINANCE_API_KEY, secret=BINANCE_SECRET_KEY)

def get_all_futures_symbols():
    """Binance UM Futures'taki tüm işlem çiftlerini alır."""
    exchange_info = client.exchange_info()
    return [symbol['symbol'] for symbol in exchange_info['symbols'] if symbol['contractType'] == 'PERPETUAL' and symbol['marginAsset'] == 'USDT']

def get_historical_klines(symbol, interval, limit=50):
    """Belirtilen sembol için kapanış fiyatlarını alır."""
    klines = client.klines(symbol=symbol, interval=interval, limit=limit)
    closes = np.array([float(k[4]) for k in klines])  # Kapanış fiyatları
    return closes

def calculate_standard_deviation(prices, window=50):
    """Standart sapma hesaplar."""
    if len(prices) < window:
        return 0
    return np.std(prices[-window:])

def calculate_z_score(current_price, avg_price, std_dev):
    """Z-skorunu hesaplar."""
    if std_dev == 0:
        return 0
    return (current_price - avg_price) / std_dev

def find_anomalies():
    """1 saatlik, 15 dakikalık ve 5 dakikalık Z-skorlarını karşılaştırarak anomaliyi bulur."""
    symbols = get_all_futures_symbols()
    anomalies = []
    
    for symbol in symbols:
        try:
            prices_1h = get_historical_klines(symbol, "1h")
            prices_15m = get_historical_klines(symbol, "15m")
            prices_5m = get_historical_klines(symbol, "5m")
            
            if len(prices_1h) < 50 or len(prices_15m) < 50 or len(prices_5m) < 50:
                continue  # Yetersiz veri olanları atla
            
            # 1 saatlik Z-skoru hesapla
            avg_price_1h = np.mean(prices_1h[-50:])
            std_dev_1h = calculate_standard_deviation(prices_1h)
            z_score_1h = calculate_z_score(prices_1h[-1], avg_price_1h, std_dev_1h)
            
            # 15 dakikalık Z-skoru hesapla
            avg_price_15m = np.mean(prices_15m[-50:])
            std_dev_15m = calculate_standard_deviation(prices_15m)
            z_score_15m = calculate_z_score(prices_15m[-1], avg_price_15m, std_dev_15m)
            
            # 5 dakikalık Z-skoru hesapla
            avg_price_5m = np.mean(prices_5m[-50:])
            std_dev_5m = calculate_standard_deviation(prices_5m)
            z_score_5m = calculate_z_score(prices_5m[-1], avg_price_5m, std_dev_5m)
            
            # 1H ve 5M aynı yönde, 15M ters yönde ise listeye ekle
            if (z_score_1h * z_score_5m < 0) and (z_score_1h * z_score_15m < 0):
                anomalies.append((symbol, abs(z_score_5m), z_score_5m))
                print(f"{symbol} - 1H Z: {z_score_1h:.2f}, 15M Z: {z_score_15m:.2f}, 5M Z: {z_score_5m:.2f}")
        
        except Exception as e:
            print(f"{symbol} için veri çekilirken hata oluştu: {e}")
    
    # 5 dakikalık en büyük mutlak sapmaya göre sırala ve ilk 20'yi al
    sorted_anomalies = sorted(anomalies, key=lambda x: x[1], reverse=True)[:20]
    
    print("\n5 dakikalık en büyük sapmaya sahip ilk 20 coin:")
    for symbol, abs_z, z in sorted_anomalies:
        print(f"{symbol} - 5M Z-skoru: {z:.2f} (Sapma büyüklüğü: {abs_z:.2f})")
    
if __name__ == "__main__":
    find_anomalies()
