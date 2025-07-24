import sys
import asyncio
import aiohttp

if sys.platform.startswith('win') and sys.version_info >= (3, 8):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

BASE_URL = "https://fapi.binance.com"

async def fetch_symbols():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/fapi/v1/exchangeInfo") as resp:
            data = await resp.json()
            return [s['symbol'] for s in data['symbols'] if s['contractType'] == 'PERPETUAL']

async def fetch_funding(session, symbol):
    try:
        async with session.get(f"{BASE_URL}/fapi/v1/fundingRate?symbol={symbol}&limit=2") as resp:
            data = await resp.json()
            if len(data) == 2:
                rate = float(data[1]['fundingRate'])  # en güncel funding rate
                time1 = int(data[0]['fundingTime'])
                time2 = int(data[1]['fundingTime'])
                interval_hours = abs(time2 - time1) / 1000 / 60 / 60
                if interval_hours == 0:
                    return None
                normalized = rate / interval_hours
                return {
                    'symbol': symbol,
                    'funding_rate': rate,
                    'interval_hours': interval_hours,
                    'normalized_rate': normalized
                }
    except:
        return None

async def main(top_n=20):
    symbols = await fetch_symbols()
    results = []

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_funding(session, symbol) for symbol in symbols]
        responses = await asyncio.gather(*tasks)

    for r in responses:
        if r:
            results.append(r)

    sorted_results = sorted(results, key=lambda x: abs(x['normalized_rate']), reverse=True)[:top_n]

    print(f"\n🔥 En yüksek normalize funding rate (funding_rate / interval) - Top {top_n}:")
    for r in sorted_results:
        print(f"{r['symbol']}: Funding Rate={r['funding_rate']:.5%}, Interval={r['interval_hours']:.2f} saat, "
              f"Normalized={r['normalized_rate']:.5%} / saat")

if __name__ == "__main__":
    asyncio.run(main())
