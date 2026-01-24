"""
Bot Runner - Main trading bot script with argparse

Usage:
    python src/bot_runner.py --strategy master_candle --symbol ETHUSDm --user admin

Each bot runs as a separate process.
"""

import argparse
import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def get_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="BotForex Trading Bot")

    # Required arguments
    parser.add_argument("--strategy", type=str, required=True,
                        help="Strategy ID (e.g., master_candle)")
    parser.add_argument("--symbol", type=str, required=True,
                        help="Trading symbol (e.g., ETHUSDm)")
    parser.add_argument("--user", type=str, required=True,
                        help="Username for MT5 credentials")

    # Optional parameters (override strategy defaults)
    parser.add_argument("--lot_size", type=float, default=None,
                        help="Lot size (default: from strategy)")
    parser.add_argument("--sl_pips", type=float, default=None,
                        help="Stop loss in pips (default: from strategy)")
    parser.add_argument("--rr_ratio", type=float, default=None,
                        help="Risk:Reward ratio (default: from strategy)")
    parser.add_argument("--max_candles", type=int, default=None,
                        help="Max candles before time exit (default: from strategy)")

    # New parameters matching backtest config
    parser.add_argument("--timeframe", type=str, default=None,
                        help="Timeframe (e.g., M5, M15, H1)")
    parser.add_argument("--entry_time", type=str, default=None,
                        help="Entry time in HH:MM format")
    parser.add_argument("--entry_mode", type=str, default=None,
                        choices=["close", "range_percent", "signal"],
                        help="Entry mode: close (at close price) or range_percent")
    parser.add_argument("--entry_percent", type=float, default=None,
                        help="Entry percent for range_percent mode (0-100)")
    parser.add_argument("--buffer_k", type=float, default=None,
                        help="Buffer K pips added to SL")
    parser.add_argument("--lot_mode", type=str, default=None,
                        choices=["fixed", "flex"],
                        help="Lot mode: fixed or flex (risk-based)")
    parser.add_argument("--starting_equity", type=float, default=None,
                        help="Starting equity for flex mode")
    parser.add_argument("--risk_mode", type=str, default=None,
                        choices=["percent", "amount", "fixed_amount"],
                        help="Risk mode: percent or fixed_amount")
    parser.add_argument("--risk_percent", type=float, default=None,
                        help="Risk percent of equity")
    parser.add_argument("--risk_amount", type=float, default=None,
                        help="Risk amount in USD")
    parser.add_argument("--risk_compounding", type=int, default=None,
                        help="Risk compounding: 1=compound (use current equity), 0=fixed (use starting equity)")
    parser.add_argument("--tp_type", type=str, default=None,
                        choices=["price_based", "close_based"],
                        help="TP type: price_based or close_based")
    parser.add_argument("--sl_type", type=str, default=None,
                        choices=["price_based", "close_based"],
                        help="SL type: price_based or close_based")

    # Bot control
    parser.add_argument("--test", type=int, default=1,
                        help="Test mode: 1=test (no real trades), 0=live")
    parser.add_argument("--interval", type=int, default=60,
                        help="Check interval in seconds (default: 60)")

    return parser.parse_args()


def log(message: str, level: str = "INFO"):
    """Log message with timestamp"""
    timestamp = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def send_telegram(text: str, is_error: bool = False) -> bool:
    """Send message to Telegram"""
    import requests

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_ERROR_CHAT_ID") if is_error else os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        log("Telegram not configured", "WARN")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}

    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.ok
    except Exception as e:
        log(f"Telegram error: {e}", "ERROR")
        return False


def get_mt5_connection(credentials: dict):
    """Initialize MT5 connection"""
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return None, "MT5 not available (Windows only)"

    if not mt5.initialize():
        return None, "MT5 initialization failed"

    login = int(credentials.get('login') or 0)
    password = credentials.get('password', '')
    server = credentials.get('server', '')

    if not login or not password or not server:
        mt5.shutdown()
        return None, "MT5 credentials not configured"

    if not mt5.login(login=login, password=password, server=server):
        error = mt5.last_error()
        mt5.shutdown()
        return None, f"MT5 login failed: {error}"

    return mt5, None


def get_pip_value(symbol: str) -> float:
    """Get pip size (price movement per 1 pip) - Industry Standard."""
    from src.utils import get_pip_value as _get_pip_value
    return _get_pip_value(symbol)


def check_entry_time(entry_time: str) -> bool:
    """Check if current time matches entry time"""
    now = datetime.now(TIMEZONE)
    target_hour, target_minute = map(int, entry_time.split(':'))
    return now.hour == target_hour and now.minute == target_minute


def get_current_candle(mt5, symbol: str, timeframe_str: str) -> dict:
    """Get current candle data"""
    timeframe_map = {
        'M1': mt5.TIMEFRAME_M1,
        'M5': mt5.TIMEFRAME_M5,
        'M15': mt5.TIMEFRAME_M15,
        'M30': mt5.TIMEFRAME_M30,
        'H1': mt5.TIMEFRAME_H1,
        'H4': mt5.TIMEFRAME_H4,
        'D1': mt5.TIMEFRAME_D1
    }

    timeframe = timeframe_map.get(timeframe_str, mt5.TIMEFRAME_M5)
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 2)

    if rates is None or len(rates) < 2:
        return None

    # Return the last closed candle
    candle = rates[-2]
    return {
        'time': datetime.fromtimestamp(candle['time'], tz=TIMEZONE),
        'open': candle['open'],
        'high': candle['high'],
        'low': candle['low'],
        'close': candle['close']
    }


def run_bot(args):
    """Main bot loop"""
    from src.strategy_manager import get_strategy, get_strategy_parameters
    from src.auth import get_user_mt5_credentials

    log(f"Starting bot: {args.strategy} | {args.symbol} | user={args.user}")
    log(f"Test mode: {'YES' if args.test else 'NO - LIVE TRADING'}")

    # Load strategy
    strategy = get_strategy(args.strategy)
    if not strategy:
        log(f"Strategy not found: {args.strategy}", "ERROR")
        return

    params = get_strategy_parameters(args.strategy)
    log(f"Strategy loaded: {strategy.get('name')}")

    # Override with command line args if provided
    sl_pips = args.sl_pips or params.get('sl_pips', 30)
    rr_ratio = args.rr_ratio or params.get('rr_ratio', 2.0)
    lot_size = args.lot_size or params.get('lot_size', 0.01)
    max_candles = args.max_candles or params.get('max_candles', 7)
    entry_time = args.entry_time or params.get('entry_time', '21:05')
    timeframe = args.timeframe or params.get('timeframe', 'M5')

    # New parameters
    entry_mode = args.entry_mode or 'close'
    # Normalize "signal" to "close" for backward compatibility
    if entry_mode == 'signal':
        entry_mode = 'close'
    entry_percent = args.entry_percent if args.entry_percent is not None else 30.0
    buffer_k = args.buffer_k if args.buffer_k is not None else params.get('buffer_k', 0)
    lot_mode = args.lot_mode or 'fixed'
    starting_equity = args.starting_equity or 1000.0
    risk_mode = args.risk_mode or 'percent'
    risk_percent = args.risk_percent if args.risk_percent is not None else 1.0
    risk_amount = args.risk_amount if args.risk_amount is not None else 10.0
    risk_compounding = bool(args.risk_compounding) if args.risk_compounding is not None else True
    tp_type = args.tp_type or 'price_based'
    sl_type = args.sl_type or 'close_based'

    log(f"Parameters: RR={rr_ratio}, MaxCandles={max_candles}, Buffer={buffer_k}")
    log(f"Entry: {entry_time}, Timeframe: {timeframe}, Mode: {entry_mode}")
    log(f"Lot: {lot_mode} ({'Lot=' + str(lot_size) if lot_mode == 'fixed' else 'Risk=' + str(risk_percent) + '%'})")
    log(f"Exit: TP={tp_type}, SL={sl_type}")

    # Get user's MT5 credentials
    credentials = get_user_mt5_credentials(args.user)
    if not credentials.get('login'):
        log(f"MT5 credentials not configured for user: {args.user}", "ERROR")
        return

    # Notify start
    send_telegram(f"Bot Started\n"
                  f"Strategy: {strategy.get('name')}\n"
                  f"Symbol: {args.symbol}\n"
                  f"User: {args.user}\n"
                  f"Test: {'Yes' if args.test else 'No'}")

    # State tracking
    active_trade = None
    last_entry_date = None

    try:
        while True:
            now = datetime.now(TIMEZONE)

            # Check if it's entry time and we haven't traded today
            if check_entry_time(entry_time) and last_entry_date != now.date():
                log(f"Entry time detected: {entry_time}")

                # Connect to MT5
                mt5, error = get_mt5_connection(credentials)
                if error:
                    log(f"MT5 connection failed: {error}", "ERROR")
                    send_telegram(f"MT5 Error: {error}", is_error=True)
                    time.sleep(args.interval)
                    continue

                # Get candle data
                candle = get_current_candle(mt5, args.symbol, timeframe)
                if not candle:
                    log("Failed to get candle data", "ERROR")
                    mt5.shutdown()
                    time.sleep(args.interval)
                    continue

                o, h, l, c = candle['open'], candle['high'], candle['low'], candle['close']
                pip_value = get_pip_value(args.symbol)
                buffer_offset = buffer_k * pip_value
                candle_body = abs(c - o)

                # Determine direction and entry price
                if c > o:
                    direction = "BUY"
                    # Calculate entry price based on entry_mode
                    if entry_mode == "range_percent":
                        # BUY: Close - X% of body (Close - Open)
                        entry_price = c - (entry_percent / 100) * candle_body
                    else:
                        entry_price = c

                    # SL is placed buffer_offset below the Low
                    stop_loss = l - buffer_offset
                    risk = entry_price - stop_loss
                    take_profit = entry_price + (risk * rr_ratio)

                elif c < o:
                    direction = "SELL"
                    # Calculate entry price based on entry_mode
                    if entry_mode == "range_percent":
                        # SELL: Close + X% of body (Open - Close)
                        entry_price = c + (entry_percent / 100) * candle_body
                    else:
                        entry_price = c

                    # SL is placed buffer_offset above the High
                    stop_loss = h + buffer_offset
                    risk = stop_loss - entry_price
                    take_profit = entry_price - (risk * rr_ratio)

                else:
                    log("Doji candle - no trade")
                    mt5.shutdown()
                    last_entry_date = now.date()
                    time.sleep(args.interval)
                    continue

                # Log signal
                log(f"Signal: {direction} @ {entry_price:.2f}, SL={stop_loss:.2f}, TP={take_profit:.2f}")

                # Send notification
                send_telegram(f"<b>Signal: {direction}</b>\n"
                              f"Symbol: {args.symbol}\n"
                              f"Entry: {entry_price:.2f}\n"
                              f"SL: {stop_loss:.2f}\n"
                              f"TP: {take_profit:.2f}")

                # Place order if not in test mode
                if not args.test:
                    # TODO: Implement actual order placement
                    log("LIVE: Would place order here")
                else:
                    log("TEST: Order simulated")

                active_trade = {
                    'direction': direction,
                    'entry': entry_price,
                    'sl': stop_loss,
                    'tp': take_profit,
                    'candles': 0
                }

                last_entry_date = now.date()
                mt5.shutdown()

            # Monitor active trade
            elif active_trade:
                mt5, error = get_mt5_connection(credentials)
                if error:
                    time.sleep(args.interval)
                    continue

                candle = get_current_candle(mt5, args.symbol, timeframe)
                if candle:
                    active_trade['candles'] += 1
                    h, l, c = candle['high'], candle['low'], candle['close']

                    exit_type = None
                    exit_price = None

                    # Check exit conditions
                    if active_trade['direction'] == "BUY":
                        if h >= active_trade['tp']:
                            exit_type, exit_price = "TP", active_trade['tp']
                        elif c <= active_trade['sl']:
                            exit_type, exit_price = "SL", c
                    else:
                        if l <= active_trade['tp']:
                            exit_type, exit_price = "TP", active_trade['tp']
                        elif c >= active_trade['sl']:
                            exit_type, exit_price = "SL", c

                    # Time limit check
                    if not exit_type and active_trade['candles'] >= max_candles:
                        exit_type = "TIME"
                        exit_price = c

                    if exit_type:
                        # Calculate P&L
                        pip_value = get_pip_value(args.symbol)
                        if active_trade['direction'] == "BUY":
                            pnl = (exit_price - active_trade['entry']) / pip_value
                        else:
                            pnl = (active_trade['entry'] - exit_price) / pip_value

                        log(f"Exit: {exit_type} @ {exit_price:.2f}, P&L: {pnl:.1f} pips")
                        send_telegram(f"<b>Exit: {exit_type}</b>\n"
                                      f"Price: {exit_price:.2f}\n"
                                      f"P&L: {pnl:.1f} pips")

                        active_trade = None

                mt5.shutdown()

            # Sleep before next check
            time.sleep(args.interval)

    except KeyboardInterrupt:
        log("Bot stopped by user")
        send_telegram("Bot Stopped (manual)")
    except Exception as e:
        log(f"Bot error: {e}", "ERROR")
        send_telegram(f"Bot Error: {e}", is_error=True)
        raise


if __name__ == "__main__":
    args = get_args()
    run_bot(args)
