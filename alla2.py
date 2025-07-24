import asyncio
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import aiohttp
import pandas as pd
import numpy as np


BINANCE_FUTURES_BASE = "https://fapi.binance.com"

async def fetch(session, url):
    try:
        async with session.get(url, timeout=10) as response:
            return await response.json()
    except Exception as e:
        print(f"Fetch error {url}: {e}")
        return None

def compute_rsi(prices, period=14):
    deltas = np.diff(prices)
    seed = deltas[:period]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down if down != 0 else 0
    rsi = np.zeros_like(prices)
    rsi[:period] = 100. - 100. / (1. + rs)

    for i in range(period, len(prices)):
        delta = deltas[i - 1]
        if delta > 0:
            upval = delta
            downval = 0.
        else:
            upval = 0.
            downval = -delta

        up = (up * (period - 1) + upval) / period
        down = (down * (period - 1) + downval) / period

        rs = up / down if down != 0 else 0
        rsi[i] = 100. - 100. / (1. + rs)

    return rsi

async def get_high_volume_symbols(session, min_volume_usd=50_000_000):
    url = f"{BINANCE_FUTURES_BASE}/fapi/v1/ticker/24hr"
    data = await fetch(session, url)
    if not data:
        return []

    symbols = []
    for item in data:
        symbol = item['symbol']
        if not symbol.endswith('USDT'):
            continue
        quote_volume = float(item.get('quoteVolume', 0))  # quoteVolume zaten USDT cinsinden
        if quote_volume >= min_volume_usd:
            symbols.append(symbol)
    return symbols

async def score_coin(session, symbol):
    try:
        url_15m = f"{BINANCE_FUTURES_BASE}/fapi/v1/klines?symbol={symbol}&interval=15m&limit=100"
        url_4h = f"{BINANCE_FUTURES_BASE}/fapi/v1/klines?symbol={symbol}&interval=4h&limit=100"
        url_funding = f"{BINANCE_FUTURES_BASE}/fapi/v1/premiumIndex?symbol={symbol}"
        url_oi = f"{BINANCE_FUTURES_BASE}/futures/data/openInterestHist?symbol={symbol}&period=5m&limit=20"

        responses = await asyncio.gather(
            fetch(session, url_15m),
            fetch(session, url_4h),
            fetch(session, url_funding),
            fetch(session, url_oi)
        )

        klines_15m, klines_4h, funding_data, oi_data = responses

        if not klines_15m or not klines_4h or not funding_data or not oi_data:
            return None

        closes_15m = [float(k[4]) for k in klines_15m]
        closes_4h = [float(k[4]) for k in klines_4h]

        rsi_15m = compute_rsi(np.array(closes_15m))[-1]
        rsi_4h = compute_rsi(np.array(closes_4h))[-1]

        funding_rate = float(funding_data.get("lastFundingRate", 0))

        oi_open = float(oi_data[0]['sumOpenInterest'])
        oi_last = float(oi_data[-1]['sumOpenInterest'])
        oi_change_pct = (oi_last - oi_open) / oi_open * 100 if oi_open != 0 else 0

        score = 0
        if rsi_15m < 30:
            score += 1
        elif rsi_15m > 70:
            score -= 1

        if rsi_4h < 30:
            score += 1
        elif rsi_4h > 70:
            score -= 1

        if funding_rate < 0:
            score += 1
        elif funding_rate > 0:
            score -= 1

        if oi_change_pct > 2:
            score += 1
        elif oi_change_pct < -2:
            score -= 1

        return {
            "symbol": symbol,
            "rsi_15m": round(rsi_15m, 2),
            "rsi_4h": round(rsi_4h, 2),
            "funding_rate": round(funding_rate, 6),
            "oi_change_pct": round(oi_change_pct, 2),
            "score": score
        }
    except Exception as e:
        print(f"Error scoring {symbol}: {e}")
        return None

async def main():
    async with aiohttp.ClientSession() as session:
        print("Coinleri hacime göre filtreliyorum...")
        symbols = await get_high_volume_symbols(session)
        print(f"Toplam {len(symbols)} coin bulundu.")

        tasks = [score_coin(session, symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks)

    df = pd.DataFrame([r for r in results if r])
    df = df.sort_values(by="score", ascending=False)
    print(df)

if __name__ == "__main__":
    asyncio.run(main())
