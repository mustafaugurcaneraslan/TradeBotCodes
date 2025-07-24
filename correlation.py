import asyncio
import aiohttp
import numpy as np
import warnings
from aiohttp import resolver

BASE_URL = "https://fapi.binance.com"
REFERENCE_SYMBOL = "BTCUSDT"
INTERVAL = "1h"
LIMIT = 100
TOP_N = 6  # En yüksek korelasyonlu kaç tane yazılacak

async def fetch_klines(session, symbol):
    url = f"{BASE_URL}/fapi/v1/klines?symbol={symbol}&interval={INTERVAL}&limit={LIMIT}"
    try:
        async with session.get(url) as response:
            data = await response.json()
            closes = [float(entry[4]) for entry in data]
            if len(closes) == LIMIT:
                return symbol, closes
            else:
                return symbol, None
    except:
        return symbol, None

async def get_all_futures_symbols(session):
    url = f"{BASE_URL}/fapi/v1/exchangeInfo"
    async with session.get(url) as response:
        data = await response.json()
        return [s["symbol"] for s in data["symbols"] if s["quoteAsset"] == "USDT" and s["contractType"] == "PERPETUAL"]

async def find_correlations():
    connector = aiohttp.TCPConnector(resolver=resolver.ThreadedResolver())
    async with aiohttp.ClientSession(connector=connector) as session:
        symbols = await get_all_futures_symbols(session)

        tasks = [fetch_klines(session, symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks)

        prices = {}
        for symbol, closes in results:
            if closes:
                prices[symbol] = closes

        ref = prices.get(REFERENCE_SYMBOL)
        if not ref:
            print(f"Referans sembol ({REFERENCE_SYMBOL}) verisi alınamadı.")
            return

        warnings.filterwarnings('ignore', category=RuntimeWarning)

        correlations = []
        for symbol, data in prices.items():
            if symbol == REFERENCE_SYMBOL:
                continue
            if np.std(ref) == 0 or np.std(data) == 0:
                continue
            try:
                corr = np.corrcoef(ref, data)[0, 1]
                if not np.isnan(corr):
                    correlations.append((symbol, corr))
            except:
                continue

        # Korelasyonlara göre azalan sırala ve ilk TOP_N tanesini al
        correlations.sort(key=lambda x: x[1], reverse=True)
        top_correlations = correlations[:TOP_N]

        print(f"En yüksek {TOP_N} korelasyon (referans: {REFERENCE_SYMBOL}):")
        for symbol, corr in top_correlations:
            print(f"{symbol}: Korelasyon = {corr:.2f}")

asyncio.run(find_correlations())
