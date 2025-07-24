import asyncio
import aiohttp
from colorama import Fore, Style
from xconfig import BINANCE_API_KEY, BINANCE_SECRET_KEY

asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

BASE_URL = "https://fapi.binance.com"
intervals = ["15m", "30m", "1h"]

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

# Wick uzunluğu hesaplama
def get_wick_length(candle):
    o, c, h, l = float(candle[1]), float(candle[4]), float(candle[2]), float(candle[3])
    body = abs(o - c)
    wick_up = h - max(o, c)
    wick_down = min(o, c) - l
    return wick_up, wick_down, body

# Mumda wick'in uzunluğunun, gövdesinden büyük olmadığını kontrol et
def is_valid_wick(candle):
    wick_up, wick_down, body = get_wick_length(candle)
    return wick_up <= body and wick_down <= body

async def is_bullish_engulfing(candles):
    o1, c1 = float(candles[-2][1]), float(candles[-2][4])
    o2, c2 = float(candles[-1][1]), float(candles[-1][4])

    return (
        c1 < o1 and
        c2 > o2 and
        (c2 - o2) > (o1 - c1) and
        o2 < c1 and c2 > o1
    )

async def is_bearish_engulfing(candles):
    o1, c1 = float(candles[-2][1]), float(candles[-2][4])
    o2, c2 = float(candles[-1][1]), float(candles[-1][4])

    return (
        c1 > o1 and
        c2 < o2 and
        (o1 - c1) > (c2 - o2) and
        o2 > c1 and c2 < o1
    )

async def is_morning_star(candles):
    o1, c1 = float(candles[-3][1]), float(candles[-3][4])
    o2, c2 = float(candles[-2][1]), float(candles[-2][4])
    o3, c3 = float(candles[-1][1]), float(candles[-1][4])

    return (
        c1 < o1 and  # 1. mum düşüş
        abs(o2 - c2) < (0.1 * (float(candles[-2][2]) - float(candles[-2][3]))) and  # 2. mum küçük
        c3 > o3 and  # 3. mum yükseliş
        c3 > c2  # 3. mum 2. mumun üstünde kapanıyor
    )

async def is_evening_star(candles):
    o1, c1 = float(candles[-3][1]), float(candles[-3][4])
    o2, c2 = float(candles[-2][1]), float(candles[-2][4])
    o3, c3 = float(candles[-1][1]), float(candles[-1][4])

    return (
        c1 > o1 and  # 1. mum yükseliş
        abs(o2 - c2) < (0.1 * (float(candles[-2][2]) - float(candles[-2][3]))) and  # 2. mum küçük
        c3 < o3 and  # 3. mum düşüş
        c3 < c2  # 3. mum 2. mumun altında kapanıyor
    )

async def is_custom_three_bearish_pattern(candles):
    o1, c1 = float(candles[-3][1]), float(candles[-3][4])  # 1. mum
    o2, c2 = float(candles[-2][1]), float(candles[-2][4])  # 2. mum
    o3, c3 = float(candles[-1][1]), float(candles[-1][4])  # 3. mum

    # Mumların wick'lerini kontrol et
    if not is_valid_wick(candles[-3]) or not is_valid_wick(candles[-2]) or not is_valid_wick(candles[-1]):
        return False

    return (
        c1 > o1 and         # 1. mum kırmızı (yani düşüş)
        c2 < o2 and         # 2. mum kırmızı değil
        c2 < o1 and         # 2. mumun kapanışı 1. mumun açılışının altında
        c3 > o3 and         # 3. mum yeşil
        c3 < o2             # 3. mumun kapanışı 2. mumun açılışının altında
    )

async def is_custom_three_bullish_pattern(candles):
    o1, c1 = float(candles[-3][1]), float(candles[-3][4])
    o2, c2 = float(candles[-2][1]), float(candles[-2][4])
    o3, c3 = float(candles[-1][1]), float(candles[-1][4])

    # Mumların wick'lerini kontrol et
    if not is_valid_wick(candles[-3]) or not is_valid_wick(candles[-2]) or not is_valid_wick(candles[-1]):
        return False

    return (
        c1 < o1 and         # 1. mum kırmızı
        c2 > o2 and         # 2. mum yeşil
        c2 > o1 and         # 2. mumun kapanışı 1. mumun açılışının üstünde
        c3 > o3 and         # 3. mum yeşil
        c3 > o2             # 3. mumun kapanışı 2. mumun açılışının üstünde
    )

async def is_not_highest_in_100(candles100, candles6):
    high_100 = max(float(c[2]) for c in candles100)
    high_6 = max(float(c[2]) for c in candles6)
    return high_6 < high_100

async def get_high_volume_symbols(session, min_volume=100_000_000):
    url = f"{BASE_URL}/fapi/v1/ticker/24hr"
    tickers = await fetch(session, url)
    if tickers is None:
        return []
    return [
        t['symbol'] for t in tickers
        if t['symbol'].endswith("USDT") and float(t['quoteVolume']) >= min_volume
    ]

async def check_symbol(session, symbol, interval):
    if symbol in blacklist:
        return None

    url = f"{BASE_URL}/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": 100}
    try:
        candles100 = await fetch(session, url, params)
        if candles100 is None or len(candles100) < 100:
            return None

        candles6 = candles100[-6:]
        candles2 = candles100[-2:]
        candles3 = candles100[-3:]

        result_messages = []

        if await is_not_highest_in_100(candles100, candles6):
            bullish_engulf = await is_bullish_engulfing(candles2)
            bearish_engulf = await is_bearish_engulfing(candles2)
            custom_bearish = await is_custom_three_bearish_pattern(candles3)
            custom_bullish = await is_custom_three_bullish_pattern(candles3)
            morning_star = await is_morning_star(candles3)
            evening_star = await is_evening_star(candles3)

            #if bullish_engulf:
            #    result_messages.append((symbol, "Bullish Engulfing", "bullish", interval))
            #if bearish_engulf:
            #    result_messages.append((symbol, "Bearish Engulfing", "bearish", interval))
            if custom_bearish:
                result_messages.append((symbol, "Custom 3 Candle Bearish", "bearish", interval))
            if custom_bullish:
                result_messages.append((symbol, "Custom 3 Candle Bullish", "bullish", interval))
            if morning_star:
                result_messages.append((symbol, "Morning Star", "bullish", interval))
            if evening_star:
                result_messages.append((symbol, "Evening Star", "bearish", interval))

        return result_messages if result_messages else None

    except Exception as e:
        print(f"⚠️ {symbol} ({interval}) - {e}")
        return None

async def check_all_symbols():
    matches = {interval: [] for interval in intervals}
    async with aiohttp.ClientSession() as session:
        symbols = await get_high_volume_symbols(session)

        print(f"{len(symbols)} sembol günlük hacmi 100M USDT üstünde, kontrol ediliyor...\n")

        for interval in intervals:
            print(f"\n⏱️ {interval} zaman dilimi kontrol ediliyor...\n")
            tasks = [check_symbol(session, symbol, interval) for symbol in symbols]
            results = await asyncio.gather(*tasks)

            for res in results:
                if res:
                    matches[interval].extend(res)

    return matches

async def main():
    all_matches = await check_all_symbols()

    print("\n📈 POTANSİYEL COİNLER 📉")
    for interval, symbols in all_matches.items():
        print(f"\n⏰ {interval} zaman dilimi:")
        if symbols:
            for sym, pattern_name, pattern_type, _ in symbols:
                if pattern_type == "bullish":
                    print(f"{Fore.GREEN}- {sym} - {pattern_name}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}- {sym} - {pattern_name}{Style.RESET_ALL}")
        else:
            print("Hiçbir coin bu formasyona uymuyor.")

if __name__ == "__main__":
    asyncio.run(main())
