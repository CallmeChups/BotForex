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
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")

# Global log file handle
_log_file = None


def setup_logging(bot_id: str):
    """Setup logging to file"""
    global _log_file

    # Create logs directory
    os.makedirs("logs", exist_ok=True)

    # Create log file
    timestamp = datetime.now(TIMEZONE).strftime("%Y%m%d_%H%M%S")
    log_path = f"logs/bot_{bot_id}_{timestamp}.log"

    _log_file = open(log_path, 'w', buffering=1, encoding='utf-8')  # Line buffered, UTF-8

    log(f"=== Bot Logs ===")
    log(f"Log file: {log_path}")
    log(f"Bot ID: {bot_id}")
    log(f"Started: {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"=" * 60)

    return log_path


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

    # Move SL to Breakeven feature
    parser.add_argument("--move_sl_to_breakeven", type=int, default=None,
                        help="Move SL to breakeven: 1=enabled, 0=disabled")
    parser.add_argument("--breakeven_trigger_percent", type=float, default=None,
                        help="% of TP to trigger breakeven move (default: 50)")
    parser.add_argument("--breakeven_target", type=str, default="entry",
                        help="Breakeven SL target: 'entry' (entry price) or 'close' (candle close price)")

    # Pending order feature
    parser.add_argument("--pending_order_max_candles", type=int, default=3,
                        help="Max candles to retry placing LIMIT order when broker rejects (default: 3, 0=no retry)")
    parser.add_argument("--pending_order_expire_candles", type=int, default=0,
                        help="Cancel LIMIT order if not filled after N candles (default: 0=wait indefinitely)")

    # Bot control
    parser.add_argument("--test", type=int, default=1,
                        help="Test mode: 1=test (no real trades), 0=live")
    parser.add_argument("--interval", type=int, default=1,
                        help="Check interval in seconds (default: 1, used for waiting entry time)")

    return parser.parse_args()


def log(message: str, level: str = "INFO"):
    """Log message with timestamp to both console and file"""
    global _log_file

    timestamp = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [{level}] {message}"

    # Print to console (handle Windows encoding issues)
    try:
        print(log_line)
    except UnicodeEncodeError:
        print(log_line.encode('ascii', errors='replace').decode('ascii'))

    # Write to file if configured
    if _log_file and not _log_file.closed:
        try:
            _log_file.write(log_line + "\n")
            _log_file.flush()  # Ensure immediate write
        except Exception:
            pass  # Ignore file write errors


def send_telegram(text: str, is_error: bool = False) -> bool:
    """Send message to Telegram (blocking)"""
    import requests

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_ERROR_CHAT_ID") if is_error else os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        log("Telegram not configured", "WARN")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}

    try:
        response = requests.post(url, json=payload, timeout=3)
        return response.ok
    except Exception as e:
        log(f"Telegram error: {e}", "ERROR")
        return False


def send_telegram_async(text: str, is_error: bool = False):
    """Send Telegram message in background thread (non-blocking)"""
    import threading
    thread = threading.Thread(target=send_telegram, args=(text, is_error), daemon=True)
    thread.start()


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


def get_timeframe_seconds(timeframe_str: str) -> int:
    """Return candle duration in seconds for a given timeframe string."""
    mapping = {
        'M1': 60, 'M5': 300, 'M15': 900, 'M30': 1800,
        'H1': 3600, 'H4': 14400, 'D1': 86400
    }
    return mapping.get(timeframe_str, 300)


def get_point_value(symbol: str) -> float:
    """Get point size (smallest price increment) for buffer calculations."""
    from src.utils import get_point_value as _get_point_value
    return _get_point_value(symbol)


def check_entry_time(entry_time: str, timeframe_str: str) -> bool:
    """Check if current time matches candle close time.

    entry_time is the CANDLE OPEN time (which candle to analyze).
    The bot triggers at entry_time + timeframe (when candle closes).

    Example (M5): entry_time="21:05" → candle opens 21:05, closes 21:10
                  → bot triggers at 21:10 to read the just-closed 21:05 candle.
    """
    now = datetime.now(TIMEZONE)
    target_hour, target_minute = map(int, entry_time.split(':'))

    # Add timeframe offset: trigger when the candle CLOSES
    timeframe_minutes = {
        'M1': 1, 'M5': 5, 'M15': 15, 'M30': 30,
        'H1': 60, 'H4': 240, 'D1': 1440
    }
    offset = timeframe_minutes.get(timeframe_str, 5)

    total_minutes = target_hour * 60 + target_minute + offset
    exec_hour = (total_minutes // 60) % 24
    exec_minute = total_minutes % 60

    return now.hour == exec_hour and now.minute == exec_minute


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

    # Ensure symbol is subscribed in Market Watch (required for copy_rates_from_pos)
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        return None
    if not symbol_info.visible:
        mt5.symbol_select(symbol, True)

    rates = mt5.copy_rates_from_pos(symbol, timeframe, 1, 1)  # Start from position 1 (last closed)

    if rates is None or len(rates) < 1:
        return None

    # Return the last closed candle (not current open candle)
    candle = rates[0]

    try:
        candle_time = datetime.fromtimestamp(candle['time'], tz=TIMEZONE)
    except (ValueError, OSError) as e:
        # Invalid timestamp - log and return None
        log(f"Invalid candle timestamp: {candle['time']} - {e}", "ERROR")
        return None

    return {
        'time': candle_time,
        'open': candle['open'],
        'high': candle['high'],
        'low': candle['low'],
        'close': candle['close']
    }


def run_bot(args):
    """Main bot loop"""
    from src.strategy_manager import get_strategy, get_strategy_parameters
    from src.auth import get_user_mt5_credentials

    # Setup logging first
    bot_id = f"{args.strategy}_{args.symbol}_{args.user}_{os.getpid()}"
    log_path = setup_logging(bot_id)

    log(f"Starting bot: {args.strategy} | {args.symbol} | user={args.user}")
    log(f"Process ID: {os.getpid()}")
    log(f"Test mode: {'YES' if args.test else 'NO - LIVE TRADING'}")

    # Load strategy
    log(f"[STEP 1/5] Loading strategy: {args.strategy}")
    strategy = get_strategy(args.strategy)
    if not strategy:
        log(f"[ERROR] CRITICAL ERROR: Strategy not found: {args.strategy}", "ERROR")
        log(f"Bot cannot start without valid strategy", "ERROR")
        return

    params = get_strategy_parameters(args.strategy)
    log(f"[OK] Strategy loaded: {strategy.get('name')}")
    log(f"  Strategy parameters: {params}")

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

    # MT5 can only enforce price_based SL/TP (wick-touch).
    # For close_based, we omit SL/TP from broker order and handle exits in software.
    send_sl_to_mt5 = (sl_type == "price_based")
    send_tp_to_mt5 = (tp_type == "price_based")

    # Move SL to Breakeven parameters
    move_sl_to_breakeven = bool(args.move_sl_to_breakeven) if args.move_sl_to_breakeven is not None else False
    breakeven_trigger_percent = args.breakeven_trigger_percent if args.breakeven_trigger_percent is not None else 50.0
    breakeven_target = args.breakeven_target or "entry"  # "entry" or "close"

    log(f"[STEP 2/5] Configuration:")
    log(f"  RR Ratio: {rr_ratio}")
    log(f"  Max Candles: {max_candles}")
    log(f"  Buffer K: {buffer_k} points")
    log(f"  Entry Time: {entry_time}")
    log(f"  Timeframe: {timeframe}")
    log(f"  Entry Mode: {entry_mode}")
    if entry_mode == 'range_percent':
        log(f"  Entry Percent: {entry_percent}%")
        log(f"  Pending Retry Candles: {args.pending_order_max_candles}")
        log(f"  Pending Expire Candles: {args.pending_order_expire_candles} {'(wait forever)' if args.pending_order_expire_candles == 0 else ''}")
    log(f"  Lot Mode: {lot_mode}")
    if lot_mode == 'fixed':
        log(f"  Lot Size: {lot_size}")
    else:
        log(f"  Risk Percent: {risk_percent}%")
        log(f"  Risk Mode: {risk_mode}")
        log(f"  Risk Compounding: {risk_compounding}")
    log(f"  TP Type: {tp_type}")
    log(f"  SL Type: {sl_type}")
    if move_sl_to_breakeven:
        log(f"  Move SL to Breakeven: ENABLED at {breakeven_trigger_percent}% TP (target: {breakeven_target})")
    else:
        log(f"  Move SL to Breakeven: DISABLED")

    # Get user's MT5 credentials
    log(f"[STEP 3/5] Getting MT5 credentials for user: {args.user}")
    credentials = get_user_mt5_credentials(args.user)

    if not credentials:
        log(f"[ERROR] CRITICAL ERROR: No credentials found for user: {args.user}", "ERROR")
        log(f"Solution: Go to Settings page and configure MT5 account", "ERROR")
        log(f"Bot cannot start without MT5 credentials", "ERROR")
        return

    if not credentials.get('login'):
        log(f"[ERROR] CRITICAL ERROR: MT5 login not configured for user: {args.user}", "ERROR")
        log(f"Credentials object: {credentials}", "ERROR")
        log(f"Solution: Go to Settings page and configure MT5 account", "ERROR")
        log(f"Bot cannot start without MT5 credentials", "ERROR")
        return

    log(f"[OK] MT5 credentials loaded:")
    log(f"  Login: {credentials.get('login')}")
    log(f"  Server: {credentials.get('server')}")
    log(f"  Password: {'*' * len(credentials.get('password', ''))}")

    # Notify start
    log(f"[STEP 4/5] Sending startup notification to Telegram")
    mode_label = "[TEST] TEST" if args.test else "[LIVE] LIVE"
    lot_info = f"Lot={lot_size}" if lot_mode == "fixed" else f"Risk={risk_percent}% {'(Compound)' if risk_compounding else '(Fixed)'}"
    be_status = f"[OK] BE@{breakeven_trigger_percent:.0f}%" if move_sl_to_breakeven else "✗"

    telegram_sent = send_telegram(f"<b>🤖 Bot Started</b>\n\n"
                  f"<b>{mode_label}</b> | {strategy.get('name')}\n"
                  f"[SIGNAL] {args.symbol} | {timeframe}\n"
                  f"👤 {args.user}\n\n"
                  f"[TIME] Entry: {entry_time}\n"
                  f"📍 Mode: {entry_mode.title()}"
                  f"{f' ({entry_percent}%)' if entry_mode == 'range_percent' else ''}\n"
                  f"💰 {lot_info}\n"
                  f"📈 RR: {rr_ratio}:1 | Buffer: {buffer_k}pt\n"
                  f"🎯 TP: {tp_type[:5]} | SL: {sl_type[:5]}\n"
                  f"🔄 Breakeven: {be_status}\n"
                  f"⏱️ Max: {max_candles}c | Check: {args.interval}s")

    if telegram_sent:
        log(f"[OK] Telegram notification sent")
    else:
        log(f"Telegram notification failed (not critical)", "WARN")

    # State tracking
    active_trade = None
    last_entry_date = None
    waiting_for_limit = None  # State for range_percent when LIMIT can't be placed yet
    pending_signal = None         # Saved signal data for retrying failed LIMIT orders
    retry_start_candle_time = None  # Candle time when first failure occurred
    retry_candles_elapsed = 0      # Number of candles elapsed since first failure

    try:
        log(f"")
        log(f"{'='*60}")
        log(f"[STEP 5/5] BOT MAIN LOOP STARTED")
        log(f"{'='*60}")
        log(f"[OK] Waiting for entry time: {entry_time}")
        log(f"[OK] Timeframe: {timeframe}")
        log(f"[OK] Symbol: {args.symbol}")
        log(f"[OK] Check interval: {args.interval}s")
        log(f"[OK] Current time: {datetime.now(TIMEZONE).strftime('%H:%M:%S %d/%m/%Y')}")
        log(f"")
        log(f"Bot is now running and monitoring...")
        log(f"Press Ctrl+C to stop or use 'Stop' button in UI")
        log(f"{'='*60}")
        log(f"")

        loop_count = 0
        while True:
            now = datetime.now(TIMEZONE)
            loop_count += 1

            # Debug log every 30 loops (every ~30 seconds if interval=1)
            if loop_count % 30 == 0:
                log(f"[Loop {loop_count}] [TIME] {now.strftime('%H:%M:%S')} | Entry: {entry_time} | Active: {active_trade is not None} | WaitLimit: {waiting_for_limit is not None}")

            # Retry failed LIMIT order with saved signal
            if pending_signal is not None and active_trade is None:
                retry_limit = args.pending_order_max_candles if args.pending_order_max_candles > 0 else 3

                # Connect to MT5
                mt5, error = get_mt5_connection(credentials)
                if error:
                    log(f"[ERROR] MT5 connection failed: {error}", "ERROR")
                    time.sleep(args.interval)
                    continue

                # Check if new candle has appeared → increment candle counter
                try:
                    current_candle = get_current_candle(mt5, args.symbol, timeframe)
                except Exception as e:
                    current_candle = None

                if current_candle and retry_start_candle_time and current_candle['time'] > retry_start_candle_time:
                    new_candles = 0
                    # Count candles elapsed (approximate by comparing times)
                    if current_candle['time'] != retry_start_candle_time:
                        # Update candle time tracking
                        if not hasattr(pending_signal, '_last_candle_time'):
                            pending_signal['_last_candle_time'] = retry_start_candle_time
                        if current_candle['time'] > pending_signal.get('_last_candle_time', retry_start_candle_time):
                            retry_candles_elapsed += 1
                            pending_signal['_last_candle_time'] = current_candle['time']
                            log(f"[RETRY] Candle elapsed: {retry_candles_elapsed}/{retry_limit}")

                # Check if exceeded max candles → stop bot
                if retry_candles_elapsed >= retry_limit:
                    log(f"")
                    log(f"{'='*60}")
                    log(f"[FAIL] LIMIT order retry expired after {retry_candles_elapsed} candles — stopping bot", "ERROR")
                    log(f"{'='*60}")
                    send_telegram_async(
                        f"[FAIL] <b>Order Retry Expired</b>\n"
                        f"Symbol: {args.symbol}\n"
                        f"Could not place LIMIT after {retry_candles_elapsed} candles\n"
                        f"Bot stopping...", is_error=True)
                    pending_signal = None
                    retry_start_candle_time = None
                    retry_candles_elapsed = 0
                    mt5.shutdown()
                    log("Bot stopping — LIMIT retry candles exhausted")
                    return

                # Re-use saved signal data
                direction = pending_signal['direction']
                entry_price = pending_signal['entry']
                stop_loss = pending_signal['sl']
                take_profit = pending_signal['tp']
                final_lot = pending_signal['lot']
                c = pending_signal['close_price']

                log(f"[RETRY] Retrying LIMIT order ({retry_candles_elapsed}/{retry_limit} candles elapsed)")

                # Check if price moved past SL (trade invalidated)
                # Respect sl_type: price_based = tick check, close_based = candle close check
                tick = mt5.symbol_info_tick(args.symbol)
                if tick:
                    sl_invalidated = False
                    if sl_type == "price_based":
                        if direction == "BUY" and tick.ask <= stop_loss:
                            sl_invalidated = True
                            log(f"  [SKIP] Price moved past SL! ask={tick.ask:.5f} <= SL={stop_loss:.5f}", "ERROR")
                        elif direction == "SELL" and tick.bid >= stop_loss:
                            sl_invalidated = True
                            log(f"  [SKIP] Price moved past SL! bid={tick.bid:.5f} >= SL={stop_loss:.5f}", "ERROR")
                    else:
                        # close_based: check previous candle close
                        try:
                            rates = mt5.copy_rates_from_pos(args.symbol, timeframe, 1, 1)
                            if rates is not None and len(rates) > 0:
                                prev_close = rates[0]['close']
                                if direction == "BUY" and prev_close <= stop_loss:
                                    sl_invalidated = True
                                    log(f"  [SKIP] Previous candle closed past SL! close={prev_close:.5f} <= SL={stop_loss:.5f}", "ERROR")
                                elif direction == "SELL" and prev_close >= stop_loss:
                                    sl_invalidated = True
                                    log(f"  [SKIP] Previous candle closed past SL! close={prev_close:.5f} >= SL={stop_loss:.5f}", "ERROR")
                        except Exception:
                            pass

                    if sl_invalidated:
                        pending_signal = None
                        retry_start_candle_time = None
                        retry_candles_elapsed = 0
                        last_entry_date = now.date()
                        mt5.shutdown()
                        time.sleep(args.interval)
                        continue

                # Check if we should use market or limit
                use_market = False
                if tick:
                    if direction == "BUY" and tick.ask <= entry_price:
                        use_market = True
                    elif direction == "SELL" and tick.bid >= entry_price:
                        use_market = True

                from src.orders import place_pending_order, place_order

                if use_market:
                    log(f"  Retrying as MARKET ORDER (price at/past entry)")
                    success, msg, order_ticket = place_order(
                        symbol=args.symbol, direction=direction, volume=final_lot,
                        sl=stop_loss if send_sl_to_mt5 else None,
                        tp=take_profit if send_tp_to_mt5 else None,
                        credentials=credentials,
                        theoretical_entry=entry_price
                    )
                    is_pending_order = False
                else:
                    log(f"  Retrying as LIMIT ORDER at {entry_price:.5f}")
                    success, msg, order_ticket = place_pending_order(
                        symbol=args.symbol, direction=direction, volume=final_lot,
                        entry_price=entry_price,
                        sl=stop_loss if send_sl_to_mt5 else None,
                        tp=take_profit if send_tp_to_mt5 else None,
                        credentials=credentials
                    )
                    is_pending_order = True if success else False

                if success:
                    log(f"  [SUCCESS] Retry succeeded! Ticket: {order_ticket}")
                    log(f"  Message: {msg}")
                    pending_signal = None
                    retry_start_candle_time = None
                    retry_candles_elapsed = 0

                    order_type_label = "Pending Order (LIMIT)" if is_pending_order else "Market Order"
                    send_telegram_async(f"[OK] <b>{order_type_label} Placed (retry)</b>\n"
                                  f"Ticket: {order_ticket}\n"
                                  f"Direction: {direction}\n"
                                  f"Lot: {final_lot}\n"
                                  f"{msg}")

                    if not is_pending_order:
                        mt5_temp, _ = get_mt5_connection(credentials)
                        if mt5_temp:
                            positions = mt5_temp.positions_get(ticket=order_ticket)
                            if positions and len(positions) > 0:
                                pos = positions[0]
                                entry_price = pos.price_open
                                # Only override SL/TP from MT5 if we actually sent them
                                if send_sl_to_mt5 and pos.sl > 0:
                                    stop_loss = pos.sl
                                if send_tp_to_mt5 and pos.tp > 0:
                                    take_profit = pos.tp
                                log(f"LIVE: Actual position - Entry={entry_price:.5f}, SL={stop_loss:.5f}, TP={take_profit:.5f}")
                            mt5_temp.shutdown()

                    mt5.shutdown()

                    active_trade = {
                        'direction': direction,
                        'entry': entry_price,
                        'sl': stop_loss,
                        'tp': take_profit,
                        'original_sl': stop_loss,
                        'close_price': c,
                        'candles': 0,
                        'ticket': order_ticket,
                        'lot': final_lot,
                        'entry_time': now,
                        'entry_candle_time': retry_start_candle_time or datetime.min.replace(tzinfo=TIMEZONE),
                        'last_checked_candle_time': retry_start_candle_time or datetime.min.replace(tzinfo=TIMEZONE),
                        'sl_moved_to_breakeven': False,
                        'is_pending': is_pending_order,
                        'candles_waited': 0,
                        'pending_placed_at': now,
                    }
                    last_entry_date = now.date()
                    time.sleep(args.interval)
                    continue
                else:
                    # Still failing — keep retrying until candle limit reached
                    log(f"  [ERROR] Retry failed: {msg}", "ERROR")
                    log(f"  [RETRY] Will retry again in 1s... ({retry_candles_elapsed}/{retry_limit} candles elapsed)", "WARN")
                    mt5.shutdown()
                    time.sleep(1)
                    continue

            # Check if it's entry time and we haven't traded today (and not already waiting for limit)
            if check_entry_time(entry_time, timeframe) and last_entry_date != now.date() and waiting_for_limit is None:
                log(f"")
                log(f"{'='*60}")
                log(f"[TIME] CANDLE CLOSE DETECTED!")
                log(f"{'='*60}")
                log(f"Master Candle (open time): {entry_time}")
                log(f"Current Time: {now.strftime('%H:%M:%S %d/%m/%Y')}")
                log(f"Last Entry Date: {last_entry_date}")
                log(f"Today: {now.date()}")
                log(f"Can place new order: {last_entry_date != now.date()}")

                # Connect to MT5
                log(f"")
                log(f"[1/6] Connecting to MT5...")
                log(f"  Server: {credentials.get('server')}")
                log(f"  Login: {credentials.get('login')}")

                mt5, error = get_mt5_connection(credentials)
                if error:
                    log(f"[ERROR] MT5 connection failed: {error}", "ERROR")
                    send_telegram_async(f"MT5 Error: {error}", is_error=True)
                    time.sleep(args.interval)
                    continue

                log(f"[OK] MT5 connected successfully")

                # Get candle data with continuous checking (no sleep)
                # Check continuously for 2 seconds to ensure we get the correct candle
                log(f"")
                log(f"[2/6] Fetching candle data...")
                log(f"  Symbol: {args.symbol}")
                log(f"  Timeframe: {timeframe}")
                log(f"  Will check continuously for up to 2 seconds to get correct candle")

                start_check = time.time()
                timeout = 2.0  # 2 seconds timeout
                candle = None
                attempts = 0

                while time.time() - start_check < timeout:
                    attempts += 1
                    temp_candle = get_current_candle(mt5, args.symbol, timeframe)

                    if temp_candle:
                        # Verify candle time is correct (should be entry_time - timeframe)
                        timeframe_minutes = {'M1': 1, 'M5': 5, 'M15': 15, 'M30': 30, 'H1': 60, 'H4': 240, 'D1': 1440}
                        offset = timeframe_minutes.get(timeframe, 5)

                        expected_candle_hour = (now.hour * 60 + now.minute - offset) // 60
                        expected_candle_minute = (now.hour * 60 + now.minute - offset) % 60

                        candle_hour = temp_candle['time'].hour
                        candle_minute = temp_candle['time'].minute

                        if candle_hour == expected_candle_hour and candle_minute == expected_candle_minute:
                            candle = temp_candle
                            elapsed = time.time() - start_check
                            log(f"[OK] Correct candle found! (attempts: {attempts}, time: {elapsed:.3f}s)")
                            log(f"Candle: {candle_hour:02d}:{candle_minute:02d} (expected {expected_candle_hour:02d}:{expected_candle_minute:02d})")
                            break
                    # No sleep - check immediately again

                if not candle:
                    elapsed = time.time() - start_check
                    log(f"Timeout: Could not get correct candle after {attempts} attempts in {elapsed:.3f}s", "WARN")

                if not candle:
                    log("Failed to get candle data", "ERROR")
                    mt5.shutdown()
                    time.sleep(args.interval)
                    continue

                o, h, l, c = candle['open'], candle['high'], candle['low'], candle['close']
                pip_value = get_pip_value(args.symbol)
                point_value = get_point_value(args.symbol)
                buffer_offset = buffer_k * point_value
                candle_body = abs(c - o)

                log(f"")
                log(f"[3/6] Analyzing candle...")
                log(f"  Candle Time: {candle['time']}")
                log(f"  O={o:.5f}, H={h:.5f}, L={l:.5f}, C={c:.5f}")
                log(f"  Body: {candle_body:.5f}")
                log(f"  Pip value: {pip_value}")
                log(f"  Point value: {point_value}")
                log(f"  Buffer K: {buffer_k} points")
                log(f"  Buffer offset: {buffer_offset:.5f}")

                # Determine direction and entry price
                log(f"")
                log(f"[4/6] Determining direction...")
                log(f"  Comparing: C ({c:.5f}) vs O ({o:.5f})")
                if c > o:
                    direction = "BUY"
                    log(f"[OK] Direction: BUY (C > O: {c:.5f} > {o:.5f})")

                    # Calculate entry price based on entry_mode
                    if entry_mode == "range_percent":
                        # BUY: Close - X% of body (Close - Open)
                        entry_price = c - (entry_percent / 100) * candle_body
                        log(f"Entry Mode: range_percent ({entry_percent}%)")
                        log(f"Entry = C - ({entry_percent}% × {candle_body:.5f}) = {c:.5f} - {(entry_percent/100)*candle_body:.5f} = {entry_price:.5f}")
                    else:
                        entry_price = c
                        log(f"Entry Mode: close")
                        log(f"Entry = Close = {entry_price:.5f}")

                    # SL is placed buffer_offset below the Low
                    stop_loss = l - buffer_offset
                    risk = entry_price - stop_loss
                    take_profit = entry_price + (risk * rr_ratio)

                    log(f"=== BUY CALCULATION ===")
                    log(f"Entry: {entry_price:.5f}")
                    log(f"SL: L - buffer = {l:.5f} - {buffer_offset:.5f} = {stop_loss:.5f}")
                    log(f"Risk: {risk:.5f} ({(entry_price - stop_loss) / pip_value:.1f} pips)")
                    log(f"TP: Entry + (Risk × {rr_ratio}) = {entry_price:.5f} + {risk * rr_ratio:.5f} = {take_profit:.5f}")
                    log(f"TP Distance: {(take_profit - entry_price) / pip_value:.1f} pips")

                elif c < o:
                    direction = "SELL"
                    log(f"[OK] Direction: SELL (C < O: {c:.5f} < {o:.5f})")

                    # Calculate entry price based on entry_mode
                    if entry_mode == "range_percent":
                        # SELL: Close + X% of body (Open - Close)
                        entry_price = c + (entry_percent / 100) * candle_body
                        log(f"Entry Mode: range_percent ({entry_percent}%)")
                        log(f"Entry = C + ({entry_percent}% × {candle_body:.5f}) = {c:.5f} + {(entry_percent/100)*candle_body:.5f} = {entry_price:.5f}")
                    else:
                        entry_price = c
                        log(f"Entry Mode: close")
                        log(f"Entry = Close = {entry_price:.5f}")

                    # SL is placed buffer_offset above the High
                    stop_loss = h + buffer_offset
                    risk = stop_loss - entry_price
                    take_profit = entry_price - (risk * rr_ratio)

                    log(f"=== SELL CALCULATION ===")
                    log(f"Entry: {entry_price:.5f}")
                    log(f"SL: H + buffer = {h:.5f} + {buffer_offset:.5f} = {stop_loss:.5f}")
                    log(f"Risk: {risk:.5f} ({(stop_loss - entry_price) / pip_value:.1f} pips)")
                    log(f"TP: Entry - (Risk × {rr_ratio}) = {entry_price:.5f} - {risk * rr_ratio:.5f} = {take_profit:.5f}")
                    log(f"SL Distance: {(stop_loss - entry_price) / pip_value:.1f} pips")
                    log(f"TP Distance: {(entry_price - take_profit) / pip_value:.1f} pips")

                else:
                    log("Doji candle - no trade")
                    mt5.shutdown()
                    last_entry_date = now.date()
                    time.sleep(args.interval)
                    continue

                # Calculate lot size based on lot mode
                log(f"")
                log(f"[5/6] Calculating lot size...")
                log(f"  Lot mode: {lot_mode}")

                if lot_mode == "flex":
                    from src.backtest import calculate_flex_lot_size
                    from src.utils import get_pip_value_per_lot

                    # Calculate SL in pips
                    sl_pips_actual = (entry_price - stop_loss) / pip_value if direction == "BUY" else (stop_loss - entry_price) / pip_value

                    # Get current equity from MT5 account (for accurate risk calculation)
                    account_info = mt5.account_info()
                    current_equity = account_info.equity if account_info else starting_equity

                    log(f"Account Equity: {current_equity:.2f} (Starting: {starting_equity:.2f})")

                    # Calculate lot size
                    if risk_mode == "fixed_amount":
                        # Fixed amount: Use current equity to maintain proper risk calculation
                        calculated_lot = calculate_flex_lot_size(
                            equity=current_equity,
                            risk_percent=0,
                            sl_pips=sl_pips_actual,
                            symbol=args.symbol,
                            risk_amount=risk_amount
                        )
                    else:
                        # Percentage mode: Use starting_equity if not compounding, current_equity if compounding
                        equity_for_risk = starting_equity if not risk_compounding else current_equity
                        calculated_lot = calculate_flex_lot_size(
                            equity=equity_for_risk,
                            risk_percent=risk_percent,
                            sl_pips=sl_pips_actual,
                            symbol=args.symbol
                        )
                    final_lot = calculated_lot
                else:
                    final_lot = lot_size

                # Log signal
                log(f"")
                log(f"{'='*60}")
                log(f"[SIGNAL] SIGNAL GENERATED: {direction}")
                log(f"{'='*60}")
                log(f"  Symbol: {args.symbol}")
                log(f"  Entry: {entry_price:.5f}")
                log(f"  SL: {stop_loss:.5f}")
                log(f"  TP: {take_profit:.5f}")
                log(f"  Lot: {final_lot}")
                log(f"  Entry Mode: {entry_mode}")
                log(f"{'='*60}")

                # Send signal notification (non-blocking to avoid delaying order)
                entry_time_label = now.strftime("%H:%M:%S %d/%m/%Y")
                send_telegram_async(f"<b>Signal: {direction}</b>\n"
                              f"Symbol: {args.symbol}\n"
                              f"Entry Time: {entry_time_label}\n"
                              f"Entry: {entry_price:.2f}\n"
                              f"SL: {stop_loss:.2f}\n"
                              f"TP: {take_profit:.2f}\n"
                              f"Lot: {final_lot}")

                # Place order if not in test mode
                order_ticket = None
                is_pending_order = False
                log(f"")
                log(f"[6/6] Placing order...")
                log(f"  Test Mode: {'YES (no real order will be placed)' if args.test else 'NO (LIVE ORDER)'}")

                if not args.test:
                    log(f"  [LIVE] LIVE MODE: Placing real order on MT5 account")
                    log(f"  Symbol: {args.symbol}")
                    log(f"  Direction: {direction}")
                    log(f"  Lot: {final_lot}")
                    log(f"  Entry: {entry_price:.5f}")
                    log(f"  SL: {stop_loss:.5f}")
                    log(f"  TP: {take_profit:.5f}")

                    # Determine order type based on entry mode
                    if entry_mode == "range_percent":
                        from src.orders import place_pending_order

                        # Check if LIMIT can be placed now (price on correct side of entry)
                        tick = mt5.symbol_info_tick(args.symbol)
                        can_place_limit = True

                        if tick:
                            if direction == "BUY" and tick.ask <= entry_price:
                                # BUY LIMIT needs ask > entry — price too low
                                can_place_limit = False
                                log(f"  [INFO] Cannot place BUY LIMIT: ask={tick.ask:.5f} <= entry={entry_price:.5f}")
                            elif direction == "SELL" and tick.bid >= entry_price:
                                # SELL LIMIT needs bid < entry — price too high
                                can_place_limit = False
                                log(f"  [INFO] Cannot place SELL LIMIT: bid={tick.bid:.5f} >= entry={entry_price:.5f}")

                        if not can_place_limit:
                            # Safety check: if price moved past SL, trade is invalidated
                            # For close_based SL: only invalidate on tick if price_based; otherwise wait for candle close
                            price_past_sl = False
                            if sl_type == "price_based":
                                # price_based: check tick price immediately (wick-touch)
                                if direction == "BUY" and tick.ask <= stop_loss:
                                    price_past_sl = True
                                    log(f"  [SKIP] Price moved past SL! ask={tick.ask:.5f} <= SL={stop_loss:.5f}")
                                elif direction == "SELL" and tick.bid >= stop_loss:
                                    price_past_sl = True
                                    log(f"  [SKIP] Price moved past SL! bid={tick.bid:.5f} >= SL={stop_loss:.5f}")
                            else:
                                # close_based: check master candle close vs SL (candle just closed)
                                if direction == "BUY" and c <= stop_loss:
                                    price_past_sl = True
                                    log(f"  [SKIP] Candle closed past SL! close={c:.5f} <= SL={stop_loss:.5f}")
                                elif direction == "SELL" and c >= stop_loss:
                                    price_past_sl = True
                                    log(f"  [SKIP] Candle closed past SL! close={c:.5f} >= SL={stop_loss:.5f}")

                            if price_past_sl:
                                log(f"  Trade invalidated - skipping this entry")
                                send_telegram_async(f"[SKIP] <b>Trade Skipped</b>\n"
                                    f"Symbol: {args.symbol}\n"
                                    f"Reason: Price {'wick' if sl_type == 'price_based' else 'close'} past SL\n"
                                    f"Signal entry: {entry_price:.5f}\n"
                                    f"Current price: {tick.ask if direction == 'BUY' else tick.bid:.5f}\n"
                                    f"SL: {stop_loss:.5f}")
                                mt5.shutdown()
                                last_entry_date = now.date()
                                time.sleep(args.interval)
                                continue

                            # Enter waiting state — wait for price to return so LIMIT can be placed
                            log(f"")
                            log(f"  [WAIT] Entering WAIT FOR LIMIT state")
                            log(f"  Reason: Price already past entry — cannot place LIMIT now")
                            log(f"  Will wait indefinitely for price to return")
                            log(f"")

                            waiting_for_limit = {
                                'direction': direction,
                                'entry_price': entry_price,
                                'stop_loss': stop_loss,
                                'take_profit': take_profit,
                                'lot': final_lot,
                                'close_price': c,  # Master candle close price
                                'candles_waited': 0,
                                'last_checked_candle_time': candle['time'],
                                'entry_candle_time': candle['time'],
                            }

                            send_telegram_async(
                                f"[WAIT] <b>Waiting for LIMIT placement</b>\n"
                                f"Symbol: {args.symbol}\n"
                                f"Direction: {direction}\n"
                                f"Entry target: {entry_price:.5f}\n"
                                f"Current price: {tick.ask if direction == 'BUY' else tick.bid:.5f}\n"
                                f"Will wait indefinitely for price to return")

                            last_entry_date = now.date()
                            mt5.shutdown()
                            time.sleep(args.interval)
                            continue
                        else:
                            log(f"")
                            log(f"  Order Type: PENDING ORDER (LIMIT)")
                            log(f"  Reason: Entry mode is 'range_percent' ({entry_percent}%)")
                            log(f"  Price will wait at: {entry_price:.5f}")
                            log(f"")
                            log(f"  Calling place_pending_order()...")
                            if not send_sl_to_mt5:
                                log(f"  [INFO] SL type is close_based — SL omitted from broker order (bot will monitor)")
                            if not send_tp_to_mt5:
                                log(f"  [INFO] TP type is close_based — TP omitted from broker order (bot will monitor)")

                            success, msg, order_ticket = place_pending_order(
                                symbol=args.symbol,
                                direction=direction,
                                volume=final_lot,
                                entry_price=entry_price,
                                sl=stop_loss if send_sl_to_mt5 else None,
                                tp=take_profit if send_tp_to_mt5 else None,
                                credentials=credentials
                            )
                            is_pending_order = True if success else False
                    else:
                        # Entry mode "close": use LIMIT order at close price
                        from src.orders import place_pending_order, place_order

                        # Check if price already passed entry level → fallback to market
                        tick = mt5.symbol_info_tick(args.symbol)
                        use_market_fallback = False

                        if tick:
                            if direction == "BUY" and tick.ask <= entry_price:
                                use_market_fallback = True
                                log(f"  [INFO] Price at/below entry: ask={tick.ask:.5f} <= entry={entry_price:.5f}")
                            elif direction == "SELL" and tick.bid >= entry_price:
                                use_market_fallback = True
                                log(f"  [INFO] Price at/above entry: bid={tick.bid:.5f} >= entry={entry_price:.5f}")

                        if use_market_fallback:
                            # Safety check: if price moved past SL, trade is invalidated
                            # Respect sl_type: price_based checks tick, close_based checks candle close
                            price_past_sl = False
                            if sl_type == "price_based":
                                if direction == "BUY" and tick.ask <= stop_loss:
                                    price_past_sl = True
                                    log(f"  [SKIP] Price moved past SL! ask={tick.ask:.5f} <= SL={stop_loss:.5f}")
                                elif direction == "SELL" and tick.bid >= stop_loss:
                                    price_past_sl = True
                                    log(f"  [SKIP] Price moved past SL! bid={tick.bid:.5f} >= SL={stop_loss:.5f}")
                            else:
                                # close_based: check master candle close vs SL
                                if direction == "BUY" and c <= stop_loss:
                                    price_past_sl = True
                                    log(f"  [SKIP] Candle closed past SL! close={c:.5f} <= SL={stop_loss:.5f}")
                                elif direction == "SELL" and c >= stop_loss:
                                    price_past_sl = True
                                    log(f"  [SKIP] Candle closed past SL! close={c:.5f} >= SL={stop_loss:.5f}")

                            if price_past_sl:
                                log(f"  Trade invalidated - skipping this entry")
                                send_telegram_async(f"[SKIP] <b>Trade Skipped</b>\n"
                                    f"Symbol: {args.symbol}\n"
                                    f"Reason: Price {'wick' if sl_type == 'price_based' else 'close'} past SL\n"
                                    f"Signal entry: {entry_price:.5f}\n"
                                    f"Current price: {tick.ask if direction == 'BUY' else tick.bid:.5f}\n"
                                    f"SL: {stop_loss:.5f}")
                                mt5.shutdown()
                                last_entry_date = now.date()
                                time.sleep(args.interval)
                                continue

                            log(f"")
                            log(f"  Order Type: MARKET ORDER (fallback)")
                            log(f"  Reason: Price already at/past close entry level")
                            log(f"")
                            log(f"  Calling place_order()...")

                            success, msg, order_ticket = place_order(
                                symbol=args.symbol,
                                direction=direction,
                                volume=final_lot,
                                sl=stop_loss if send_sl_to_mt5 else None,
                                tp=take_profit if send_tp_to_mt5 else None,
                                credentials=credentials,
                                theoretical_entry=entry_price
                            )
                            is_pending_order = False
                        else:
                            log(f"")
                            log(f"  Order Type: PENDING ORDER (LIMIT)")
                            log(f"  Reason: Entry mode is 'close' - limit at close price")
                            log(f"  Price will wait at: {entry_price:.5f}")
                            log(f"")
                            log(f"  Calling place_pending_order()...")

                            success, msg, order_ticket = place_pending_order(
                                symbol=args.symbol,
                                direction=direction,
                                volume=final_lot,
                                entry_price=entry_price,
                                sl=stop_loss if send_sl_to_mt5 else None,
                                tp=take_profit if send_tp_to_mt5 else None,
                                credentials=credentials
                            )
                            is_pending_order = True if success else False

                    log(f"")
                    if success:
                        log(f"  [SUCCESS] SUCCESS! Order placed")
                        log(f"  Ticket: {order_ticket}")
                        log(f"  Message: {msg}")

                        order_type_label = "Pending Order (LIMIT)" if is_pending_order else "Market Order"
                        send_telegram_async(f"[OK] <b>{order_type_label} Placed</b>\n"
                                      f"Ticket: {order_ticket}\n"
                                      f"Direction: {direction}\n"
                                      f"Lot: {final_lot}\n"
                                      f"{msg}")

                        # For MARKET orders: Get actual entry/sl/tp from MT5 position
                        # For PENDING orders: Will get after order fills
                        if not is_pending_order:
                            mt5_temp, _ = get_mt5_connection(credentials)
                            if mt5_temp:
                                positions = mt5_temp.positions_get(ticket=order_ticket)
                                if positions and len(positions) > 0:
                                    pos = positions[0]
                                    actual_entry = pos.price_open
                                    actual_sl = pos.sl
                                    actual_tp = pos.tp
                                    log(f"LIVE: Actual position - Entry={actual_entry:.5f}, SL={actual_sl:.5f}, TP={actual_tp:.5f}")
                                    # Override with actual prices for monitoring
                                    entry_price = actual_entry
                                    stop_loss = actual_sl
                                    take_profit = actual_tp
                                mt5_temp.shutdown()
                        else:
                            log(f"LIVE: Pending order placed - waiting for fill...")
                    else:
                        log(f"")
                        log(f"  [ERROR] FAILURE! Order placement failed", "ERROR")
                        log(f"  Error message: {msg}", "ERROR")

                        # Save signal for retry (handled in retry block above)
                        # Track candle time at failure to count elapsed candles
                        pending_signal = {
                            'direction': direction,
                            'entry': entry_price,
                            'sl': stop_loss,
                            'tp': take_profit,
                            'lot': final_lot,
                            'close_price': c,
                        }
                        retry_start_candle_time = candle['time']  # Current candle when failure occurred
                        retry_candles_elapsed = 0
                        retry_limit = args.pending_order_max_candles if args.pending_order_max_candles > 0 else 3
                        log(f"  [RETRY] Will retry in 1s (0/{retry_limit} candles elapsed)...", "WARN")
                        send_telegram_async(f"[RETRY] <b>Order Failed - Will Retry</b>\n{msg}\n0/{retry_limit} candles to retry")
                        mt5.shutdown()
                        time.sleep(1)
                        continue
                else:
                    log(f"  [TEST] TEST MODE: Order NOT placed (simulation only)")
                    log(f"TEST MODE: Order simulated (Lot={final_lot})")

                active_trade = {
                    'direction': direction,
                    'entry': entry_price,  # Now uses actual entry in LIVE mode
                    'sl': stop_loss,       # Now uses actual SL in LIVE mode
                    'tp': take_profit,     # Now uses actual TP in LIVE mode
                    'original_sl': stop_loss,  # Keep for reference
                    'close_price': c,      # Master candle close price (for breakeven_target=close)
                    'candles': 0,
                    'ticket': order_ticket,
                    'lot': final_lot,
                    'entry_time': now,
                    'entry_candle_time': candle['time'],  # Track entry candle to avoid re-checking it
                    'last_checked_candle_time': candle['time'],  # Track last checked candle
                    'sl_moved_to_breakeven': False,  # Track if SL has been moved to breakeven
                    'is_pending': is_pending_order,  # Track if this is a pending order
                    'candles_waited': 0,              # Track candles waited for pending order fill
                    'pending_placed_at': now,         # Wall-clock time when LIMIT was placed
                }

                log(f"")
                log(f"{'='*60}")
                log(f"[OK] Trade Created and Tracking Started")
                log(f"{'='*60}")
                log(f"  Direction: {direction}")
                log(f"  Entry: {entry_price:.5f}")
                log(f"  SL: {stop_loss:.5f}")
                log(f"  TP: {take_profit:.5f}")
                log(f"  Lot: {final_lot}")
                log(f"  Ticket: {order_ticket}")
                log(f"  Is Pending: {is_pending_order}")
                log(f"  Max Candles: {max_candles}")
                log(f"{'='*60}")
                log(f"")
                log(f"Bot will now monitor this trade until exit...")
                log(f"")

                last_entry_date = now.date()
                mt5.shutdown()

            # Monitor waiting_for_limit state (range_percent: waiting for price to return)
            elif waiting_for_limit:
                mt5, error = get_mt5_connection(credentials)
                if error:
                    time.sleep(0.1)
                    continue

                wfl = waiting_for_limit  # shorthand

                # Track candle progress
                try:
                    current_candle = get_current_candle(mt5, args.symbol, timeframe)
                except Exception as e:
                    log(f"Error getting current candle in wait state: {e}", "ERROR")
                    current_candle = None

                if current_candle and current_candle['time'] > wfl['last_checked_candle_time']:
                    wfl['candles_waited'] += 1
                    wfl['last_checked_candle_time'] = current_candle['time']
                    expire = args.pending_order_expire_candles
                    if expire > 0:
                        log(f"[WAIT] Waiting for LIMIT: {wfl['candles_waited']}/{expire} candles")
                    else:
                        log(f"[WAIT] Waiting for LIMIT: {wfl['candles_waited']} candles elapsed")

                    # NOTE: No SL check during WAIT — LIMIT not placed yet, no position exists.
                    # SL only applies after the trade is actually entered.

                    # Check if expired
                    if expire > 0 and wfl['candles_waited'] >= expire:
                        log(f"[SKIP] LIMIT not filled after {wfl['candles_waited']} candles — cancelling")
                        send_telegram_async(
                            f"[SKIP] <b>LIMIT Expired</b>\n"
                            f"Symbol: {args.symbol}\n"
                            f"Direction: {wfl['direction']}\n"
                            f"Price did not return to entry after {wfl['candles_waited']} candles\n"
                            f"Entry target: {wfl['entry_price']:.5f}\n\n"
                            f"Bot stopping...")
                        mt5.shutdown()
                        log("Bot stopping — LIMIT fill expired")
                        return

                # Check current price
                tick = mt5.symbol_info_tick(args.symbol)
                if tick:
                    # Check if price has returned to valid LIMIT side
                    can_place_now = False
                    if wfl['direction'] == "BUY" and tick.ask > wfl['entry_price']:
                        # BUY LIMIT: need ask > entry
                        can_place_now = True
                        log(f"[OK] Price returned! ask={tick.ask:.5f} > entry={wfl['entry_price']:.5f} — placing BUY LIMIT")
                    elif wfl['direction'] == "SELL" and tick.bid < wfl['entry_price']:
                        # SELL LIMIT: need bid < entry
                        can_place_now = True
                        log(f"[OK] Price returned! bid={tick.bid:.5f} < entry={wfl['entry_price']:.5f} — placing SELL LIMIT")

                    if can_place_now:
                        from src.orders import place_pending_order
                        log(f"")
                        log(f"  Order Type: PENDING ORDER (LIMIT)")
                        log(f"  Reason: Price returned to valid side after waiting {wfl['candles_waited']} candles")
                        log(f"  Calling place_pending_order()...")

                        success, msg, order_ticket = place_pending_order(
                            symbol=args.symbol,
                            direction=wfl['direction'],
                            volume=wfl['lot'],
                            entry_price=wfl['entry_price'],
                            sl=wfl['stop_loss'] if send_sl_to_mt5 else None,
                            tp=wfl['take_profit'] if send_tp_to_mt5 else None,
                            credentials=credentials
                        )

                        if success:
                            log(f"  [SUCCESS] LIMIT order placed! Ticket: {order_ticket}")
                            send_telegram_async(
                                f"[OK] <b>Pending Order (LIMIT) Placed</b>\n"
                                f"Ticket: {order_ticket}\n"
                                f"Direction: {wfl['direction']}\n"
                                f"Entry: {wfl['entry_price']:.5f}\n"
                                f"Waited {wfl['candles_waited']} candles for price to return\n"
                                f"{msg}")

                            # Transition to active_trade with pending order
                            active_trade = {
                                'direction': wfl['direction'],
                                'entry': wfl['entry_price'],
                                'sl': wfl['stop_loss'],
                                'tp': wfl['take_profit'],
                                'original_sl': wfl['stop_loss'],
                                'close_price': wfl['close_price'],  # Master candle close price
                                'candles': 0,
                                'ticket': order_ticket,
                                'lot': wfl['lot'],
                                'entry_time': now,
                                'entry_candle_time': wfl['entry_candle_time'],
                                'last_checked_candle_time': wfl['last_checked_candle_time'],
                                'sl_moved_to_breakeven': False,
                                'is_pending': True,
                                'candles_waited': 0,  # Reset for pending order fill tracking
                                'pending_placed_at': now,
                            }
                            waiting_for_limit = None  # Clear waiting state

                            log(f"")
                            log(f"{'='*60}")
                            log(f"[OK] Trade Created (after wait) and Tracking Started")
                            log(f"{'='*60}")
                            log(f"  Direction: {wfl['direction']}")
                            log(f"  Entry: {wfl['entry_price']:.5f}")
                            log(f"  SL: {wfl['stop_loss']:.5f}")
                            log(f"  TP: {wfl['take_profit']:.5f}")
                            log(f"  Lot: {wfl['lot']}")
                            log(f"  Ticket: {order_ticket}")
                            log(f"  Is Pending: True")
                            log(f"  Max Candles: {max_candles}")
                            log(f"{'='*60}")
                        else:
                            log(f"  [ERROR] LIMIT order placement failed: {msg}", "ERROR")
                            send_telegram_async(
                                f"[FAIL] <b>LIMIT Order Failed</b>\n"
                                f"{msg}\n\n"
                                f"Bot stopping...", is_error=True)
                            mt5.shutdown()
                            log("Bot stopping — LIMIT order failed after wait")
                            return

                mt5.shutdown()
                time.sleep(0.1)  # Fast poll while waiting

            # Monitor active trade
            elif active_trade:
                mt5, error = get_mt5_connection(credentials)
                if error:
                    time.sleep(0.1)  # Short sleep on error
                    continue

                # LIVE MODE: Check position/order status REALTIME
                if not args.test and active_trade['ticket']:
                    # If pending order: Check if filled or expired
                    if active_trade.get('is_pending', False):
                        from src.orders import check_order_status, cancel_order

                        log(f"DEBUG: Checking pending order status for ticket {active_trade['ticket']}")
                        try:
                            status, status_msg, position_data = check_order_status(active_trade['ticket'], credentials)
                            log(f"Pending order status: {status} - {status_msg}")
                        except Exception as e:
                            import traceback
                            log(f"ERROR in check_order_status: {e}", "ERROR")
                            log(f"Traceback: {traceback.format_exc()}", "ERROR")
                            status = 'ERROR'
                            status_msg = str(e)
                            position_data = None

                        if status == 'FILLED':
                            # Order filled! Use position data returned by check_order_status
                            log(f"[OK] Pending order FILLED! {status_msg}")
                            send_telegram_async(f"[OK] <b>Pending Order Filled</b>\n"
                                         f"Ticket: {active_trade['ticket']}\n"
                                         f"{status_msg}")

                            if position_data:
                                active_trade['entry'] = position_data['price_open']
                                # Only override SL/TP from MT5 if we actually sent them
                                if send_sl_to_mt5 and position_data['sl'] > 0:
                                    active_trade['sl'] = position_data['sl']
                                if send_tp_to_mt5 and position_data['tp'] > 0:
                                    active_trade['tp'] = position_data['tp']
                                # Use actual position ticket (may differ from order ticket on some brokers)
                                if position_data['ticket'] != active_trade['ticket']:
                                    log(f"Position ticket differs: order={active_trade['ticket']}, position={position_data['ticket']}")
                                active_trade['ticket'] = position_data['ticket']
                                active_trade['is_pending'] = False
                                log(f"Actual position - Entry={position_data['price_open']:.5f}, SL={active_trade['sl']:.5f}, TP={active_trade['tp']:.5f}")
                            else:
                                log("Warning: Position details not available after fill", "WARN")
                                active_trade['is_pending'] = False  # Still mark as filled

                            # Continue to monitoring loop (re-establish MT5 connection on next iteration)
                            mt5.shutdown()
                            time.sleep(0.1)
                            continue

                        elif status == 'PENDING':
                            # Still pending — track elapsed candles via wall-clock time
                            # (avoids copy_rates_from_pos which requires market data subscription)
                            expire = args.pending_order_expire_candles
                            tf_seconds = get_timeframe_seconds(timeframe)
                            placed_at = active_trade.get('pending_placed_at')
                            elapsed_seconds = (datetime.now(TIMEZONE) - placed_at).total_seconds() if placed_at else 0
                            expire_at_seconds = expire * tf_seconds if expire > 0 else float('inf')
                            seconds_to_expire = expire_at_seconds - elapsed_seconds

                            if expire > 0:
                                candles_elapsed = int(elapsed_seconds / tf_seconds)
                                # Log once per candle boundary
                                prev = active_trade.get('candles_waited', 0)
                                if candles_elapsed > prev:
                                    active_trade['candles_waited'] = candles_elapsed
                                    log(f"Pending order waiting: {candles_elapsed}/{expire} candles ({elapsed_seconds:.0f}s elapsed)")

                                if seconds_to_expire <= 0:
                                    log(f"[WARN] Pending order expired after {candles_elapsed} candles — attempting cancel")
                                    cancel_success, cancel_msg = cancel_order(active_trade['ticket'], credentials)
                                    if cancel_success:
                                        log(f"[OK] {cancel_msg}")
                                        send_telegram_async(
                                            f"[WARN] <b>Pending Order Expired</b>\n"
                                            f"Ticket: {active_trade['ticket']}\n"
                                            f"Not filled after {candles_elapsed} candles\n"
                                            f"Entry target: {active_trade['entry']:.5f}\n\n"
                                            f"Bot stopping...")
                                        mt5.shutdown()
                                        log("Bot stopping — pending order not filled")
                                        return
                                    else:
                                        # Cancel failed — order may have just filled, re-check status
                                        log(f"[WARN] Cancel failed ({cancel_msg}) — re-checking order status", "WARN")
                                        status2, status_msg2, position_data2 = check_order_status(active_trade['ticket'], credentials)
                                        if status2 == 'FILLED':
                                            log(f"[OK] Order filled just before cancel — continuing to monitor")
                                            if position_data2:
                                                active_trade['entry'] = position_data2['price_open']
                                                if send_sl_to_mt5 and position_data2['sl'] > 0:
                                                    active_trade['sl'] = position_data2['sl']
                                                if send_tp_to_mt5 and position_data2['tp'] > 0:
                                                    active_trade['tp'] = position_data2['tp']
                                                active_trade['ticket'] = position_data2['ticket']
                                            active_trade['is_pending'] = False
                                        else:
                                            log(f"[FAIL] Cancel failed and order still {status2} — stopping", "ERROR")
                                            mt5.shutdown()
                                            return

                            # Adaptive sleep: fast poll near expiry, slow poll when far away
                            # - >10s to expire: check every 2s (reduce MT5 connection overhead)
                            # - <=10s to expire: check every 100ms (tight loop to catch fill/expire)
                            if seconds_to_expire > 10:
                                sleep_duration = 2.0
                            else:
                                sleep_duration = 0.1

                            mt5.shutdown()
                            time.sleep(sleep_duration)
                            continue

                        elif status == 'CANCELLED':
                            # Order was cancelled (manually or by broker)
                            log(f"[WARN] Pending order cancelled: {status_msg}")
                            send_telegram_async(f"[WARN] <b>Pending Order Cancelled</b>\n"
                                         f"Ticket: {active_trade['ticket']}\n"
                                         f"{status_msg}\n\n"
                                         f"Bot stopping...")
                            mt5.shutdown()
                            log("Bot stopping - pending order cancelled")
                            return

                        else:  # ERROR
                            log(f"[ERROR] {status_msg}", "ERROR")
                            mt5.shutdown()
                            time.sleep(1)
                            continue

                    # Check if position still exists (MT5 may have closed it)
                    positions = mt5.positions_get(ticket=active_trade['ticket'])

                    if not positions or len(positions) == 0:
                        # Position was closed by MT5 (SL/TP hit or manual close)
                        from datetime import timedelta

                        try:
                            # Calculate history start time (5 minutes before entry)
                            entry_time = active_trade['entry_time']
                            if not isinstance(entry_time, datetime):
                                log(f"Invalid entry_time type: {type(entry_time)}", "ERROR")
                                entry_time = datetime.now(TIMEZONE)

                            history_start = entry_time - timedelta(minutes=5)
                            deals = mt5.history_deals_get(history_start, datetime.now(TIMEZONE))
                        except (ValueError, OSError, TypeError) as e:
                            log(f"Error calculating history time: {e}", "ERROR")
                            deals = None

                        exit_info = None
                        if deals:
                            for deal in deals:
                                if deal.position_id == active_trade['ticket'] and deal.entry == 1:
                                    pip_value = get_pip_value(args.symbol)
                                    if active_trade['direction'] == "BUY":
                                        pnl_pips = (deal.price - active_trade['entry']) / pip_value
                                    else:
                                        pnl_pips = (active_trade['entry'] - deal.price) / pip_value

                                    if abs(deal.price - active_trade['tp']) < pip_value:
                                        exit_type = "TP"
                                    elif abs(deal.price - active_trade['sl']) < pip_value * 2:  # Allow 2 pip tolerance
                                        exit_type = "SL"
                                    else:
                                        exit_type = "MANUAL/OTHER"

                                    exit_info = {
                                        'type': exit_type,
                                        'price': deal.price,
                                        'pnl_pips': pnl_pips,
                                        'pnl_usd': deal.profit,
                                        'time': datetime.fromtimestamp(deal.time, tz=TIMEZONE)
                                    }
                                    break

                        if exit_info:
                            log(f"[OK] Position closed by MT5: {exit_info['type']} @ {exit_info['price']:.5f}")
                            log(f"P&L: {exit_info['pnl_pips']:.1f} pips (${exit_info['pnl_usd']:.2f})")

                            pnl_emoji = "🟢" if exit_info['pnl_usd'] > 0 else "🔴" if exit_info['pnl_usd'] < 0 else "⚪"
                            pnl_sign = "+" if exit_info['pnl_usd'] > 0 else ""
                            duration_min = (exit_info['time'] - active_trade['entry_time']).total_seconds() / 60

                            send_telegram_async(
                                f"{pnl_emoji} <b>Position Closed: {exit_info['type']}</b>\n\n"
                                f"Symbol: {args.symbol}\n"
                                f"Direction: {active_trade['direction']}\n"
                                f"Lot: {active_trade['lot']}\n\n"
                                f"Entry: {active_trade['entry']:.5f}\n"
                                f"Exit: {exit_info['price']:.5f}\n\n"
                                f"{pnl_emoji} <b>P&L: {pnl_sign}{exit_info['pnl_pips']:.1f} pips ({pnl_sign}${exit_info['pnl_usd']:.2f})</b>\n"
                                f"Duration: {duration_min:.1f} min\n\n"
                                f"Bot stopping..."
                            )

                            # Log to orders CSV
                            from src.orders import log_order_close
                            log_order_close(
                                ticket=active_trade['ticket'], exit_type=exit_info['type'],
                                exit_price=exit_info['price'], profit=exit_info['pnl_usd'],
                                symbol=args.symbol, direction=active_trade['direction'],
                                entry_price=active_trade['entry'], pnl_pips=exit_info['pnl_pips'],
                                pnl_usd=exit_info['pnl_usd'], lot=active_trade['lot'],
                                strategy=args.strategy, user=args.user
                            )
                        else:
                            log("Position closed by MT5 (details unavailable)", "WARN")
                            log(f"  DEBUG: Trade state at close:")
                            log(f"    Entry: {active_trade['entry']:.5f}")
                            log(f"    SL: {active_trade['sl']:.5f} (type: {sl_type})")
                            log(f"    TP: {active_trade['tp']:.5f} (type: {tp_type})")
                            log(f"    Candles: {active_trade['candles']}/{max_candles if max_candles > 0 else '∞'}")
                            log(f"    SL sent to MT5: {send_sl_to_mt5}")
                            log(f"    TP sent to MT5: {send_tp_to_mt5}")
                            log(f"    BE moved: {active_trade.get('sl_moved_to_breakeven', False)}")
                            send_telegram_async(f"⚪ <b>Position Closed</b>\n\n"
                                         f"Ticket: {active_trade['ticket']}\n"
                                         f"Symbol: {args.symbol}\n"
                                         f"Entry: {active_trade['entry']:.5f}\n"
                                         f"SL: {active_trade['sl']:.5f} ({sl_type})\n"
                                         f"TP: {active_trade['tp']:.5f} ({tp_type})\n\n"
                                         f"Bot stopping...")

                        mt5.shutdown()
                        log("Bot stopping - position closed by MT5")
                        return

                    # Position still open - check for breakeven trigger using current price
                    if move_sl_to_breakeven and not active_trade['sl_moved_to_breakeven']:
                        tick = mt5.symbol_info_tick(args.symbol)
                        if tick:
                            current_price = tick.bid if active_trade['direction'] == "SELL" else tick.ask
                            entry = active_trade['entry']
                            tp = active_trade['tp']
                            # Breakeven target: entry price or master candle close price
                            be_target = active_trade.get('close_price', entry) if breakeven_target == "close" else entry

                            if active_trade['direction'] == "BUY":
                                tp_distance = tp - entry
                                trigger_price = entry + (tp_distance * breakeven_trigger_percent / 100)
                                if current_price >= trigger_price:
                                    new_sl = be_target
                                    request = {
                                        "action": mt5.TRADE_ACTION_SLTP,
                                        "symbol": args.symbol,
                                        "position": active_trade['ticket'],
                                        "sl": new_sl,
                                        "tp": tp
                                    }
                                    log(f"  [BE] Trigger hit! price={current_price:.5f} >= trigger={trigger_price:.5f}, moving SL to {new_sl:.5f}")
                                    result = mt5.order_send(request)
                                    if result.retcode == mt5.TRADE_RETCODE_DONE:
                                        log(f"[OK] SL moved to breakeven ({breakeven_target}): {new_sl:.5f}")
                                        send_telegram_async(f"[OK] <b>SL Moved to Breakeven</b>\n\n"
                                                     f"Symbol: {args.symbol}\n"
                                                     f"Entry: {entry:.5f}\n"
                                                     f"New SL: {new_sl:.5f} ({breakeven_target})\n\n"
                                                     f"Trade is now risk-free!")
                                        active_trade['sl'] = new_sl
                                        active_trade['sl_moved_to_breakeven'] = True
                                    else:
                                        log(f"  [ERROR] Failed to move SL to breakeven: {result.retcode} - {result.comment}", "ERROR")
                            else:  # SELL
                                tp_distance = entry - tp
                                trigger_price = entry - (tp_distance * breakeven_trigger_percent / 100)
                                if current_price <= trigger_price:
                                    new_sl = be_target
                                    request = {
                                        "action": mt5.TRADE_ACTION_SLTP,
                                        "symbol": args.symbol,
                                        "position": active_trade['ticket'],
                                        "sl": new_sl,
                                        "tp": tp
                                    }
                                    log(f"  [BE] Trigger hit! price={current_price:.5f} <= trigger={trigger_price:.5f}, moving SL to {new_sl:.5f}")
                                    result = mt5.order_send(request)
                                    if result.retcode == mt5.TRADE_RETCODE_DONE:
                                        log(f"[OK] SL moved to breakeven ({breakeven_target}): {new_sl:.5f}")
                                        send_telegram_async(f"[OK] <b>SL Moved to Breakeven</b>\n\n"
                                                     f"Symbol: {args.symbol}\n"
                                                     f"Entry: {entry:.5f}\n"
                                                     f"New SL: {new_sl:.5f} ({breakeven_target})\n\n"
                                                     f"Trade is now risk-free!")
                                        active_trade['sl'] = new_sl
                                        active_trade['sl_moved_to_breakeven'] = True
                                    else:
                                        log(f"  [ERROR] Failed to move SL to breakeven: {result.retcode} - {result.comment}", "ERROR")

                    # LIVE MODE: Candle-based monitoring (close_based exits + max_candles TIME exit)
                    # Must run here since LIVE mode doesn't reach test-mode monitoring below
                    needs_candle_monitoring = (max_candles > 0) or (not send_sl_to_mt5) or (not send_tp_to_mt5)
                    if needs_candle_monitoring:
                        candle = get_current_candle(mt5, args.symbol, timeframe)
                        if candle and candle['time'] > active_trade.get('last_checked_candle_time', active_trade['entry_candle_time']):
                            # New candle — increment counter
                            if candle['time'] > active_trade['entry_candle_time']:
                                active_trade['candles'] += 1
                                log(f"Monitoring: Candle {active_trade['candles']}/{max_candles if max_candles > 0 else '∞'}")
                                log(f"  Candle: O={candle['open']:.5f} H={candle['high']:.5f} L={candle['low']:.5f} C={candle['close']:.5f}")
                                log(f"  Trade: Entry={active_trade['entry']:.5f} SL={active_trade['sl']:.5f} TP={active_trade['tp']:.5f}")
                                if not send_sl_to_mt5:
                                    log(f"  [close_based SL] checking candle close vs SL...")
                                if not send_tp_to_mt5:
                                    log(f"  [close_based TP] checking candle close vs TP...")
                            active_trade['last_checked_candle_time'] = candle['time']

                            # Check close_based TP/SL exits on candle close
                            if (not send_sl_to_mt5) or (not send_tp_to_mt5):
                                from src.utils import check_exit
                                cb_exit_type, cb_exit_price = check_exit(
                                    direction=active_trade['direction'],
                                    candle={'high': candle['high'], 'low': candle['low'], 'close': candle['close']},
                                    tp=active_trade['tp'],
                                    sl=active_trade['sl'],
                                    tp_type=tp_type,
                                    sl_type=sl_type
                                )

                                if cb_exit_type:
                                    log(f"[{cb_exit_type} EXIT] close_based exit detected: {cb_exit_type} @ {cb_exit_price:.5f}")
                                    from src.orders import close_position
                                    success, msg = close_position(active_trade['ticket'], credentials=credentials)
                                    if success:
                                        log(f"{cb_exit_type} exit: Position {active_trade['ticket']} closed at market")
                                        send_telegram_async(
                                            f"{'🟢' if cb_exit_type == 'TP' else '🔴'} <b>{cb_exit_type} EXIT (close_based)</b>\n\n"
                                            f"Symbol: {args.symbol}\n"
                                            f"Direction: {active_trade['direction']}\n"
                                            f"Entry: {active_trade['entry']:.5f}\n"
                                            f"Exit trigger: {cb_exit_price:.5f}\n"
                                            f"Candle close: {candle['close']:.5f}\n\n"
                                            f"Position closed at market."
                                        )
                                    else:
                                        log(f"[ERROR] Failed to close position for {cb_exit_type} exit: {msg}", "ERROR")

                            # TIME exit: close position after max_candles
                            if max_candles > 0 and active_trade['candles'] >= max_candles:
                                log(f"[TIME EXIT] Max candles reached ({active_trade['candles']}/{max_candles}), closing position...")
                                from src.orders import close_position
                                success, msg = close_position(active_trade['ticket'], credentials=credentials)
                                if success:
                                    log(f"TIME exit: Position {active_trade['ticket']} closed")
                                    send_telegram_async(
                                        f"⏰ <b>TIME EXIT</b>\n\n"
                                        f"Symbol: {args.symbol}\n"
                                        f"Direction: {active_trade['direction']}\n"
                                        f"Max candles reached: {active_trade['candles']}/{max_candles}\n\n"
                                        f"Position closed at market."
                                    )
                                else:
                                    log(f"[ERROR] Failed to close position for TIME exit: {msg}", "ERROR")
                                # Don't return yet — let next loop iteration detect position gone
                                # and handle exit logging properly

                    mt5.shutdown()
                    # Fast loop for LIVE mode (100ms)
                    time.sleep(0.1)
                    continue

                # TEST MODE or LIVE without position: Use candle-based monitoring
                candle = get_current_candle(mt5, args.symbol, timeframe)
                if candle:
                    # Only process NEW candles (not the entry candle or already checked candles)
                    if candle['time'] <= active_trade['last_checked_candle_time']:
                        # Same candle as before, skip checking
                        mt5.shutdown()
                        time.sleep(0.1)  # Fast check
                        continue

                    # This is a NEW candle - increment counter and update last checked time
                    if candle['time'] > active_trade['entry_candle_time']:
                        active_trade['candles'] += 1
                        log(f"Monitoring: Candle {active_trade['candles']}/{max_candles}")

                    active_trade['last_checked_candle_time'] = candle['time']

                    h, l, c = candle['high'], candle['low'], candle['close']

                    # Check if we should move SL to breakeven
                    if move_sl_to_breakeven and not active_trade['sl_moved_to_breakeven']:
                        # Calculate trigger price (breakeven_trigger_percent% of TP distance)
                        entry = active_trade['entry']
                        tp = active_trade['tp']
                        # Breakeven target: entry price or master candle close price
                        be_target = active_trade.get('close_price', entry) if breakeven_target == "close" else entry

                        if active_trade['direction'] == "BUY":
                            tp_distance = tp - entry
                            trigger_price = entry + (tp_distance * breakeven_trigger_percent / 100)
                            # Check if price has reached trigger (use high for BUY)
                            if h >= trigger_price:
                                new_sl = be_target

                                # Modify SL in LIVE mode
                                if not args.test and active_trade['ticket']:
                                    # Modify position SL in MT5
                                    request = {
                                        "action": mt5.TRADE_ACTION_SLTP,
                                        "symbol": args.symbol,
                                        "position": active_trade['ticket'],
                                        "sl": new_sl,
                                        "tp": tp
                                    }
                                    result = mt5.order_send(request)
                                    if result.retcode == mt5.TRADE_RETCODE_DONE:
                                        log(f"[OK] SL moved to breakeven ({breakeven_target}): {new_sl:.5f} (was {active_trade['sl']:.5f})")
                                        send_telegram_async(f"[OK] <b>SL Moved to Breakeven</b>\n\n"
                                                     f"Symbol: {args.symbol}\n"
                                                     f"Direction: {active_trade['direction']}\n"
                                                     f"Entry: {entry:.5f}\n"
                                                     f"New SL: {new_sl:.5f} ({breakeven_target})\n"
                                                     f"Trigger: {trigger_price:.5f} ({breakeven_trigger_percent}% TP)\n\n"
                                                     f"Trade is now risk-free!")
                                        active_trade['sl'] = new_sl
                                        active_trade['sl_moved_to_breakeven'] = True
                                    else:
                                        log(f"[WARN] Failed to modify SL: {result.comment}", "WARN")
                                else:
                                    # TEST mode: just update tracking
                                    log(f"[OK] SL moved to breakeven ({breakeven_target}): {new_sl:.5f} (was {active_trade['sl']:.5f})")
                                    send_telegram_async(f"[OK] <b>SL Moved to Breakeven</b>\n\n"
                                                 f"Symbol: {args.symbol}\n"
                                                 f"Direction: {active_trade['direction']}\n"
                                                 f"Entry: {entry:.5f}\n"
                                                 f"New SL: {new_sl:.5f} ({breakeven_target})\n"
                                                 f"Trigger: {trigger_price:.5f} ({breakeven_trigger_percent}% TP)\n\n"
                                                 f"Trade is now risk-free!")
                                    active_trade['sl'] = new_sl
                                    active_trade['sl_moved_to_breakeven'] = True

                        else:  # SELL
                            tp_distance = entry - tp
                            trigger_price = entry - (tp_distance * breakeven_trigger_percent / 100)
                            # Check if price has reached trigger (use low for SELL)
                            if l <= trigger_price:
                                new_sl = be_target

                                # Modify SL in LIVE mode
                                if not args.test and active_trade['ticket']:
                                    # Modify position SL in MT5
                                    request = {
                                        "action": mt5.TRADE_ACTION_SLTP,
                                        "symbol": args.symbol,
                                        "position": active_trade['ticket'],
                                        "sl": new_sl,
                                        "tp": tp
                                    }
                                    result = mt5.order_send(request)
                                    if result.retcode == mt5.TRADE_RETCODE_DONE:
                                        log(f"[OK] SL moved to breakeven ({breakeven_target}): {new_sl:.5f} (was {active_trade['sl']:.5f})")
                                        send_telegram_async(f"[OK] <b>SL Moved to Breakeven</b>\n\n"
                                                     f"Symbol: {args.symbol}\n"
                                                     f"Direction: {active_trade['direction']}\n"
                                                     f"Entry: {entry:.5f}\n"
                                                     f"New SL: {new_sl:.5f} ({breakeven_target})\n"
                                                     f"Trigger: {trigger_price:.5f} ({breakeven_trigger_percent}% TP)\n\n"
                                                     f"Trade is now risk-free!")
                                        active_trade['sl'] = new_sl
                                        active_trade['sl_moved_to_breakeven'] = True
                                    else:
                                        log(f"[WARN] Failed to modify SL: {result.comment}", "WARN")
                                else:
                                    # TEST mode: just update tracking
                                    log(f"[OK] SL moved to breakeven ({breakeven_target}): {new_sl:.5f} (was {active_trade['sl']:.5f})")
                                    send_telegram_async(f"[OK] <b>SL Moved to Breakeven</b>\n\n"
                                                 f"Symbol: {args.symbol}\n"
                                                 f"Direction: {active_trade['direction']}\n"
                                                 f"Entry: {entry:.5f}\n"
                                                 f"New SL: {new_sl:.5f} ({breakeven_target})\n"
                                                 f"Trigger: {trigger_price:.5f} ({breakeven_trigger_percent}% TP)\n\n"
                                                 f"Trade is now risk-free!")
                                    active_trade['sl'] = new_sl
                                    active_trade['sl_moved_to_breakeven'] = True

                    exit_type = None
                    exit_price = None

                    # Check if position still exists in LIVE mode
                    position_closed = False
                    if not args.test and active_trade['ticket']:
                        positions = mt5.positions_get(ticket=active_trade['ticket'])
                        if not positions or len(positions) == 0:
                            # Position was closed by MT5 (SL/TP hit)
                            # Get closed position details from history
                            from datetime import timedelta

                            try:
                                entry_time = active_trade['entry_time']
                                if not isinstance(entry_time, datetime):
                                    log(f"Invalid entry_time type: {type(entry_time)}", "ERROR")
                                    entry_time = datetime.now(TIMEZONE)

                                history_start = entry_time - timedelta(minutes=5)
                                deals = mt5.history_deals_get(history_start, datetime.now(TIMEZONE))
                            except (ValueError, OSError, TypeError) as e:
                                log(f"Error calculating history time: {e}", "ERROR")
                                deals = None

                            exit_info = None
                            if deals:
                                for deal in deals:
                                    if deal.position_id == active_trade['ticket'] and deal.entry == 1:  # Exit deal
                                        pip_value = get_pip_value(args.symbol)
                                        if active_trade['direction'] == "BUY":
                                            pnl_pips = (deal.price - active_trade['entry']) / pip_value
                                        else:
                                            pnl_pips = (active_trade['entry'] - deal.price) / pip_value

                                        # Determine exit type
                                        if abs(deal.price - active_trade['tp']) < pip_value:
                                            exit_type = "TP"
                                        elif abs(deal.price - active_trade['sl']) < pip_value:
                                            exit_type = "SL"
                                        else:
                                            exit_type = "MANUAL/OTHER"

                                        exit_info = {
                                            'type': exit_type,
                                            'price': deal.price,
                                            'pnl_pips': pnl_pips,
                                            'pnl_usd': deal.profit,
                                            'time': datetime.fromtimestamp(deal.time, tz=TIMEZONE)
                                        }
                                        break

                            if exit_info:
                                log(f"[OK] Position closed: {exit_info['type']} @ {exit_info['price']:.5f}")
                                log(f"P&L: {exit_info['pnl_pips']:.1f} pips (${exit_info['pnl_usd']:.2f})")

                                pnl_emoji = "🟢" if exit_info['pnl_usd'] > 0 else "🔴" if exit_info['pnl_usd'] < 0 else "⚪"
                                pnl_sign = "+" if exit_info['pnl_usd'] > 0 else ""
                                duration_min = (exit_info['time'] - active_trade['entry_time']).total_seconds() / 60

                                send_telegram_async(
                                    f"{pnl_emoji} <b>Position Closed: {exit_info['type']}</b>\n\n"
                                    f"Symbol: {args.symbol}\n"
                                    f"Direction: {active_trade['direction']}\n"
                                    f"Lot: {active_trade['lot']}\n\n"
                                    f"Entry: {active_trade['entry']:.5f}\n"
                                    f"Exit: {exit_info['price']:.5f}\n\n"
                                    f"{pnl_emoji} <b>P&L: {pnl_sign}{exit_info['pnl_pips']:.1f} pips ({pnl_sign}${exit_info['pnl_usd']:.2f})</b>\n"
                                    f"Duration: {duration_min:.1f} min\n\n"
                                    f"Bot stopping..."
                                )

                                # Log to orders CSV
                                from src.orders import log_order_close
                                log_order_close(
                                    ticket=active_trade['ticket'], exit_type=exit_info['type'],
                                    exit_price=exit_info['price'], profit=exit_info['pnl_usd'],
                                    symbol=args.symbol, direction=active_trade['direction'],
                                    entry_price=active_trade['entry'], pnl_pips=exit_info['pnl_pips'],
                                    pnl_usd=exit_info['pnl_usd'], lot=active_trade['lot'],
                                    strategy=args.strategy, user=args.user
                                )
                            else:
                                log("Position closed by MT5 (details unavailable)", "WARN")
                                log(f"  DEBUG: Trade state at close:")
                                log(f"    Entry: {active_trade['entry']:.5f}")
                                log(f"    SL: {active_trade['sl']:.5f} (type: {sl_type})")
                                log(f"    TP: {active_trade['tp']:.5f} (type: {tp_type})")
                                log(f"    Candles: {active_trade['candles']}/{max_candles if max_candles > 0 else '∞'}")
                                log(f"    SL sent to MT5: {send_sl_to_mt5}")
                                log(f"    TP sent to MT5: {send_tp_to_mt5}")
                                log(f"    BE moved: {active_trade.get('sl_moved_to_breakeven', False)}")
                                send_telegram_async(f"⚪ <b>Position Closed</b>\n\n"
                                             f"Ticket: {active_trade['ticket']}\n"
                                             f"Symbol: {args.symbol}\n"
                                             f"Entry: {active_trade['entry']:.5f}\n"
                                             f"SL: {active_trade['sl']:.5f} ({sl_type})\n"
                                             f"TP: {active_trade['tp']:.5f} ({tp_type})\n\n"
                                             f"Bot stopping...")

                            # Bot should stop after position is closed
                            log("Bot stopping - position closed")
                            mt5.shutdown()
                            return  # Exit the bot completely

                    if not position_closed:
                        # Check exit conditions for both TEST and LIVE modes
                        # LIVE mode needs this for close-based exits (MT5 only handles price-based)
                        from src.utils import check_exit

                        exit_type, exit_price = check_exit(
                            direction=active_trade['direction'],
                            candle={'high': h, 'low': l, 'close': c},
                            tp=active_trade['tp'],
                            sl=active_trade['sl'],
                            tp_type=tp_type,
                            sl_type=sl_type
                        )

                        # In LIVE mode with exit signal, close the position
                        if not args.test and exit_type and active_trade['ticket']:
                            from src.orders import close_position
                            success, msg = close_position(active_trade['ticket'], credentials=credentials)
                            if success:
                                log(f"{exit_type} exit: Position {active_trade['ticket']} closed at {exit_price:.5f}")
                            else:
                                log(f"Failed to close position: {msg}", "ERROR")
                                # Still exit the trade tracking even if close failed
                                exit_type = exit_type  # Keep exit type

                        # Time limit check (both TEST and LIVE modes)
                        if not exit_type and max_candles > 0 and active_trade['candles'] >= max_candles:
                            exit_type = "TIME"
                            exit_price = c

                            # Close position in LIVE mode
                            if not args.test and active_trade['ticket']:
                                from src.orders import close_position
                                success, msg = close_position(active_trade['ticket'], credentials=credentials)
                                if success:
                                    log(f"TIME exit: Position {active_trade['ticket']} closed")
                                else:
                                    log(f"Failed to close position: {msg}", "ERROR")

                        if exit_type:
                            # Calculate P&L in pips and USD
                            pip_value = get_pip_value(args.symbol)
                            if active_trade['direction'] == "BUY":
                                pnl_pips = (exit_price - active_trade['entry']) / pip_value
                            else:
                                pnl_pips = (active_trade['entry'] - exit_price) / pip_value

                            # Calculate P&L in USD
                            from src.utils import get_pip_value_per_lot
                            pip_value_per_lot = get_pip_value_per_lot(args.symbol)
                            pnl_usd = active_trade['lot'] * pnl_pips * pip_value_per_lot

                            # Calculate duration
                            duration_minutes = (now - active_trade['entry_time']).total_seconds() / 60

                            log(f"[OK] Exit: {exit_type} @ {exit_price:.5f}, P&L: {pnl_pips:.1f} pips (${pnl_usd:.2f})")

                            pnl_emoji = "🟢" if pnl_usd > 0 else "🔴" if pnl_usd < 0 else "⚪"
                            pnl_sign = "+" if pnl_usd > 0 else ""

                            send_telegram_async(
                                f"{pnl_emoji} <b>Position Closed: {exit_type}</b>\n\n"
                                f"Symbol: {args.symbol}\n"
                                f"Direction: {active_trade['direction']}\n"
                                f"Lot: {active_trade['lot']}\n\n"
                                f"Entry: {active_trade['entry']:.5f}\n"
                                f"Exit: {exit_price:.5f}\n\n"
                                f"{pnl_emoji} <b>P&L: {pnl_sign}{pnl_pips:.1f} pips ({pnl_sign}${pnl_usd:.2f})</b>\n"
                                f"Duration: {duration_minutes:.1f} min\n"
                                f"Candles held: {active_trade['candles']}\n\n"
                                f"Bot stopping..."
                            )

                            # Log to orders CSV
                            from src.orders import log_order_close
                            log_order_close(
                                ticket=active_trade.get('ticket', 0), exit_type=exit_type,
                                exit_price=exit_price, profit=pnl_usd,
                                symbol=args.symbol, direction=active_trade['direction'],
                                entry_price=active_trade['entry'], pnl_pips=pnl_pips,
                                pnl_usd=pnl_usd, lot=active_trade['lot'],
                                strategy=args.strategy, user=args.user
                            )

                            active_trade = None

                            # Stop bot after exit (as designed)
                            log("Bot stopping - trade exited")
                            mt5.shutdown()
                            return  # Exit the bot completely

                mt5.shutdown()

            # Sleep before next check
            # Use shorter interval when monitoring active trade for faster response
            if active_trade:
                check_interval = min(args.interval, 5)  # Max 5 seconds when monitoring
            else:
                check_interval = args.interval  # Full interval when waiting for entry
            time.sleep(check_interval)

    except KeyboardInterrupt:
        log("Bot stopped by user")
        send_telegram_async("Bot Stopped (manual)")
        time.sleep(1)  # Allow async telegram to send before exit
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        log(f"Bot error: {e}", "ERROR")
        log(f"Traceback:\n{error_trace}", "ERROR")
        send_telegram_async(f"Bot Error: {e}\n\nCheck logs for details", is_error=True)
        time.sleep(1)  # Allow async telegram to send before exit
        raise


if __name__ == "__main__":
    args = get_args()
    run_bot(args)
