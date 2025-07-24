import asyncio
import aiohttp
from colorama import Fore, Style
from xconfig import BINANCE_API_KEY  # Binance API key’in burada olsun

asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

BASE_URL = "https://fapi.binance.com"
intervals = ["15m","30m","1h", "2h", "3h", "4h"]

headers = {
    "X-MBX-APIKEY": BINANCE_API_KEY
}

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

async def get_klines(session, symbol, interval="1h", limit=100):
    url = f"{BASE_URL}/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    data = await fetch(session, url, params)
    if not data or len(data) < limit:
        return None
    return data

def calculate_wavetrend(klines, n1=9, n2=12):
    closes = [float(k[4]) for k in klines]
    highs = [float(k[2]) for k in klines]
    lows = [float(k[3]) for k in klines]

    typical_prices = [(highs[i] + lows[i] + closes[i]) / 3 for i in range(len(klines))]

    def ema(values, period):
        ema_vals = []
        k = 2 / (period + 1)
        for i, val in enumerate(values):
            if i == 0:
                ema_vals.append(val)
            else:
                ema_vals.append(val * k + ema_vals[-1] * (1 - k))
        return ema_vals

    esa = ema(typical_prices, n1)
    d = [abs(typical_prices[i] - esa[i]) for i in range(len(esa))]
    esa_d = ema(d, n1)
    ci = [(typical_prices[i] - esa[i]) / (0.015 * esa_d[i]) if esa_d[i] != 0 else 0 for i in range(len(esa))]

    wt1 = ema(ci, n2)
    wt2 = [sum(wt1[max(0, i-3):i+1])/min(i+1, 4) for i in range(len(wt1))]

    return wt1, wt2

async def check_symbol_wavetrend_cross(session, symbol, interval):
    klines = await get_klines(session, symbol, interval, limit=100)
    if not klines:
        return None

    wt1, wt2 = calculate_wavetrend(klines)
    if len(wt1) < 3 or len(wt2) < 3:
        return None

    prev_wt1 = wt1[-2]
    prev_wt2 = wt2[-2]
    last_wt1 = wt1[-1]
    last_wt2 = wt2[-1]

    prev_diff = prev_wt1 - prev_wt2
    last_diff = last_wt1 - last_wt2

    # Short sinyal: 0-30 aralığında yukarıdan aşağı kesişim
    if 0 <= prev_wt1 <= 30 and 0 <= prev_wt2 <= 30:
        if prev_diff > 0 and last_diff < 0:
            # Filtre: önceki fark 0'ın altında olmamalı
            if prev_diff < 0:
                return None
            return (symbol, f"Short WaveTrend cross between 0-30: {prev_wt1:.2f} → {last_wt1:.2f}", "bearish", interval)

    # Long sinyal: 0 ile -30 aralığında aşağıdan yukarı kesişim
    if -30 <= prev_wt1 <= 0 and -30 <= prev_wt2 <= 0:
        if prev_diff < 0 and last_diff > 0:
            # Filtre: önceki fark 0'ın üstünde olmamalı
            if prev_diff > 0:
                return None
            return (symbol, f"Long WaveTrend cross between 0 and -30: {prev_wt1:.2f} → {last_wt1:.2f}", "bullish", interval)

    return None


async def check_all_symbols():
    async with aiohttp.ClientSession() as session:
        symbols = await get_high_volume_symbols(session)

        print(f"{len(symbols)} sembol günlük hacmi 100M USDT üstünde, kontrol ediliyor...\n")

        for interval in intervals:
            print(f"\n⏱️ {interval} zaman dilimi kontrol ediliyor...\n")
            tasks = []
            for symbol in symbols:
                tasks.append(check_symbol_wavetrend_cross(session, symbol, interval))
            results = await asyncio.gather(*tasks)

            filtered = [res for res in results if res]

            if filtered:
                for sym, msg, typ, intrvl in filtered:
                    if typ == "bullish":
                        print(f"{Fore.GREEN}- {sym} - {msg} ({intrvl}){Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}- {sym} - {msg} ({intrvl}){Style.RESET_ALL}")
            else:
                print("Hiçbir coin WaveTrend short/long kesişimi sağlamıyor.")

async def main():
    await check_all_symbols()

if __name__ == "__main__":
    asyncio.run(main())
