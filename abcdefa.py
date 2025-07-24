import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf
from binance.um_futures import UMFutures
from xconfig import BINANCE_API_KEY, BINANCE_SECRET_KEY
from scipy.spatial.distance import euclidean

# Binance client
client = UMFutures(key=BINANCE_API_KEY, secret=BINANCE_SECRET_KEY)

later_candles = 20

def get_historical_klines(symbol, interval, limit=1000):
    """Belirtilen sembol için Open, High, Low ve Close fiyatlarını alır."""
    klines = client.klines(symbol=symbol, interval=interval, limit=limit)
    ohlc = np.array([[float(k[1]), float(k[2]), float(k[3]), float(k[4])] for k in klines])  # Open, High, Low, Close
    timestamps = np.array([int(k[0]) for k in klines])  # Zaman damgaları (milisaniye cinsinden)
    return timestamps, ohlc

def find_most_similar_patterns(symbol, interval="15m", window=20, top_n=8):
    """Son 20 mumluk Open, High, Low ve Close paterne en çok benzeyen geçmiş paternleri bul ve grafikle göster."""
    timestamps, ohlc = get_historical_klines(symbol, interval, limit=1000)
    
    if len(ohlc) < window:
        print("Yetersiz veri!")
        return
    
    latest_pattern = ohlc[-window:, :]  # En son 20 mum (Open, High, Low, Close)
    latest_timestamps = timestamps[-window:]
    
    # Open - Close farklarını hesaplayalım
    latest_pattern_diff = latest_pattern[:, 0] - latest_pattern[:, 3]  # Open - Close farkı

    distances = []
    for i in range(len(ohlc) - window - later_candles):  # 5 ekstra mum için sınır koyduk
        past_pattern = ohlc[i:i + window, :]
        
        # Open - Close farklarını hesapla
        past_pattern_diff = past_pattern[:, 0] - past_pattern[:, 3]  # Open - Close farkı
        
        # Euclidean mesafeyi sadece Open - Close farkları üzerinden hesapla
        dist = euclidean(latest_pattern_diff, past_pattern_diff)
        
        future_pattern = ohlc[i:i + window + later_candles, :]  # Sonraki 25 mum (20 benzer + 5 devam)
        distances.append((timestamps[i], dist, future_pattern, timestamps[i:i + window + later_candles], i))  # index de ekledik
    
    distances.sort(key=lambda x: x[1])  # Mesafeye göre sırala
    
    print(f"{symbol} için en benzer {top_n} patern:")
    
    # 3lü sıra düzeni için alt alta 3 grafik göstermek için subplot ayarlaması yapalım
    rows = (top_n + 2) // 3  # Satır sayısını 3 grafik olacak şekilde hesapla
    fig, axes = plt.subplots(rows, 3, figsize=(12, 6 * rows))
    
    def plot_candlestick(ax, pattern, timestamps, title):
        """Mum grafiği çizme fonksiyonu."""
        df = pd.DataFrame(pattern, columns=["Open", "High", "Low", "Close"], index=pd.to_datetime(timestamps, unit='ms'))
        mpf.plot(df, type='candle', ax=ax, style='charles')
        ax.set_title(title)
    
    # İlk grafikte şu anki son 20 mum gösteriliyor
    axes = axes.flatten()  # Axes'i 1D hale getirelim
    plot_candlestick(axes[0], latest_pattern, latest_timestamps, "Son 20 Mum")
    
    # Benzer paternleri bulalım, ancak aynı yerleri tekrar seçmemek için bir kontrol ekleyelim
    selected_indexes = set()  # Seçilen indeksleri burada tutacağız
    displayed = 0  # Kaç adet patern seçildiğini takip edelim
    for i in range(len(distances)):
        timestamp, dist, future_pattern, future_timestamps, idx = distances[i]
        
        # Eğer bu indeks daha önce seçildiyse, devam et
        if idx in selected_indexes:
            continue
        
        # Seçilen paterni kaydedelim
        selected_indexes.add(idx)
        
        # 8 tane benzer paternin her biri eklenene kadar devam et
        print(f"Zaman: {pd.to_datetime(timestamp, unit='ms')} - Mesafe: {dist:.5f}")
        plot_candlestick(axes[displayed + 1], future_pattern, future_timestamps, f"Benzer {displayed + 1} - 25 Mum (20 Benzer + 5 Devam)")
        
        displayed += 1
        if displayed >= top_n:  # Eğer istediğimiz kadar benzer patern bulduysak çık
            break
    
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    symbol = "ETHUSDT"
    find_most_similar_patterns(symbol)