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
# Real
# account = 126787238
# password = "Taptrade0412@"
# server = "Exness-MT5Real7"

# Demo
account = 415016785
password = "Taptrade211225@"
server = "Exness-MT5Trial14"

mt5.initialize()
ic(mt5.initialize())
authorized = mt5.login(login=account, password=password, server=server)
ic(authorized)
ic(mt5.account_info()._asdict()['leverage'])
ic(mt5.account_info()._asdict()['balance'])


######################################## %%%%% DEFINE VARIABLE %%%%% ########################################

SYMBOL = "BTCUSDm"
TRADE_FRAME = mt5.TIMEFRAME_M1
timezone = ZoneInfo("Asia/Ho_Chi_Minh")

n = 2

######################################## %%%%% GET DATA %%%%% ########################################

date_to = datetime.now(tz=timezone)
date_from = date_to - timedelta(weeks=1)
short_data = pd.DataFrame(mt5.copy_rates_range(SYMBOL, TRADE_FRAME, date_from, date_to))

# Thêm cột real_time và chuyển đổi timestamp sang thời gian thực tế
short_data['real_time'] = pd.to_datetime(short_data['time'], unit='s').dt.tz_localize('UTC').dt.tz_convert(timezone)

# Định dạng cột real_time (tùy chọn, nếu muốn hiển thị dạng cụ thể như YYYY-MM-DD HH:MM:SS)
short_data['real_time'] = short_data['real_time'].dt.strftime('%Y-%m-%d %H:%M:%S')

print("short_data /n",short_data)