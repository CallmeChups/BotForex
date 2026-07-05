import sys, os, pandas as pd
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()
import MetaTrader5 as mt5

login = 415929088
password = "Hang1970@"
server = "Exness-MT5Trial14"
print(f"Trying: login={login}, server={server}")

if not mt5.initialize():
    print("initialize failed:", mt5.last_error())
    sys.exit(1)

ok = mt5.login(login=login, password=password, server=server)
if not ok:
    print("login failed:", mt5.last_error())
    mt5.shutdown()
    sys.exit(1)

info = mt5.account_info()
print(f"Logged in: {info.name}, server={info.server}")

symbol = "XAUUSDm"
mt5.symbol_select(symbol, True)

print("Fetching M1 (up to 1M candles)...")
r = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 1_000_000)
if r is not None and len(r) > 0:
    df = pd.DataFrame(r)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    oldest = df["time"].min()
    newest = df["time"].max()
    print(f"Total M1: {len(df)} candles")
    print(f"Oldest:   {oldest}")
    print(f"Newest:   {newest}")
else:
    print("M1 no data:", mt5.last_error())

print("\nFetching M5 (up to 500k candles)...")
r5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 500_000)
if r5 is not None and len(r5) > 0:
    df5 = pd.DataFrame(r5)
    df5["time"] = pd.to_datetime(df5["time"], unit="s")
    print(f"Total M5: {len(df5)} candles")
    print(f"Oldest:   {df5['time'].min()}")
    print(f"Newest:   {df5['time'].max()}")
else:
    print("M5 no data:", mt5.last_error())

print("\nFetching D1...")
r2 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 10_000)
if r2 is not None and len(r2) > 0:
    df2 = pd.DataFrame(r2)
    df2["time"] = pd.to_datetime(df2["time"], unit="s")
    oldest2 = df2["time"].min().date()
    newest2 = df2["time"].max().date()
    print(f"Total D1: {len(df2)} candles, oldest={oldest2}, newest={newest2}")
else:
    print("D1 no data:", mt5.last_error())

mt5.shutdown()
