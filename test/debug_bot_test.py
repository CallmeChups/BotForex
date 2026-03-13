"""
Debug bot execution - simulate order placement and monitoring
"""
import sys
sys.path.insert(0, 'D:\BotForex')

from datetime import datetime
from zoneinfo import ZoneInfo
from src.bot_runner import get_current_candle, get_mt5_connection
from src.auth import get_user_mt5_credentials
from src.utils import get_pip_value, check_exit

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")

print("=" * 60)
print("DEBUG BOT ORDER PLACEMENT & MONITORING")
print("=" * 60)

# Get credentials
credentials = get_user_mt5_credentials("user")
print(f"\nCredentials: {credentials.get('login')}")

# Connect to MT5
mt5, error = get_mt5_connection(credentials)
if error:
    print(f"ERROR: {error}")
    sys.exit(1)

print("✅ Connected to MT5")

# Simulate SELL order like in user's case
symbol = "XAUUSD"
timeframe = "M5"
direction = "SELL"
entry_price = 5285.68
stop_loss = 5295.59
take_profit = 5265.85
sl_type = "price_based"  # Default
tp_type = "price_based"  # Default

print(f"\n📊 SIMULATED ORDER:")
print(f"  Symbol: {symbol}")
print(f"  Direction: {direction}")
print(f"  Entry: {entry_price}")
print(f"  SL: {stop_loss} (distance: {stop_loss - entry_price:.2f})")
print(f"  TP: {take_profit} (distance: {entry_price - take_profit:.2f})")

# Get current candle
candle = get_current_candle(mt5, symbol, timeframe)
if not candle:
    print("ERROR: Failed to get candle")
    mt5.shutdown()
    sys.exit(1)

print(f"\n📈 CURRENT CANDLE (LAST CLOSED):")
print(f"  Time: {candle['time']}")
print(f"  Open: {candle['open']:.2f}")
print(f"  High: {candle['high']:.2f}")
print(f"  Low: {candle['low']:.2f}")
print(f"  Close: {candle['close']:.2f}")

# Check if would exit immediately
pip_value = get_pip_value(symbol)
print(f"\n🔍 PIP VALUE: {pip_value}")

h, l, c = candle['high'], candle['low'], candle['close']

exit_type, exit_price = check_exit(
    direction=direction,
    candle={'high': h, 'low': l, 'close': c},
    tp=take_profit,
    sl=stop_loss,
    tp_type=tp_type,
    sl_type=sl_type
)

if exit_type:
    print(f"\n❌ WOULD EXIT IMMEDIATELY!")
    print(f"  Exit Type: {exit_type}")
    print(f"  Exit Price: {exit_price:.2f}")
    
    # Calculate P&L
    if direction == "BUY":
        pnl_pips = (exit_price - entry_price) / pip_value
    else:
        pnl_pips = (entry_price - exit_price) / pip_value
    
    print(f"  P&L: {pnl_pips:.1f} pips")
else:
    print(f"\n✅ NO IMMEDIATE EXIT")
    print(f"  Position would stay open")
    print(f"  Current price: {c:.2f}")
    print(f"  Distance to SL: {abs(c - stop_loss):.2f} ({abs(c - stop_loss) / pip_value:.1f} pips)")
    print(f"  Distance to TP: {abs(c - take_profit):.2f} ({abs(c - take_profit) / pip_value:.1f} pips)")

mt5.shutdown()
print("\n" + "=" * 60)
