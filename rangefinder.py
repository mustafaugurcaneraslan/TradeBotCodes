import asyncio
import aiohttp
import pandas as pd
import ta
import time
import sys

if sys.platform.startswith('win') and sys.version_info >= (3, 8):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

BASE_URL = 'https://api.binance.com'

HEADERS = {
    'Accepts': 'application/json',
    'User-Agent': 'binance-ranger'
}

async def fetch_usdt_symbols():
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(f'{BASE_URL}/api/v3/exchangeInfo') as resp:
            data = await resp.json()
            symbols = [
                s['symbol'] for s in data['symbols']
                if s['quoteAsset'] == 'USDT' and s['status'] == 'TRADING'
                and 'UP' not in s['symbol'] and 'DOWN' not in s['symbol'] and 'BULL' not in s['symbol']
            ]
            return symbols

async def fetch_klines(session, symbol, interval='1h', limit=100):
    url = f'{BASE_URL}/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}'
    try:
        async with session.get(url) as resp:
            data = await resp.json()
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            df['close'] = df['close'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            return symbol, df
    except:
        return symbol, None

def is_ranging(df):
    try:
        bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
        width = bb.bollinger_hband() - bb.bollinger_lband()
        width_mean = width.rolling(20).mean()

        rsi = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
        recent_rsi = rsi.iloc[-1]

        bb_condition = width.iloc[-1] < width_mean.iloc[-1] * 0.7
        rsi_condition = 45 < recent_rsi < 55

        return bb_condition and rsi_condition
    except:
        return False

async def check_symbol(session, symbol):
    symbol, df = await fetch_klines(session, symbol)
    if df is not None and len(df) >= 30:
        if is_ranging(df):
            print(f"✅ Ranging: {symbol}")
            return symbol
    print(f"❌ Not Ranging: {symbol}")
    return None

async def main():
    start = time.time()
    symbols = await fetch_usdt_symbols()
    print(f"Toplam {len(symbols)} USDT paritesi taranacak...\n")

    results = []
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        tasks = [check_symbol(session, symbol) for symbol in symbols]
        ranged = await asyncio.gather(*tasks)
        results = [s for s in ranged if s]

    print("\n🔍 Ranging Marketler:")
    for s in results:
        print(f"➡️  {s}")

    print(f"\n⏱️ Tarama süresi: {round(time.time() - start, 2)} saniye")

if __name__ == "__main__":
    asyncio.run(main())
