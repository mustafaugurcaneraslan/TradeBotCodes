import time
from datetime import datetime
import ta
import ta.trend
import numpy as np
from xconfig import BINANCE_API_KEY, BINANCE_SECRET_KEY
from binance.um_futures import UMFutures
import pandas as pd
from binance.error import ClientError
from pricepredict2 import analyze_and_predict_close
from pricepredict3 import analyze_and_predict

client = UMFutures(key=BINANCE_API_KEY, secret=BINANCE_SECRET_KEY)

volume = 30
leverage = 20
symbol = "MUBARAKUSDT"

def get_balance_usdt():
    try:
        response = client.balance(recvWindow=6000)
        for elem in response:
            if elem['asset'] == 'USDT':
                return elem['balance']
        print(response)
    except ClientError as error:
        print("Found error. status: {}, error code: {}, error message: {}".format(
            error.status_code, error.error_code, error.error_message
        ))

balance =  get_balance_usdt()
print("Balance: ", get_balance_usdt(), "USDT")

volume = 50

def klines(symbol, interval):
    try:
        resp = pd.DataFrame(client.klines(symbol, interval))
        resp = resp.iloc[:, :6]
        resp.columns = ['open_time', 'open', 'high', 'low', 'close', 'volume']
        resp = resp.set_index('open_time')
        resp.index = pd.to_datetime(resp.index, unit='ms')
        resp = resp.astype(float)
        return resp
    except ClientError as error:
        print("Found error. status: {}, error code: {}, error message: {}".format(
            error.status_code, error.error_code, error.error_message
        ))

def calculate_signal(symbol, interval='1m'):
    df = klines(symbol, interval)
    
    # Bollinger Bandı
    df['bb_percent_b'] = ta.volatility.BollingerBands(df['close']).bollinger_pband()

    # Hull MA hesaplaması
    hma_period = 180  # HMA için kullanılan periyot
    half_length = hma_period // 2
    sqrt_length = int(hma_period ** 0.5)

    # WMA hesaplama
    wma1 = ta.trend.WMAIndicator(df['close'], window=half_length).wma()
    wma2 = ta.trend.WMAIndicator(df['close'], window=hma_period).wma()

    # WMA farkını al
    wma_diff = 2 * wma1 - wma2

    # HMA'yı hesapla
    hma = ta.trend.WMAIndicator(wma_diff, window=sqrt_length).wma()

    # HMA'yı dataframe'e ekle
    df['hma'] = hma

    row = df.iloc[-1]
    prew = df.iloc[-2]
    print("BBpercent_b: ", row['bb_percent_b'] )

    # İşlem sinyalleri
    if row['bb_percent_b'] > 0 and prew['bb_percent_b'] < 0:
        return 'buy'
    elif row['bb_percent_b'] < 1 and prew['bb_percent_b'] > 1:
        return 'sell'
    
    return 'hold'


def get_price_precision(symbol):
    resp = client.exchange_info()['symbols']
    for elem in resp:
        if elem['symbol'] == symbol:
            return elem['pricePrecision']
        
def get_qty_precision(symbol):
    resp = client.exchange_info()['symbols']
    for elem in resp:
        if elem['symbol'] == symbol:
            return elem['quantityPrecision']
        

def open_order(symbol, side):
    close_open_orders(symbol)  # Mevcut emirleri kapat

    price = float(client.ticker_price(symbol)['price'])
    qty_precision = get_qty_precision(symbol)
    price_precision = get_price_precision(symbol)
    qty = round(volume / price, qty_precision)

    if side == 'buy':
        try:
            resp1 = client.new_order(
                symbol=symbol,
                side='BUY',
                type='LIMIT',
                quantity=qty,
                timeInForce='GTC',
                price=price
            )
            print(symbol, side, "placing order")
            print(resp1)
            time.sleep(2)
            
            # Stop Loss hesapla: %1.5 düşüş
            sl_price = round(price - price * sl_percentage, price_precision)
            resp2 = client.new_order(
                symbol=symbol,
                side='SELL',
                type='STOP_MARKET',
                timeInForce='GTE_GTC',
                quantity=qty,
                stopPrice=sl_price,
                reduceOnly=True
            )
            print("Stop Loss:", resp2)
            time.sleep(2)
            
            # Take Profit hesapla: %2 artış
            tp_price = round(price + price * tp_percentage, price_precision)
            resp3 = client.new_order(
                symbol=symbol,
                side='SELL',
                type='TAKE_PROFIT_MARKET',
                timeInForce='GTE_GTC',
                quantity=qty,
                stopPrice=tp_price,
                reduceOnly=True
            )
            print("Take Profit:", resp3)

        except ClientError as error:
            print(
                "Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )

    elif side == 'sell':
        try:
            resp1 = client.new_order(
                symbol=symbol,
                side='SELL',
                type='LIMIT',
                quantity=qty,
                timeInForce='GTC',
                price=price
            )
            print(symbol, side, "placing order")
            print(resp1)
            time.sleep(2)

            # Stop Loss hesapla: %1.5 artış
            sl_price = round(price + price * sl_percentage, price_precision)
            resp2 = client.new_order(
                symbol=symbol,
                side='BUY',
                type='STOP_MARKET',
                timeInForce='GTE_GTC',
                quantity=qty, 
                stopPrice=sl_price,
                reduceOnly=True
            )
            print("Stop Loss:", resp2)
            time.sleep(2)

            # Take Profit hesapla: %2 düşüş
            tp_price = round(price - price * tp_percentage, price_precision)
            resp3 = client.new_order(
                symbol=symbol,
                side='BUY',
                type='TAKE_PROFIT_MARKET',
                timeInForce='GTE_GTC',
                quantity=qty,
                stopPrice=tp_price,
                reduceOnly=True
            )
            print("Take Profit:", resp3)

        except ClientError as error:
            print(
                "Found error. status: {}, error code:  {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )

def get_current_price(symbol):
    try:
        response = client.ticker_price(symbol=symbol)
        return float(response['price'])
    except ClientError as error:
        print(f"Error fetching current price. Status: {error.status_code}, Error code: {error.error_code}, Message: {error.error_message}")
        return None

def check_positions():
    try:
        resp = client.get_position_risk()
        positions = []
        for elem in resp:
            if float(elem['positionAmt']) != 0:
                positions.append(elem['symbol'])
                return positions, elem['positionAmt']
        return positions, 0
    except ClientError as error:
        print("Found error. status: {}, error code: {}, error message: {}".format(
            error.status_code, error.error_code, error.error_message
        ))

def close_open_orders(symbol):
    try:
        client.cancel_open_orders(symbol=symbol, recvWindow=2000)
    except ClientError as error:
        print("Found error. status: {}, error code: {}, error message: {}".format(
            error.status_code, error.error_code, error.error_message
        ))
def log_position(symbol, price, up1, down1, up3, down3):
    with open("positions_log.txt", "a") as file:
        file.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {symbol} | Price: {price} | Up1: {up1} | Down1: {down1} | Up3: {up3} | Down3: {down3} | Balance: {balance}\n")


#main-----------------------------------------------------------------------------------------------------------------------

avoid_long = False
avoid_short = False

positions,position_side = check_positions()
position_side = float(position_side)
current_positions = len(positions)
fiyat = get_current_price(symbol)

print(f"You have {current_positions} active positions: {positions}")
print("Position AMT: ", position_side)
print(f"Fiyat: {fiyat}" )
signal = calculate_signal(symbol, interval="1m")

#up1, down1 = analyze_and_predict(symbol, interval="30m")
#up3,down3 = analyze_and_predict(symbol, interval="2h")
#print("Up Down 30m: ", up1,down1)
#print("Up Down 2h:  ", up3, down3)

prediction = analyze_and_predict_close(symbol, interval="1h")
print("Prediction: ", prediction)
tp_percentage = 0.02  # %2
sl_percentage = 0.015  # %1.5    

if current_positions == 0:
    
    if signal == "buy" and not avoid_long:
        print("\033[32mFound BUY signal for", symbol, "\033[0m")
        #open_order(symbol, 'buy')
        #log_position(symbol, fiyat, up1, down1, up3, down3)
        time.sleep(10)
    elif signal == "sell" and not avoid_short:
        print("\033[31mFound SELL signal for", symbol, "\033[0m")
        #open_order(symbol, 'sell')
        #log_position(symbol, fiyat, up1, down1, up3, down3)
        time.sleep(10)


current_time = datetime.now().strftime("%H:%M:%S")
print(f'*********(Time: {current_time})***********')
