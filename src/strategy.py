"""
Daily M5 Master Candle Strategy

Strategy Rules:
- Check M5 candle closing at 21:05 (Asia/Ho_Chi_Minh) = Master Candle
- Bullish (Close > Open): BUY, SL = Low - 30 pips
- Bearish (Close < Open): SELL, SL = High + 30 pips
- TP = Entry ± (Risk × 2) for RR 1:2

Exit Rules:
- TP: Price-based (immediate) - triggers when price touches TP
- SL: Close-based (delayed) - triggers when candle CLOSES beyond SL
- Time limit: Close after 7 M5 candles (~35 min) if neither hit
"""

from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import os
import requests
import MetaTrader5 as mt5

from src.utils import get_pip_value, check_exit

load_dotenv()

# Constants
MASTER_CANDLE_HOUR = 21
MASTER_CANDLE_MINUTE = 5
LOT_SIZE = 0.01
SL_PIPS = 30
MAX_CANDLES = 7  # Close after 7 M5 candles if SL/TP not hit
TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_ERROR_CHAT_ID = os.getenv("TELEGRAM_ERROR_CHAT_ID")


def send_telegram(text: str, is_error: bool = False) -> bool:
    """Send message to Telegram"""
    chat_id = TELEGRAM_ERROR_CHAT_ID if is_error else TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    response = requests.post(url, json=payload)
    return response.ok


def is_master_candle_time(candle_time: datetime) -> bool:
    """Check if candle closes at 21:05 HCM time"""
    # Convert to HCM timezone if needed
    if candle_time.tzinfo is None:
        candle_time = candle_time.replace(tzinfo=TIMEZONE)

    return candle_time.hour == MASTER_CANDLE_HOUR and candle_time.minute == MASTER_CANDLE_MINUTE


def analyze_master_candle(symbol: str, open_price: float, high: float, low: float, close: float, candle_time: datetime) -> dict | None:
    """
    Analyze Master Candle and generate trade signal

    Args:
        symbol: Trading symbol (e.g., "BTCUSDm", "ETHUSDm")
        open_price: Candle open price
        high: Candle high price
        low: Candle low price
        close: Candle close price
        candle_time: Candle close time

    Returns:
        dict with trade signal or None if no signal
    """
    pip_value = get_pip_value(symbol)
    sl_distance = SL_PIPS * pip_value

    # Bullish: Close > Open -> BUY (RR 1:2)
    if close > open_price:
        direction = "BUY"
        entry_price = close
        stop_loss = low - sl_distance
        risk = entry_price - stop_loss
        reward = risk * 2
        take_profit = entry_price + reward

    # Bearish: Close < Open -> SELL (RR 1:2)
    elif close < open_price:
        direction = "SELL"
        entry_price = close
        stop_loss = high + sl_distance
        risk = stop_loss - entry_price
        reward = risk * 2
        take_profit = entry_price - reward

    # Doji: Close == Open -> No trade
    else:
        return None

    return {
        "symbol": symbol,
        "direction": direction,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "lot_size": LOT_SIZE,
        "candle_time": candle_time,
        "master_candle": {
            "open": open_price,
            "high": high,
            "low": low,
            "close": close
        }
    }


def notify_signal(signal: dict) -> bool:
    """Send trade signal notification to Telegram"""
    direction_emoji = "🟢" if signal["direction"] == "BUY" else "🔴"

    message = f"""<b>{direction_emoji} MASTER CANDLE SIGNAL</b>

<b>Symbol:</b> {signal['symbol']}
<b>Direction:</b> {signal['direction']}
<b>Entry Price:</b> {signal['entry_price']:.2f}
<b>Stop Loss:</b> {signal['stop_loss']:.2f}
<b>Take Profit:</b> {signal['take_profit']:.2f}
<b>Lot Size:</b> {signal['lot_size']}

<b>Master Candle (21:05 HCM):</b>
  Open: {signal['master_candle']['open']:.2f}
  High: {signal['master_candle']['high']:.2f}
  Low: {signal['master_candle']['low']:.2f}
  Close: {signal['master_candle']['close']:.2f}

<i>Time limit: {MAX_CANDLES} candles (~35 min)</i>"""

    return send_telegram(message)


def place_order(signal: dict) -> int | None:
    """
    Place order based on signal

    Returns:
        Order ticket number or None if failed
    """
    symbol = signal["symbol"]
    direction = signal["direction"]
    lot = signal["lot_size"]
    sl = signal["stop_loss"]
    tp = signal["take_profit"]

    # Get symbol info
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        send_telegram(f"Symbol {symbol} not found", is_error=True)
        return None

    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            send_telegram(f"Failed to select {symbol}", is_error=True)
            return None

    # Get current price
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        send_telegram(f"Failed to get tick for {symbol}", is_error=True)
        return None

    # Prepare order request
    if direction == "BUY":
        order_type = mt5.ORDER_TYPE_BUY
        price = tick.ask
    else:
        order_type = mt5.ORDER_TYPE_SELL
        price = tick.bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": 210500,  # Magic number: 2105 (21:05)
        "comment": "MasterCandle",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    # # UNCOMMENT TO ENABLE LIVE TRADING
    # result = mt5.order_send(request)
    # if result.retcode != mt5.TRADE_RETCODE_DONE:
    #     send_telegram(f"Order failed: {result.comment}", is_error=True)
    #     return None
    #
    # send_telegram(f"Order placed! Ticket: {result.order}")
    # return result.order

    # For testing: just log the request
    print(f"[TEST] Order request prepared: {request}")
    return None


def close_position_by_ticket(ticket: int) -> bool:
    """
    Close position by ticket number (for time limit rule)

    Args:
        ticket: Position ticket number

    Returns:
        True if closed successfully
    """
    position = mt5.positions_get(ticket=ticket)
    if not position:
        return False

    position = position[0]
    symbol = position.symbol
    lot = position.volume

    # Determine close direction
    if position.type == mt5.POSITION_TYPE_BUY:
        order_type = mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(symbol).bid
    else:
        order_type = mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(symbol).ask

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "position": ticket,
        "price": price,
        "deviation": 20,
        "magic": 210500,
        "comment": "MasterCandle_TimeLimit",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    # # UNCOMMENT TO ENABLE LIVE TRADING
    # result = mt5.order_send(request)
    # if result.retcode != mt5.TRADE_RETCODE_DONE:
    #     send_telegram(f"Close failed: {result.comment}", is_error=True)
    #     return False
    #
    # send_telegram(f"Position closed (time limit): Ticket {ticket}")
    # return True

    # For testing: just log
    print(f"[TEST] Close request prepared: {request}")
    return False


def check_and_execute_strategy(symbol: str, ohlc_data: dict) -> dict | None:
    """
    Main strategy function - check Master Candle and execute

    Args:
        symbol: Trading symbol
        ohlc_data: dict with keys: open, high, low, close, time (datetime)

    Returns:
        Signal dict if trade signal generated, None otherwise
    """
    candle_time = ohlc_data["time"]

    # Check if this is Master Candle time (21:05 HCM)
    if not is_master_candle_time(candle_time):
        return None

    print(f"[MASTER CANDLE] Detected at {candle_time}")

    # Analyze and generate signal
    signal = analyze_master_candle(
        symbol=symbol,
        open_price=ohlc_data["open"],
        high=ohlc_data["high"],
        low=ohlc_data["low"],
        close=ohlc_data["close"],
        candle_time=candle_time
    )

    if signal is None:
        print("[MASTER CANDLE] Doji candle - no trade")
        return None

    # Send notification
    notify_signal(signal)

    # Place order (commented out for testing)
    # ticket = place_order(signal)
    # if ticket:
    #     signal["ticket"] = ticket

    return signal


# For testing
if __name__ == "__main__":
    # Test with sample data
    test_ohlc = {
        "open": 100000.0,
        "high": 100500.0,
        "low": 99500.0,
        "close": 100300.0,  # Bullish: Close > Open
        "time": datetime(2025, 1, 17, 21, 5, 0, tzinfo=TIMEZONE)
    }

    print("Testing Master Candle Strategy...")
    signal = check_and_execute_strategy("BTCUSDm", test_ohlc)

    if signal:
        print(f"\nSignal generated: {signal['direction']}")
        print(f"Entry: {signal['entry_price']}, SL: {signal['stop_loss']}, TP: {signal['take_profit']}")
