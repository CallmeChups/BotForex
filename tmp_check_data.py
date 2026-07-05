from dotenv import load_dotenv
import os
load_dotenv()
import MetaTrader5 as mt5
from datetime import datetime, timezone
import pandas as pd
import time

login = int(os.getenv('MT5_LOGIN') or 0)
password = os.getenv('MT5_PASSWORD')
server = os.getenv('MT5_SERVER')

print(f"Connecting to {server} as {login}...")
if not mt5.initialize():
    print("initialize failed:", mt5.last_error())
    exit(1)

ok = mt5.login(login=login, password=password, server=server)
if not ok:
    print("login failed:", mt5.last_error())
    mt5.shutdown()
    exit(1)

info = mt5.account_info()
print(f"Logged in: {info.name}, balance={info.balance}")

symbol = 'XAUUSDm'
tf = mt5.TIMEFRAME_M1

# Warmup — đảm bảo symbol được load
mt5.symbol_select(symbol, True)
time.sleep(1)

r = mt5.copy_rates_from_pos(symbol, tf, 0, 500_000)
if r is not None and len(r) > 0:
    df = pd.DataFrame(r)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    print(f"Total M1 candles: {len(df)}")
    print(f"Oldest: {df['time'].min()}")
    print(f"Newest: {df['time'].max()}")
else:
    print("No data:", mt5.last_error())

mt5.shutdown()
