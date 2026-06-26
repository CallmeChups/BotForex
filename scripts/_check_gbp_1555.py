import sys, yaml
from datetime import datetime
from zoneinfo import ZoneInfo
sys.path.insert(0, '.')
from src.bot_runner import get_mt5_connection
import pandas as pd

with open('config/auth.yaml') as f:
    cfg = yaml.safe_load(f)
creds = cfg['credentials']['usernames']['admin']['mt5']
mt5, err = get_mt5_connection(creds)
if err:
    print('ERROR:', err); sys.exit(1)

TZ = ZoneInfo('Asia/Ho_Chi_Minh')

rates = mt5.copy_rates_from_pos('GBPUSDm', mt5.TIMEFRAME_M5, 0, 32)
mt5.shutdown()

if rates is None:
    print('ERROR: no data for GBPUSDm'); sys.exit(1)

df = pd.DataFrame(rates)
df['dt'] = df['time'].apply(lambda t: datetime.fromtimestamp(int(t), tz=TZ))
ema = df['close'].ewm(span=21, adjust=False).mean()

print('Last 10 M5 candles (GBPUSDm):')
print(f"{'Time':<18} {'O':>8} {'H':>8} {'L':>8} {'C':>8} {'EMA21':>8}")
print('-' * 62)
for i in df.index[-10:]:
    row = df.loc[i]
    e = ema.loc[i]
    t = row['dt'].strftime('%H:%M')
    mark = ' <<' if t in ('15:50', '15:55') else ''
    print(f"{row['dt'].strftime('%Y-%m-%d %H:%M'):<18} {row['open']:>8.5f} {row['high']:>8.5f} {row['low']:>8.5f} {row['close']:>8.5f} {e:>8.5f}{mark}")

print()

# Find 15:50 and 15:55 candles
idx50 = next((i for i in df.index if df.loc[i,'dt'].strftime('%H:%M') == '15:50'), None)
idx55 = next((i for i in df.index if df.loc[i,'dt'].strftime('%H:%M') == '15:55'), None)

if idx55 is None or idx50 is None:
    times = [df.loc[i,'dt'].strftime('%H:%M') for i in df.index[-12:]]
    print(f'Khong tim thay nen 15:50/15:55. Times co trong data: {times}')
    sys.exit(0)

c1 = df.loc[idx50]
c2 = df.loc[idx55]
e2 = ema.loc[idx55]

print('--- FEG check: C1=15:50, C2=15:55 ---')
print(f"C1 (15:50): H={c1['high']:.5f}  L={c1['low']:.5f}  C={c1['close']:.5f}")
print(f"C2 (15:55): H={c2['high']:.5f}  L={c2['low']:.5f}  C={c2['close']:.5f}")
print(f"EMA21     : {e2:.5f}")
print()

s1 = c2['high'] > c1['high']
s2 = c2['close'] < c1['low']
s3 = c2['low'] > e2
print(f"SELL: H2({c2['high']:.5f})>H1({c1['high']:.5f}) = {'[ok]' if s1 else '[!!]'}")
print(f"      C2({c2['close']:.5f})<L1({c1['low']:.5f}) = {'[ok]' if s2 else '[!!]'}")
print(f"      L2({c2['low']:.5f})>EMA({e2:.5f}) = {'[ok]' if s3 else '[!!]'}")
print(f"  -> SELL: {'YES *** SIGNAL ***' if (s1 and s2 and s3) else 'NO'}")
print()

b1 = c2['low'] < c1['low']
b2 = c2['close'] > c1['high']
b3 = c2['high'] < e2
print(f"BUY:  L2({c2['low']:.5f})<L1({c1['low']:.5f}) = {'[ok]' if b1 else '[!!]'}")
print(f"      C2({c2['close']:.5f})>H1({c1['high']:.5f}) = {'[ok]' if b2 else '[!!]'}")
print(f"      H2({c2['high']:.5f})<EMA({e2:.5f}) = {'[ok]' if b3 else '[!!]'}")
print(f"  -> BUY: {'YES *** SIGNAL ***' if (b1 and b2 and b3) else 'NO'}")
