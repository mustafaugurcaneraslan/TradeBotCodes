import asyncio
import aiohttp
import numpy as np
from colorama import Fore, Style
from xconfig import BINANCE_API_KEY

# Windows uyumu
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

BASE_URL = "https://fapi.binance.com"
interval = "15m"
headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
blacklist = ["TRXUSDT", "BTCUSDT"]

async def fetch(session, url, params=None):
    try:
        async with session.get(url, params=params, headers=headers, timeout=10) as response:
            return await response.json()
    except Exception as e:
        print(f"Fetch error: {e}")
        return None

async def get_high_volume_symbols(session, min_volume=100_000_000):
    url = f"{BASE_URL}/fapi/v1/ticker/24hr"
    tickers = await fetch(session, url)
    if tickers is None:
        return []
    return [
        t['symbol'] for t in tickers
        if t['symbol'].endswith("USDT") and float(t['quoteVolume']) >= min_volume and t['symbol'] not in blacklist
    ]

async def get_average_percent_range(session, symbol):
    url = f"{BASE_URL}/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": 100}
    candles = await fetch(session, url, params)
    if not candles or len(candles) < 100:
        return None

    # % range = ((High - Low) / Low) * 100 her mum için
    percent_ranges = [((float(c[2]) - float(c[3])) / float(c[3])) * 100 for c in candles]

    avg_percent_range = np.mean(percent_ranges)
    max_percent_range = max(percent_ranges)
    return symbol, round(avg_percent_range, 4), round(max_percent_range, 4)

async def get_top_range_movers():
    async with aiohttp.ClientSession() as session:
        symbols = await get_high_volume_symbols(session)
        print(f"\n📊 {interval} için kontrol ediliyor... Toplam {len(symbols)} sembol\n")
        tasks = [get_average_percent_range(session, symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks)
        results = [r for r in results if r is not None]
        # Maksimum yüzde range'e göre sırala, en çok hareket edenler önde
        results.sort(key=lambda x: x[2], reverse=True)
        return results[:5]

async def main():
    movers = await get_top_range_movers()
    print(f"\n🔥 15 dakikalık mumda en çok hareket eden coinler (yüzde range bazlı):\n")
    for symbol, avg, max_r in movers:
        print(f"{Fore.CYAN}- {symbol}: Ortalama % Range = %{avg}, En Büyük % Range = %{max_r}{Style.RESET_ALL}")

if __name__ == "__main__":
    asyncio.run(main())
