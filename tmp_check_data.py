import sys, os
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()
import MetaTrader5 as mt5
from datetime import datetime, timezone
import pandas as pd

# Dùng env credentials để test
login = int(os.getenv('MT5_LOGIN') or 0)
password = os.getenv('MT5_PASSWORD')
server = os.getenv('MT5_SERVER')
print(f"Env creds: login={login}, server={server}")

print("Initializing MT5...")
if not mt5.initialize():
    print("initialize failed:", mt5.last_error())
    exit(1)

ok = mt5.login(login=login, password=password, server=server)
if not ok:
    print("login failed:", mt5.last_error())
    mt5.shutdown()
    exit(1)

info = mt5.account_info()
print(f"Logged in: {info.name}, server={info.server}")

symbol = 'XAUUSDm'
mt5.symbol_select(symbol, True)

print("\nFetching max M1 candles (up to 1M)...")
r = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 1_000_000)
if r is not None and len(r) > 0:
    df = pd.DataFrame(r)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    print(f"Total M1: {len(df)} candles")
    print(f"Oldest:   {df['time'].min()}")
    print(f"Newest:   {df['time'].max()}")
else:
    print("M1 no data:", mt5.last_error())

print("\nFetching D1...")
r2 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 10_000)
if r2 is not None and len(r2) > 0:
    df2 = pd.DataFrame(r2)
    df2['time'] = pd.to_datetime(df2['time'], unit='s')
    print(f"Total D1: {len(df2)} candles, oldest={df2['time'].min().date()}, newest={df2['time'].max().date()}")
else:
    print("D1 no data:", mt5.last_error())

mt5.shutdown()
