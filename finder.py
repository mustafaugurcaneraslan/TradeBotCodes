from helper import Binance
from keys import api, secret
import ta
import pandas as pd
from time import sleep

session = Binance(api, secret)


def bol(symbol, period=20, dev=2):
    kl = session.klines(symbol, '1m')
    bol_h = ta.volatility.BollingerBands(kl.Close, period, dev).bollinger_hband()
    bol_l = ta.volatility.BollingerBands(kl.Close, period, dev).bollinger_lband()
    if kl.Close.iloc[-2] > bol_h.iloc[-2] and kl.Close.iloc[-1] < bol_h.iloc[-1]:
        return 'sell'
    if kl.Close.iloc[-2] < bol_l.iloc[-2] and kl.Close.iloc[-1] > bol_l.iloc[-1]:
        return 'buy'


qty = 10
leverage = 10
mode = 'ISOLATED'
max_pos = 10
# symbols = session.get_tickers_usdt()
symbol = 'LAUSDT'


balance = session.get_balance_usdt()
qty = balance * 1

while True:
    try:
        balance = session.get_balance_usdt()
        qty = balance * leverage * 0.1
        print(f'Balance: {round(balance, 3)} USDT')
        positions = session.get_positions()
        orders = session.check_orders()
        print(f'{len(positions)} Positions: {positions}')

        sign = bol(symbol, period=20, dev=2)
        if sign is not None and len(positions) == 0:
            print(symbol, sign)
            session.open_order_market_nostops(symbol, sign, qty, leverage, mode)
            sleep(1)

        if sign is not None and 1 <= len(positions) <= 10:
            side = session.get_position_side(symbol)
            sleep(1)
            if side == 'BUY' and sign == 'sell':
                print(symbol, sign)
                qty = session.get_position_size_usdt(symbol)
                sleep(1)
                session.open_order_market_nostops(symbol, 'sell', qty, leverage, mode)
                sleep(1)
                balance = session.get_balance_usdt()
                qty = balance * leverage * 0.1
                session.open_order_market_nostops(symbol, sign, qty, leverage, mode)
            if side == 'BUY' and sign == 'buy':
                print(symbol, 'one more order:', sign)
                sleep(1)
                balance = session.get_balance_usdt()
                qty = balance * leverage * 0.1
                session.open_order_market_nostops(symbol, sign, qty, leverage, mode)
            sleep(1)
            if side == 'SELL' and sign == 'buy':
                print(symbol, sign)
                qty = session.get_position_size_usdt(symbol)
                sleep(1)
                session.open_order_market_nostops(symbol, 'buy', qty, leverage, mode)
                sleep(1)
                balance = session.get_balance_usdt()
                qty = balance * leverage * 0.1
                session.open_order_market_nostops(symbol, sign, qty, leverage, mode)
            if side == 'SELL' and sign == 'sell':
                print(symbol, 'one more order:', sign)
                sleep(1)
                balance = session.get_balance_usdt()
                qty = balance * leverage * 0.1
                session.open_order_market_nostops(symbol, sign, qty, leverage, mode)

        wait = 40
        print(f'Waiting {wait} sec')
        sleep(wait)

    except Exception as err:
        print(err)
        sleep(30)