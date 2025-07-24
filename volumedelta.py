import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
import sys

if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

BASE_URL = "https://fapi.binance.com"

async def fetch_klines(session, symbol, interval, start_time=None, limit=500):
    url = f"{BASE_URL}/fapi/v1/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }
    if start_time:
        params["startTime"] = int(start_time.timestamp() * 1000)
    async with session.get(url, params=params) as resp:
        data = await resp.json()
        return data

def calculate_cvd(klines):
    # klines = list of lists, each kline = [open_time, open, high, low, close, volume, ...]
    cvd_values = []
    cumulative_delta = 0.0

    for k in klines:
        open_p = float(k[1])
        close_p = float(k[4])
        volume = float(k[5])

        # Eğer fiyat yükseldiyse hacim pozitif, düştüyse negatif hacim
        delta = volume if close_p > open_p else -volume
        cumulative_delta += delta
        cvd_values.append(cumulative_delta)

    return cvd_values

async def main():
    symbol = "BTCUSDT"
    interval = "1m"
    
    # Günlük anchor zamanı: bugün saat 03:00 UTC
    now_utc = datetime.now(timezone.utc)
    anchor = now_utc.replace(hour=3, minute=0, second=0, microsecond=0)
    if now_utc < anchor:
        anchor -= timedelta(days=1)

    print(f"Anchor start time UTC: {anchor}")

    async with aiohttp.ClientSession() as session:
        klines = await fetch_klines(session, symbol, interval, start_time=anchor, limit=100)
        
        if not klines:
            print("Kline verisi alınamadı.")
            return
        
        # Örnek olarak ilk 5 mum basılıyor
        for k in klines[:5]:
            open_time = datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc)
            print(f"{open_time} O:{k[1]} H:{k[2]} L:{k[3]} C:{k[4]} V:{k[5]}")
        
        cvd = calculate_cvd(klines)
        print("\nCumulative Volume Delta (son 5 değer):")
        for i, val in enumerate(cvd[-5:], start=len(cvd)-5):
            print(f"Bar {i}: {val:.2f}")

if __name__ == "__main__":
    asyncio.run(main())
