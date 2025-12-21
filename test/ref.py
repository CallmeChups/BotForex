from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from src.calculation import (
    calculate_ma,
    calculate_stoch,
    calculate_macd,
    check_cross_2_list_updated,
)
from icecream import ic
import MetaTrader5 as mt5
import time
import numpy as np
import pandas as pd


######################################## %%%%% CONNECT WITH MT5 %%%%% ########################################

## Account Info ##
account = 243254313
password = "Test2312025@"
server = "Exness-MT5Trial14"

mt5.initialize()
print(mt5.initialize())
authorized = mt5.login(login=account, password=password, server=server)
print(authorized)

######################################## %%%%% DEFINE VARIABLE %%%%% ########################################
SYMBOL = "BTCUSDm"
LONG_TRADE_FRAME = mt5.TIMEFRAME_H4
MID_TRADE_FRAME = mt5.TIMEFRAME_M30
SHORT_TRADE_FRAME = mt5.TIMEFRAME_M5
STOP_LOSS, TAKE_PROFIT = 1.5, 1.5
LOT = 0.1 # lot = volume / 100
DEVIATION = 20

MA_LONG_PERIOD = 20
MA_SHORT_PERIOD = 10
FIRST_STOCH = [7,5,3]
SECOND_STOCH = [13,13,5]

timezone = ZoneInfo("Asia/Ho_Chi_Minh")
ma_long, ma_short = [], []
macd_line, signal_line = [], []
first_stoch, second_stoch = {}, {}

######################################## %%%%% GET DATA %%%%% ########################################
while True:
    ## Data
    date_to = datetime.now(tz=timezone)
    date_from = date_to - timedelta(weeks=1)
    # date_from = datetime(2024, 12, 20 ,tzinfo=timezone)
    # date_to = datetime(2024, 12, 23 ,tzinfo=timezone)

    long_data = pd.DataFrame(mt5.copy_rates_range(SYMBOL, LONG_TRADE_FRAME, date_from, date_to))
    mid_data = pd.DataFrame(mt5.copy_rates_range(SYMBOL, MID_TRADE_FRAME, date_from, date_to))
    short_data = pd.DataFrame(mt5.copy_rates_range(SYMBOL, SHORT_TRADE_FRAME, date_from, date_to))

    close_price_list = short_data['close'].tolist()
    # Convert 'time' to datetime
    # data["mt5_time"] = pd.to_datetime(data["time"], unit="s")
    # # Convert 'mt5_time' to Vietnam time zone
    # data["vn_time"] = (
    #     data["mt5_time"].dt.tz_localize("UTC").dt.tz_convert("Asia/Ho_Chi_Minh")
    # )
    # data["vn_time"] = data["vn_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
    # # Reorder columns to have 'mt5_time' at index [1] and 'vn_time' at index [2]
    # columns = data.columns.tolist()
    # columns.insert(1, columns.pop(columns.index("mt5_time")))
    # columns.insert(2, columns.pop(columns.index("vn_time")))
    # data = data[columns]
    # ic(data.tail())

    # Indicator
    first_stoch = calculate_stoch(mid_data, k_length=FIRST_STOCH[0], k_smooth=FIRST_STOCH[1], d_smooth=FIRST_STOCH[2])
    second_stoch = calculate_stoch(mid_data, k_length=SECOND_STOCH[0], k_smooth=SECOND_STOCH[1], d_smooth=SECOND_STOCH[2])
    macd_line, signal_line = calculate_macd(long_data)
    cross_macd_line_signal_line = check_cross_2_list_updated(macd_line, signal_line, period = 10, confirm = 1)
    ma_short = calculate_ma(short_data, period=MA_SHORT_PERIOD)
    ma_long = calculate_ma(short_data, period=MA_LONG_PERIOD)
    cross_close_price_ma_short = check_cross_2_list_updated(close_price_list, ma_short, period = 10, confirm = 1)
    cross_close_price_ma_long = check_cross_2_list_updated(close_price_list, ma_long, period = 10, confirm = 1)
                            ####### ENTRY LONG #######
    if (
        cross_macd_line_signal_line["up"]
        and first_stoch["k"][-1] < 20
        and second_stoch["k"][-1] < 50
        and cross_close_price_ma_short["up"]
        and cross_close_price_ma_long["up"] 
        ):
        print("Match Condition")
        # DEFINE REQUEST
        sell_price = mt5.symbol_info_tick(SYMBOL).bid
        buy_price = mt5.symbol_info_tick(SYMBOL).ask
        request = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': SYMBOL,
            'price': buy_price,
            'sl': buy_price*(1 - STOP_LOSS),
            'tp': buy_price*(1 + TAKE_PROFIT),
            'deviation': DEVIATION,
            'type': mt5.ORDER_TYPE_BUY,
            'volume': LOT,
            'type_time': mt5.ORDER_TIME_GTC,
            'type_filling': mt5.ORDER_FILLING_IOC,
            'comment': 'Py Buy Position'
        }
        authorized = mt5.login(login = account, password = password, server = server)
        print(authorized)
        result = mt5.order_send(request)
        if result._asdict()['order'] == 0:
            error = result._asdict()['comment']
            print(f'Fail to order due to {error}')
            dt_object = datetime.fromtimestamp(time.time())
            print("Time ", dt_object)
            continue        
           
        print('BUY SUCCESSFULLY')
        dt_object = datetime.fromtimestamp(time.time())
        print("Time ", dt_object)
        authorized = mt5.login(login = account, password = password, server = server)    

        break

                            ####### ENTRY SHORT #######
    elif (
        cross_macd_line_signal_line["down"]
        and first_stoch["k"][-1] > 80
        and second_stoch["k"][-1] > 50
        and cross_close_price_ma_short["low"]
        and cross_close_price_ma_long["low"] 
        ):
        print("Match Condition")
        # DEFINE REQUEST
        sell_price = mt5.symbol_info_tick(SYMBOL).bid
        buy_price = mt5.symbol_info_tick(SYMBOL).ask
        request = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': SYMBOL,
            'price': sell_price,
            'sl': sell_price*(1 + STOP_LOSS),
            'tp': sell_price*(1 - TAKE_PROFIT),
            'deviation': DEVIATION,
            'type': mt5.ORDER_TYPE_SELL,
            'volume': LOT,
            'type_time': mt5.ORDER_TIME_GTC,
            'type_filling': mt5.ORDER_FILLING_IOC,
            'comment': 'Py Sell Position'
        }
        authorized = mt5.login(login = account, password = password, server = server)
        print(authorized)
        result = mt5.order_send(request)
        if result._asdict()['order'] == 0:
            error = result._asdict()['comment']
            print(f'Fail to order due to {error}')
            dt_object = datetime.fromtimestamp(time.time())
            print("Time ", dt_object)
            continue        
           
        print('SELL SUCCESSFULLY')
        dt_object = datetime.fromtimestamp(time.time())
        print("Time ", dt_object)
        authorized = mt5.login(login = account, password = password, server = server)    

        break