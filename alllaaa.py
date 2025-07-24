import asyncio
import aiohttp
import numpy as np
from colorama import Fore, Style
from xconfig import BINANCE_API_KEY, BINANCE_SECRET_KEY

BASE_URL = "https://fapi.binance.com"

headers = {
    "X-MBX-APIKEY": BINANCE_API_KEY
}

asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

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
        if t['symbol'].endswith("USDT") and float(t['quoteVolume']) >= min_volume
    ]

async def get_klines(session, symbol, interval="15m", limit=100):
    url = f"{BASE_URL}/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    return await fetch(session, url, params)

def calculate_rsi(closes, period=14):
    closes = np.array(closes, dtype=float)
    deltas = np.diff(closes)
    seed = deltas[:period]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down if down != 0 else 0
    rsi = np.zeros_like(closes)
    rsi[:period] = 50  # ilk değer ortalama

    for i in range(period, len(closes)):
        delta = deltas[i - 1]
        if delta > 0:
            up_val = delta
            down_val = 0
        else:
            up_val = 0
            down_val = -delta
        up = (up * (period - 1) + up_val) / period
        down = (down * (period - 1) + down_val) / period
        rs = up / down if down != 0 else 0
        rsi[i] = 100 - 100 / (1 + rs)
    return rsi

async def analyze_symbol(session, symbol):
    klines = await get_klines(session, symbol, "15m", 100)
    if klines is None or len(klines) < 20:
        return None

    closes = [float(c[4]) for c in klines]
    highs = [float(c[2]) for c in klines]
    lows = [float(c[3]) for c in klines]

    last_close = closes[-1]
    last_high = highs[-1]
    last_low = lows[-1]

    rsi = calculate_rsi(closes)
    last_rsi = rsi[-1]

    # Fiyat son zamanlarda tepe yaptı mı?
    local_top = (last_close < highs[-2]) and (highs[-2] > highs[-3])

    # Son mum uzun wick'li ve düşüş mü göstermiş?
    upper_wick = highs[-1] - max(closes[-1], closes[-1])
    body = abs(closes[-1] - closes[-1])
    wick_ratio = upper_wick / (body + 1e-6)

    # Kriter: RSI yüksek + local tepe var + wick uzun
    score = 0
    if last_rsi > 65:   
        score += 1
    if local_top:
        score += 1
    if wick_ratio > 2:
        score += 1

    if score >= 2:
        return (symbol, last_rsi, score)
    return None

async def find_top_shortables():
    async with aiohttp.ClientSession() as session:
        symbols = await get_high_volume_symbols(session)
        print(f"{len(symbols)} sembol taranıyor...")

        tasks = [analyze_symbol(session, symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks)

        valid_results = [r for r in results if r is not None]
        sorted_results = sorted(valid_results, key=lambda x: (-x[2], -x[1]))  # skor ve RSI'ya göre sırala

        print(f"\n🔴 TOP 5 SHORT ADAYLARI 🔴")
        for symbol, rsi_value, score in sorted_results[:5]:
            print(f"{Fore.RED}{symbol}{Style.RESET_ALL} | RSI: {rsi_value:.2f} | Score: {score}")

if __name__ == "__main__":
    asyncio.run(find_top_shortables())
