"""
Debug script: tìm trades bị ghi TP/SL nhưng fill candle không thực sự chạm entry_price.
Chạy: python test/debug_backtest_fill.py
"""
import sys
sys.path.insert(0, '.')

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from src.backtest import fetch_historical_data
from src.utils import get_pip_value, get_point_value
from dotenv import load_dotenv

load_dotenv()
TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")

# ── CONFIG — chỉnh theo đúng params bạn đang test ──
SYMBOL = "XAUUSD"
TIMEFRAME = "M5"
ENTRY_HOUR = 21
ENTRY_MINUTE = 5
ENTRY_PERCENT = 30.0   # % của body
BUFFER_K = 5.0
RR_RATIO = 2.0
EXPIRE_CANDLES = 0

from src.auth import load_config, get_user_mt5_credentials
config = load_config()
credentials = None
if config:
    for uname in config['credentials']['usernames']:
        creds = get_user_mt5_credentials(uname)
        if creds.get('login'):
            credentials = creds
            print(f"Using credentials of user: {uname}")
            break

if not credentials:
    print("No MT5 credentials found. Edit this script to provide credentials manually.")
    sys.exit(1)

end_dt = datetime.now(TIMEZONE)
start_dt = end_dt - timedelta(days=30)

print(f"Fetching {SYMBOL} {TIMEFRAME} from {start_dt.date()} to {end_dt.date()}...")
df, error = fetch_historical_data(SYMBOL, start_dt, end_dt, credentials, TIMEFRAME)
if error:
    print(f"Error: {error}")
    sys.exit(1)
print(f"Fetched {len(df)} candles")

pip_value = get_pip_value(SYMBOL)
point_value = get_point_value(SYMBOL)

df['date'] = df['time'].dt.date
df['hour'] = df['time'].dt.hour
df['minute'] = df['time'].dt.minute
entry_candles = df[(df['hour'] == ENTRY_HOUR) & (df['minute'] == ENTRY_MINUTE)]

print(f"\nChecking {len(entry_candles)} entry candles...\n")

problems_found = 0

for idx, entry_row in entry_candles.iterrows():
    entry_time = entry_row['time']
    o, h, l, c = entry_row['open'], entry_row['high'], entry_row['low'], entry_row['close']
    candle_body = abs(c - o)

    if c > o:
        direction = "BUY"
        entry_price = c - (ENTRY_PERCENT / 100) * candle_body
        stop_loss = l - BUFFER_K * point_value
        risk = entry_price - stop_loss
        take_profit = entry_price + risk * RR_RATIO
    elif c < o:
        direction = "SELL"
        entry_price = c + (ENTRY_PERCENT / 100) * candle_body
        stop_loss = h + BUFFER_K * point_value
        risk = stop_loss - entry_price
        take_profit = entry_price - risk * RR_RATIO
    else:
        continue

    entry_idx = df.index.get_loc(idx)
    pending_candles = df.iloc[entry_idx + 1:]

    for check_idx, check_candle in pending_candles.iterrows():
        ck_open = check_candle['open']
        ck_high = check_candle['high']
        ck_low = check_candle['low']

        if direction == "BUY":
            fill_condition = ck_low <= entry_price
            # Bug scenario: open already below entry (gap down), fill at open not at entry_price
            gap_down_fill = ck_open < entry_price
            # Bug scenario 2: fill candle also hits TP (same candle)
            tp_on_fill_candle = fill_condition and (ck_high >= take_profit)

            if fill_condition:
                if gap_down_fill:
                    print(f"[GAP-DOWN FILL] {entry_time.strftime('%Y-%m-%d %H:%M')} {direction}")
                    print(f"  Entry candle: O={o:.2f} H={h:.2f} L={l:.2f} C={c:.2f}")
                    print(f"  LIMIT entry_price={entry_price:.2f}, SL={stop_loss:.2f}, TP={take_profit:.2f}")
                    print(f"  Fill candle: O={ck_open:.2f} H={ck_high:.2f} L={ck_low:.2f}")
                    print(f"  → Fill would be at OPEN={ck_open:.2f} (gap below entry_price={entry_price:.2f})")
                    if tp_on_fill_candle:
                        print(f"  → TP HIT ON SAME CANDLE! high={ck_high:.2f} >= TP={take_profit:.2f}")
                    problems_found += 1
                elif tp_on_fill_candle:
                    print(f"[TP ON FILL CANDLE] {entry_time.strftime('%Y-%m-%d %H:%M')} {direction}")
                    print(f"  Entry candle: C={c:.2f}, entry_price={entry_price:.2f}, TP={take_profit:.2f}")
                    print(f"  Fill candle: O={ck_open:.2f} H={ck_high:.2f} L={ck_low:.2f}")
                    print(f"  → Touched entry ({ck_low:.2f} <= {entry_price:.2f}) AND TP ({ck_high:.2f} >= {take_profit:.2f}) same candle")
                    problems_found += 1
                break

        else:  # SELL
            fill_condition = ck_high >= entry_price
            gap_up_fill = ck_open > entry_price
            tp_on_fill_candle = fill_condition and (ck_low <= take_profit)

            if fill_condition:
                if gap_up_fill:
                    print(f"[GAP-UP FILL] {entry_time.strftime('%Y-%m-%d %H:%M')} {direction}")
                    print(f"  Entry candle: O={o:.2f} H={h:.2f} L={l:.2f} C={c:.2f}")
                    print(f"  LIMIT entry_price={entry_price:.2f}, SL={stop_loss:.2f}, TP={take_profit:.2f}")
                    print(f"  Fill candle: O={ck_open:.2f} H={ck_high:.2f} L={ck_low:.2f}")
                    print(f"  → Fill would be at OPEN={ck_open:.2f} (gap above entry_price={entry_price:.2f})")
                    if tp_on_fill_candle:
                        print(f"  → TP HIT ON SAME CANDLE! low={ck_low:.2f} <= TP={take_profit:.2f}")
                    problems_found += 1
                elif tp_on_fill_candle:
                    print(f"[TP ON FILL CANDLE] {entry_time.strftime('%Y-%m-%d %H:%M')} {direction}")
                    print(f"  Entry candle: C={c:.2f}, entry_price={entry_price:.2f}, TP={take_profit:.2f}")
                    print(f"  Fill candle: O={ck_open:.2f} H={ck_high:.2f} L={ck_low:.2f}")
                    print(f"  → Touched entry AND TP same candle")
                    problems_found += 1
                break

print(f"\n{'='*50}")
print(f"Total suspicious trades found: {problems_found}")
print(f"Total entry candles checked: {len(entry_candles)}")
