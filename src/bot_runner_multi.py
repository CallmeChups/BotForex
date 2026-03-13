"""
Bot Runner Multi - Multiple Master Candle Strategy Bot

Monitors a time window and enters trades on each qualifying candle within the window.
Multiple trades can be active simultaneously.

Usage:
    python src/bot_runner_multi.py --symbol XAUUSD --window_start 09:00 --window_end 11:00
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




def get_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="BotForex Multiple Master Candle Bot")

    # Required
    parser.add_argument("--strategy", type=str, required=True,
                        help="Strategy ID (e.g., multiple_master_candle)")
    parser.add_argument("--symbol", type=str, required=True,
                        help="Trading symbol (e.g., XAUUSD)")
    parser.add_argument("--user", type=str, required=True,
                        help="Username for MT5 credentials")

    # Window params (replaces --entry_time from bot_runner.py)
    parser.add_argument("--window_start", type=str, required=True,
                        help="Window start HH:MM (candle open times)")
    parser.add_argument("--window_end", type=str, required=True,
                        help="Window end HH:MM (exclusive, candle open times)")
    parser.add_argument("--priority_direction", type=str, default="auto",
                        choices=["BUY", "SELL", "auto"],
                        help="Priority direction: BUY, SELL, or auto (first candle locks direction)")

    # Optional parameters (override strategy defaults)
    parser.add_argument("--lot_size", type=float, default=None)
    parser.add_argument("--sl_pips", type=float, default=None)
    parser.add_argument("--rr_ratio", type=float, default=None)
    parser.add_argument("--max_candles", type=int, default=None)
    parser.add_argument("--timeframe", type=str, default=None)
    parser.add_argument("--entry_mode", type=str, default=None,
                        choices=["close", "range_percent", "signal"])
    parser.add_argument("--entry_percent", type=float, default=None)
    parser.add_argument("--buffer_k", type=float, default=None)
    parser.add_argument("--lot_mode", type=str, default=None,
                        choices=["fixed", "flex"])
    parser.add_argument("--starting_equity", type=float, default=None)
    parser.add_argument("--risk_mode", type=str, default=None,
                        choices=["percent", "amount", "fixed_amount"])
    parser.add_argument("--risk_percent", type=float, default=None)
    parser.add_argument("--risk_amount", type=float, default=None)
    parser.add_argument("--risk_compounding", type=int, default=None)
    parser.add_argument("--tp_type", type=str, default=None,
                        choices=["price_based", "close_based"])
    parser.add_argument("--sl_type", type=str, default=None,
                        choices=["price_based", "close_based"])

    # Move SL to Breakeven
    parser.add_argument("--move_sl_to_breakeven", type=int, default=None)
    parser.add_argument("--breakeven_trigger_percent", type=float, default=None)
    parser.add_argument("--breakeven_target", type=str, default="entry")

    # Pending order expiry (no retry logic in multi — failed placements skipped)
    parser.add_argument("--pending_order_expire_candles", type=int, default=0,
                        help="Cancel LIMIT if not filled after N candles (0=wait indefinitely)")

    # Bot control
    parser.add_argument("--test", type=int, default=1,
                        help="Test mode: 1=test (no real trades), 0=live")
    parser.add_argument("--interval", type=int, default=1,
                        help="Check interval in seconds (default: 1)")

    return parser.parse_args()


def is_candle_in_window(now: datetime, window_start: str, window_end: str, timeframe: str) -> bool:
    """Check if a candle just closed within the window.

    Window refers to candle OPEN times.
    E.g., window 09:00-11:00 with M5: candles opening 09:00..10:55 close at 09:05..11:00.
    A candle that just closed at time `now` has open_time = now - timeframe_minutes.
    Returns True if open_time falls within [window_start, window_end).
    """
    tf_map = {
        'M1': 1, 'M5': 5, 'M15': 15, 'M30': 30,
        'H1': 60, 'H4': 240, 'D1': 1440
    }
    tf_mins = tf_map.get(timeframe, 5)

    # Candle open time in total minutes from midnight
    open_total = now.hour * 60 + now.minute - tf_mins

    ws_h, ws_m = map(int, window_start.split(":"))
    we_h, we_m = map(int, window_end.split(":"))
    start_total = ws_h * 60 + ws_m
    end_total = we_h * 60 + we_m

    return start_total <= open_total < end_total


def run_bot(args):
    """Main bot loop - multi-trade version for Multiple Master Candle Strategy"""
    from src.strategy_manager import get_strategy, get_strategy_parameters
    from src.auth import get_user_mt5_credentials

    bot_id = f"{args.strategy}_{args.symbol}_{args.user}_{os.getpid()}"
    log_path = setup_logging(bot_id)

    log(f"Starting bot (MULTI): {args.strategy} | {args.symbol} | user={args.user}")
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

    # Parameters (same defaults as bot_runner.py)
    sl_pips = args.sl_pips or params.get('sl_pips', 30)
    rr_ratio = args.rr_ratio or params.get('rr_ratio', 2.0)
    lot_size = args.lot_size or params.get('lot_size', 0.01)
    max_candles = args.max_candles or params.get('max_candles', 7)
    timeframe = args.timeframe or params.get('timeframe', 'M5')

    entry_mode = args.entry_mode or 'close'
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

    send_sl_to_mt5 = (sl_type == "price_based")
    send_tp_to_mt5 = (tp_type == "price_based")

    move_sl_to_breakeven = bool(args.move_sl_to_breakeven) if args.move_sl_to_breakeven is not None else False
    breakeven_trigger_percent = args.breakeven_trigger_percent if args.breakeven_trigger_percent is not None else 50.0
    breakeven_target = args.breakeven_target or "entry"

    window_start = args.window_start
    window_end = args.window_end
    priority_direction = args.priority_direction

    we_h, we_m = map(int, window_end.split(":"))
    window_end_total = we_h * 60 + we_m

    tf_map_mins = {'M1': 1, 'M5': 5, 'M15': 15, 'M30': 30, 'H1': 60, 'H4': 240, 'D1': 1440}
    tf_mins = tf_map_mins.get(timeframe, 5)

    log(f"[STEP 2/5] Configuration:")
    log(f"  Window: {window_start} - {window_end}")
    log(f"  Priority Direction: {priority_direction}")
    log(f"  RR Ratio: {rr_ratio}")
    log(f"  Max Candles: {max_candles}")
    log(f"  Buffer K: {buffer_k} points")
    log(f"  Timeframe: {timeframe}")
    log(f"  Entry Mode: {entry_mode}")
    if entry_mode == 'range_percent':
        log(f"  Entry Percent: {entry_percent}%")
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

    log(f"[STEP 3/5] Getting MT5 credentials for user: {args.user}")
    credentials = get_user_mt5_credentials(args.user)

    if not credentials:
        log(f"[ERROR] CRITICAL ERROR: No credentials found for user: {args.user}", "ERROR")
        log(f"Solution: Go to Settings page and configure MT5 account", "ERROR")
        return

    if not credentials.get('login'):
        log(f"[ERROR] CRITICAL ERROR: MT5 login not configured for user: {args.user}", "ERROR")
        log(f"Credentials object: {credentials}", "ERROR")
        log(f"Solution: Go to Settings page and configure MT5 account", "ERROR")
        return

    log(f"[OK] MT5 credentials loaded:")
    log(f"  Login: {credentials.get('login')}")
    log(f"  Server: {credentials.get('server')}")
    log(f"  Password: {'*' * len(credentials.get('password', ''))}")

    log(f"[STEP 4/5] Sending startup notification to Telegram")
    mode_label = "[TEST] TEST" if args.test else "[LIVE] LIVE"
    lot_info = f"Lot={lot_size}" if lot_mode == 'fixed' else f"Risk={risk_percent}% {'(Compound)' if risk_compounding else '(Fixed)'}"
    be_status = f"[OK] BE@{breakeven_trigger_percent:.0f}%" if move_sl_to_breakeven else "x"
    telegram_sent = send_telegram(
        f"<b>Bot Started (MULTI)</b>\n\n"
        f"<b>{mode_label}</b> | {strategy.get('name')}\n"
        f"[SIGNAL] {args.symbol} | {timeframe}\n"
        f"User: {args.user}\n\n"
        f"Window: {window_start} - {window_end}\n"
        f"Priority: {priority_direction}\n"
        f"Mode: {entry_mode.title()}"
        f"{f'({entry_percent}%)' if entry_mode == 'range_percent' else ''}\n"
        f"Lot: {lot_info}\n"
        f"RR: {rr_ratio}:1 | Buffer: {buffer_k}pt\n"
        f"TP: {tp_type[:5]} | SL: {sl_type[:5]}\n"
        f"Breakeven: {be_status}\n"
        f"Max: {max_candles}c | Check: {args.interval}s"
    )
    if telegram_sent:
        log(f"[OK] Telegram notification sent")
    else:
        log(f"Telegram notification failed (not critical)", "WARN")

    # Multi-trade state
    active_trades = []       # List of active trade dicts
    waiting_for_limits = []  # List of waiting_for_limit states (range_percent mode)
    priority_locked = None   # For auto mode, reset each day
    last_entry_date = None
    last_checked_candle_time = datetime.min.replace(tzinfo=TIMEZONE)
    try:
        log(f"")
        sep = '='*60
        log(f"[STEP 5/5] BOT MAIN LOOP STARTED (MULTI)")
        log(f"[OK] Window: {window_start} - {window_end}")
        log(f"[OK] Timeframe: {timeframe}")
        log(f"[OK] Symbol: {args.symbol}")
        log(f"[OK] Priority: {priority_direction}")
        log(f"[OK] Current time: {datetime.now(TIMEZONE).strftime('%H:%M:%S %d/%m/%Y')}")
        log(f"")
        log(f"Bot is now running and monitoring...")
        log(f"")

        loop_count = 0

        while True:
            now = datetime.now(TIMEZONE)
            loop_count += 1
            now_total = now.hour * 60 + now.minute
            past_window_end = now_total >= window_end_total + tf_mins

            if loop_count % 30 == 0:
                log(f"[Loop {loop_count}] {now.strftime('%H:%M:%S')} | "
                    f"Active: {len(active_trades)} | WaitLimit: {len(waiting_for_limits)} | "
                    f"PastWindow: {past_window_end} | Priority: {priority_locked}")

            if last_entry_date != now.date():
                priority_locked = None
                last_entry_date = now.date()
                log(f"New trading day - priority lock reset")

            # ================================================================
            # SECTION 1: ENTRY DETECTION
            # ================================================================
            if is_candle_in_window(now, window_start, window_end, timeframe):
                mt5, error = get_mt5_connection(credentials)
                if error:
                    log(f"[ERROR] MT5 connection failed (entry check): {error}", "ERROR")
                else:
                    start_check = time.time()
                    candle = None
                    attempts = 0

                    while time.time() - start_check < 2.0:
                        attempts += 1
                        temp_candle = get_current_candle(mt5, args.symbol, timeframe)
                        if temp_candle and temp_candle['time'] > last_checked_candle_time:
                            candle = temp_candle
                            log(f"[OK] New candle (attempts={attempts})")
                            break

                    if candle:
                        last_checked_candle_time = candle['time']
                        o = candle['open']
                        h = candle['high']
                        l = candle['low']
                        c = candle['close']
                        pip_value = get_pip_value(args.symbol)
                        point_value = get_point_value(args.symbol)
                        buffer_offset = buffer_k * point_value
                        candle_body = abs(c - o)

                        log(f"")
                        log(f"[CANDLE] {candle['time'].strftime('%H:%M')} "
                            f"O={o:.5f} H={h:.5f} L={l:.5f} C={c:.5f}")

                        if c == o:
                            log(f"Doji candle - no trade")
                        else:
                            direction = "BUY" if c > o else "SELL"
                            trade_id = f"{direction}_{candle['time'].strftime('%H%M')}"
                            if priority_direction == "auto" and priority_locked is None:
                                priority_locked = direction
                                log(f"[{trade_id}] Auto priority locked: {priority_locked}")

                            effective = priority_locked if priority_direction == "auto" else priority_direction
                            log(f"[{trade_id}] Direction: {direction} | Effective: {effective}")

                            if direction != effective:
                                log(f"[{trade_id}] {direction} != {effective} - skipping")
                            else:
                                log(f"[{trade_id}] Direction matches - processing signal")

                                # ---- Calculate entry price ----
                                if direction == "BUY":
                                    if entry_mode == "range_percent":
                                        entry_price = c - (entry_percent / 100) * candle_body
                                        log(f"[{trade_id}] Entry = C - {entry_percent}% x body = {entry_price:.5f}")
                                    else:
                                        entry_price = c
                                        log(f"[{trade_id}] Entry = Close = {entry_price:.5f}")
                                    stop_loss = l - buffer_offset
                                    risk = entry_price - stop_loss
                                    take_profit = entry_price + (risk * rr_ratio)
                                    log(f"[{trade_id}] BUY: Entry={entry_price:.5f}"
                                        f" SL={stop_loss:.5f} TP={take_profit:.5f}"
                                        f" Risk={(entry_price-stop_loss)/pip_value:.1f}pips")
                                else:  # SELL
                                    if entry_mode == "range_percent":
                                        entry_price = c + (entry_percent / 100) * candle_body
                                        log(f"[{trade_id}] Entry = C + {entry_percent}% x body = {entry_price:.5f}")
                                    else:
                                        entry_price = c
                                        log(f"[{trade_id}] Entry = Close = {entry_price:.5f}")
                                    stop_loss = h + buffer_offset
                                    risk = stop_loss - entry_price
                                    take_profit = entry_price - (risk * rr_ratio)
                                    log(f"[{trade_id}] SELL: Entry={entry_price:.5f}"
                                        f" SL={stop_loss:.5f} TP={take_profit:.5f}"
                                        f" Risk={(stop_loss-entry_price)/pip_value:.1f}pips")

                                # ---- Calculate lot size ----
                                if lot_mode == 'flex':
                                    from src.backtest import calculate_flex_lot_size
                                    sl_pips_actual = (
                                        (entry_price - stop_loss) / pip_value if direction == "BUY"
                                        else (stop_loss - entry_price) / pip_value
                                    )
                                    account_info = mt5.account_info()
                                    current_equity = account_info.equity if account_info else starting_equity
                                    log(f"[{trade_id}] Equity: {current_equity:.2f}")
                                    if risk_mode == "fixed_amount":
                                        final_lot = calculate_flex_lot_size(
                                            equity=current_equity, risk_percent=0,
                                            sl_pips=sl_pips_actual, symbol=args.symbol,
                                            risk_amount=risk_amount
                                        )
                                    else:
                                        equity_for_risk = starting_equity if not risk_compounding else current_equity
                                        final_lot = calculate_flex_lot_size(
                                            equity=equity_for_risk, risk_percent=risk_percent,
                                            sl_pips=sl_pips_actual, symbol=args.symbol
                                        )
                                else:
                                    final_lot = lot_size

                                log(f"[{trade_id}] Lot: {final_lot}")

                                send_telegram_async(
                                    f"<b>[{trade_id}] Signal: {direction}</b>\n"
                                    f"SL: {stop_loss:.2f} TP: {take_profit:.2f} Lot: {final_lot}"
                                )

                                order_ticket = None
                                is_pending_order = False
                                add_to_active = False

                                if not args.test:
                                    log(f"[{trade_id}] [LIVE] Placing order...")
                                    if entry_mode == "range_percent":
                                        from src.orders import place_pending_order
                                        tick = mt5.symbol_info_tick(args.symbol)
                                        can_place_limit = True
                                        if tick:
                                            if direction == "BUY" and tick.ask <= entry_price:
                                                can_place_limit = False
                                            elif direction == "SELL" and tick.bid >= entry_price:
                                                can_place_limit = False
                                        if not can_place_limit:
                                            price_past_sl = False
                                            if sl_type == "price_based":
                                                if tick:
                                                    if direction == "BUY" and tick.ask <= stop_loss:
                                                        price_past_sl = True
                                                    elif direction == "SELL" and tick.bid >= stop_loss:
                                                        price_past_sl = True
                                            else:
                                                # close_based: check candle close vs SL
                                                if direction == "BUY" and c <= stop_loss:
                                                    price_past_sl = True
                                                elif direction == "SELL" and c >= stop_loss:
                                                    price_past_sl = True
                                            if price_past_sl:
                                                log(f"[{trade_id}] Trade invalidated")
                                            else:
                                                waiting_for_limits.append({
                                                    'trade_id': trade_id,
                                                    'direction': direction,
                                                    'entry_price': entry_price,
                                                    'stop_loss': stop_loss,
                                                    'take_profit': take_profit,
                                                    'lot': final_lot,
                                                    'close_price': c,
                                                    'candles_waited': 0,
                                                    'last_checked_candle_time': candle['time'],
                                                    'entry_candle_time': candle['time'],
                                                })
                                                log(f"[{trade_id}] WAIT FOR LIMIT entered")
                                        else:
                                            success, msg, order_ticket = place_pending_order(
                                                symbol=args.symbol, direction=direction,
                                                volume=final_lot, entry_price=entry_price,
                                                sl=stop_loss if send_sl_to_mt5 else None,
                                                tp=take_profit if send_tp_to_mt5 else None,
                                                credentials=credentials
                                            )
                                            is_pending_order = True if success else False
                                            if success:
                                                log(f"[{trade_id}] LIMIT ok: {order_ticket}")
                                                add_to_active = True
                                            else:
                                                log(f"[{trade_id}] LIMIT failed: {msg}")
                                    else:  # entry_mode close
                                        from src.orders import place_pending_order, place_order
                                        tick = mt5.symbol_info_tick(args.symbol)
                                        use_market_fallback = False
                                        if tick:
                                            if direction == "BUY" and tick.ask <= entry_price:
                                                use_market_fallback = True
                                                log(f"[{trade_id}] Price at/below entry: ask={tick.ask:.5f}")
                                            elif direction == "SELL" and tick.bid >= entry_price:
                                                use_market_fallback = True
                                                log(f"[{trade_id}] Price at/above entry: bid={tick.bid:.5f}")
                                        if use_market_fallback:
                                            price_past_sl = False
                                            if sl_type == "price_based":
                                                if tick:
                                                    if direction == "BUY" and tick.ask <= stop_loss:
                                                        price_past_sl = True
                                                    elif direction == "SELL" and tick.bid >= stop_loss:
                                                        price_past_sl = True
                                            else:
                                                # close_based: check candle close vs SL
                                                if direction == "BUY" and c <= stop_loss:
                                                    price_past_sl = True
                                                elif direction == "SELL" and c >= stop_loss:
                                                    price_past_sl = True
                                            if price_past_sl:
                                                log(f"[{trade_id}] Price past SL - skipping")
                                                send_telegram_async(f"[{trade_id}] [SKIP] Price past SL")
                                            else:
                                                log(f"[{trade_id}] Market order (price at/past entry)")
                                                success, msg, order_ticket = place_order(
                                                    symbol=args.symbol, direction=direction, volume=final_lot,
                                                    sl=stop_loss if send_sl_to_mt5 else None,
                                                    tp=take_profit if send_tp_to_mt5 else None,
                                                    credentials=credentials,
                                                    theoretical_entry=entry_price
                                                )
                                                is_pending_order = False
                                                if success:
                                                    mt5_temp, _ = get_mt5_connection(credentials)
                                                    if mt5_temp:
                                                        positions = mt5_temp.positions_get(ticket=order_ticket)
                                                        if positions and len(positions) > 0:
                                                            pos = positions[0]
                                                            entry_price = pos.price_open
                                                            if send_sl_to_mt5 and pos.sl > 0:
                                                                stop_loss = pos.sl
                                                            if send_tp_to_mt5 and pos.tp > 0:
                                                                take_profit = pos.tp
                                                            log(f"[{trade_id}] Actual: Entry={entry_price:.5f}")
                                                        mt5_temp.shutdown()
                                                    log(f"[{trade_id}] Market order! Ticket: {order_ticket}")
                                                    send_telegram_async(f"[{trade_id}] [OK] Market Order Placed, Ticket: {order_ticket}")
                                                    add_to_active = True
                                                else:
                                                    log(f"[{trade_id}] Market order failed: {msg}", "ERROR")
                                                    send_telegram_async(f"[{trade_id}] [FAIL] {msg}", is_error=True)
                                        else:  # LIMIT at close price
                                            if not send_sl_to_mt5:
                                                log(f"[{trade_id}] SL is close_based - omitting from broker")
                                            if not send_tp_to_mt5:
                                                log(f"[{trade_id}] TP is close_based - omitting from broker")
                                            success, msg, order_ticket = place_pending_order(
                                                symbol=args.symbol, direction=direction, volume=final_lot,
                                                entry_price=entry_price,
                                                sl=stop_loss if send_sl_to_mt5 else None,
                                                tp=take_profit if send_tp_to_mt5 else None,
                                                credentials=credentials
                                            )
                                            is_pending_order = True if success else False
                                            if success:
                                                log(f"[{trade_id}] LIMIT placed! Ticket: {order_ticket}")
                                                send_telegram_async(f"[{trade_id}] [OK] LIMIT Placed, Ticket: {order_ticket}")
                                                add_to_active = True
                                            else:
                                                log(f"[{trade_id}] Order failed: {msg}", "ERROR")
                                                send_telegram_async(f"[{trade_id}] [FAIL] {msg}", is_error=True)
                                else:  # TEST MODE
                                    log(f"[{trade_id}] [TEST] Order simulated (Lot={final_lot})")
                                    add_to_active = True

                                # Add to active_trades if placement succeeded
                                if add_to_active:
                                    active_trades.append({
                                        'trade_id': trade_id,
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
                                        'entry_candle_time': candle['time'],
                                        'last_checked_candle_time': candle['time'],
                                        'sl_moved_to_breakeven': False,
                                        'is_pending': is_pending_order,
                                        'candles_waited': 0,
                                        'pending_placed_at': now,
                                    })
                                    log(f"[{trade_id}] Trade tracking started"
                                        f" (active={len(active_trades)}, waiting={len(waiting_for_limits)})")

                    mt5.shutdown()

            # ================================================================
            # SECTION 2: MONITOR WAITING_FOR_LIMITS
            # range_percent: waiting for price to return to valid LIMIT side
            # ================================================================
            for wfl in waiting_for_limits[:]:
                tid = wfl['trade_id']

                mt5, error = get_mt5_connection(credentials)
                if error:
                    log(f"[{tid}] MT5 connection failed (wfl monitor): {error}", "WARN")
                    continue

                try:
                    current_candle = get_current_candle(mt5, args.symbol, timeframe)
                except Exception as e:
                    log(f"[{tid}] Error getting candle in wait state: {e}", "ERROR")
                    current_candle = None

                if current_candle and current_candle['time'] > wfl['last_checked_candle_time']:
                    wfl['candles_waited'] += 1
                    wfl['last_checked_candle_time'] = current_candle['time']
                    expire = args.pending_order_expire_candles
                    if expire > 0:
                        log(f"[{tid}] Waiting for LIMIT: {wfl['candles_waited']}/{expire} candles")
                    else:
                        log(f"[{tid}] Waiting for LIMIT: {wfl['candles_waited']} candles elapsed")

                    # close_based SL: check previous candle close vs SL on candle boundary
                    if sl_type == "close_based":
                        try:
                            rates = mt5.copy_rates_from_pos(args.symbol, timeframe, 1, 1)
                            if rates is not None and len(rates) > 0:
                                prev_close = rates[0]['close']
                                sl_hit = False
                                if wfl['direction'] == "BUY" and prev_close <= wfl['stop_loss']:
                                    sl_hit = True
                                elif wfl['direction'] == "SELL" and prev_close >= wfl['stop_loss']:
                                    sl_hit = True
                                if sl_hit:
                                    log(f"[{tid}] Candle closed past SL while waiting - MISSED (close={prev_close:.5f}, SL={wfl['stop_loss']:.5f})")
                                    send_telegram_async(
                                        f"[{tid}] [MISS] Trade Missed\n"
                                        f"Reason: Candle closed past SL while waiting for LIMIT"
                                    )
                                    waiting_for_limits.remove(wfl)
                                    mt5.shutdown()
                                    continue
                        except Exception:
                            pass

                    if expire > 0 and wfl['candles_waited'] >= expire:
                        log(f"[{tid}] LIMIT wait expired after {wfl['candles_waited']} candles")
                        send_telegram_async(
                            f"[{tid}] [SKIP] LIMIT Wait Expired\n"
                            f"Price did not return after {wfl['candles_waited']} candles"
                        )
                        waiting_for_limits.remove(wfl)
                        mt5.shutdown()
                        continue
                tick = mt5.symbol_info_tick(args.symbol)
                if tick:
                    # SL check: price_based uses tick, close_based already handled above at candle boundary
                    if sl_type == "price_based":
                        if wfl['direction'] == "BUY" and tick.ask <= wfl['stop_loss']:
                            log(f"[{tid}] Price past SL while waiting - MISSED")
                            send_telegram_async(
                                f"[{tid}] [MISS] Trade Missed\n"
                                f"Reason: SL hit while waiting for LIMIT"
                            )
                            waiting_for_limits.remove(wfl)
                            mt5.shutdown()
                            continue

                        if wfl['direction'] == "SELL" and tick.bid >= wfl['stop_loss']:
                            log(f"[{tid}] Price past SL while waiting - MISSED")
                            send_telegram_async(
                                f"[{tid}] [MISS] Trade Missed\n"
                                f"Reason: SL hit while waiting for LIMIT"
                            )
                            waiting_for_limits.remove(wfl)
                            mt5.shutdown()
                            continue

                    can_place_now = False
                    if wfl['direction'] == "BUY" and tick.ask > wfl['entry_price']:
                        can_place_now = True
                        log(f"[{tid}] Price returned! ask={tick.ask:.5f} > entry={wfl['entry_price']:.5f}")
                    elif wfl['direction'] == "SELL" and tick.bid < wfl['entry_price']:
                        can_place_now = True
                        log(f"[{tid}] Price returned! bid={tick.bid:.5f} < entry={wfl['entry_price']:.5f}")

                    if can_place_now:
                        from src.orders import place_pending_order
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
                            log(f"[{tid}] LIMIT placed after {wfl['candles_waited']} candles! Ticket: {order_ticket}")
                            send_telegram_async(
                                f"[{tid}] [OK] LIMIT Placed After Wait\n"
                                f"Ticket: {order_ticket}\n"
                                f"Waited {wfl['candles_waited']} candles"
                            )
                            active_trades.append({
                                'trade_id': tid,
                                'direction': wfl['direction'],
                                'entry': wfl['entry_price'],
                                'sl': wfl['stop_loss'],
                                'tp': wfl['take_profit'],
                                'original_sl': wfl['stop_loss'],
                                'close_price': wfl['close_price'],
                                'candles': 0,
                                'ticket': order_ticket,
                                'lot': wfl['lot'],
                                'entry_time': now,
                                'entry_candle_time': wfl['entry_candle_time'],
                                'last_checked_candle_time': wfl['last_checked_candle_time'],
                                'sl_moved_to_breakeven': False,
                                'is_pending': True,
                                'candles_waited': 0,
                                'pending_placed_at': now,
                            })
                            waiting_for_limits.remove(wfl)
                        else:
                            log(f"[{tid}] LIMIT failed after wait: {msg}", "ERROR")
                            send_telegram_async(f"[{tid}] [FAIL] LIMIT Failed: {msg}", is_error=True)
                            waiting_for_limits.remove(wfl)

                mt5.shutdown()
            # ================================================================
            # SECTION 3: MONITOR ACTIVE TRADES
            # ================================================================
            for trade in active_trades[:]:
                tid = trade['trade_id']

                mt5, error = get_mt5_connection(credentials)
                if error:
                    log(f"[{tid}] MT5 connection failed (trade monitor): {error}", "WARN")
                    continue

                # --- LIVE MODE: Check pending order status ---
                if not args.test and trade['ticket']:
                    if trade.get("is_pending", False):
                        from src.orders import check_order_status, cancel_order
                        try:
                            status, status_msg, position_data = check_order_status(trade['ticket'], credentials)
                        except Exception as e:
                            import traceback
                            log(f"[{tid}] ERROR in check_order_status: {e}", "ERROR")
                            status = "ERROR"
                            status_msg = str(e)
                            position_data = None

                        if status == "FILLED":
                            log(f"[{tid}] Pending order FILLED!")
                            send_telegram_async(f"[{tid}] [OK] Order Filled, Ticket: {trade['ticket']}")
                            if position_data:
                                trade['entry'] = position_data['price_open']
                                if send_sl_to_mt5 and position_data['sl'] > 0:
                                    trade['sl'] = position_data['sl']
                                if send_tp_to_mt5 and position_data['tp'] > 0:
                                    trade['tp'] = position_data['tp']
                                if position_data['ticket'] != trade['ticket']:
                                    log(f"[{tid}] Position ticket differs from order ticket")
                                trade['ticket'] = position_data['ticket']
                                log(f"[{tid}] Actual: Entry={trade['entry']:.5f}")
                            trade['is_pending'] = False
                            mt5.shutdown()
                            continue

                        elif status == "PENDING":
                            expire = args.pending_order_expire_candles
                            tf_seconds = get_timeframe_seconds(timeframe)
                            placed_at = trade.get("pending_placed_at")
                            elapsed_seconds = (datetime.now(TIMEZONE) - placed_at).total_seconds() if placed_at else 0
                            expire_at_seconds = expire * tf_seconds if expire > 0 else float("inf")
                            seconds_to_expire = expire_at_seconds - elapsed_seconds

                            if expire > 0:
                                candles_elapsed = int(elapsed_seconds / tf_seconds)
                                prev = trade.get("candles_waited", 0)
                                if candles_elapsed > prev:
                                    trade['candles_waited'] = candles_elapsed
                                    log(f"[{tid}] Pending: {candles_elapsed}/{expire} candles")

                                if seconds_to_expire <= 0:
                                    log(f"[{tid}] Pending expired - cancelling")
                                    cancel_success, cancel_msg = cancel_order(trade['ticket'], credentials)
                                    if cancel_success:
                                        send_telegram_async(f"[{tid}] [WARN] Pending Expired")
                                        active_trades.remove(trade)
                                    else:
                                        log(f"[{tid}] Cancel failed - re-checking status", "WARN")
                                        status2, _, position_data2 = check_order_status(trade['ticket'], credentials)
                                        if status2 == "FILLED":
                                            log(f"[{tid}] Filled just before cancel - continuing")
                                            if position_data2:
                                                trade['entry'] = position_data2['price_open']
                                                if send_sl_to_mt5 and position_data2['sl'] > 0:
                                                    trade['sl'] = position_data2['sl']
                                                if send_tp_to_mt5 and position_data2['tp'] > 0:
                                                    trade['tp'] = position_data2['tp']
                                                trade['ticket'] = position_data2['ticket']
                                            trade['is_pending'] = False
                                        else:
                                            log(f"[{tid}] Cancel failed, still {status2} - removing", "ERROR")
                                            active_trades.remove(trade)
                                    mt5.shutdown()
                                    continue

                            sleep_dur = 0.1 if seconds_to_expire <= 10 else 2.0
                            mt5.shutdown()
                            time.sleep(sleep_dur)
                            continue

                        elif status == "CANCELLED":
                            log(f"[{tid}] Pending order cancelled: {status_msg}")
                            send_telegram_async(f"[{tid}] [WARN] Pending Cancelled")
                            active_trades.remove(trade)
                            mt5.shutdown()
                            continue

                        else:  # ERROR
                            log(f"[{tid}] Order status error: {status_msg}", "ERROR")
                            mt5.shutdown()
                            time.sleep(1)
                            continue
                    # --- Check if position still open ---
                    positions = mt5.positions_get(ticket=trade['ticket'])
                    if not positions or len(positions) == 0:
                        log(f"[{tid}] Position no longer in MT5 - checking deal history")
                        try:
                            entry_time_val = trade['entry_time']
                            if not isinstance(entry_time_val, datetime):
                                entry_time_val = datetime.now(TIMEZONE)
                            history_start = entry_time_val - timedelta(minutes=5)
                            deals = mt5.history_deals_get(history_start, datetime.now(TIMEZONE))
                        except (ValueError, OSError, TypeError) as e:
                            log(f"[{tid}] Error getting history: {e}", "ERROR")
                            deals = None

                        exit_info = None
                        if deals:
                            for deal in deals:
                                if deal.position_id == trade['ticket'] and deal.entry == 1:
                                    pip_value = get_pip_value(args.symbol)
                                    if trade['direction'] == "BUY":
                                        pnl_pips = (deal.price - trade['entry']) / pip_value
                                    else:
                                        pnl_pips = (trade['entry'] - deal.price) / pip_value
                                    if abs(deal.price - trade['tp']) < pip_value:
                                        exit_type = "TP"
                                    elif abs(deal.price - trade['sl']) < pip_value * 2:
                                        exit_type = "SL"
                                    else:
                                        exit_type = "MANUAL/OTHER"
                                    exit_info = {
                                        "type": exit_type, "price": deal.price,
                                        "pnl_pips": pnl_pips, "pnl_usd": deal.profit,
                                        "time": datetime.fromtimestamp(deal.time, tz=TIMEZONE)
                                    }
                                    break

                        if exit_info:
                            pnl_emoji = "G" if exit_info['pnl_usd'] > 0 else "R" if exit_info['pnl_usd'] < 0 else "W"
                            pnl_sign = "+" if exit_info['pnl_usd'] > 0 else ""
                            duration_min = (exit_info['time'] - trade['entry_time']).total_seconds() / 60
                            log(f"[{tid}] Closed by MT5: {exit_info['type']} @ {exit_info['price']:.5f}"
                                f" | P&L: {exit_info['pnl_pips']:.1f}pips (${exit_info['pnl_usd']:.2f})")
                            send_telegram_async(
                                f"[{tid}] <b>Position Closed: {exit_info['type']}</b>\n\n"
                                f"Symbol: {args.symbol}\n"
                                f"Direction: {trade['direction']} | Lot: {trade['lot']}\n\n"
                                f"Entry: {trade['entry']:.5f}\n"
                                f"Exit: {exit_info['price']:.5f}\n\n"
                                f"P&L: {pnl_sign}{exit_info['pnl_pips']:.1f}pips"
                                f" ({pnl_sign}${exit_info['pnl_usd']:.2f})\n"
                                f"Duration: {duration_min:.1f}min | "
                                f"Remaining active: {len(active_trades)-1}"
                            )
                            from src.orders import log_order_close
                            log_order_close(
                                ticket=trade['ticket'], exit_type=exit_info['type'],
                                exit_price=exit_info['price'], profit=exit_info['pnl_usd'],
                                symbol=args.symbol, direction=trade['direction'],
                                entry_price=trade['entry'], pnl_pips=exit_info['pnl_pips'],
                                pnl_usd=exit_info['pnl_usd'], lot=trade['lot'],
                                strategy=args.strategy, user=args.user
                            )
                        else:
                            log(f"[{tid}] Position closed by MT5 (details unavailable)", "WARN")
                            send_telegram_async(f"[{tid}] Position Closed (details unavailable)")
                        active_trades.remove(trade)
                        mt5.shutdown()
                        continue
                    # --- Breakeven: real-time price check (LIVE) ---
                    if move_sl_to_breakeven and not trade['sl_moved_to_breakeven']:
                        tick = mt5.symbol_info_tick(args.symbol)
                        if tick:
                            cur_price = tick.bid if trade['direction'] == "SELL" else tick.ask
                            entry = trade['entry']
                            tp = trade['tp']
                            be_target = trade.get("close_price", entry) if breakeven_target == "close" else entry
                            if trade['direction'] == "BUY":
                                tp_dist = tp - entry
                                trigger = entry + (tp_dist * breakeven_trigger_percent / 100)
                                if cur_price >= trigger:
                                    new_sl = be_target
                                    req = {"action": mt5.TRADE_ACTION_SLTP, "symbol": args.symbol,
                                           "position": trade['ticket'], "sl": new_sl, "tp": tp}
                                    result = mt5.order_send(req)
                                    if result.retcode == mt5.TRADE_RETCODE_DONE:
                                        log(f"[{tid}] SL moved to BE: {new_sl:.5f}")
                                        send_telegram_async(f"[{tid}] [OK] SL to Breakeven: {new_sl:.5f}")
                                        trade['sl'] = new_sl
                                        trade['sl_moved_to_breakeven'] = True
                                    else:
                                        log(f"[{tid}] BE move failed: {result.comment}", "ERROR")
                            else:  # SELL
                                tp_dist = entry - tp
                                trigger = entry - (tp_dist * breakeven_trigger_percent / 100)
                                if cur_price <= trigger:
                                    new_sl = be_target
                                    req = {"action": mt5.TRADE_ACTION_SLTP, "symbol": args.symbol,
                                           "position": trade['ticket'], "sl": new_sl, "tp": tp}
                                    result = mt5.order_send(req)
                                    if result.retcode == mt5.TRADE_RETCODE_DONE:
                                        log(f"[{tid}] SL moved to BE: {new_sl:.5f}")
                                        send_telegram_async(f"[{tid}] [OK] SL to Breakeven: {new_sl:.5f}")
                                        trade['sl'] = new_sl
                                        trade['sl_moved_to_breakeven'] = True
                                    else:
                                        log(f"[{tid}] BE move failed: {result.comment}", "ERROR")

                    # --- Candle-based monitoring: close_based exits + TIME exit ---
                    needs_candle_monitoring = (max_candles > 0) or (not send_sl_to_mt5) or (not send_tp_to_mt5)
                    if needs_candle_monitoring:
                        candle = get_current_candle(mt5, args.symbol, timeframe)
                        last_ct = trade.get("last_checked_candle_time", trade['entry_candle_time'])
                        if candle and candle['time'] > last_ct:
                            if candle['time'] > trade['entry_candle_time']:
                                trade['candles'] += 1
                                log(f"[{tid}] Monitoring: Candle {trade['candles']}/{max_candles if max_candles > 0 else chr(8734)}")
                            trade['last_checked_candle_time'] = candle['time']

                            if (not send_sl_to_mt5) or (not send_tp_to_mt5):
                                from src.utils import check_exit
                                cb_exit_type, cb_exit_price = check_exit(
                                    direction=trade['direction'],
                                    candle={"high": candle['high'], "low": candle['low'], "close": candle['close']},
                                    tp=trade['tp'], sl=trade['sl'],
                                    tp_type=tp_type, sl_type=sl_type
                                )
                                if cb_exit_type:
                                    log(f"[{tid}] close_based {cb_exit_type} exit @ {cb_exit_price:.5f}")
                                    from src.orders import close_position
                                    cl_ok, cl_msg = close_position(trade['ticket'], credentials=credentials)
                                    if cl_ok:
                                        send_telegram_async(f"[{tid}] {cb_exit_type} EXIT (close_based)")
                                    else:
                                        log(f"[{tid}] Close failed: {cl_msg}", "ERROR")

                            if max_candles > 0 and trade['candles'] >= max_candles:
                                log(f"[{tid}] TIME EXIT: {trade['candles']}/{max_candles} candles")
                                from src.orders import close_position
                                cl_ok, cl_msg = close_position(trade['ticket'], credentials=credentials)
                                if cl_ok:
                                    send_telegram_async(f"[{tid}] TIME EXIT - max candles reached")
                                else:
                                    log(f"[{tid}] TIME close failed: {cl_msg}", "ERROR")

                    mt5.shutdown()
                    continue  # next loop will detect position gone
                # --- TEST MODE candle-based monitoring ---
                candle = get_current_candle(mt5, args.symbol, timeframe)
                if not candle:
                    mt5.shutdown()
                    continue
                if candle['time'] <= trade['last_checked_candle_time']:
                    mt5.shutdown()
                    continue
                if candle['time'] > trade['entry_candle_time']:
                    trade['candles'] += 1
                    log(f"[{tid}] Monitoring: Candle {trade['candles']}/{max_candles}")
                trade['last_checked_candle_time'] = candle['time']
                h_c = candle['high']
                l_c = candle['low']
                c_c = candle['close']

                # Breakeven check (TEST/LIVE candle path)
                if move_sl_to_breakeven and not trade['sl_moved_to_breakeven']:
                    entry = trade['entry']
                    tp = trade['tp']
                    be_t = trade.get("close_price", entry) if breakeven_target == "close" else entry
                    if trade['direction'] == "BUY":
                        trigger = entry + ((tp - entry) * breakeven_trigger_percent / 100)
                        if h_c >= trigger:
                            new_sl = be_t
                            if not args.test and trade['ticket']:
                                req = {"action": mt5.TRADE_ACTION_SLTP, "symbol": args.symbol,
                                       "position": trade['ticket'], "sl": new_sl, "tp": tp}
                                res = mt5.order_send(req)
                                if res.retcode == mt5.TRADE_RETCODE_DONE:
                                    log(f"[{tid}] SL->BE: {new_sl:.5f}")
                                    trade['sl'] = new_sl; trade['sl_moved_to_breakeven'] = True
                                    send_telegram_async(f"[{tid}] [OK] SL to BE: {new_sl:.5f}")
                            else:
                                log(f"[{tid}] [TEST] SL->BE: {new_sl:.5f}")
                                trade['sl'] = new_sl; trade['sl_moved_to_breakeven'] = True
                                send_telegram_async(f"[{tid}] [OK] SL to BE: {new_sl:.5f}")
                    else:
                        trigger = entry - ((entry - tp) * breakeven_trigger_percent / 100)
                        if l_c <= trigger:
                            new_sl = be_t
                            if not args.test and trade['ticket']:
                                req = {"action": mt5.TRADE_ACTION_SLTP, "symbol": args.symbol,
                                       "position": trade['ticket'], "sl": new_sl, "tp": tp}
                                res = mt5.order_send(req)
                                if res.retcode == mt5.TRADE_RETCODE_DONE:
                                    log(f"[{tid}] SL->BE: {new_sl:.5f}")
                                    trade['sl'] = new_sl; trade['sl_moved_to_breakeven'] = True
                                    send_telegram_async(f"[{tid}] [OK] SL to BE: {new_sl:.5f}")
                            else:
                                log(f"[{tid}] [TEST] SL->BE: {new_sl:.5f}")
                                trade['sl'] = new_sl; trade['sl_moved_to_breakeven'] = True
                                send_telegram_async(f"[{tid}] [OK] SL to BE: {new_sl:.5f}")

                # Check MT5 closed position (LIVE secondary path)
                position_closed_live = False
                if not args.test and trade['ticket']:
                    pos_check = mt5.positions_get(ticket=trade['ticket'])
                    if not pos_check or len(pos_check) == 0:
                        position_closed_live = True
                        log(f"[{tid}] Position gone (candle path)")
                        try:
                            etv = trade['entry_time']
                            if not isinstance(etv, datetime): etv = datetime.now(TIMEZONE)
                            deals = mt5.history_deals_get(etv - timedelta(minutes=5), datetime.now(TIMEZONE))
                        except Exception:
                            deals = None
                        if deals:
                            for deal in deals:
                                if deal.position_id == trade['ticket'] and deal.entry == 1:
                                    pv = get_pip_value(args.symbol)
                                    pp = ((deal.price - trade['entry']) if trade['direction'] == "BUY" else (trade['entry'] - deal.price)) / pv
                                    if abs(deal.price - trade['tp']) < pv: et2 = "TP"
                                    elif abs(deal.price - trade['sl']) < pv: et2 = "SL"
                                    else: et2 = "MANUAL/OTHER"
                                    ps2 = "+" if deal.profit > 0 else ""
                                    log(f"[{tid}] Closed {et2} P&L:{ps2}{pp:.1f}pips")
                                    send_telegram_async(f"[{tid}] Closed {et2} P&L:{ps2}{pp:.1f}pips")
                                    from src.orders import log_order_close
                                    log_order_close(ticket=trade['ticket'], exit_type=et2,
                                        exit_price=deal.price, profit=deal.profit,
                                        symbol=args.symbol, direction=trade['direction'],
                                        entry_price=trade['entry'], pnl_pips=pp, pnl_usd=deal.profit,
                                        lot=trade['lot'], strategy=args.strategy, user=args.user)
                                    break
                        active_trades.remove(trade)
                        mt5.shutdown()
                        continue
                if not position_closed_live:
                    from src.utils import check_exit
                    exit_type, exit_price = check_exit(
                        direction=trade['direction'],
                        candle={"high": h_c, "low": l_c, "close": c_c},
                        tp=trade['tp'], sl=trade['sl'],
                        tp_type=tp_type, sl_type=sl_type
                    )

                    # Close position in LIVE mode if exit triggered
                    if not args.test and exit_type and trade['ticket']:
                        from src.orders import close_position
                        ok_cl, msg_cl = close_position(trade['ticket'], credentials=credentials)
                        if not ok_cl:
                            log(f"[{tid}] Failed to close: {msg_cl}", "ERROR")

                    # TIME exit
                    if not exit_type and max_candles > 0 and trade['candles'] >= max_candles:
                        exit_type = "TIME"
                        exit_price = c_c
                        if not args.test and trade['ticket']:
                            from src.orders import close_position
                            ok_cl, msg_cl = close_position(trade['ticket'], credentials=credentials)
                            if ok_cl:
                                log(f"[{tid}] TIME exit: position closed")
                            else:
                                log(f"[{tid}] TIME close failed: {msg_cl}", "ERROR")

                    if exit_type:
                        pv = get_pip_value(args.symbol)
                        pnl_pips = ((exit_price - trade['entry']) if trade['direction'] == "BUY"
                                    else (trade['entry'] - exit_price)) / pv
                        from src.utils import get_pip_value_per_lot
                        pnl_usd = trade['lot'] * pnl_pips * get_pip_value_per_lot(args.symbol)
                        dur_m = (now - trade['entry_time']).total_seconds() / 60
                        ps = "+" if pnl_usd > 0 else ""
                        log(f"[{tid}] Exit: {exit_type} @ {exit_price:.5f} P&L:{ps}{pnl_pips:.1f}pips")
                        send_telegram_async(
                            f"[{tid}] <b>Closed: {exit_type}</b>\n\n"
                            f"Symbol: {args.symbol} | {trade['direction']} | Lot: {trade['lot']}\n\n"
                            f"Entry: {trade['entry']:.5f} -> Exit: {exit_price:.5f}\n"
                            f"P&L: {ps}{pnl_pips:.1f}pips ({ps}${pnl_usd:.2f})"
                            f" | {dur_m:.1f}min | {trade['candles']}c\n"
                            f"Active remaining: {len(active_trades)-1}"
                        )
                        from src.orders import log_order_close
                        log_order_close(
                            ticket=trade.get("ticket", 0), exit_type=exit_type,
                            exit_price=exit_price, profit=pnl_usd,
                            symbol=args.symbol, direction=trade['direction'],
                            entry_price=trade['entry'], pnl_pips=pnl_pips,
                            pnl_usd=pnl_usd, lot=trade['lot'],
                            strategy=args.strategy, user=args.user
                        )
                        active_trades.remove(trade)

                mt5.shutdown()
            # ================================================================
            # SECTION 4: EXIT CONDITION - window ended, all trades closed
            # ================================================================
            if past_window_end and not active_trades and not waiting_for_limits:
                log(f"")
                log(f"{'='*60}")
                log(f"Window {window_start}-{window_end} ended and all trades closed. Bot stopping.")
                log(f"{'='*60}")
                send_telegram_async(
                    f"<b>Bot Completed</b>\n\n"
                    f"Strategy: {strategy.get('name')}\n"
                    f"Symbol: {args.symbol}\n"
                    f"Window: {window_start} - {window_end} complete"
                )
                return

            # Sleep: fast poll when trades active, full interval when idle
            if active_trades or waiting_for_limits:
                time.sleep(0.1)
            else:
                time.sleep(args.interval)

    except KeyboardInterrupt:
        log("Bot stopped by user")
        send_telegram_async("Bot Stopped (manual)")
        time.sleep(1)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        log(f"Bot error: {e}", "ERROR")
        log(f"Traceback:\n{error_trace}", "ERROR")
        send_telegram_async(f"Bot Error: {e}\n\nCheck logs for details", is_error=True)
        time.sleep(1)
        raise


if __name__ == "__main__":
    args = get_args()
    run_bot(args)

