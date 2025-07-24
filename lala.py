import pandas as pd
from ta import trend, momentum, volatility, volume
from binance.um_futures import UMFutures
from xconfig import BINANCE_API_KEY, BINANCE_SECRET_KEY
from rich.console import Console
from rich.table import Table
from rich.columns import Columns

client = UMFutures(key=BINANCE_API_KEY, secret=BINANCE_SECRET_KEY)

def get_ohlcv(symbol, interval, limit=200):
    klines = client.klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time',
        'quote_asset_volume', 'num_trades', 'taker_base_volume',
        'taker_quote_volume', 'ignore'
    ])
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].astype(float)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def compute_indicators(df):
    results = {}
    close = df['close']
    high = df['high']
    low = df['low']
    volume_ = df['volume']

    results['SMA20'] = close.iloc[-1] > close.rolling(20).mean().iloc[-1]
    results['EMA20'] = close.iloc[-1] > close.ewm(span=20).mean().iloc[-1]

    macd = trend.MACD(close)
    results['MACD'] = macd.macd_diff().iloc[-1] > 0

    try:
        st = trend.stc(close)
        results['STC'] = st.iloc[-1] > 50
    except:
        results['STC'] = False

    results['RSI'] = momentum.RSIIndicator(close).rsi().iloc[-1] > 50
    results['Stochastic'] = momentum.StochasticOscillator(high, low, close).stoch().iloc[-1] > 50
    results['CCI'] = trend.CCIIndicator(high, low, close).cci().iloc[-1] > 0
    results['WilliamsR'] = momentum.WilliamsRIndicator(high, low, close).williams_r().iloc[-1] > -50

    bb = volatility.BollingerBands(close)
    results['Bollinger %B'] = bb.bollinger_pband().iloc[-1] > 0.5

    atr = volatility.AverageTrueRange(high, low, close).average_true_range()
    std_dev = close.pct_change().rolling(14).std()
    results['ATR'] = atr.iloc[-1] > std_dev.iloc[-1]

    dc = volatility.DonchianChannel(high, low, close)
    mid = (dc.donchian_channel_hband() + dc.donchian_channel_lband()) / 2
    results['Donchian'] = close.iloc[-1] > mid.iloc[-1]

    obv = volume.OnBalanceVolumeIndicator(close, volume_).on_balance_volume()

    # OBV'nin 50 periyotluk EMA'sını hesapla
    obv_ema_50 = obv.ewm(span=50).mean()

    # OBV'nin son değeri ile 50 EMA'nın son değerini karşılaştır
    results['OBV'] = obv.iloc[-1] > obv_ema_50.iloc[-1]
    results['MFI'] = volume.MFIIndicator(high, low, close, volume_).money_flow_index().iloc[-1] > 50

    kijun = high.rolling(26).max().add(low.rolling(26).min()).div(2)
    results['KijunSen'] = close.iloc[-1] > kijun.iloc[-1]

    results['ROC'] = momentum.ROCIndicator(close).roc().iloc[-1] > 0
    results['ParabolicSAR'] = trend.PSARIndicator(high, low, close).psar().iloc[-1] < close.iloc[-1]
    results['TSI'] = momentum.TSIIndicator(close).tsi().iloc[-1] > 0
    results['ADX'] = trend.ADXIndicator(high, low, close).adx().iloc[-1] > 20

    return results

def create_table(results, tf):
    table = Table(title=f"[bold yellow]{tf}[/bold yellow]", expand=True)
    table.add_column("İndikatör", style="cyan", no_wrap=True)
    table.add_column("Sinyal", justify="center")

    for name, result in results.items():
        if name != 'ADX':
            emoji = "✅" if result else "❌"
        else:
            emoji='Trend' if result else 'Not Trend'
        color = "green" if result else "red"
        table.add_row(name, f"[{color}]{emoji}[/{color}]")

    return table

def analyze_multiple(symbol, timeframes):
    console = Console()
    tables = []

    for tf in timeframes:
        try:
            df = get_ohlcv(symbol, tf)
            results = compute_indicators(df)
            table = create_table(results, tf)
            tables.append(table)
        except Exception as e:
            error_table = Table(title=f"{tf} HATA", expand=True)
            error_table.add_column("Hata", justify="center", style="red")
            error_table.add_row(str(e))
            tables.append(error_table)

    console.print(Columns(tables))

if __name__ == "__main__":
    timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]
    analyze_multiple("XRPUSDT", timeframes)
