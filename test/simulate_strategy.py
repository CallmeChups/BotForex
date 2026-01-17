"""
Simulate Master Candle Strategy
- TP: Price-based (immediate when price touches)
- SL: Close-based (only when candle CLOSES beyond SL)
- Time limit: 7 candles max
"""

from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import os
import requests
import MetaTrader5 as mt5
import pandas as pd

load_dotenv()

# Constants
SYMBOL = os.getenv("SYMBOL", "ETHUSDm")
TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
LOT_SIZE = 0.01
SL_PIPS = 30
MAX_CANDLES = 7

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_TEST_CHAT_ID = os.getenv("TELEGRAM_TEST_CHAT_ID")
TELEGRAM_ERROR_CHAT_ID = os.getenv("TELEGRAM_ERROR_CHAT_ID")


def send_telegram(text: str, is_error: bool = False) -> bool:
    chat_id = TELEGRAM_ERROR_CHAT_ID if is_error else TELEGRAM_TEST_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    response = requests.post(url, json=payload)
    return response.ok


def get_pip_value(symbol: str) -> float:
    if "BTC" in symbol:
        return 1.0
    elif "ETH" in symbol:
        return 0.1
    elif "XAU" in symbol:
        return 0.1
    elif "JPY" in symbol:
        return 0.01
    return 0.0001


def check_exit(direction: str, candle: dict, tp: float, sl: float) -> tuple[str, float]:
    """
    Check exit conditions for a candle.

    TP: Price-based (immediate) - check High/Low
    SL: Close-based - check Close only

    Returns: (exit_type, exit_price) or (None, None)
    """
    h, l, c = candle["high"], candle["low"], candle["close"]

    if direction == "BUY":
        # TP: Price touches (High >= TP)
        if h >= tp:
            return ("TP", tp)
        # SL: Close-based (Close <= SL)
        if c <= sl:
            return ("SL", c)
    else:  # SELL
        # TP: Price touches (Low <= TP)
        if l <= tp:
            return ("TP", tp)
        # SL: Close-based (Close >= SL)
        if c >= sl:
            return ("SL", c)

    return (None, None)


def run_simulation():
    """Connect to MT5, simulate strategy with real candle data"""

    # Connect
    account = int(os.getenv("MT5_LOGIN"))
    password = os.getenv("MT5_PASSWORD")
    server = os.getenv("MT5_SERVER")

    if not mt5.initialize():
        send_telegram("Simulation failed: MT5 init error", is_error=True)
        return

    if not mt5.login(login=account, password=password, server=server):
        send_telegram(f"Simulation failed: {mt5.last_error()}", is_error=True)
        return

    print(f"Connected to MT5")

    # Get candles (need master + 7 following for simulation)
    data = pd.DataFrame(mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, 15))

    if data.empty or len(data) < 10:
        send_telegram(f"No data for {SYMBOL}", is_error=True)
        mt5.shutdown()
        return

    # Convert time
    data['time_hcm'] = pd.to_datetime(data['time'], unit='s').dt.tz_localize('UTC').dt.tz_convert(TIMEZONE)

    print(f"\nCurrent time: {datetime.now(TIMEZONE).strftime('%H:%M:%S')}")

    # Use candle at index -9 as master candle (so we have 7 following candles to simulate)
    master_idx = len(data) - 9
    master = data.iloc[master_idx]
    master_time = master['time_hcm']

    o, h, l, c = master["open"], master["high"], master["low"], master["close"]
    pip = get_pip_value(SYMBOL)
    sl_dist = SL_PIPS * pip

    # Determine direction and calculate levels (RR 1:2)
    if c > o:  # Bullish
        direction = "BUY"
        entry = c
        sl = l - sl_dist
        risk = entry - sl
        reward = risk * 2
        tp = entry + reward
    else:  # Bearish
        direction = "SELL"
        entry = c
        sl = h + sl_dist
        risk = sl - entry
        reward = risk * 2
        tp = entry - reward

    print(f"\nMaster Candle: {master_time.strftime('%H:%M')} | {direction}")
    print(f"Entry: {entry:.2f} | SL: {sl:.2f} | TP: {tp:.2f}")
    print(f"\nSimulating next {MAX_CANDLES} candles:")

    # Simulate following candles
    exit_type = None
    exit_price = None
    exit_candle = None
    candle_results = []

    for i in range(1, MAX_CANDLES + 1):
        candle_idx = master_idx + i
        if candle_idx >= len(data):
            break

        candle = data.iloc[candle_idx]
        candle_time = candle['time_hcm'].strftime('%H:%M')
        ch, cl, cc = candle["high"], candle["low"], candle["close"]

        # Check exit
        exit_type, exit_price = check_exit(direction, {
            "high": ch, "low": cl, "close": cc
        }, tp, sl)

        status = "..."
        if exit_type == "TP":
            status = f"[TP] price touched {tp:.2f}"
            exit_candle = i
        elif exit_type == "SL":
            status = f"[SL] closed @ {cc:.2f}"
            exit_candle = i

        candle_results.append({
            "num": i,
            "time": candle_time,
            "h": ch, "l": cl, "c": cc,
            "status": status
        })

        print(f"  [{i}] {candle_time} | H:{ch:.2f} L:{cl:.2f} C:{cc:.2f} | {status}")

        if exit_type:
            break

    # Time limit if no exit
    if not exit_type:
        exit_type = "TIME"
        last_candle = data.iloc[master_idx + MAX_CANDLES] if master_idx + MAX_CANDLES < len(data) else data.iloc[-1]
        exit_price = last_candle["close"]
        exit_candle = MAX_CANDLES
        print(f"  [TIME] Force close @ {exit_price:.2f}")

    # Calculate P&L
    if direction == "BUY":
        pnl = (exit_price - entry) / pip
    else:
        pnl = (entry - exit_price) / pip

    rr_ratio = reward / risk if risk > 0 else 0

    # Build message
    dir_emoji = "🟢" if direction == "BUY" else "🔴"
    candle_type = "Bullish" if c > o else "Bearish"

    result_emoji = "✅" if exit_type == "TP" else "❌" if exit_type == "SL" else "⏰"
    result_text = "TP HIT" if exit_type == "TP" else "SL HIT" if exit_type == "SL" else "TIME LIMIT"

    # Candle-by-candle summary
    candle_lines = []
    for cr in candle_results:
        if "TP HIT" in cr["status"]:
            candle_lines.append(f"  {cr['num']}. {cr['time']} ✅ TP")
        elif "SL HIT" in cr["status"]:
            candle_lines.append(f"  {cr['num']}. {cr['time']} ❌ SL (C:{cr['c']:.2f})")
        else:
            candle_lines.append(f"  {cr['num']}. {cr['time']} H:{cr['h']:.2f} L:{cr['l']:.2f} C:{cr['c']:.2f}")

    if exit_type == "TIME":
        candle_lines.append(f"  ⏰ Force close after {MAX_CANDLES} candles")

    candles_str = "\n".join(candle_lines)

    msg = f"""<b>{dir_emoji} MASTER CANDLE SIMULATION</b>
<code>{SYMBOL} | M5 | {master_time.strftime('%H:%M %d/%m')}</code>

<b>MASTER CANDLE</b> ({candle_type})
<code>O {o:.2f}  H {h:.2f}
L {l:.2f}  C {c:.2f}</code>

<b>SIGNAL: {direction}</b>
<code>Entry  {entry:.2f}
SL     {sl:.2f} (close-based)
TP     {tp:.2f} (price-based)</code>
<code>Lot {LOT_SIZE} | RR 1:{rr_ratio:.1f}</code>

<b>EXIT RULES</b>
<code>TP: Price touches → immediate
SL: Candle CLOSES beyond → delayed
Time: {MAX_CANDLES} candles → force close</code>

<b>CANDLE TRACKING</b>
<code>{candles_str}</code>

<b>{result_emoji} RESULT: {result_text}</b>
<code>Exit @ {exit_price:.2f} | Candle #{exit_candle}
P&L: {pnl:+.1f} pips</code>"""

    if send_telegram(msg):
        print("\n[OK] Simulation sent to Telegram")
    else:
        print("\n[ERROR] Failed to send")

    mt5.shutdown()


if __name__ == "__main__":
    run_simulation()
