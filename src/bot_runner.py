"""
Bot Runner - Main trading bot script with argparse

Usage:
    python src/bot_runner.py --strategy master_candle --symbol ETHUSDm --user admin

Each bot runs as a separate process.
"""

import argparse
import hashlib
import json
import os
import sys
import time
import requests
from datetime import datetime, time as _time
from zoneinfo import ZoneInfo

# Add parent directory to path and load the repository env file independently
# of the subprocess working directory.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_REPO_ROOT, ".env"), override=True)

from src.utils import _in_time_window
from src.strategy_manager import is_flappy_strategy, is_swing_strategy
from src.flappy_bird_strategy import (
    EMA_WARMUP_WINDOW,
    calculate_flappy_ema_series,
    calculate_flappy_ema_cross_lifecycle,
)

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


class _GracefulRestart(Exception):
    """Raised when bot should restart gracefully (pending_restart flag detected while idle)."""


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
    parser.add_argument("--ema_period", type=int, default=None,
                        help="EMA period for pattern strategies (default: from strategy)")
    parser.add_argument("--h2_exceed_pips", type=float, default=0.0,
                        help="H2 > H1 + N pips / L2 < L1 - N pips (điều kiện 4, default 0)")
    parser.add_argument("--c2_gap_pips", type=float, default=0.0,
                        help="C2 < L1 - N pips / C2 > H1 + N pips (điều kiện 5, default 0)")
    parser.add_argument("--ema_margin_pips", type=float, default=0.0,
                        help="L2/H2 cách EMA + N pips (điều kiện 6, default 0)")
    parser.add_argument("--limit_order_candles", type=int, default=None,
                        help="Chờ khớp lệnh tối đa N nến (default: from strategy)")
    parser.add_argument("--min_father_body_points", type=float, default=None,
                        help="Minimum Father candle body in price points (Flappy Bird)")
    parser.add_argument("--min_child_candles", type=int, default=None,
                        help="Minimum child candles (Flappy Bird)")
    parser.add_argument("--max_child_candles", type=int, default=None,
                        help="Maximum child candles (Flappy Bird)")
    parser.add_argument("--max_child_body_points", type=float, default=None,
                        help="Maximum body size for each of the final two child candles")
    parser.add_argument("--cross_window_candles", type=int, default=None,
                        help="Maximum candles after EMA 8/13 cross for a Flappy signal")
    parser.add_argument("--mother_coverage_enabled", type=int, default=None,
                        help="Require Mother wick/body coverage of children (Flappy Bird)")
    parser.add_argument("--use_mother_candle", type=int, default=None,
                        help="Multi Flappy: require Mother candle (1/0)")
    parser.add_argument("--no_mother_child_candles", type=int, default=None)
    parser.add_argument("--no_mother_child_body_ratio", type=float, default=None)
    parser.add_argument("--no_mother_child_body_max_points", type=float, default=None)
    parser.add_argument("--no_mother_father_wick_max_pct", type=float, default=None)
    parser.add_argument("--no_mother_cross_window_candles", type=int, default=None)
    parser.add_argument("--no_mother_sl_buffer_pips", type=float, default=None)
    parser.add_argument("--flappy_consensus_enabled", type=int, default=None)
    parser.add_argument("--flappy_fallback_enabled", type=int, default=None)
    for group, label in (
        ("consensus", "strict EMA consensus"),
        ("fallback", "EMA fallback"),
    ):
        for slot in ("short", "medium", "long"):
            parser.add_argument(
                f"--flappy_{group}_{slot}", type=int, default=None,
                help=f"Flappy {label} {slot} EMA period",
            )
    parser.add_argument("--entry_mode", type=str, default=None,
                        help="Entry mode: 'close' or 'range_percent' (default: from strategy)")
    parser.add_argument("--entry_percent", type=float, default=None,
                        help="Entry percent for range_percent mode (default: from strategy)")
    parser.add_argument("--entry_body_percent", type=float, default=None,
                        help="Flappy Entry offset as percentage of Father body (default: from strategy)")
    parser.add_argument("--higher_timeframe", type=str, default=None,
                        help="Multi Flappy higher timeframe, e.g. M5")
    parser.add_argument("--higher_timeframe_filter_enabled", type=int, default=None,
                        help="Multi Flappy HTF filter: 1=enabled, 0=disabled")
    parser.add_argument("--current_timeframe_filter_enabled", type=int, default=None,
                        help="Multi Flappy current-TF filter: 1=enabled, 0=disabled")
    for group, label in (
        ("higher_ema_consensus", "higher timeframe consensus"),
        ("higher_ema_fallback", "higher timeframe fallback"),
    ):
        for slot in ("short", "medium", "long"):
            parser.add_argument(
                f"--{group}_{slot}", type=int, default=None,
                help=f"Multi Flappy {label} {slot} EMA period",
            )
    parser.add_argument("--higher_ema_consensus_enabled", type=int, default=None)
    parser.add_argument("--higher_ema_fallback_enabled", type=int, default=None)
    parser.add_argument("--ema_short_period", type=int, default=None,
                        help="Swing EMA fast period override")
    parser.add_argument("--ema_medium_period", type=int, default=None,
                        help="Swing EMA medium period override")
    parser.add_argument("--ema_long_period", type=int, default=None,
                        help="Swing EMA slow period override")
    parser.add_argument("--zigzag_depth", type=int, default=None,
                        help="Swing zigzag depth override")
    parser.add_argument("--zigzag_deviation_points", type=float, default=None,
                        help="Swing zigzag deviation in point-size units")
    parser.add_argument("--zigzag_back_step", type=int, default=None,
                        help="Swing zigzag back-step override")
    parser.add_argument("--min_structure_candles", type=int, default=None,
                        help="Minimum candles spanned by latest swing structure")
    parser.add_argument("--max_structure_candles", type=int, default=None,
                        help="Maximum candles spanned by latest swing structure")
    parser.add_argument("--ema_cross_window_candles", type=int, default=None,
                        help="Maximum candles since fast/medium EMA cross")
    parser.add_argument("--ema_exit_enabled", type=int, default=None,
                        help="Swing EMA exit filter: 1=enabled, 0=disabled")
    parser.add_argument("--ema_exit_period", type=int, default=None,
                        help="Swing EMA exit period override")
    parser.add_argument("--pending_expiry_candles", type=int, default=None,
                        help="Swing pending order expiry in candles")
    parser.add_argument("--entry_buffer_pips", type=float, default=None,
                        help="Swing stop-entry offset from pivot in pips")
    parser.add_argument("--max_pending_orders_per_symbol", type=int, default=None,
                        help="Swing pending-order cap; 0 means unlimited")
    parser.add_argument("--sl_buffer_pips", type=float, default=None,
                        help="Swing stop-loss buffer beyond activation reference")
    parser.add_argument("--use_pivot2_for_buy", type=int, default=None,
                        help="Use High 2 for BUY setup: 1=enabled, 0=disabled")
    parser.add_argument("--use_pivot2_for_sell", type=int, default=None,
                        help="Use Low 2 for SELL setup: 1=enabled, 0=disabled")
    parser.add_argument("--ema_consensus_enabled", type=int, default=None,
                        help="Swing EMA consensus route: 1=enabled, 0=disabled")
    parser.add_argument("--ema_fallback_enabled", type=int, default=None,
                        help="Swing Multi Flappy fallback route: 1=enabled, 0=disabled")
    parser.add_argument("--fallback_ema_short_period", type=int, default=None)
    parser.add_argument("--fallback_ema_medium_period", type=int, default=None)
    parser.add_argument("--fallback_ema_long_period", type=int, default=None)
    parser.add_argument("--tp_type", type=str, default=None,
                        help="TP exit type: 'price_based' or 'close_based' (default: from strategy)")
    parser.add_argument("--sl_type", type=str, default=None,
                        help="SL exit type: 'close_based' or 'price_based' (default: from strategy)")
    parser.add_argument("--buffer_k", type=float, default=None,
                        help="SL buffer in pips beyond candle extreme (default: from strategy)")
    parser.add_argument("--ema_filter_enabled", type=int, default=1,
                        help="EMA filter: 1=enabled, 0=disabled (feg_stop_order only)")
    parser.add_argument("--buy_ema_side", type=str, default="below_ema",
                        help="EMA side for BUY: 'above_ema' | 'below_ema' (feg_stop_order only)")
    parser.add_argument("--sell_ema_side", type=str, default="above_ema",
                        help="EMA side for SELL: 'above_ema' | 'below_ema' (feg_stop_order only)")
    parser.add_argument("--lot_mode", type=str, default="fixed",
                        help="Lot size mode: 'fixed' or 'flex' (default: fixed)")
    parser.add_argument("--risk_mode", type=str, default="percent",
                        help="Risk mode for flex lots: 'percent' or 'fixed_amount'")
    parser.add_argument("--risk_percent", type=float, default=0.5,
                        help="Risk per trade as % of equity (flex mode)")
    parser.add_argument("--risk_amount", type=float, default=0.0,
                        help="Fixed risk per trade in USD (flex mode)")

    # Bot control
    parser.add_argument("--test", type=int, default=1,
                        help="Test mode: 1=test (no real trades), 0=live")
    parser.add_argument("--managed_by_ui", type=int, default=0,
                        help="Suppress local stop notification when UI sends it")
    parser.add_argument("--interval", type=float, default=60.0,
                        help="Check interval in seconds (default: 60)")
    parser.add_argument("--timeframe", type=str, default=None,
                        help="Candle timeframe override, e.g. M1/M5/M15 (default: from strategy)")

    parser.add_argument('--entry_start_time', type=str, default='00:00',
                        help='Entry window start HH:MM (Asia/Ho_Chi_Minh). Default 00:00 = no filter.')
    parser.add_argument('--entry_end_time', type=str, default='23:59',
                        help='Entry window end HH:MM (Asia/Ho_Chi_Minh). Default 23:59 = no filter.')
    parser.add_argument('--be_enabled', type=int, default=0,
                        help='Break-even: 1=enabled, 0=disabled (default 0)')
    parser.add_argument('--be_r', type=float, default=1.0,
                        help='Break-even trigger at be_r * SL_distance profit (default 1.0)')
    parser.add_argument('--re_entry_after_sl', type=int, default=0,
                        help='Re-entry after SL: scan signal in parallel while trade is open. '
                             'If SL hits exactly at candle2 of pending signal → re-entry limit immediately. '
                             '1=enabled, 0=disabled (default 0)')
    parser.add_argument('--c2_buy_upper_wick_max_pct', type=float, default=None,
                        help='BUY — Ngưỡng %% body C2 cho râu trên (high-close). None = tắt.')
    parser.add_argument('--c2_buy_lower_wick_max_pct', type=float, default=None,
                        help='BUY — Ngưỡng %% body C2 cho râu dưới (open-low). None = tắt.')
    parser.add_argument('--c2_sell_upper_wick_max_pct', type=float, default=None,
                        help='SELL — Ngưỡng %% body C2 cho râu trên (high-open). None = tắt.')
    parser.add_argument('--c2_sell_lower_wick_max_pct', type=float, default=None,
                        help='SELL — Ngưỡng %% body C2 cho râu dưới (close-low). None = tắt.')
    parser.add_argument('--c2_buy_upper_wick_cmp', type=str, default='lt',
                        help='BUY râu trên: "lt" = râu < pct%% body (default) | "gt" = râu > pct%% body')
    parser.add_argument('--c2_buy_lower_wick_cmp', type=str, default='lt',
                        help='BUY râu dưới: "lt" = râu < pct%% body (default) | "gt" = râu > pct%% body')
    parser.add_argument('--c2_sell_upper_wick_cmp', type=str, default='lt',
                        help='SELL râu trên: "lt" = râu < pct%% body (default) | "gt" = râu > pct%% body')
    parser.add_argument('--c2_sell_lower_wick_cmp', type=str, default='lt',
                        help='SELL râu dưới: "lt" = râu < pct%% body (default) | "gt" = râu > pct%% body')
    parser.add_argument('--log_file', type=str, default=None,
                        help='Path to log file (default: stderr only)')

    return parser.parse_args()


# Module-level logger — configured in __main__ after args parsed
import logging as _logging
_logger = _logging.getLogger("bot_runner")


def log(message: str, level: str = "INFO"):
    """Log message with timestamp via logging module (writes to file + stderr)."""
    lvl = getattr(_logging, level.upper(), _logging.INFO)
    _logger.log(lvl, message)


def send_telegram(text: str, is_error: bool = False) -> bool:
    """Send message to Telegram"""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_ERROR_CHAT_ID") if is_error else os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        log("Telegram not configured", "WARN")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}

    try:
        response = requests.post(url, json=payload, timeout=10)
        if not response.ok:
            detail = response.text[:500].replace("\n", " ")
            log(f"Telegram rejected message: HTTP {response.status_code} - {detail}", "ERROR")
            return False
        return True
    except Exception as e:
        log(f"Telegram error: {e}", "ERROR")
        return False


def get_mt5_connection(credentials: dict):
    """Initialize MT5 connection (fresh connect — use _ensure_mt5_connected for persistent sessions)."""
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


def _ensure_mt5_connected(mt5_ref: list, credentials: dict) -> tuple:
    """Return live MT5 module, reconnecting only when the terminal lost connection.

    mt5_ref is a 1-element list used as a mutable cell so callers can share the
    same connection across loop iterations without a global variable.

    Usage:
        _mt5_ref = [None]
        while True:
            mt5, err = _ensure_mt5_connected(_mt5_ref, credentials)
            if err: ...
    """
    try:
        import MetaTrader5 as mt5_mod
    except ImportError:
        return None, "MT5 not available (Windows only)"

    mt5 = mt5_ref[0]

    # Fast-path: already initialized — just ping terminal_info
    if mt5 is not None:
        try:
            info = mt5_mod.terminal_info()
            if info is not None and info.connected:
                return mt5_mod, None
        except Exception:
            pass
        # Terminal gone — fall through to reconnect
        try:
            mt5_mod.shutdown()
        except Exception:
            pass

    # Reconnect
    if not mt5_mod.initialize():
        mt5_ref[0] = None
        return None, "MT5 initialization failed"

    login = int(credentials.get('login') or 0)
    password = credentials.get('password', '')
    server = credentials.get('server', '')

    if not login or not password or not server:
        mt5_mod.shutdown()
        mt5_ref[0] = None
        return None, "MT5 credentials not configured"

    if not mt5_mod.login(login=login, password=password, server=server):
        error = mt5_mod.last_error()
        mt5_mod.shutdown()
        mt5_ref[0] = None
        return None, f"MT5 login failed: {error}"

    mt5_ref[0] = mt5_mod
    return mt5_mod, None


def get_pip_value(symbol: str) -> float:
    """Get pip value for symbol"""
    if "BTC" in symbol:
        return 1.0
    elif "ETH" in symbol:
        return 0.1
    elif "XAU" in symbol:
        return 0.1
    elif "JPY" in symbol:
        return 0.01
    return 0.0001


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
        msg = f"Strategy not found: {args.strategy}"
        log(msg, "ERROR")
        send_telegram(f"❌ Bot startup failed\n{msg}", is_error=True)
        return

    params = get_strategy_parameters(args.strategy)
    log(f"Strategy loaded: {strategy.get('name')}")

    entry_start = datetime.strptime(args.entry_start_time, '%H:%M').time()
    entry_end   = datetime.strptime(args.entry_end_time,   '%H:%M').time()

    # Dispatch theo entry type
    if params.get('entry_type', 'time') == 'pattern':
        credentials = get_user_mt5_credentials(args.user)
        if not credentials.get('login'):
            msg = f"MT5 credentials not configured for user: {args.user}"
            log(msg, "ERROR")
            send_telegram(f"❌ Bot startup failed\n{msg}", is_error=True)
            return
        if args.strategy == 'feg_stop_order':
            run_feg_stop_order_bot(args, strategy, params, credentials,
                                   entry_start_time=entry_start, entry_end_time=entry_end)
        elif args.strategy == 'feg_reverse':
            run_feg_reverse_bot(args, strategy, params, credentials,
                                entry_start_time=entry_start, entry_end_time=entry_end)
        elif is_swing_strategy(args.strategy):
            run_swing_ema_zigzag_bot(args, strategy, params, credentials,
                                     entry_start_time=entry_start, entry_end_time=entry_end)
        elif is_flappy_strategy(args.strategy):
            run_feg_bot(args, strategy, params, credentials,
                        entry_start_time=entry_start, entry_end_time=entry_end)
        else:
            run_feg_bot(args, strategy, params, credentials,
                        entry_start_time=entry_start, entry_end_time=entry_end)
        return

    # Override with command line args if provided
    sl_pips = args.sl_pips or params.get('sl_pips', 30)
    rr_ratio = args.rr_ratio or params.get('rr_ratio', 2.0)
    lot_size = args.lot_size or params.get('lot_size', 0.01)
    max_candles = args.max_candles or params.get('max_candles', 7)
    entry_time = params.get('entry_time', '21:05')
    timeframe = args.timeframe or params.get('timeframe', 'M5')

    # Get user's MT5 credentials
    credentials = get_user_mt5_credentials(args.user)
    if not credentials.get('login'):
        msg = f"MT5 credentials not configured for user: {args.user}"
        log(msg, "ERROR")
        send_telegram(f"❌ Bot startup failed\n{msg}", is_error=True)
        return

    # Auto-detect symbol min lot and clamp
    mt5_tmp, err_tmp = get_mt5_connection(credentials)
    if not err_tmp:
        sym_info = mt5_tmp.symbol_info(args.symbol)
        if sym_info and lot_size < sym_info.volume_min:
            log(f"lot_size {lot_size} < symbol min {sym_info.volume_min} — using {sym_info.volume_min}", "WARN")
            lot_size = sym_info.volume_min
        mt5_tmp.shutdown()

    log(f"Parameters: SL={sl_pips} pips, RR={rr_ratio}, Lot={lot_size}, MaxCandles={max_candles}")
    log(f"Entry time: {entry_time}, Timeframe: {timeframe}")

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
            if check_entry_time(entry_time) and last_entry_date != now.date() and _in_time_window(datetime.now(TIMEZONE), entry_start, entry_end):
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
                    send_telegram(f"❌ Failed to get candle data\nSymbol: {args.symbol}", is_error=True)
                    mt5.shutdown()
                    time.sleep(args.interval)
                    continue

                o, h, l, c = candle['open'], candle['high'], candle['low'], candle['close']
                pip_value = get_pip_value(args.symbol)
                sl_distance = sl_pips * pip_value

                # Determine direction
                if c > o:
                    direction = "BUY"
                    entry_price = c
                    stop_loss = l - sl_distance
                    risk = entry_price - stop_loss
                    take_profit = entry_price + (risk * rr_ratio)
                elif c < o:
                    direction = "SELL"
                    entry_price = c
                    stop_loss = h + sl_distance
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
                    log(f"MT5 connection failed (monitoring): {error}", "ERROR")
                    send_telegram(f"❌ MT5 Error (monitoring active trade)\n{error}", is_error=True)
                    time.sleep(args.interval)
                    continue

                candle = get_current_candle(mt5, args.symbol, timeframe)
                if candle:
                    active_trade['candles'] += 1
                    h, l, c = candle['high'], candle['low'], candle['close']

                    exit_type = None
                    exit_price = None

                    # Break-even: move SL to entry when profit >= be_r * sl_dist
                    be_enabled = bool(args.be_enabled)
                    if be_enabled and not active_trade.get('be_triggered'):
                        entry_p = active_trade['entry']
                        sl_dist = abs(entry_p - active_trade['sl'])
                        if active_trade['direction'] == "BUY" and h >= entry_p + args.be_r * sl_dist:
                            active_trade['sl'] = entry_p
                            active_trade['be_triggered'] = True
                            log(f"BE triggered — SL moved to entry {entry_p:.2f}")
                        elif active_trade['direction'] == "SELL" and l <= entry_p - args.be_r * sl_dist:
                            active_trade['sl'] = entry_p
                            active_trade['be_triggered'] = True
                            log(f"BE triggered — SL moved to entry {entry_p:.2f}")

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

            # Write idle state — run_bot doesn't track active/pending, always 0
            _write_bot_state(os.getpid(), args.symbol,
                             args.strategy, 1 if active_trade else 0, 0)
            # Graceful restart: exit when idle and flagged
            if _check_pending_restart(os.getpid()) and not active_trade:
                log("Pending restart flag detected and bot is idle — restarting with new code")
                _clear_pending_restart(os.getpid())
                _write_bot_state(os.getpid(), args.symbol, args.strategy, 0, 0)
                raise _GracefulRestart()

            # Sleep before next check
            time.sleep(args.interval)

    except KeyboardInterrupt:
        log("Bot stopped by user")
        _write_bot_state(os.getpid(), args.symbol, args.strategy, 0, 0)
        if not args.managed_by_ui:
            send_telegram("Bot Stopped (manual)")
    except _GracefulRestart:
        raise
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log(f"Bot error: {e}", "ERROR")
        _write_bot_state(os.getpid(), args.symbol, args.strategy, 0, 0)
        send_telegram(f"❌ Bot crashed\nStrategy: {args.strategy}\nSymbol: {args.symbol}\nError: {e}\n\n<pre>{tb[-800:]}</pre>", is_error=True)
        raise


def feg_entry_decision(
    active_trade, candle1, candle2, ema2, symbol,
    rr_ratio, buffer_k, lot_size, entry_mode, entry_percent,
    h2_exceed_pips=0.0, c2_gap_pips=0.0, ema_margin_pips=0.0,
    ema_filter_enabled=True, buy_ema_side="below_ema", sell_ema_side="above_ema",
    c2_buy_upper_wick_max_pct=None, c2_buy_lower_wick_max_pct=None,
    c2_sell_upper_wick_max_pct=None, c2_sell_lower_wick_max_pct=None,
    c2_buy_upper_wick_cmp="lt", c2_buy_lower_wick_cmp="lt",
    c2_sell_upper_wick_cmp="lt", c2_sell_lower_wick_cmp="lt",
):
    """Quyết định vào lệnh FEG. None nếu đang có lệnh (1 lệnh/lúc) hoặc không có pattern."""
    from src.feg_strategy import analyze_feg
    if active_trade is not None:
        return None
    return analyze_feg(
        symbol, candle1, candle2, ema2,
        rr_ratio=rr_ratio, buffer_k=buffer_k, lot_size=lot_size,
        entry_mode=entry_mode, entry_percent=entry_percent,
        h2_exceed_pips=h2_exceed_pips, c2_gap_pips=c2_gap_pips, ema_margin_pips=ema_margin_pips,
        ema_filter_enabled=ema_filter_enabled, buy_ema_side=buy_ema_side, sell_ema_side=sell_ema_side,
        c2_buy_upper_wick_max_pct=c2_buy_upper_wick_max_pct,
        c2_buy_lower_wick_max_pct=c2_buy_lower_wick_max_pct,
        c2_sell_upper_wick_max_pct=c2_sell_upper_wick_max_pct,
        c2_sell_lower_wick_max_pct=c2_sell_lower_wick_max_pct,
        c2_buy_upper_wick_cmp=c2_buy_upper_wick_cmp,
        c2_buy_lower_wick_cmp=c2_buy_lower_wick_cmp,
        c2_sell_upper_wick_cmp=c2_sell_upper_wick_cmp,
        c2_sell_lower_wick_cmp=c2_sell_lower_wick_cmp,
    )


def feg_stop_order_entry_decision(
    active_trade, candle1, candle2, ema2, symbol,
    rr_ratio, buffer_k, lot_size,
    h2_exceed_pips=0.0, c2_gap_pips=0.0,
    ema_filter_enabled=True, buy_ema_side="below_ema", sell_ema_side="above_ema",
    ema_margin_pips=0.0,
    c2_buy_upper_wick_max_pct=None, c2_buy_lower_wick_max_pct=None,
    c2_sell_upper_wick_max_pct=None, c2_sell_lower_wick_max_pct=None,
    c2_buy_upper_wick_cmp="lt", c2_buy_lower_wick_cmp="lt",
    c2_sell_upper_wick_cmp="lt", c2_sell_lower_wick_cmp="lt",
):
    """Quyết định vào lệnh FEG Stop Order. None nếu đang có lệnh (1 lệnh/lúc) hoặc không có pattern."""
    from src.feg_stop_order_strategy import analyze_feg_stop_order
    if active_trade is not None:
        return None
    return analyze_feg_stop_order(
        symbol, candle1, candle2, ema2,
        rr_ratio=rr_ratio, buffer_k=buffer_k, lot_size=lot_size,
        h2_exceed_pips=h2_exceed_pips, c2_gap_pips=c2_gap_pips,
        ema_filter_enabled=ema_filter_enabled,
        buy_ema_side=buy_ema_side, sell_ema_side=sell_ema_side,
        ema_margin_pips=ema_margin_pips,
        c2_buy_upper_wick_max_pct=c2_buy_upper_wick_max_pct,
        c2_buy_lower_wick_max_pct=c2_buy_lower_wick_max_pct,
        c2_sell_upper_wick_max_pct=c2_sell_upper_wick_max_pct,
        c2_sell_lower_wick_max_pct=c2_sell_lower_wick_max_pct,
        c2_buy_upper_wick_cmp=c2_buy_upper_wick_cmp,
        c2_buy_lower_wick_cmp=c2_buy_lower_wick_cmp,
        c2_sell_upper_wick_cmp=c2_sell_upper_wick_cmp,
        c2_sell_lower_wick_cmp=c2_sell_lower_wick_cmp,
    )


def feg_reverse_entry_decision(
    active_trade, candle1, candle2, ema2, symbol,
    rr_ratio, buffer_k, lot_size, entry_mode, entry_percent,
    h2_exceed_pips=0.0, c2_gap_pips=0.0, ema_margin_pips=0.0,
    ema_filter_enabled=True, buy_ema_side="below_ema", sell_ema_side="above_ema",
    c2_buy_upper_wick_max_pct=None, c2_buy_lower_wick_max_pct=None,
    c2_sell_upper_wick_max_pct=None, c2_sell_lower_wick_max_pct=None,
    c2_buy_upper_wick_cmp="lt", c2_buy_lower_wick_cmp="lt",
    c2_sell_upper_wick_cmp="lt", c2_sell_lower_wick_cmp="lt",
):
    """Quyết định vào lệnh FEG Reverse. None nếu đang có lệnh hoặc không có pattern."""
    from src.feg_reverse_strategy import analyze_feg_reverse
    if active_trade is not None:
        return None
    return analyze_feg_reverse(
        symbol, candle1, candle2, ema2,
        rr_ratio=rr_ratio, buffer_k=buffer_k, lot_size=lot_size,
        entry_mode=entry_mode, entry_percent=entry_percent,
        h2_exceed_pips=h2_exceed_pips, c2_gap_pips=c2_gap_pips, ema_margin_pips=ema_margin_pips,
        ema_filter_enabled=ema_filter_enabled, buy_ema_side=buy_ema_side, sell_ema_side=sell_ema_side,
        c2_buy_upper_wick_max_pct=c2_buy_upper_wick_max_pct,
        c2_buy_lower_wick_max_pct=c2_buy_lower_wick_max_pct,
        c2_sell_upper_wick_max_pct=c2_sell_upper_wick_max_pct,
        c2_sell_lower_wick_max_pct=c2_sell_lower_wick_max_pct,
        c2_buy_upper_wick_cmp=c2_buy_upper_wick_cmp,
        c2_buy_lower_wick_cmp=c2_buy_lower_wick_cmp,
        c2_sell_upper_wick_cmp=c2_sell_upper_wick_cmp,
        c2_sell_lower_wick_cmp=c2_sell_lower_wick_cmp,
    )


def _latest_structure_span(structured_pivots: list[dict]) -> int | None:
    """Return the candle span of the latest 2 highs + 2 lows used for structure."""
    from src.swing_ema_strategy import latest_structure_span

    return latest_structure_span(structured_pivots)


def _swing_setup_order_comment(setup_id: str) -> str:
    """Encode a setup identity in the broker comment for restart reconciliation."""
    setup_hash = hashlib.sha256(setup_id.encode("utf-8")).hexdigest()[:20]
    return f"SWG-{setup_hash}"


def _has_duplicate_swing_pending(
    mt5,
    pending_orders: list,
    signal: dict,
    symbol: str,
    magic: int,
    active_trades: list | None = None,
) -> bool:
    """Prevent duplicate entries, setups, or untracked legacy Swing orders."""
    def matches(candidate: dict) -> bool:
        existing = candidate.get("signal", candidate)
        return (
            existing.get("direction") == signal.get("direction")
            and abs(float(existing.get("entry_price", 0.0)) - float(signal.get("entry_price", 0.0))) < 1e-8
        )

    if any(matches(order) for order in pending_orders):
        return True
    if active_trades and any(matches(trade) for trade in active_trades):
        return True

    broker_orders = mt5.orders_get(symbol=symbol)
    if broker_orders is None:
        raise RuntimeError(f"Could not read pending orders for {symbol}")
    setup_comment = (
        _swing_setup_order_comment(signal["setup_id"])
        if signal.get("setup_id")
        else None
    )
    for order in broker_orders:
        if (
            getattr(order, "magic", None) != magic
            or getattr(order, "symbol", None) != symbol
        ):
            continue
        comment = str(getattr(order, "comment", "") or "")
        if comment == setup_comment or not comment.startswith("SWG-"):
            return True
        if (
            _order_direction(mt5, order) == signal.get("direction")
            and abs(float(getattr(order, "price_open", 0.0)) - float(signal["entry_price"])) < 1e-8
        ):
            return True

    positions_get = getattr(mt5, "positions_get", None)
    if callable(positions_get):
        broker_positions = positions_get(symbol=symbol)
        if broker_positions is None:
            raise RuntimeError(f"Could not read open positions for {symbol}")
        for position in broker_positions:
            if (
                getattr(position, "magic", None) != magic
                or getattr(position, "symbol", None) != symbol
            ):
                continue
            comment = str(getattr(position, "comment", "") or "")
            if comment == setup_comment or not comment.startswith("SWG-"):
                return True
    return False


def swing_ema_zigzag_entry_decision(
    df,
    symbol: str,
    ema_periods: dict[str, int],
    zigzag_depth: int,
    zigzag_deviation_points: float,
    zigzag_back_step: int,
    min_structure_candles: int,
    max_structure_candles: int,
    ema_cross_window_candles: int,
    rr_ratio: float,
    pending_expiry_candles: int,
    sl_buffer_price: float,
    entry_buffer_price: float = 0.0,
    use_pivot2_for_buy: bool = True,
    use_pivot2_for_sell: bool = True,
    ema_consensus_enabled: bool = True,
    ema_fallback_enabled: bool = False,
    fallback_ema_periods: dict[str, int] | None = None,
):
    """Build a swing EMA zigzag stop-order signal from recent closed candles."""
    from src.swing_ema_strategy import build_swing_ema_entry_signal

    return build_swing_ema_entry_signal(
        data=df,
        symbol_point_size=get_pip_value(symbol),
        ema_periods=ema_periods,
        zigzag_depth=zigzag_depth,
        zigzag_deviation_points=zigzag_deviation_points,
        zigzag_back_step=zigzag_back_step,
        min_structure_candles=min_structure_candles,
        max_structure_candles=max_structure_candles,
        ema_cross_window_candles=ema_cross_window_candles,
        rr_ratio=rr_ratio,
        pending_expiry_candles=pending_expiry_candles,
        sl_buffer_price=sl_buffer_price,
        entry_buffer_price=entry_buffer_price,
        use_pivot2_for_buy=use_pivot2_for_buy,
        use_pivot2_for_sell=use_pivot2_for_sell,
        ema_consensus_enabled=ema_consensus_enabled,
        ema_fallback_enabled=ema_fallback_enabled,
        fallback_ema_periods=fallback_ema_periods or ema_periods,
    )


def get_recent_candles(mt5, symbol: str, timeframe_str: str, count: int = 120):
    """Lấy `count` nến đã đóng gần nhất dưới dạng DataFrame (cũ -> mới)."""
    import pandas as pd
    timeframe_map = {
        'M1': mt5.TIMEFRAME_M1, 'M5': mt5.TIMEFRAME_M5, 'M15': mt5.TIMEFRAME_M15,
        'M30': mt5.TIMEFRAME_M30, 'H1': mt5.TIMEFRAME_H1, 'H4': mt5.TIMEFRAME_H4,
        'D1': mt5.TIMEFRAME_D1,
    }
    timeframe = timeframe_map.get(timeframe_str, mt5.TIMEFRAME_M5)
    # +1 vì nến cuối (index 0) đang chạy, ta bỏ nó đi
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count + 1)
    if rates is None or len(rates) < 3:
        return None
    df = pd.DataFrame(rates)
    df = df.iloc[:-1]  # bỏ nến đang chạy -> chỉ nến đã đóng
    return df


def _calc_flex_lot(mt5, symbol: str, risk_mode: str, risk_percent: float, risk_amount: float,
                   entry_price: float, sl_price: float) -> float:
    """Calculate lot size from account equity and SL distance (flex mode)."""
    pip_value = get_pip_value(symbol)
    sl_pips = abs(entry_price - sl_price) / pip_value
    if sl_pips == 0:
        return 0.01

    # Get account equity and symbol tick info
    account = mt5.account_info()
    sym_info = mt5.symbol_info(symbol)
    if not account or not sym_info:
        return 0.01

    equity = account.equity
    if risk_mode == "percent":
        risk_usd = equity * risk_percent / 100
    else:
        risk_usd = risk_amount

    # pip_value_per_lot: dollar value of 1 pip for 1 lot
    # = tick_value * (pip_value / tick_size)
    tick_value = sym_info.trade_tick_value
    tick_size = sym_info.trade_tick_size
    if tick_size == 0:
        return 0.01
    pip_value_per_lot = tick_value * (pip_value / tick_size)
    if pip_value_per_lot == 0:
        return 0.01

    raw_lot = risk_usd / (sl_pips * pip_value_per_lot)
    # Round to symbol's volume step
    step = sym_info.volume_step or 0.01
    lot = max(sym_info.volume_min, round(raw_lot / step) * step)
    lot = min(lot, sym_info.volume_max)
    return round(lot, 2)


def _write_bot_state(pid: int, symbol: str, strategy: str, active: int, pending: int):
    """Write runtime state without allowing telemetry errors to crash trading."""
    state_path = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "bot_state.json")
    )
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    entry = {"pid": pid, "symbol": symbol, "strategy": strategy, "active": active, "pending": pending}
    try:
        from src.state_file import update_bot_state
        update_bot_state(state_path, entry)
    except OSError as error:
        log(f"Could not update bot runtime state: {error}", "WARN")


def _register_in_running_bots(pid: int, symbol: str, strategy: str, user: str,
                               test: bool, log_path: str, started_at: str):
    """Upsert this process into data/running_bots.json so the UI can see it.

    Called at bot startup — handles bots launched via run_bots.ps1 or any
    path that bypasses bot_manager.start_bot().
    """
    bots_path = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "running_bots.json")
    )
    os.makedirs(os.path.dirname(bots_path), exist_ok=True)
    tmp = bots_path + f".{pid}.tmp"
    try:
        with open(bots_path, "r", encoding="utf-8") as f:
            bots = json.load(f)
    except Exception:
        bots = []
    bots = [b for b in bots if b.get("pid") != pid]
    bots.append({
        "id": f"{strategy}_{symbol}_{user}_{pid}",
        "pid": pid,
        "strategy": strategy,
        "symbol": symbol,
        "user": user,
        "test": test,
        "started_at": started_at,
        "log_path": log_path,
    })
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(bots, f, indent=2)
    os.replace(tmp, bots_path)


def _unregister_from_running_bots(pid: int):
    """Remove this process from data/running_bots.json on clean exit."""
    bots_path = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "running_bots.json")
    )
    if not os.path.exists(bots_path):
        return
    tmp = bots_path + f".{pid}.tmp"
    try:
        with open(bots_path, "r", encoding="utf-8") as f:
            bots = json.load(f)
        bots = [b for b in bots if b.get("pid") != pid]
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(bots, f, indent=2)
        os.replace(tmp, bots_path)
    except Exception:
        pass


def _flag_path(pid: int) -> str:
    """Absolute path to the pending_restart flag file for this pid."""
    return os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "pending_restart", f"{pid}.flag")
    )


def _check_pending_restart(pid: int) -> bool:
    """Return True if a pending_restart flag file exists for this PID."""
    return os.path.exists(_flag_path(pid))


def _clear_pending_restart(pid: int):
    """Remove the pending_restart flag file."""
    try:
        os.remove(_flag_path(pid))
    except FileNotFoundError:
        pass


def _estimate_pnl_usd(mt5, symbol: str, direction: str, entry: float, exit_price: float,
                       lot: float, pip_value: float) -> float | None:
    """Estimate P&L in USD using broker tick value (correct for all symbols including XAU/BTC).

    Returns None when MT5 symbol info is unavailable (caller should omit USD figure).
    """
    try:
        sym_info = mt5.symbol_info(symbol)
        if sym_info is None:
            return None
        tick_value = sym_info.trade_tick_value
        tick_size = sym_info.trade_tick_size
        if not tick_size or not tick_value:
            return None
        pip_value_per_lot = tick_value * (pip_value / tick_size)
        pnl_pips = (
            (exit_price - entry) / pip_value if direction == "BUY"
            else (entry - exit_price) / pip_value
        )
        return pnl_pips * pip_value_per_lot * lot
    except Exception:
        return None


def _get_exit_deal(mt5, ticket: int, retries: int = 3, delay: float = 1.0):
    """Tìm deal đóng lệnh (DEAL_ENTRY_OUT=1) từ history theo position ticket.

    Retry vì deal history có thể delay vài giây sau khi broker close.
    Returns dict {price, profit, swap, commission} hoặc None nếu không tìm được.
    """
    import time as _time
    for attempt in range(retries):
        deals = mt5.history_deals_get(position=ticket)
        if deals:
            exit_deal = next((d for d in deals if d.entry == 1), None)  # 1 = DEAL_ENTRY_OUT
            if exit_deal:
                return {
                    "price": exit_deal.price,
                    "profit": exit_deal.profit,
                    "swap": exit_deal.swap,
                    "commission": exit_deal.commission,
                }
        if attempt < retries - 1:
            _time.sleep(delay)
    return None


def _is_flappy_order(order, symbol: str, magic: int) -> bool:
    """Match broker-side Flappy orders without depending on local process state."""
    return (
        getattr(order, "symbol", None) == symbol
        and (
            getattr(order, "magic", None) == magic
            or str(getattr(order, "comment", "")).upper().startswith("FLAPPY-")
        )
    )


def _order_direction(mt5, order) -> str | None:
    """Map a broker pending/position type to the strategy direction."""
    order_type = getattr(order, "type", None)
    buy_types = {
        getattr(mt5, "ORDER_TYPE_BUY_LIMIT", object()),
        getattr(mt5, "ORDER_TYPE_BUY_STOP", object()),
        getattr(mt5, "ORDER_TYPE_BUY_STOP_LIMIT", object()),
        getattr(mt5, "ORDER_TYPE_BUY", object()),
    }
    sell_types = {
        getattr(mt5, "ORDER_TYPE_SELL_LIMIT", object()),
        getattr(mt5, "ORDER_TYPE_SELL_STOP", object()),
        getattr(mt5, "ORDER_TYPE_SELL_STOP_LIMIT", object()),
        getattr(mt5, "ORDER_TYPE_SELL", object()),
    }
    if order_type in buy_types:
        return "BUY"
    if order_type in sell_types:
        return "SELL"
    return None


def _find_filled_position(
    mt5,
    pending_order,
    symbol: str,
    magic: int,
    direction: str | None = None,
    pending_ticket: int | None = None,
):
    """Find the position created by a pending order, even when tickets differ."""
    direction = direction or _order_direction(mt5, pending_order)
    positions = mt5.positions_get(symbol=symbol) or []
    candidates = [
        position for position in positions
        if _is_flappy_order(position, symbol, magic)
        and (direction is None or _order_direction(mt5, position) == direction)
    ]
    if pending_ticket is None:
        pending_ticket = getattr(pending_order, "ticket", None)
    linked = [
        position for position in candidates
        if pending_ticket in {
            getattr(position, "ticket", None),
            getattr(position, "identifier", None),
            getattr(position, "order", None),
        }
    ]
    if linked:
        return linked[0]
    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        return max(candidates, key=lambda item: getattr(item, "time", 0) or 0)
    return None


def _recover_flappy_state(mt5, symbol: str, magic: int, limit_order_candles: int,
                          timeframe: str, lot_size: float) -> tuple[list, list]:
    """Recover broker-side Flappy orders/positions after a process restart."""
    pending_orders = []
    active_trades = []
    orders = mt5.orders_get(symbol=symbol) or []
    positions = mt5.positions_get(symbol=symbol) or []
    timeframe_minutes = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}.get(timeframe, 5)
    now = time.time()
    for order in orders:
        if not _is_flappy_order(order, symbol, magic):
            continue
        direction = _order_direction(mt5, order)
        if direction is None:
            continue
        age_candles = max(0, int((now - (getattr(order, "time_setup", now) or now)) / (timeframe_minutes * 60)))
        candles_left = limit_order_candles - age_candles
        pending_orders.append({
            "signal": {
                "direction": direction,
                "entry_price": order.price_open,
                "stop_loss": order.sl,
                "take_profit": order.tp,
            },
            "trade_lot": getattr(order, "volume_current", lot_size) or lot_size,
            "candles_left": candles_left,
            "order_id": f"RECOVERED-{getattr(order, 'ticket', 'UNKNOWN')}",
            "mt5_ticket": getattr(order, "ticket", None),
        })
    for position in positions:
        if not _is_flappy_order(position, symbol, magic):
            continue
        direction = _order_direction(mt5, position)
        if direction is None:
            continue
        active_trades.append({
            "direction": direction,
            "entry": position.price_open,
            "sl": position.sl,
            "tp": position.tp,
            "ticket": position.ticket,
            "candles": 0,
            "order_id": f"RECOVERED-{position.ticket}",
            "lot": getattr(position, "volume", lot_size) or lot_size,
        })
    return pending_orders, active_trades


def _has_duplicate_pending(mt5, pending_orders: list, signal: dict,
                           symbol: str, magic: int) -> bool:
    """Prevent the same Flappy signal from being submitted twice."""
    def matches(candidate: dict) -> bool:
        existing = candidate.get("signal", candidate)
        return (
            existing.get("direction") == signal.get("direction")
            and all(
                abs(float(existing.get(key, 0)) - float(signal.get(key, 0))) < 1e-8
                for key in ("entry_price", "stop_loss", "take_profit")
            )
        )

    if any(matches(order) for order in pending_orders):
        return True
    broker_orders = mt5.orders_get(symbol=symbol) or []
    for order in broker_orders:
        if not _is_flappy_order(order, symbol, magic):
            continue
        if (
            _order_direction(mt5, order) == signal.get("direction")
            and abs(order.price_open - signal["entry_price"]) < 1e-8
            and abs(order.sl - signal["stop_loss"]) < 1e-8
            and abs(order.tp - signal["take_profit"]) < 1e-8
        ):
            return True
    return False


def run_swing_ema_zigzag_bot(
    args, strategy, params, credentials,
    entry_start_time: _time = _time(0, 0),
    entry_end_time: _time = _time(23, 59),
):
    """Live loop for confirmed swing EMA zigzag stop-order entries."""
    from src.orders import (
        cancel_pending_order,
        close_position,
        modify_position_sl_tp,
        place_stop_order,
    )
    from src.bot_history_manager import create_session, close_session, record_trade as _record_trade
    from src.swing_ema_strategy import (
        calculate_ema_series,
        calculate_swing_exit_levels,
        evaluate_ema_exit,
        is_pending_signal_expired,
    )
    from src.utils import check_exit

    timeframe = args.timeframe or params.get("timeframe", "M1")
    ema_periods = {
        "fast": args.ema_short_period or params.get("swing_ema_periods", {}).get("fast", 13),
        "medium": args.ema_medium_period or params.get("swing_ema_periods", {}).get("medium", 21),
        "slow": args.ema_long_period or params.get("swing_ema_periods", {}).get("slow", 55),
    }
    configured_fallback_emas = params.get(
        "swing_fallback_ema_periods",
        {"fast": 13, "medium": 21, "slow": 55},
    )
    fallback_ema_periods = {
        "fast": (
            args.fallback_ema_short_period
            if args.fallback_ema_short_period is not None
            else configured_fallback_emas.get("fast", 13)
        ),
        "medium": (
            args.fallback_ema_medium_period
            if args.fallback_ema_medium_period is not None
            else configured_fallback_emas.get("medium", 21)
        ),
        "slow": (
            args.fallback_ema_long_period
            if args.fallback_ema_long_period is not None
            else configured_fallback_emas.get("slow", 55)
        ),
    }
    use_pivot2_for_buy = (
        bool(args.use_pivot2_for_buy)
        if args.use_pivot2_for_buy is not None
        else bool(params.get("use_pivot2_for_buy", True))
    )
    use_pivot2_for_sell = (
        bool(args.use_pivot2_for_sell)
        if args.use_pivot2_for_sell is not None
        else bool(params.get("use_pivot2_for_sell", True))
    )
    ema_consensus_enabled = (
        bool(args.ema_consensus_enabled)
        if args.ema_consensus_enabled is not None
        else bool(params.get("ema_consensus_enabled", True))
    )
    ema_fallback_enabled = (
        bool(args.ema_fallback_enabled)
        if args.ema_fallback_enabled is not None
        else bool(params.get("ema_fallback_enabled", False))
    )
    zigzag_depth = args.zigzag_depth or params.get("zigzag_depth", 3)
    zigzag_deviation_points = (
        args.zigzag_deviation_points
        if args.zigzag_deviation_points is not None
        else params.get("zigzag_deviation_points", 3.0)
    )
    zigzag_back_step = (
        args.zigzag_back_step
        if args.zigzag_back_step is not None
        else params.get("zigzag_back_step", 3)
    )
    min_structure_candles = (
        args.min_structure_candles
        if args.min_structure_candles is not None
        else params.get("min_structure_candles", 10)
    )
    max_structure_candles = (
        args.max_structure_candles
        if args.max_structure_candles is not None
        else params.get("max_structure_candles", 20)
    )
    ema_cross_window_candles = (
        args.ema_cross_window_candles
        if args.ema_cross_window_candles is not None
        else params.get("ema_cross_window_candles", 15)
    )
    ema_exit_enabled = (
        bool(args.ema_exit_enabled)
        if args.ema_exit_enabled is not None
        else bool(params.get("ema_exit_enabled", True))
    )
    ema_exit_period = (
        args.ema_exit_period
        if args.ema_exit_period is not None
        else params.get("ema_exit_period", 21)
    )
    pending_expiry_candles = (
        args.pending_expiry_candles
        if args.pending_expiry_candles is not None
        else params.get("pending_expiry_candles", 7)
    )
    max_pending_orders_per_symbol = (
        args.max_pending_orders_per_symbol
        if args.max_pending_orders_per_symbol is not None
        else params.get("max_pending_orders_per_symbol", 0)
    )
    sl_buffer_pips = (
        args.sl_buffer_pips
        if args.sl_buffer_pips is not None
        else params.get("sl_buffer_pips", 5.0)
    )
    entry_buffer_pips = (
        args.entry_buffer_pips
        if args.entry_buffer_pips is not None
        else params.get("entry_buffer_pips", 2.0)
    )
    if entry_buffer_pips < 0:
        raise ValueError("Swing entry_buffer_pips cannot be negative")
    tp_type = args.tp_type or params.get("tp_type", "price_based")
    sl_type = args.sl_type or params.get("sl_type", "price_based")
    rr_ratio = args.rr_ratio or params.get("rr_ratio", 2.0)
    lot_size = args.lot_size or params.get("lot_size", 0.01)
    lot_mode = args.lot_mode or "fixed"
    risk_mode = args.risk_mode or "percent"
    risk_percent = args.risk_percent
    risk_amount = args.risk_amount
    magic = int(params.get("magic") or 212500)
    setup_state_path = os.path.join(_REPO_ROOT, "data", "swing_setup_state.json")
    setup_state_key = (
        f"{args.strategy}:{args.symbol}:{args.user}:{magic}:"
        f"{'test' if args.test else 'live'}"
    )
    from src.state_file import (
        load_swing_setup_ids,
        release_swing_setup_id,
        reserve_swing_setup_id,
    )
    try:
        used_setup_ids = (
            set()
            if args.test
            else load_swing_setup_ids(setup_state_path, setup_state_key)
        )
    except (OSError, ValueError) as error:
        message = f"Could not load Swing setup history: {error}"
        log(message, "ERROR")
        send_telegram(message, is_error=True)
        raise
    signal_lookback = max(
        120,
        int(ema_periods["slow"]) * 4,
        (
            max(int(period) for period in fallback_ema_periods.values()) * 4
            if ema_fallback_enabled
            else 0
        ),
        int(ema_exit_period) * 4,
        int(max_structure_candles) + int(zigzag_depth) * 6 + 30,
    )
    sl_buffer_price = sl_buffer_pips * get_pip_value(args.symbol)
    entry_buffer_price = entry_buffer_pips * get_pip_value(args.symbol)

    mt5_tmp, err_tmp = get_mt5_connection(credentials)
    if not err_tmp:
        sym_info = mt5_tmp.symbol_info(args.symbol)
        if sym_info and lot_mode == "fixed" and lot_size < sym_info.volume_min:
            log(f"lot_size {lot_size} < symbol min {sym_info.volume_min} — using {sym_info.volume_min}", "WARN")
            lot_size = sym_info.volume_min
        mt5_tmp.shutdown()

    log(
        "Swing EMA ZigZag params: "
        f"EMA={ema_periods['fast']}/{ema_periods['medium']}/{ema_periods['slow']}, "
        f"zigzag={zigzag_depth}/{zigzag_deviation_points}/{zigzag_back_step}, "
        f"structure={min_structure_candles}-{max_structure_candles}, "
        f"cross_window={ema_cross_window_candles}, expiry={pending_expiry_candles}, "
        f"max_pending={max_pending_orders_per_symbol}, ema_exit={'ON' if ema_exit_enabled else 'OFF'}({ema_exit_period}), "
        f"pivot2=BUY:{'ON' if use_pivot2_for_buy else 'OFF'}/SELL:{'ON' if use_pivot2_for_sell else 'OFF'}, "
        f"EMA consensus={'ON' if ema_consensus_enabled else 'OFF'}, "
        f"fallback={'ON' if ema_fallback_enabled else 'OFF'}, "
        f"entry_buffer={entry_buffer_pips}p, sl_buffer={sl_buffer_pips}p, rr={rr_ratio}"
    )
    send_telegram(
        f"Swing EMA ZigZag Bot Started\nSymbol: {args.symbol}\nUser: {args.user}\n"
        f"Test: {'Yes' if args.test else 'No'}"
    )

    _now_str = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    _session_id = create_session(
        strategy=args.strategy,
        symbol=args.symbol,
        mode="test" if args.test else "live",
        user=args.user,
        log_path=args.log_file or "",
    )
    _register_in_running_bots(
        pid=os.getpid(),
        symbol=args.symbol,
        strategy=args.strategy,
        user=args.user,
        test=bool(args.test),
        log_path=args.log_file or "",
        started_at=_now_str,
    )

    pending_orders = []
    active_trades = []
    last_candle_time = None
    live_bar_index = -1
    _mt5_ref = [None]

    def entry_identity(signal):
        return signal["direction"], round(float(signal["entry_price"]), 8)

    def apply_trade_protection(trade, mt5_connection):
        if args.test or trade.get("protection_applied", False):
            return

        applied, message = modify_position_sl_tp(
            trade["ticket"],
            trade["sl"],
            trade["tp"],
            credentials=credentials,
            mt5_connection=mt5_connection,
        )
        if applied:
            trade["protection_applied"] = True
            trade["protection_error_reported"] = False
            log(f"[{trade['order_id']}] {message}")
        elif not trade.get("protection_error_reported", False):
            error_message = (
                f"[{trade['order_id']}] Failed to apply fill-based SL/TP: {message}"
            )
            log(error_message, "ERROR")
            send_telegram(error_message, is_error=True)
            trade["protection_error_reported"] = True
        else:
            log(
                f"[{trade['order_id']}] SL/TP protection retry failed: {message}",
                "WARN",
            )

    def activate_filled_order(
        order, fill_price, position_ticket, previous_candle, mt5_connection
    ):
        signal = order["signal"]
        setup_id = signal.get("setup_id")
        if setup_id:
            used_setup_ids.add(setup_id)

        try:
            levels = calculate_swing_exit_levels(
                direction=signal["direction"],
                entry_price=float(fill_price),
                previous_candle=previous_candle,
                buffer_price=float(sl_buffer_price),
                rr_ratio=float(rr_ratio),
            )
        except ValueError as exc:
            message = f"[{order['order_id']}] Filled Swing order has invalid SL/TP: {exc}"
            log(message, "ERROR")
            send_telegram(message, is_error=True)
            if not args.test and position_ticket is not None:
                ok_close, close_msg = close_position(
                    position_ticket, credentials=credentials
                )
                if not ok_close:
                    error_message = (
                        f"[{order['order_id']}] Emergency close failed: {close_msg}"
                    )
                    log(error_message, "ERROR")
                    send_telegram(error_message, is_error=True)
            return None

        signal.update(levels)
        log(
            f"[{order['order_id']}] Fill-based protection: "
            f"SL={levels['stop_loss']:.5f} TP={levels['take_profit']:.5f}"
        )
        trade = {
            "direction": signal["direction"],
            "entry": float(fill_price),
            "sl": levels["stop_loss"],
            "tp": levels["take_profit"],
            "ticket": position_ticket,
            "order_id": order["order_id"],
            "lot": order["trade_lot"],
            "signal": signal,
            "protection_applied": bool(args.test),
            "protection_error_reported": False,
        }
        apply_trade_protection(trade, mt5_connection)
        return trade

    try:
        while True:
            mt5, error = _ensure_mt5_connected(_mt5_ref, credentials)
            if error:
                log(f"MT5 connection failed: {error}", "ERROR")
                send_telegram(f"MT5 Error: {error}", is_error=True)
                time.sleep(args.interval)
                continue

            df = get_recent_candles(mt5, args.symbol, timeframe, signal_lookback)
            if df is None or len(df) < max(ema_periods["slow"] + 5, (zigzag_depth * 2) + 5):
                time.sleep(args.interval)
                continue

            last = df.iloc[-1]
            candle_time = datetime.fromtimestamp(int(last["time"]), tz=TIMEZONE)
            is_new_candle = (last_candle_time is None) or (candle_time > last_candle_time)

            if is_new_candle:
                live_bar_index += 1
                current_bar_index = live_bar_index
                candle = {
                    "open": float(last["open"]),
                    "high": float(last["high"]),
                    "low": float(last["low"]),
                    "close": float(last["close"]),
                }
                ema_exit_value = None
                if ema_exit_enabled:
                    ema_exit_series = calculate_ema_series(df["close"], int(ema_exit_period))
                    if ema_exit_series:
                        ema_exit_value = float(ema_exit_series[-1])

                still_pending = []
                processed_pending_entry_ids = set()
                for order in pending_orders:
                    oid = order["order_id"]
                    mt5_ticket = order.get("mt5_ticket")
                    signal = order["signal"]
                    direction = signal["direction"]
                    signal_entry_id = entry_identity(signal)
                    if args.test or mt5_ticket is None:
                        if is_pending_signal_expired(signal, current_bar_index):
                            log(f"[{oid}] [TEST] Swing stop expired")
                            continue
                        if signal_entry_id in processed_pending_entry_ids:
                            log(f"[{oid}] Duplicate Swing Entry discarded")
                            continue
                        processed_pending_entry_ids.add(signal_entry_id)
                        filled = (
                            candle["high"] >= signal["entry_price"]
                            if direction == "BUY"
                            else candle["low"] <= signal["entry_price"]
                        )
                        if filled:
                            fill_price = (
                                max(signal["entry_price"], candle["open"])
                                if direction == "BUY"
                                else min(signal["entry_price"], candle["open"])
                            )
                            log(f"[{oid}] [TEST] Swing stop filled @ {fill_price:.2f}")
                            trade = activate_filled_order(
                                order,
                                fill_price,
                                None,
                                {
                                    "high": float(df.iloc[-2]["high"]),
                                    "low": float(df.iloc[-2]["low"]),
                                },
                                mt5,
                            )
                            if trade is not None:
                                active_trades.append(trade)
                        else:
                            still_pending.append(order)
                        continue

                    pending_on_mt5 = mt5.orders_get(ticket=mt5_ticket)
                    if pending_on_mt5:
                        if is_pending_signal_expired(signal, current_bar_index):
                            ok_cancel, cancel_msg = cancel_pending_order(
                                mt5_ticket, credentials=credentials
                            )
                            if not ok_cancel:
                                log(f"[{oid}] Cancel FAILED: {cancel_msg}", "ERROR")
                                still_pending.append(order)
                            else:
                                log(f"[{oid}] Swing stop expired and cancelled")
                            continue
                        if signal_entry_id in processed_pending_entry_ids:
                            ok_cancel, cancel_msg = cancel_pending_order(
                                mt5_ticket, credentials=credentials
                            )
                            if not ok_cancel:
                                log(
                                    f"[{oid}] Duplicate pending order cancel failed: "
                                    f"{cancel_msg}",
                                    "ERROR",
                                )
                                still_pending.append(order)
                            else:
                                log(f"[{oid}] Duplicate Swing Entry cancelled")
                            continue
                        processed_pending_entry_ids.add(signal_entry_id)
                        still_pending.append(order)
                        continue

                    position = _find_filled_position(
                        mt5,
                        None,
                        args.symbol,
                        magic,
                        direction=direction,
                        pending_ticket=mt5_ticket,
                    )
                    if position:
                        if signal_entry_id in processed_pending_entry_ids:
                            position_ticket = getattr(
                                position, "ticket", mt5_ticket
                            )
                            ok_close, close_msg = close_position(
                                position_ticket, credentials=credentials
                            )
                            if not ok_close:
                                error_message = (
                                    f"[{oid}] Duplicate filled Swing position "
                                    f"could not be closed: {close_msg}"
                                )
                                log(error_message, "ERROR")
                                send_telegram(error_message, is_error=True)
                            else:
                                log(f"[{oid}] Duplicate filled Swing Entry closed")
                            continue
                        processed_pending_entry_ids.add(signal_entry_id)
                        fill_price = float(position.price_open)
                        position_ticket = getattr(position, "ticket", mt5_ticket)
                        log(f"[{oid}] Swing stop filled @ {fill_price:.5f} (ticket={position_ticket})")
                        trade = activate_filled_order(
                            order,
                            fill_price,
                            position_ticket,
                            {
                                "high": float(df.iloc[-2]["high"]),
                                "low": float(df.iloc[-2]["low"]),
                            },
                            mt5,
                        )
                        if trade is not None:
                            active_trades.append(trade)
                    else:
                        log(f"[{oid}] Pending order disappeared without open position", "WARN")

                pending_orders = still_pending

                still_active = []
                for trade in active_trades:
                    oid = trade["order_id"]
                    position_open = True
                    if not args.test and trade.get("ticket") is not None:
                        position_open = bool(mt5.positions_get(ticket=trade["ticket"]) or [])

                    if position_open:
                        apply_trade_protection(trade, mt5)

                    exit_type, exit_price = check_exit(
                        trade["direction"], candle, trade["tp"], trade["sl"],
                        tp_type=tp_type, sl_type=sl_type,
                    )
                    verified = False
                    if exit_type is None and ema_exit_enabled and ema_exit_value is not None:
                        ema_exit = evaluate_ema_exit(trade["direction"], candle, ema_exit_value, use_close=True)
                        if ema_exit["exit"]:
                            exit_type = "EMA"
                            exit_price = float(ema_exit["price"])

                    if exit_type is None and not position_open:
                        exit_type = "BROKER"
                        exit_price = float(candle["close"])

                    if exit_type is None:
                        still_active.append(trade)
                        continue

                    if not args.test and position_open and trade.get("ticket") is not None:
                        ok_close, close_msg = close_position(
                            trade["ticket"], credentials=credentials, test=False
                        )
                        if not ok_close:
                            log(f"[{oid}] Close FAILED: {close_msg}", "ERROR")
                            still_active.append(trade)
                            continue
                        log(f"[{oid}] Swing exit close sent: {close_msg}")

                    pnl_usd = None
                    if not args.test:
                        pnl_usd = _estimate_pnl_usd(
                            mt5, args.symbol, trade["direction"], trade["entry"],
                            float(exit_price), trade["lot"], get_pip_value(args.symbol),
                        )
                    _record_trade(
                        _session_id, oid, trade["direction"], trade["entry"],
                        float(exit_price), exit_type, pnl_usd, trade["lot"], verified=verified
                    )
                    log(f"[{oid}] Swing exit: {exit_type} @ {float(exit_price):.5f}")

                active_trades = still_active

                now_hcm = datetime.now(TIMEZONE)
                in_window = _in_time_window(now_hcm, entry_start_time, entry_end_time)
                pending_cap_reached = (
                    max_pending_orders_per_symbol > 0
                    and len(pending_orders) >= max_pending_orders_per_symbol
                )
                if in_window and not pending_cap_reached:
                    signal = swing_ema_zigzag_entry_decision(
                        df=df,
                        symbol=args.symbol,
                        ema_periods=ema_periods,
                        zigzag_depth=int(zigzag_depth),
                        zigzag_deviation_points=float(zigzag_deviation_points),
                        zigzag_back_step=int(zigzag_back_step),
                        min_structure_candles=int(min_structure_candles),
                        max_structure_candles=int(max_structure_candles),
                        ema_cross_window_candles=int(ema_cross_window_candles),
                        rr_ratio=float(rr_ratio),
                        pending_expiry_candles=int(pending_expiry_candles),
                        sl_buffer_price=float(sl_buffer_price),
                        entry_buffer_price=float(entry_buffer_price),
                        use_pivot2_for_buy=use_pivot2_for_buy,
                        use_pivot2_for_sell=use_pivot2_for_sell,
                        ema_consensus_enabled=ema_consensus_enabled,
                        ema_fallback_enabled=ema_fallback_enabled,
                        fallback_ema_periods=fallback_ema_periods,
                    )
                    if (
                        signal
                        and signal.get("setup_id") not in used_setup_ids
                        and not _has_duplicate_swing_pending(
                            mt5,
                            pending_orders,
                            signal,
                            args.symbol,
                            magic,
                            active_trades=active_trades,
                        )
                    ):
                        signal["created_bar_index"] = current_bar_index
                        signal["expires_at_bar"] = (
                            current_bar_index + int(pending_expiry_candles)
                        )
                        trade_lot = lot_size
                        if lot_mode == "flex":
                            trade_lot = _calc_flex_lot(
                                mt5, args.symbol, risk_mode, risk_percent, risk_amount,
                                signal["entry_price"], signal["stop_loss"],
                            )
                        import uuid as _uuid
                        order_id = (
                            f"ORD-{candle_time.strftime('%y%m%d-%H%M%S')}-"
                            f"{args.symbol}-{_uuid.uuid4().hex[:4].upper()}"
                        )
                        setup_id = signal.get("setup_id")
                        can_submit = True
                        if setup_id and not args.test:
                            can_submit = reserve_swing_setup_id(
                                setup_state_path,
                                setup_state_key,
                                setup_id,
                            )
                            if not can_submit:
                                used_setup_ids.add(setup_id)
                                log(
                                    f"[{order_id}] Swing setup was already reserved "
                                    "by another bot process"
                                )
                        if can_submit:
                            if setup_id and not args.test:
                                used_setup_ids.add(setup_id)
                            ok_stop, msg_stop, mt5_ticket, submission_status = place_stop_order(
                                args.symbol, signal["direction"], trade_lot, signal["entry_price"],
                                sl=None, tp=None,
                                credentials=credentials, test=bool(args.test),
                                magic=magic,
                                comment=(
                                    _swing_setup_order_comment(setup_id)
                                    if setup_id
                                    else f"SWING-{order_id[-4:]}"
                                ),
                                return_status=True,
                            )
                            if not ok_stop:
                                if (
                                    setup_id
                                    and not args.test
                                    and submission_status == "rejected"
                                ):
                                    release_swing_setup_id(
                                        setup_state_path,
                                        setup_state_key,
                                        setup_id,
                                    )
                                    used_setup_ids.discard(setup_id)
                                log(f"[{order_id}] Failed to place swing stop: {msg_stop}", "ERROR")
                                if submission_status == "unknown":
                                    warning = (
                                        f"[{order_id}] Submission outcome is unknown; "
                                        "setup remains reserved to prevent duplicates"
                                    )
                                    log(warning, "WARN")
                                    send_telegram(warning, is_error=True)
                            else:
                                if setup_id:
                                    used_setup_ids.add(setup_id)
                                log(
                                    f"[{order_id}] Swing stop placed {signal['direction']} "
                                    f"entry={signal['entry_price']:.5f} "
                                    f"estimated_sl={signal['stop_loss']:.5f} "
                                    f"estimated_tp={signal['take_profit']:.5f} "
                                    f"expiry={signal['expiry_bars']} bars"
                                )
                                pending_orders.append({
                                    "signal": signal,
                                    "trade_lot": trade_lot,
                                    "order_id": order_id,
                                    "mt5_ticket": mt5_ticket,
                                })

                last_candle_time = candle_time
                _write_bot_state(os.getpid(), args.symbol, args.strategy, len(active_trades), len(pending_orders))
                if _check_pending_restart(os.getpid()) and not active_trades and not pending_orders:
                    log("Pending restart flag detected and bot is idle — restarting with new code")
                    _clear_pending_restart(os.getpid())
                    _write_bot_state(os.getpid(), args.symbol, args.strategy, 0, 0)
                    _unregister_from_running_bots(os.getpid())
                    close_session(_session_id)
                    raise _GracefulRestart()
            elif not args.test and pending_orders:
                still_pending = []
                for order in pending_orders:
                    mt5_ticket = order.get("mt5_ticket")
                    if mt5_ticket is None or mt5.orders_get(ticket=mt5_ticket):
                        still_pending.append(order)
                        continue

                    signal = order["signal"]
                    direction = signal["direction"]
                    position = _find_filled_position(
                        mt5,
                        None,
                        args.symbol,
                        magic,
                        direction=direction,
                        pending_ticket=mt5_ticket,
                    )
                    if position is None:
                        log(
                            f"[{order['order_id']}] Pending order disappeared "
                            "without open position",
                            "WARN",
                        )
                        continue

                    fill_price = float(position.price_open)
                    position_ticket = getattr(position, "ticket", mt5_ticket)
                    trade = activate_filled_order(
                        order,
                        fill_price,
                        position_ticket,
                        {
                            "high": float(df.iloc[-2]["high"]),
                            "low": float(df.iloc[-2]["low"]),
                        },
                        mt5,
                    )
                    if trade is not None:
                        active_trades.append(trade)
                    log(
                        f"[{order['order_id']}] Swing stop filled @ "
                        f"{fill_price:.5f} (ticket={position_ticket})"
                    )
                pending_orders = still_pending

            if not is_new_candle and not args.test:
                for trade in active_trades:
                    if trade.get("ticket") is not None:
                        apply_trade_protection(trade, mt5)

            time.sleep(args.interval)

    except KeyboardInterrupt:
        log("Swing EMA ZigZag Bot stopped by user")
        _write_bot_state(os.getpid(), args.symbol, args.strategy, 0, 0)
        _unregister_from_running_bots(os.getpid())
        close_session(_session_id)
        if not args.managed_by_ui:
            send_telegram("Swing EMA ZigZag Bot Stopped (manual)")
    except _GracefulRestart:
        raise
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log(f"Swing EMA ZigZag Bot error: {e}", "ERROR")
        _write_bot_state(os.getpid(), args.symbol, args.strategy, 0, 0)
        _unregister_from_running_bots(os.getpid())
        close_session(_session_id)
        send_telegram(
            f"❌ Swing EMA ZigZag Bot crashed\nSymbol: {args.symbol}\nError: {e}\n\n<pre>{tb[-800:]}</pre>",
            is_error=True,
        )
        raise
    finally:
        try:
            import MetaTrader5 as _mt5_mod
            _mt5_mod.shutdown()
        except Exception:
            pass


def run_feg_bot(args, strategy, params, credentials,
                entry_start_time: _time = _time(0, 0),
                entry_end_time: _time = _time(23, 59)):
    """Run the shared pattern live loop for FEG and Flappy Bird."""
    from src.orders import place_order, close_position, place_limit_order, cancel_pending_order

    strategy_label = "Flappy Bird" if args.strategy == "flappy_bird" else "FEG"
    is_flappy = is_flappy_strategy(args.strategy)
    if is_flappy:
        strategy_label = "Multi Flappy Bird" if args.strategy == "multi_flappy_bird" else "Flappy Bird"
    timeframe = args.timeframe or params.get('timeframe', 'M5')
    ema_period = args.ema_period or params.get('ema_period', 21)
    rr_ratio = args.rr_ratio or params.get('rr_ratio', 2.0)
    buffer_k = args.buffer_k if args.buffer_k is not None else params.get('buffer_k', 5)
    entry_body_percent = (
        args.entry_body_percent
        if args.entry_body_percent is not None
        else params.get('entry_body_percent', 5.0)
    )
    lot_size = args.lot_size or params.get('lot_size', 0.01)
    max_candles = args.max_candles if args.max_candles is not None else params.get('max_candles', 7)
    h2_exceed_pips = args.h2_exceed_pips if args.h2_exceed_pips else params.get('h2_exceed_pips', 0.0)
    c2_gap_pips    = args.c2_gap_pips    if args.c2_gap_pips    else params.get('c2_gap_pips',    0.0)
    ema_margin_pips = args.ema_margin_pips if args.ema_margin_pips else params.get('ema_margin_pips', 0.0)
    ema_filter_enabled = bool(args.ema_filter_enabled)
    buy_ema_side  = args.buy_ema_side  or params.get('buy_ema_side',  'below_ema')
    sell_ema_side = args.sell_ema_side or params.get('sell_ema_side', 'above_ema')
    limit_order_candles = (
        args.limit_order_candles
        if args.limit_order_candles is not None
        else params.get('limit_order_candles', 7 if is_flappy else 1)
    )
    if limit_order_candles <= 0:
        raise ValueError("limit_order_candles must be positive")
    max_candles = (
        0 if is_flappy
        else args.max_candles if args.max_candles is not None
        else params.get('max_candles', 7)
    )
    min_father_body_points = (
        args.min_father_body_points
        if args.min_father_body_points is not None
        else params.get('min_father_body_points', 2.0)
    )
    min_child_candles = (
        args.min_child_candles if args.min_child_candles is not None
        else params.get("min_child_candles", 2)
    )
    max_child_candles = (
        args.max_child_candles if args.max_child_candles is not None
        else params.get("max_child_candles", 5)
    )
    max_child_body_points = (
        args.max_child_body_points if args.max_child_body_points is not None
        else params.get("max_child_body_points", 2.0)
    )
    cross_window_candles = (
        args.cross_window_candles
        if args.cross_window_candles is not None
        else params.get("cross_window_candles", 12)
    )
    use_mother_candle = (
        bool(args.use_mother_candle)
        if args.use_mother_candle is not None
        else bool(params.get("use_mother_candle", True))
    )
    no_mother_child_candles = (
        args.no_mother_child_candles
        if args.no_mother_child_candles is not None
        else int(params.get("no_mother_child_candles", 2))
    )
    no_mother_child_body_ratio = (
        args.no_mother_child_body_ratio
        if args.no_mother_child_body_ratio is not None
        else float(params.get("no_mother_child_body_ratio", 1.5))
    )
    no_mother_child_body_max_points = (
        args.no_mother_child_body_max_points
        if args.no_mother_child_body_max_points is not None
        else float(params.get("no_mother_child_body_max_points", 1.5))
    )
    no_mother_father_wick_max_pct = (
        args.no_mother_father_wick_max_pct
        if args.no_mother_father_wick_max_pct is not None
        else float(params.get("no_mother_father_wick_max_pct", 40.0))
    )
    no_mother_cross_window_candles = (
        args.no_mother_cross_window_candles
        if args.no_mother_cross_window_candles is not None
        else int(params.get("no_mother_cross_window_candles", 15))
    )
    no_mother_sl_buffer_pips = (
        args.no_mother_sl_buffer_pips
        if args.no_mother_sl_buffer_pips is not None
        else float(params.get("no_mother_sl_buffer_pips", 5.0))
    )
    ema_groups = {}
    for group in ("consensus", "fallback"):
        ema_groups[group] = {}
        for slot, default in (("short", 13), ("medium", 21), ("long", 55)):
            arg_value = getattr(args, f"flappy_{group}_{slot}")
            config = params.get(f"ema_{group}", {})
            ema_groups[group][slot] = (
                arg_value if arg_value is not None
                else int(config.get(slot, default))
            )
        values = [ema_groups[group][slot] for slot in ("short", "medium", "long")]
        if not values[0] < values[1] < values[2]:
            raise ValueError(f"Flappy {group} EMA periods must be strictly increasing")
    consensus_short, consensus_medium, consensus_long = (
        ema_groups["consensus"][slot] for slot in ("short", "medium", "long")
    )
    fallback_short, fallback_medium, fallback_long = (
        ema_groups["fallback"][slot] for slot in ("short", "medium", "long")
    )
    higher_ema_consensus_enabled = (
        bool(args.higher_ema_consensus_enabled)
        if args.higher_ema_consensus_enabled is not None
        else bool(params.get("higher_ema_consensus_enabled", True))
    )
    higher_ema_fallback_enabled = (
        bool(args.higher_ema_fallback_enabled)
        if args.higher_ema_fallback_enabled is not None
        else bool(params.get("higher_ema_fallback_enabled", True))
    )
    higher_timeframe = (
        args.higher_timeframe or params.get("higher_timeframe", "M5")
    )
    higher_timeframe_filter_enabled = (
        bool(args.higher_timeframe_filter_enabled)
        if args.higher_timeframe_filter_enabled is not None
        else bool(params.get("higher_timeframe_filter_enabled", False))
    )
    current_timeframe_filter_enabled = (
        bool(args.current_timeframe_filter_enabled)
        if args.current_timeframe_filter_enabled is not None
        else bool(params.get("current_timeframe_filter_enabled", True))
    )
    higher_ema_groups = {}
    for group in ("higher_ema_consensus", "higher_ema_fallback"):
        config = params.get(group, {})
        higher_ema_groups[group] = {}
        for slot, default in (("short", 13), ("medium", 21), ("long", 55)):
            arg_value = getattr(args, f"{group}_{slot}")
            higher_ema_groups[group][slot] = (
                arg_value if arg_value is not None else int(config.get(slot, default))
            )
        # These periods only drive real trading logic when the HTF filter (and
        # this specific mode) is actually enabled; skip the ordering check
        # otherwise so stale/disabled widget values can never block startup.
        group_mode_enabled = (
            higher_ema_consensus_enabled if group == "higher_ema_consensus"
            else higher_ema_fallback_enabled
        )
        if higher_timeframe_filter_enabled and group_mode_enabled:
            values = [higher_ema_groups[group][slot] for slot in ("short", "medium", "long")]
            if not values[0] < values[1] < values[2]:
                raise ValueError(f"Multi Flappy {group} EMA periods must be strictly increasing")
    if is_flappy and args.strategy == "multi_flappy_bird" and higher_timeframe_filter_enabled:
        if not higher_ema_consensus_enabled and not higher_ema_fallback_enabled:
            raise ValueError("At least one Multi Flappy higher timeframe mode must be enabled")
    consensus_enabled = (
        bool(args.flappy_consensus_enabled)
        if args.flappy_consensus_enabled is not None
        else bool(params.get("ema_consensus_enabled", True))
    )
    fallback_enabled = (
        bool(args.flappy_fallback_enabled)
        if args.flappy_fallback_enabled is not None
        else bool(params.get("ema_fallback_enabled", True))
    )
    if not consensus_enabled and not fallback_enabled:
        raise ValueError("At least one Flappy EMA mode must be enabled")
    if min_child_candles < 2 or max_child_candles < min_child_candles:
        raise ValueError("Flappy child candle range is invalid")
    mother_coverage_enabled = (
        bool(args.mother_coverage_enabled)
        if args.mother_coverage_enabled is not None
        else bool(params.get("mother_coverage_enabled", True))
    )
    flappy_magic = params.get("magic") or 212400
    entry_mode = args.entry_mode or params.get('entry_mode', 'close')
    entry_percent = args.entry_percent if args.entry_percent is not None else params.get('entry_percent', 0.0)
    tp_type = args.tp_type or params.get('tp_type', 'price_based')
    sl_type = args.sl_type or params.get('sl_type', 'close_based')
    lot_mode = args.lot_mode or 'fixed'
    risk_mode = args.risk_mode or 'percent'
    risk_percent = args.risk_percent
    risk_amount = args.risk_amount
    re_entry_after_sl = bool(args.re_entry_after_sl)
    c2_buy_upper_wick_max_pct  = args.c2_buy_upper_wick_max_pct
    c2_buy_lower_wick_max_pct  = args.c2_buy_lower_wick_max_pct
    c2_sell_upper_wick_max_pct = args.c2_sell_upper_wick_max_pct
    c2_sell_lower_wick_max_pct = args.c2_sell_lower_wick_max_pct
    c2_buy_upper_wick_cmp  = args.c2_buy_upper_wick_cmp  or "lt"
    c2_buy_lower_wick_cmp  = args.c2_buy_lower_wick_cmp  or "lt"
    c2_sell_upper_wick_cmp = args.c2_sell_upper_wick_cmp or "lt"
    c2_sell_lower_wick_cmp = args.c2_sell_lower_wick_cmp or "lt"

    # Auto-detect symbol min lot and clamp (only for fixed mode)
    mt5_tmp, err_tmp = get_mt5_connection(credentials)
    if not err_tmp:
        sym_info = mt5_tmp.symbol_info(args.symbol)
        if sym_info and lot_mode == "fixed" and lot_size < sym_info.volume_min:
            log(f"lot_size {lot_size} < symbol min {sym_info.volume_min} — using {sym_info.volume_min}", "WARN")
            lot_size = sym_info.volume_min
        mt5_tmp.shutdown()

    lot_log = f"flex({risk_mode} {risk_percent}%/{risk_amount}$)" if lot_mode == "flex" else f"fixed={lot_size}"
    be_log = f"BE=ON(r={args.be_r})" if args.be_enabled else "BE=OFF"
    ema_filter_str = f"EMA_filter=ON(buy={buy_ema_side},sell={sell_ema_side},margin={ema_margin_pips}p)" if ema_filter_enabled else "EMA_filter=OFF"
    re_entry_log = "ReEntry=ON" if re_entry_after_sl else "ReEntry=OFF"
    _wb = []
    if c2_buy_upper_wick_max_pct is not None: _wb.append(f"upper{c2_buy_upper_wick_cmp}{c2_buy_upper_wick_max_pct}%")
    if c2_buy_lower_wick_max_pct is not None: _wb.append(f"lower{c2_buy_lower_wick_cmp}{c2_buy_lower_wick_max_pct}%")
    _ws = []
    if c2_sell_upper_wick_max_pct is not None: _ws.append(f"upper{c2_sell_upper_wick_cmp}{c2_sell_upper_wick_max_pct}%")
    if c2_sell_lower_wick_max_pct is not None: _ws.append(f"lower{c2_sell_lower_wick_cmp}{c2_sell_lower_wick_max_pct}%")
    wick_log = f"WickFilter=BUY({','.join(_wb) or 'OFF'}) SELL({','.join(_ws) or 'OFF'})"
    if is_flappy:
        log(
            f"Flappy Bird params: consensus EMA{consensus_short}/{consensus_medium}/{consensus_long}, "
            f"fallback EMA{fallback_short}/{fallback_medium}/{fallback_long}, RR={rr_ratio}, "
            f"lot={lot_log}, pending_candles={limit_order_candles}, "
            f"max_candles={max_candles or 'unlimited'}, timeframe={timeframe}"
        )
    else:
        log(f"FEG params: EMA{ema_period}, RR={rr_ratio}, buffer_k={buffer_k}, "
            f"lot={lot_log}, max_candles={max_candles or 'unlimited'}, "
            f"h2_exceed={h2_exceed_pips}p, c2_gap={c2_gap_pips}p, {ema_filter_str}, {be_log}, {re_entry_log}, {wick_log}")

    if not send_telegram(
        f"{strategy_label} Bot Started\nSymbol: {args.symbol}\nUser: {args.user}\n"
        f"Test: {'Yes' if args.test else 'No'}"
    ):
        log("Startup Telegram notification failed; inspect Telegram configuration/API error above", "ERROR")

    from src.bot_history_manager import create_session, close_session, record_trade as _record_trade
    _now_str = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    _session_id = create_session(
        strategy=args.strategy,
        symbol=args.symbol,
        mode="test" if args.test else "live",
        user=args.user,
        log_path=args.log_file or "",
    )
    _register_in_running_bots(
        pid=os.getpid(),
        symbol=args.symbol,
        strategy=args.strategy,
        user=args.user,
        test=bool(args.test),
        log_path=args.log_file or "",
        started_at=_now_str,
    )

    # pending_orders: list of {signal, trade_lot, candles_left, order_id}
    # active_trades: list of {direction, entry, sl, tp, ticket, candles, order_id}
    pending_orders = []
    active_trades  = []
    last_candle_time = None
    _mt5_ref = [None]  # persistent MT5 connection — reconnects only when terminal disconnects
    state_recovered = False

    try:
        while True:
            mt5, error = _ensure_mt5_connected(_mt5_ref, credentials)
            if error:
                log(f"MT5 connection failed: {error}", "ERROR")
                send_telegram(f"MT5 Error: {error}", is_error=True)
                time.sleep(args.interval)
                continue

            if is_flappy and not args.test and not state_recovered:
                pending_orders, active_trades = _recover_flappy_state(
                    mt5, args.symbol, flappy_magic, limit_order_candles,
                    timeframe, lot_size,
                )
                state_recovered = True
                _write_bot_state(os.getpid(), args.symbol, args.strategy,
                                 len(active_trades), len(pending_orders))
                log(f"Recovered Flappy state: pending={len(pending_orders)} active={len(active_trades)}")

            df = get_recent_candles(
                mt5, args.symbol, timeframe,
                count=max(
                    EMA_WARMUP_WINDOW,
                    consensus_long * 4,
                    fallback_long * 4,
                ) if is_flappy else max(EMA_WARMUP_WINDOW, ema_period * 4),
            )
            if df is None or len(df) < ema_period + 2:
                log(f"Insufficient candle data for {args.symbol} (got {len(df) if df is not None else 0})", "ERROR")
                send_telegram(f"❌ Insufficient candle data\nSymbol: {args.symbol}", is_error=True)
                time.sleep(args.interval)
                continue

            higher_df = None
            higher_ema_series = {}
            if is_flappy and args.strategy == "multi_flappy_bird" and higher_timeframe_filter_enabled:
                higher_longest = max(
                    higher_ema_groups["higher_ema_consensus"]["long"],
                    higher_ema_groups["higher_ema_fallback"]["long"],
                )
                higher_df = get_recent_candles(
                    mt5, args.symbol, higher_timeframe,
                    count=max(EMA_WARMUP_WINDOW, higher_longest * 4),
                )
                if higher_df is None or len(higher_df) < higher_longest + 2:
                    log(
                        f"Insufficient higher timeframe data for {args.symbol} "
                        f"({higher_timeframe}, got {len(higher_df) if higher_df is not None else 0})",
                        "ERROR",
                    )
                    time.sleep(args.interval)
                    continue
                for group_name, group_periods in higher_ema_groups.items():
                    higher_ema_series[group_name] = {
                        slot: calculate_flappy_ema_series(
                            higher_df["close"], period, EMA_WARMUP_WINDOW
                        )
                        for slot, period in group_periods.items()
                    }

            ema = df["close"].ewm(span=ema_period, adjust=False).mean().tolist()
            ema13_series = calculate_flappy_ema_series(
                df["close"], consensus_short, EMA_WARMUP_WINDOW
            )
            ema21_series = calculate_flappy_ema_series(
                df["close"], consensus_medium, EMA_WARMUP_WINDOW
            )
            ema55_series = calculate_flappy_ema_series(
                df["close"], consensus_long, EMA_WARMUP_WINDOW
            )
            fallback_ema13_series = calculate_flappy_ema_series(
                df["close"], fallback_short, EMA_WARMUP_WINDOW
            )
            fallback_ema21_series = calculate_flappy_ema_series(
                df["close"], fallback_medium, EMA_WARMUP_WINDOW
            )
            fallback_ema55_series = calculate_flappy_ema_series(
                df["close"], fallback_long, EMA_WARMUP_WINDOW
            )
            cross_directions, cross_ages = calculate_flappy_ema_cross_lifecycle(
                df["close"], 8, 13, EMA_WARMUP_WINDOW
            )
            last = df.iloc[-1]
            prev = df.iloc[-2]
            candle_time = datetime.fromtimestamp(int(last["time"]), tz=TIMEZONE)
            is_new_candle = (last_candle_time is None) or (candle_time > last_candle_time)

            if pending_orders or active_trades:
                log(f"Tick check @ {datetime.now(TIMEZONE).strftime('%H:%M:%S')} | "
                    f"last candle: {candle_time.strftime('%H:%M')} "
                    f"O={last['open']:.2f} H={last['high']:.2f} L={last['low']:.2f} C={last['close']:.2f} | "
                    f"EMA={ema[-1]:.2f} | new_candle={is_new_candle} | "
                    f"pending={len(pending_orders)} active={len(active_trades)}")

            if is_new_candle:
                from src.utils import check_exit
                candle = {"high": last["high"], "low": last["low"], "close": last["close"]}

                # 1. Check pending orders — poll MT5 ticket each candle
                still_pending = []
                for order in pending_orders:
                    oid = order["order_id"]
                    mt5_ticket = order.get("mt5_ticket")
                    _sig = order["signal"]

                    # Test mode: simulate fill by candle low/high (unchanged behaviour)
                    if args.test or mt5_ticket is None:
                        filled = (
                            candle["low"] <= _sig["entry_price"]
                            if _sig["direction"] == "BUY"
                            else candle["high"] >= _sig["entry_price"]
                        )
                        if filled:
                            log(f"[{oid}] [TEST] Limit order filled @ {_sig['entry_price']:.2f}")
                            send_telegram(f"<b>{strategy_label} Limit Filled (TEST): {_sig['direction']}</b>\n"
                                          f"ID: <code>{oid}</code>\nEntry: {_sig['entry_price']:.2f}\n"
                                          f"SL: {_sig['stop_loss']:.2f} TP: {_sig['take_profit']:.2f}\n"
                                          f"Lot: {order['trade_lot']}")
                            active_trades.append({
                                "direction": _sig["direction"],
                                "entry": _sig["entry_price"],
                                "sl": _sig["stop_loss"],
                                "tp": _sig["take_profit"],
                                "ticket": None, "candles": 0, "order_id": oid,
                                "lot": order.get("trade_lot", lot_size),
                                "ema_mode": _sig.get("ema_mode"),
                            })
                        else:
                            order["candles_left"] -= 1
                            if order["candles_left"] > 0:
                                still_pending.append(order)
                            else:
                                log(f"[{oid}] [TEST] Limit order expired (no fill)")
                                send_telegram(
                                    f"⏰ <b>Limit order hết hạn (không khớp) [TEST]</b>\n"
                                    f"ID: <code>{oid}</code>\nSymbol: {args.symbol}\n"
                                    f"Direction: {_sig['direction']}\nEntry: {_sig['entry_price']:.2f}\n"
                                    f"SL: {_sig['stop_loss']:.2f} TP: {_sig['take_profit']:.2f}"
                                )
                        continue  # skip live logic below

                    # Live: poll MT5 pending orders by ticket
                    pending_on_mt5 = mt5.orders_get(ticket=mt5_ticket)
                    if pending_on_mt5:
                        # Still pending on broker — decrement counter
                        order["candles_left"] -= 1
                        if order["candles_left"] > 0:
                            still_pending.append(order)
                        else:
                            # Timeout — cancel the pending order on MT5
                            log(f"[{oid}] Limit order timed out (ticket={mt5_ticket}) — cancelling")
                            ok_cancel, cancel_msg = cancel_pending_order(mt5_ticket, credentials=credentials)
                            if not ok_cancel:
                                log(f"[{oid}] Cancel FAILED: {cancel_msg} — retrying next candle", "ERROR")
                                send_telegram(f"❌ Cancel failed — order still live\nID: <code>{oid}</code>\nReason: {cancel_msg}", is_error=True)
                                # Keep in still_pending so next candle retries the cancel
                                still_pending.append(order)
                            else:
                                log(f"[{oid}] Cancel result: {cancel_msg}")
                                send_telegram(
                                    f"⏰ <b>Limit order hết hạn (không khớp)</b>\n"
                                    f"ID: <code>{oid}</code>\nSymbol: {args.symbol}\n"
                                    f"Direction: {_sig['direction']}\nEntry: {_sig['entry_price']:.2f}\n"
                                    f"SL: {_sig['stop_loss']:.2f} TP: {_sig['take_profit']:.2f}"
                                )
                    else:
                        # Order gone from MT5 pending list — check if it became a position (filled)
                        if is_flappy:
                            pending_ref = type(
                                "PendingOrderRef", (), {
                                    "ticket": mt5_ticket,
                                    "type": (
                                        getattr(mt5, "ORDER_TYPE_BUY_LIMIT", None)
                                        if _sig["direction"] == "BUY"
                                        else getattr(mt5, "ORDER_TYPE_SELL_LIMIT", None)
                                    ),
                                }
                            )()
                            position = _find_filled_position(
                                mt5, pending_ref, args.symbol,
                                flappy_magic,
                            )
                        else:
                            positions = mt5.positions_get(ticket=mt5_ticket) or []
                            position = positions[0] if positions else None
                        if position:
                            fill_price = position.price_open
                            position_ticket = getattr(position, "ticket", mt5_ticket)
                            log(f"[{oid}] Limit order filled by broker @ {fill_price:.5f} (ticket={position_ticket})")
                            send_telegram(f"<b>{strategy_label} Limit Filled: {_sig['direction']}</b>\n"
                                          f"ID: <code>{oid}</code>\nFill: {fill_price:.2f}\n"
                                          f"SL: {_sig['stop_loss']:.2f} TP: {_sig['take_profit']:.2f}\n"
                                          f"Lot: {order['trade_lot']} | Ticket: {mt5_ticket}")
                            active_trades.append({
                                "direction": _sig["direction"],
                                "entry": fill_price,          # actual fill price from MT5
                                "sl": _sig["stop_loss"],
                                "tp": _sig["take_profit"],
                                "ticket": position_ticket, "candles": 0, "order_id": oid,
                                "lot": order.get("trade_lot", lot_size),
                                "ema_mode": _sig.get("ema_mode"),
                            })
                        else:
                            # Disappeared without becoming a position — cancelled externally or rejected
                            log(f"[{oid}] Pending order {mt5_ticket} no longer on MT5 (cancelled externally or rejected)")
                            send_telegram(f"⚠️ Pending order removed externally\nID: <code>{oid}</code>\nTicket: {mt5_ticket}")
                pending_orders = still_pending

                # 2. Check active trades — exit
                feg_be_enabled = bool(args.be_enabled)
                still_active = []
                for trade in active_trades:
                    trade["candles"] += 1
                    # Break-even: move SL to entry when profit >= be_r * sl_dist
                    if feg_be_enabled and not trade.get('be_triggered'):
                        entry_p = trade["entry"]
                        sl_dist = abs(entry_p - trade["sl"])
                        if trade["direction"] == "BUY" and candle["high"] >= entry_p + args.be_r * sl_dist:
                            trade["sl"] = entry_p
                            trade["be_triggered"] = True
                            log(f"[{trade.get('order_id','')}] BE triggered — SL → {entry_p:.2f}")
                        elif trade["direction"] == "SELL" and candle["low"] <= entry_p - args.be_r * sl_dist:
                            trade["sl"] = entry_p
                            trade["be_triggered"] = True
                            log(f"[{trade.get('order_id','')}] BE triggered — SL → {entry_p:.2f}")
                    if is_flappy:
                        if trade["direction"] == "BUY" and candle["low"] <= trade["sl"]:
                            exit_type, exit_price = "SL", trade["sl"]
                        elif trade["direction"] == "BUY" and candle["high"] >= trade["tp"]:
                            exit_type, exit_price = "TP", trade["tp"]
                        elif trade["direction"] == "SELL" and candle["high"] >= trade["sl"]:
                            exit_type, exit_price = "SL", trade["sl"]
                        elif trade["direction"] == "SELL" and candle["low"] <= trade["tp"]:
                            exit_type, exit_price = "TP", trade["tp"]
                        else:
                            exit_type, exit_price = None, None
                    else:
                        exit_type, exit_price = check_exit(
                            trade["direction"], candle, trade["tp"], trade["sl"], tp_type, sl_type,
                        )
                    if not exit_type and max_candles > 0 and trade["candles"] >= max_candles:
                        exit_type, exit_price = "TIME", last["close"]
                    if exit_type:
                        pv = get_pip_value(args.symbol)
                        trade_lot = trade.get("lot", lot_size)
                        oid = trade.get("order_id", "")
                        ticket = trade.get("ticket")

                        # Step 1: Close position if still open (live mode only)
                        if not args.test and ticket:
                            _pos = mt5.positions_get(ticket=ticket)
                            if not _pos:
                                log(f"[{oid}] Position already closed by broker (TP/SL hit server-side)")
                            else:
                                closed_ok, close_msg = close_position(ticket, credentials=credentials)
                                if not closed_ok:
                                    if "not found" in close_msg.lower():
                                        # Race: broker closed between positions_get check and close call
                                        log(f"[{oid}] Position closed by broker between check and close (race)")
                                    else:
                                        log(f"[{oid}] Close failed: {close_msg}", "ERROR")
                                        send_telegram(f"❌ Close failed\nID: <code>{oid}</code>\nReason: {close_msg}", is_error=True)
                                        still_active.append(trade)
                                        continue

                        # Step 2: Verify exit from MT5 deal history (live mode only)
                        # deal.profit = net P&L from broker (after spread); swap = overnight fee
                        deal = None
                        if not args.test and ticket:
                            deal = _get_exit_deal(mt5, ticket)
                            if deal is None:
                                log(f"[{oid}] Could not verify exit from deal history — using estimated price", "WARN")

                        # Step 3: Use verified data if available, else fall back to candle estimate
                        if deal:
                            actual_price = deal["price"]
                            actual_pnl_usd = deal["profit"] + deal["swap"]  # net USD after overnight
                            verified = True
                        else:
                            actual_price = exit_price  # candle-based estimate
                            actual_pnl_usd = _estimate_pnl_usd(
                                mt5, args.symbol, trade["direction"],
                                trade["entry"], exit_price, trade_lot, pv,
                            )  # None when symbol info unavailable
                            verified = False
                            if actual_pnl_usd is None:
                                log(f"[{oid}] USD P&L unavailable from MT5 symbol info; recording 0.00 estimate", "WARN")
                                actual_pnl_usd = 0.0

                        actual_pips = (
                            (actual_price - trade["entry"]) / pv if trade["direction"] == "BUY"
                            else (trade["entry"] - actual_price) / pv
                        )

                        # Step 4: Log, Telegram, record — mark estimated data clearly
                        price_str = f"{actual_price:.2f}"
                        usd_part = f" (${actual_pnl_usd:.2f})" if actual_pnl_usd is not None else ""
                        pnl_str = f"{actual_pips:.1f} pips{usd_part}"
                        if not verified:
                            price_str += " ~est"
                            pnl_str = "~" + pnl_str + " ⚠️"

                        log(f"[{oid}] {strategy_label} Exit: {exit_type} @ {price_str}, P&L: {pnl_str}")
                        send_telegram(f"<b>{strategy_label} Exit: {exit_type}</b>\nID: <code>{oid}</code>\nPrice: {price_str}\nP&L: {pnl_str}")
                        _record_trade(_session_id, oid, trade["direction"],
                                      trade["entry"], actual_price, exit_type,
                                      actual_pnl_usd, trade_lot, verified=verified)
                    else:
                        still_active.append(trade)
                active_trades = still_active

                # 3. Scan FEG signal → tạo pending order mới
                now_hcm = datetime.now(TIMEZONE)
                in_window = _in_time_window(now_hcm, entry_start_time, entry_end_time)
                occupied_modes = {
                    trade.get("ema_mode")
                    for trade in active_trades
                    if trade.get("ema_mode")
                } | {
                    order.get("signal", {}).get("ema_mode")
                    for order in pending_orders
                    if order.get("signal", {}).get("ema_mode")
                }
                enabled_modes = [
                    mode for mode, enabled in (
                        ("consensus", consensus_enabled),
                        ("fallback", fallback_enabled),
                    )
                    if enabled and (re_entry_after_sl or mode not in occupied_modes)
                ]
                can_scan = bool(enabled_modes) or not is_flappy
                log(f"New candle {candle_time.strftime('%H:%M')} | "
                    f"C1: O={prev['open']:.2f} H={prev['high']:.2f} L={prev['low']:.2f} C={prev['close']:.2f} | "
                    f"C2: O={last['open']:.2f} H={last['high']:.2f} L={last['low']:.2f} C={last['close']:.2f} | "
                    f"EMA={ema[-1]:.2f} | in_window={in_window} can_scan={can_scan}")
                if in_window and can_scan:
                    scan_mode = None
                    signal = None
                    if is_flappy:
                        from src.flappy_bird_strategy import analyze_flappy_bird
                        c2 = {"open": last["open"], "high": last["high"], "low": last["low"], "close": last["close"]}
                        for candidate_mode in enabled_modes:
                            child_counts = (
                                [no_mother_child_candles]
                                if args.strategy == "multi_flappy_bird" and not use_mother_candle
                                else range(max_child_candles, min_child_candles - 1, -1)
                            )
                            for child_count in child_counts:
                                mother_idx = (
                                    len(df) - child_count - 2
                                    if use_mother_candle or args.strategy != "multi_flappy_bird"
                                    else None
                                )
                                if mother_idx is not None and mother_idx < 0:
                                    continue
                                mother = (
                                    df.loc[mother_idx, ["open", "high", "low", "close"]].to_dict()
                                    if mother_idx is not None else None
                                )
                                child_start = (
                                    mother_idx + 1
                                    if mother_idx is not None
                                    else len(df) - 1 - child_count
                                )
                                children = [
                                    df.loc[idx, ["open", "high", "low", "close"]].to_dict()
                                    for idx in range(child_start, len(df) - 1)
                                ]
                                for direction in ("BUY", "SELL"):
                                    if (
                                        (
                                            no_mother_cross_window_candles
                                            if args.strategy == "multi_flappy_bird" and not use_mother_candle
                                            else cross_window_candles
                                        ) > 0
                                        and (
                                            cross_directions[-1] != direction
                                            or cross_ages[-1] is None
                                            or cross_ages[-1] > (
                                                no_mother_cross_window_candles
                                                if args.strategy == "multi_flappy_bird" and not use_mother_candle
                                                else cross_window_candles
                                            )
                                        )
                                    ):
                                        continue
                                    higher_filter = None
                                    if (
                                        args.strategy == "multi_flappy_bird"
                                        and higher_timeframe_filter_enabled
                                    ):
                                        eligible = higher_df[
                                            higher_df["time"] <= int(last["time"])
                                        ]
                                        if len(eligible) == 0:
                                            continue
                                        htf_idx = eligible.index[-1]
                                        htf_candle = higher_df.loc[
                                            htf_idx, ["open", "high", "low", "close"]
                                        ].to_dict()
                                        htf_group = (
                                            "higher_ema_consensus"
                                            if candidate_mode == "consensus"
                                            else "higher_ema_fallback"
                                        )
                                        higher_filter = {
                                            "enabled": (
                                                True
                                            ),
                                            "mode_enabled": (
                                                higher_ema_consensus_enabled
                                                if candidate_mode == "consensus"
                                                else higher_ema_fallback_enabled
                                            ),
                                            "candle": htf_candle,
                                            "ema_values": {
                                                slot: values[htf_idx]
                                                for slot, values in higher_ema_series[htf_group].items()
                                            },
                                            "mode": candidate_mode,
                                        }
                                    signal = analyze_flappy_bird(
                                        args.symbol, mother, children, c2,
                                        ema13_series[-1], ema21_series[-1], ema55_series[-1],
                                        lot_size,
                                        params.get('sl_buffer_pips', 5.0),
                                        entry_body_percent,
                                        rr_ratio,
                                        min_father_body_points,
                                        direction,
                                        min_child_candles=min_child_candles,
                                        max_child_candles=max_child_candles,
                                        max_child_body_points=max_child_body_points,
                                        mother_coverage_enabled=mother_coverage_enabled,
                                        fallback_ema13=fallback_ema13_series[-1],
                                        fallback_ema21=fallback_ema21_series[-1],
                                        fallback_ema55=fallback_ema55_series[-1],
                                        consensus_enabled=consensus_enabled,
                                        fallback_enabled=fallback_enabled,
                                        requested_ema_mode=candidate_mode,
                                        higher_timeframe_filter=higher_filter,
                                        current_timeframe_filter_enabled=current_timeframe_filter_enabled,
                                        use_mother_candle=use_mother_candle,
                                        no_mother_child_candles=no_mother_child_candles,
                                        no_mother_child_body_ratio=no_mother_child_body_ratio,
                                        no_mother_child_body_max_points=no_mother_child_body_max_points,
                                        no_mother_father_wick_max_pct=no_mother_father_wick_max_pct,
                                        no_mother_sl_buffer_pips=no_mother_sl_buffer_pips,
                                    )
                                    if signal:
                                        scan_mode = candidate_mode
                                        break
                                if signal:
                                    break
                            if signal:
                                break
                    else:
                        c1 = {"open": prev["open"], "high": prev["high"], "low": prev["low"], "close": prev["close"]}
                        c2 = {"open": last["open"], "high": last["high"], "low": last["low"], "close": last["close"]}
                        signal = feg_entry_decision(
                            None, c1, c2, ema[-1], args.symbol,
                            rr_ratio, buffer_k, lot_size, entry_mode, entry_percent,
                            h2_exceed_pips, c2_gap_pips, ema_margin_pips,
                            ema_filter_enabled, buy_ema_side, sell_ema_side,
                            c2_buy_upper_wick_max_pct, c2_buy_lower_wick_max_pct,
                            c2_sell_upper_wick_max_pct, c2_sell_lower_wick_max_pct,
                            c2_buy_upper_wick_cmp, c2_buy_lower_wick_cmp,
                            c2_sell_upper_wick_cmp, c2_sell_lower_wick_cmp,
                        )
                    log(f"Signal scan ({scan_mode or 'generic'}): {signal['direction'] if signal else 'NO SIGNAL'}"
                        + (f" entry={signal['entry_price']:.2f} sl={signal['stop_loss']:.2f} tp={signal['take_profit']:.2f}" if signal else ""))
                    if signal:
                        if is_flappy and _has_duplicate_pending(
                            mt5, pending_orders, signal, args.symbol,
                            params.get("magic", 212400),
                        ):
                            log("Flappy signal already has a pending order; skipping duplicate")
                            signal = None
                    if signal:
                        trade_lot = lot_size
                        if lot_mode == "flex":
                            trade_lot = _calc_flex_lot(
                                mt5, args.symbol, risk_mode, risk_percent, risk_amount,
                                signal["entry_price"], signal["stop_loss"],
                            )
                        import uuid as _uuid
                        _candle_dt = datetime.fromtimestamp(int(last['time']), tz=TIMEZONE)
                        order_id = f"ORD-{_candle_dt.strftime('%y%m%d-%H%M%S')}-{args.symbol}-{_uuid.uuid4().hex[:4].upper()}"
                        log(f"[{order_id}] {strategy_label} Signal: {signal['direction']} @ {signal['entry_price']:.2f}, "
                            f"SL={signal['stop_loss']:.2f}, TP={signal['take_profit']:.2f}, lot={trade_lot}, "
                            f"limit_timeout={limit_order_candles}c")
                        # Place real MT5 pending limit order
                        ok_limit, msg_limit, mt5_ticket = place_limit_order(
                            args.symbol, signal["direction"], trade_lot, signal["entry_price"],
                            sl=signal["stop_loss"], tp=signal["take_profit"],
                            credentials=credentials, test=bool(args.test),
                            magic=flappy_magic if is_flappy else 212100,
                            comment=f"FLAPPY-{order_id[-4:]}" if is_flappy else f"FEG-{order_id[-4:]}",
                        )
                        if not ok_limit:
                            log(f"[{order_id}] Failed to place limit order: {msg_limit}", "ERROR")
                            send_telegram(f"❌ Limit order failed\nID: <code>{order_id}</code>\nReason: {msg_limit}", is_error=True)
                        else:
                            log(f"[{order_id}] Limit order placed on MT5 ticket={mt5_ticket}")
                            _pv = get_pip_value(args.symbol)
                            _sym_tag = "BTC" if "BTC" in args.symbol else "ETH" if "ETH" in args.symbol else "XAU" if "XAU" in args.symbol else "FX"
                            _o, _h, _l, _c = c2["open"], c2["high"], c2["low"], c2["close"]
                            _body = abs(_c - _o)
                            _buf_offset = buffer_k * _pv
                            _em_str = f"Body {entry_percent:.0f}%" if entry_mode == "range_percent" else "Close"
                            _ep = signal["entry_price"]
                            _sl = signal["stop_loss"]
                            _tp = signal["take_profit"]
                            _sl_pips = signal["sl_pips"]
                            if signal["direction"] == "SELL":
                                _entry_calc = f"Entry = C + {entry_percent:.0f}%×body = {_c:.2f} + {(entry_percent/100*_body):.2f} = {_ep:.2f}" if entry_mode == "range_percent" else f"Entry = C = {_ep:.2f}"
                                _sl_calc   = f"SL    = H + buffer   = {_h:.2f} + {_buf_offset:.2f} = {_sl:.2f}"
                                _tp_calc   = f"TP    = Entry - Risk×{rr_ratio:.1f} = {_tp:.2f}"
                            else:
                                _entry_calc = f"Entry = C - {entry_percent:.0f}%×body = {_c:.2f} - {(entry_percent/100*_body):.2f} = {_ep:.2f}" if entry_mode == "range_percent" else f"Entry = C = {_ep:.2f}"
                                _sl_calc   = f"SL    = L - buffer   = {_l:.2f} - {_buf_offset:.2f} = {_sl:.2f}"
                                _tp_calc   = f"TP    = Entry + Risk×{rr_ratio:.1f} = {_tp:.2f}"
                            _calc_block = (
                                f"C2: O={_o:.2f} H={_h:.2f} L={_l:.2f} C={_c:.2f}\n"
                                f"Entry Mode: {_em_str}\n"
                                f"pip_value = {_pv} ({_sym_tag})\n"
                                f"Buffer_k = {buffer_k} → buffer_offset = Buffer_k × pip_value = ${_buf_offset:.2f}\n"
                                f"---\n"
                                f"Body = |C - O| = |{_c:.2f} - {_o:.2f}| = {_body:.2f}\n"
                                f"{_entry_calc}\n"
                                f"{_sl_calc}\n"
                                f"Risk  = {_sl_pips:.2f} pips\n"
                                f"{_tp_calc}"
                            )
                            send_telegram(f"<b>{strategy_label} Signal (pending): {signal['direction']}</b>\n"
                                          f"ID: <code>{order_id}</code>\n"
                                          f"Symbol: {args.symbol} | Lot: {trade_lot} | Ticket: {mt5_ticket} | Chờ: {limit_order_candles} nến\n\n"
                                          f"<pre>{_calc_block}</pre>")
                            pending_orders.append({
                                "signal": signal,
                                "trade_lot": trade_lot,
                                "candles_left": limit_order_candles,
                                "order_id": order_id,
                                "mt5_ticket": mt5_ticket,
                            })

                last_candle_time = candle_time

                _write_bot_state(os.getpid(), args.symbol, args.strategy,
                                 len(active_trades), len(pending_orders))

                # Graceful restart: if flagged and idle, raise sentinel so __main__ re-runs bot
                if _check_pending_restart(os.getpid()) and not active_trades and not pending_orders:
                    log("Pending restart flag detected and bot is idle — restarting with new code")
                    _clear_pending_restart(os.getpid())
                    _write_bot_state(os.getpid(), args.symbol, args.strategy, 0, 0)
                    _unregister_from_running_bots(os.getpid())
                    close_session(_session_id)
                    raise _GracefulRestart()

            time.sleep(args.interval)

    except KeyboardInterrupt:
        log(f"{strategy_label} Bot stopped by user")
        _write_bot_state(os.getpid(), args.symbol, args.strategy, 0, 0)
        _unregister_from_running_bots(os.getpid())
        close_session(_session_id)
        if not args.managed_by_ui:
            send_telegram(f"{strategy_label} Bot Stopped (manual)")
    except _GracefulRestart:
        raise
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log(f"{strategy_label} Bot error: {e}", "ERROR")
        _write_bot_state(os.getpid(), args.symbol, args.strategy, 0, 0)
        _unregister_from_running_bots(os.getpid())
        close_session(_session_id)
        send_telegram(f"❌ {strategy_label} Bot crashed\nSymbol: {args.symbol}\nError: {e}\n\n<pre>{tb[-800:]}</pre>", is_error=True)
        raise
    finally:
        # Shutdown MT5 once when the bot loop exits (any reason)
        try:
            import MetaTrader5 as _mt5_mod
            _mt5_mod.shutdown()
        except Exception:
            pass


def run_feg_stop_order_bot(args, strategy, params, credentials,
                            entry_start_time: _time = _time(0, 0),
                            entry_end_time: _time = _time(23, 59)):
    """Vòng lặp live cho strategy FEG Stop Order (pattern + EMA21, nhiều pending orders + trades cùng lúc)."""
    from src.orders import place_order, close_position, place_limit_order, cancel_pending_order

    timeframe = params.get('timeframe', 'M5')
    ema_period = args.ema_period or params.get('ema_period', 21)
    rr_ratio = args.rr_ratio or params.get('rr_ratio', 2.0)
    buffer_k = args.buffer_k if args.buffer_k is not None else params.get('buffer_k', 5)
    lot_size = args.lot_size or params.get('lot_size', 0.01)
    max_candles = args.max_candles if args.max_candles is not None else params.get('max_candles', 7)
    h2_exceed_pips = args.h2_exceed_pips if args.h2_exceed_pips else params.get('h2_exceed_pips', 0.0)
    c2_gap_pips    = args.c2_gap_pips    if args.c2_gap_pips    else params.get('c2_gap_pips',    0.0)
    ema_margin_pips = args.ema_margin_pips if args.ema_margin_pips else params.get('ema_margin_pips', 0.0)
    ema_filter_enabled = bool(args.ema_filter_enabled)
    buy_ema_side  = args.buy_ema_side  or params.get('buy_ema_side',  'below_ema')
    sell_ema_side = args.sell_ema_side or params.get('sell_ema_side', 'above_ema')
    limit_order_candles = args.limit_order_candles if args.limit_order_candles else params.get('limit_order_candles', 1)
    tp_type = args.tp_type or params.get('tp_type', 'price_based')
    sl_type = args.sl_type or params.get('sl_type', 'price_based')
    lot_mode = args.lot_mode or 'fixed'
    risk_mode = args.risk_mode or 'percent'
    risk_percent = args.risk_percent
    risk_amount = args.risk_amount
    re_entry_after_sl = bool(args.re_entry_after_sl)
    c2_buy_upper_wick_max_pct  = args.c2_buy_upper_wick_max_pct
    c2_buy_lower_wick_max_pct  = args.c2_buy_lower_wick_max_pct
    c2_sell_upper_wick_max_pct = args.c2_sell_upper_wick_max_pct
    c2_sell_lower_wick_max_pct = args.c2_sell_lower_wick_max_pct
    c2_buy_upper_wick_cmp  = args.c2_buy_upper_wick_cmp  or "lt"
    c2_buy_lower_wick_cmp  = args.c2_buy_lower_wick_cmp  or "lt"
    c2_sell_upper_wick_cmp = args.c2_sell_upper_wick_cmp or "lt"
    c2_sell_lower_wick_cmp = args.c2_sell_lower_wick_cmp or "lt"

    # Auto-detect symbol min lot and clamp (only for fixed mode)
    mt5_tmp, err_tmp = get_mt5_connection(credentials)
    if not err_tmp:
        sym_info = mt5_tmp.symbol_info(args.symbol)
        if sym_info and lot_mode == "fixed" and lot_size < sym_info.volume_min:
            log(f"lot_size {lot_size} < symbol min {sym_info.volume_min} — using {sym_info.volume_min}", "WARN")
            lot_size = sym_info.volume_min
        mt5_tmp.shutdown()

    ema_filter_str = f"EMA_filter=ON(buy={buy_ema_side},sell={sell_ema_side},margin={ema_margin_pips}p)" if ema_filter_enabled else "EMA_filter=OFF"
    lot_log = f"flex({risk_mode} {risk_percent}%/{risk_amount}$)" if lot_mode == "flex" else f"fixed={lot_size}"
    be_log = f"BE=ON(r={args.be_r})" if args.be_enabled else "BE=OFF"
    re_entry_log = "ReEntry=ON" if re_entry_after_sl else "ReEntry=OFF"
    _wick_buy2 = []
    if c2_buy_upper_wick_max_pct is not None: _wick_buy2.append(f"upper={c2_buy_upper_wick_max_pct}%")
    if c2_buy_lower_wick_max_pct is not None: _wick_buy2.append(f"lower={c2_buy_lower_wick_max_pct}%")
    _wick_sell2 = []
    if c2_sell_upper_wick_max_pct is not None: _wick_sell2.append(f"upper={c2_sell_upper_wick_max_pct}%")
    if c2_sell_lower_wick_max_pct is not None: _wick_sell2.append(f"lower={c2_sell_lower_wick_max_pct}%")
    wick_log = f"WickFilter=BUY({','.join(_wick_buy2) or 'OFF'}) SELL({','.join(_wick_sell2) or 'OFF'})"
    log(f"FEG Stop Order params: EMA{ema_period}, RR={rr_ratio}, buffer_k={buffer_k}, "
        f"lot={lot_log}, max_candles={max_candles or 'unlimited'}, "
        f"h2_exceed={h2_exceed_pips}p, c2_gap={c2_gap_pips}p, {ema_filter_str}, {be_log}, {re_entry_log}, {wick_log}")

    send_telegram(f"FEG Stop Order Bot Started\nSymbol: {args.symbol}\nUser: {args.user}\n"
                  f"Test: {'Yes' if args.test else 'No'}")

    from src.bot_history_manager import create_session, close_session, record_trade as _record_trade
    _now_str = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    _session_id = create_session(
        strategy=args.strategy,
        symbol=args.symbol,
        mode="test" if args.test else "live",
        user=args.user,
        log_path=args.log_file or "",
    )
    _register_in_running_bots(
        pid=os.getpid(),
        symbol=args.symbol,
        strategy=args.strategy,
        user=args.user,
        test=bool(args.test),
        log_path=args.log_file or "",
        started_at=_now_str,
    )

    # pending_orders: list of {signal, trade_lot, candles_left, order_id}
    # active_trades: list of {direction, entry, sl, tp, ticket, candles, order_id}
    pending_orders = []
    active_trades  = []
    last_candle_time = None
    _mt5_ref = [None]  # persistent MT5 connection — reconnects only when terminal disconnects

    try:
        while True:
            mt5, error = _ensure_mt5_connected(_mt5_ref, credentials)
            if error:
                log(f"MT5 connection failed: {error}", "ERROR")
                send_telegram(f"MT5 Error: {error}", is_error=True)
                time.sleep(args.interval)
                continue

            df = get_recent_candles(mt5, args.symbol, timeframe, count=max(120, ema_period * 4))
            if df is None or len(df) < ema_period + 2:
                log(f"Insufficient candle data for {args.symbol} (got {len(df) if df is not None else 0})", "ERROR")
                send_telegram(f"❌ Insufficient candle data\nSymbol: {args.symbol}", is_error=True)
                time.sleep(args.interval)
                continue

            ema = df["close"].ewm(span=ema_period, adjust=False).mean().tolist()
            last = df.iloc[-1]
            prev = df.iloc[-2]
            candle_time = datetime.fromtimestamp(int(last["time"]), tz=TIMEZONE)
            is_new_candle = (last_candle_time is None) or (candle_time > last_candle_time)

            if pending_orders or active_trades:
                log(f"Tick check @ {datetime.now(TIMEZONE).strftime('%H:%M:%S')} | "
                    f"last candle: {candle_time.strftime('%H:%M')} "
                    f"O={last['open']:.2f} H={last['high']:.2f} L={last['low']:.2f} C={last['close']:.2f} | "
                    f"EMA={ema[-1]:.2f} | new_candle={is_new_candle} | "
                    f"pending={len(pending_orders)} active={len(active_trades)}")

            if is_new_candle:
                from src.utils import check_exit
                candle = {"high": last["high"], "low": last["low"], "close": last["close"]}

                # 1. Check pending orders — poll MT5 ticket each candle
                still_pending = []
                for order in pending_orders:
                    oid = order["order_id"]
                    mt5_ticket = order.get("mt5_ticket")
                    _sig = order["signal"]

                    # Test mode: simulate fill by candle low/high (unchanged behaviour)
                    if args.test or mt5_ticket is None:
                        filled = candle["low"] <= _sig["entry_price"] <= candle["high"]
                        if filled:
                            log(f"[{oid}] [TEST] Limit order filled @ {_sig['entry_price']:.2f}")
                            send_telegram(f"<b>FEG SO Limit Filled (TEST): {_sig['direction']}</b>\n"
                                          f"ID: <code>{oid}</code>\nEntry: {_sig['entry_price']:.2f}\n"
                                          f"SL: {_sig['stop_loss']:.2f} TP: {_sig['take_profit']:.2f}\n"
                                          f"Lot: {order['trade_lot']}")
                            active_trades.append({
                                "direction": _sig["direction"],
                                "entry": _sig["entry_price"],
                                "sl": _sig["stop_loss"],
                                "tp": _sig["take_profit"],
                                "ticket": None, "candles": 0, "order_id": oid,
                                "lot": order.get("trade_lot", lot_size),
                            })
                        else:
                            order["candles_left"] -= 1
                            if order["candles_left"] > 0:
                                still_pending.append(order)
                            else:
                                log(f"[{oid}] [TEST] Limit order expired (no fill)")
                                send_telegram(
                                    f"⏰ <b>Limit order hết hạn (không khớp) [TEST]</b>\n"
                                    f"ID: <code>{oid}</code>\nSymbol: {args.symbol}\n"
                                    f"Direction: {_sig['direction']}\nEntry: {_sig['entry_price']:.2f}\n"
                                    f"SL: {_sig['stop_loss']:.2f} TP: {_sig['take_profit']:.2f}"
                                )
                        continue  # skip live logic below

                    # Live: poll MT5 pending orders by ticket
                    pending_on_mt5 = mt5.orders_get(ticket=mt5_ticket)
                    if pending_on_mt5:
                        # Still pending on broker — decrement counter
                        order["candles_left"] -= 1
                        if order["candles_left"] > 0:
                            still_pending.append(order)
                        else:
                            # Timeout — cancel the pending order on MT5
                            log(f"[{oid}] Limit order timed out (ticket={mt5_ticket}) — cancelling")
                            ok_cancel, cancel_msg = cancel_pending_order(mt5_ticket, credentials=credentials)
                            if not ok_cancel:
                                log(f"[{oid}] Cancel FAILED: {cancel_msg} — retrying next candle", "ERROR")
                                send_telegram(f"❌ Cancel failed — order still live\nID: <code>{oid}</code>\nReason: {cancel_msg}", is_error=True)
                                still_pending.append(order)
                            else:
                                log(f"[{oid}] Cancel result: {cancel_msg}")
                                send_telegram(
                                    f"⏰ <b>Limit order hết hạn (không khớp)</b>\n"
                                    f"ID: <code>{oid}</code>\nSymbol: {args.symbol}\n"
                                    f"Direction: {_sig['direction']}\nEntry: {_sig['entry_price']:.2f}\n"
                                    f"SL: {_sig['stop_loss']:.2f} TP: {_sig['take_profit']:.2f}"
                                )
                    else:
                        # Order gone from MT5 pending list — check if it became a position (filled)
                        pos = mt5.positions_get(ticket=mt5_ticket)
                        if pos:
                            position = pos[0]
                            fill_price = position.price_open
                            log(f"[{oid}] Limit order filled by broker @ {fill_price:.5f} (ticket={mt5_ticket})")
                            send_telegram(f"<b>FEG SO Limit Filled: {_sig['direction']}</b>\n"
                                          f"ID: <code>{oid}</code>\nFill: {fill_price:.2f}\n"
                                          f"SL: {_sig['stop_loss']:.2f} TP: {_sig['take_profit']:.2f}\n"
                                          f"Lot: {order['trade_lot']} | Ticket: {mt5_ticket}")
                            active_trades.append({
                                "direction": _sig["direction"],
                                "entry": fill_price,
                                "sl": _sig["stop_loss"],
                                "tp": _sig["take_profit"],
                                "ticket": mt5_ticket, "candles": 0, "order_id": oid,
                                "lot": order.get("trade_lot", lot_size),
                            })
                        else:
                            log(f"[{oid}] Pending order {mt5_ticket} no longer on MT5 (cancelled externally or rejected)")
                            send_telegram(f"⚠️ Pending order removed externally\nID: <code>{oid}</code>\nTicket: {mt5_ticket}")
                pending_orders = still_pending

                # 2. Check active trades — exit
                feg_be_enabled = bool(args.be_enabled)
                still_active = []
                for trade in active_trades:
                    trade["candles"] += 1
                    # Break-even: move SL to entry when profit >= be_r * sl_dist
                    if feg_be_enabled and not trade.get('be_triggered'):
                        entry_p = trade["entry"]
                        sl_dist = abs(entry_p - trade["sl"])
                        if trade["direction"] == "BUY" and candle["high"] >= entry_p + args.be_r * sl_dist:
                            trade["sl"] = entry_p
                            trade["be_triggered"] = True
                            log(f"[{trade.get('order_id','')}] BE triggered — SL → {entry_p:.2f}")
                        elif trade["direction"] == "SELL" and candle["low"] <= entry_p - args.be_r * sl_dist:
                            trade["sl"] = entry_p
                            trade["be_triggered"] = True
                            log(f"[{trade.get('order_id','')}] BE triggered — SL → {entry_p:.2f}")
                    exit_type, exit_price = check_exit(
                        trade["direction"], candle, trade["tp"], trade["sl"], tp_type, sl_type,
                    )
                    if not exit_type and max_candles > 0 and trade["candles"] >= max_candles:
                        exit_type, exit_price = "TIME", last["close"]
                    if exit_type:
                        pv = get_pip_value(args.symbol)
                        trade_lot = trade.get("lot", lot_size)
                        oid = trade.get("order_id", "")
                        ticket = trade.get("ticket")

                        # Step 1: Close position if still open (live mode only)
                        if not args.test and ticket:
                            _pos = mt5.positions_get(ticket=ticket)
                            if not _pos:
                                log(f"[{oid}] Position already closed by broker (TP/SL hit server-side)")
                            else:
                                closed_ok, close_msg = close_position(ticket, credentials=credentials)
                                if not closed_ok:
                                    if "not found" in close_msg.lower():
                                        log(f"[{oid}] Position closed by broker between check and close (race)")
                                    else:
                                        log(f"[{oid}] Close failed: {close_msg}", "ERROR")
                                        send_telegram(f"❌ Close failed\nID: <code>{oid}</code>\nReason: {close_msg}", is_error=True)
                                        still_active.append(trade)
                                        continue

                        # Step 2: Verify exit from MT5 deal history (live mode only)
                        deal = None
                        if not args.test and ticket:
                            deal = _get_exit_deal(mt5, ticket)
                            if deal is None:
                                log(f"[{oid}] Could not verify exit from deal history — using estimated price", "WARN")

                        # Step 3: Use verified data if available, else fall back to candle estimate
                        if deal:
                            actual_price = deal["price"]
                            actual_pnl_usd = deal["profit"] + deal["swap"]
                            verified = True
                        else:
                            actual_price = exit_price
                            actual_pnl_usd = _estimate_pnl_usd(
                                mt5, args.symbol, trade["direction"],
                                trade["entry"], exit_price, trade_lot, pv,
                            )  # None when symbol info unavailable
                            verified = False
                            if actual_pnl_usd is None:
                                log(f"[{oid}] USD P&L unavailable from MT5 symbol info; recording 0.00 estimate", "WARN")
                                actual_pnl_usd = 0.0

                        actual_pips = (
                            (actual_price - trade["entry"]) / pv if trade["direction"] == "BUY"
                            else (trade["entry"] - actual_price) / pv
                        )

                        # Step 4: Log, Telegram, record
                        price_str = f"{actual_price:.2f}"
                        usd_part = f" (${actual_pnl_usd:.2f})" if actual_pnl_usd is not None else ""
                        pnl_str = f"{actual_pips:.1f} pips{usd_part}"
                        if not verified:
                            price_str += " ~est"
                            pnl_str = "~" + pnl_str + " ⚠️"

                        log(f"[{oid}] FEG SO Exit: {exit_type} @ {price_str}, P&L: {pnl_str}")
                        send_telegram(f"<b>FEG SO Exit: {exit_type}</b>\nID: <code>{oid}</code>\nPrice: {price_str}\nP&L: {pnl_str}")
                        _record_trade(_session_id, oid, trade["direction"],
                                      trade["entry"], actual_price, exit_type,
                                      actual_pnl_usd, trade_lot, verified=verified)
                    else:
                        still_active.append(trade)
                active_trades = still_active

                # 3. Scan FEG Stop Order signal → tạo pending order mới
                now_hcm = datetime.now(TIMEZONE)
                in_window = _in_time_window(now_hcm, entry_start_time, entry_end_time)
                can_scan = re_entry_after_sl or not active_trades
                log(f"New candle {candle_time.strftime('%H:%M')} | "
                    f"C1: O={prev['open']:.2f} H={prev['high']:.2f} L={prev['low']:.2f} C={prev['close']:.2f} | "
                    f"C2: O={last['open']:.2f} H={last['high']:.2f} L={last['low']:.2f} C={last['close']:.2f} | "
                    f"EMA={ema[-1]:.2f} | in_window={in_window} can_scan={can_scan}")
                if in_window and can_scan:
                    c1 = {"open": prev["open"], "high": prev["high"], "low": prev["low"], "close": prev["close"]}
                    c2 = {"open": last["open"], "high": last["high"], "low": last["low"], "close": last["close"]}
                    signal = feg_stop_order_entry_decision(
                        None, c1, c2, ema[-1], args.symbol,
                        rr_ratio, buffer_k, lot_size,
                        h2_exceed_pips, c2_gap_pips,
                        ema_filter_enabled, buy_ema_side, sell_ema_side, ema_margin_pips,
                        c2_buy_upper_wick_max_pct, c2_buy_lower_wick_max_pct,
                        c2_sell_upper_wick_max_pct, c2_sell_lower_wick_max_pct,
                        c2_buy_upper_wick_cmp, c2_buy_lower_wick_cmp,
                        c2_sell_upper_wick_cmp, c2_sell_lower_wick_cmp,
                    )
                    log(f"Signal scan: {signal['direction'] if signal else 'NO SIGNAL'}"
                        + (f" entry={signal['entry_price']:.2f} sl={signal['stop_loss']:.2f} tp={signal['take_profit']:.2f}" if signal else ""))
                    if signal:
                        trade_lot = lot_size
                        if lot_mode == "flex":
                            trade_lot = _calc_flex_lot(
                                mt5, args.symbol, risk_mode, risk_percent, risk_amount,
                                signal["entry_price"], signal["stop_loss"],
                            )
                        import uuid as _uuid
                        _candle_dt = datetime.fromtimestamp(int(last['time']), tz=TIMEZONE)
                        order_id = f"ORD-{_candle_dt.strftime('%y%m%d-%H%M%S')}-{args.symbol}-{_uuid.uuid4().hex[:4].upper()}"
                        log(f"[{order_id}] FEG SO Signal: {signal['direction']} @ {signal['entry_price']:.2f}, "
                            f"SL={signal['stop_loss']:.2f}, TP={signal['take_profit']:.2f}, lot={trade_lot}, "
                            f"limit_timeout={limit_order_candles}c")
                        # Place MT5 stop order (buy stop / sell stop)
                        from src.orders import place_stop_order as _place_stop_order
                        ok_stop, msg_stop, mt5_ticket = _place_stop_order(
                            args.symbol, signal["direction"], trade_lot, signal["entry_price"],
                            sl=signal["stop_loss"], tp=signal["take_profit"],
                            credentials=credentials, test=bool(args.test),
                            magic=212200, comment=f"FEGSO-{order_id[-4:]}",
                        )
                        if not ok_stop:
                            log(f"[{order_id}] Failed to place stop order: {msg_stop}", "ERROR")
                            send_telegram(f"❌ Stop order failed\nID: <code>{order_id}</code>\nReason: {msg_stop}", is_error=True)
                        else:
                            log(f"[{order_id}] Stop order placed on MT5 ticket={mt5_ticket}")
                            _pv = get_pip_value(args.symbol)
                            _sym_tag = "BTC" if "BTC" in args.symbol else "ETH" if "ETH" in args.symbol else "XAU" if "XAU" in args.symbol else "FX"
                            _h, _l = c2["high"], c2["low"]
                            _buf_offset = buffer_k * _pv
                            _ep = signal["entry_price"]
                            _sl = signal["stop_loss"]
                            _tp = signal["take_profit"]
                            _sl_pips = signal["sl_pips"]
                            _ema_str = f"EMA filter: {sell_ema_side if signal['direction'] == 'SELL' else buy_ema_side}" if ema_filter_enabled else "EMA filter: OFF"
                            if signal["direction"] == "SELL":
                                _entry_calc = f"Entry = L2 - buffer   = {_l:.2f} - {_buf_offset:.2f} = {_ep:.2f}"
                                _sl_calc    = f"SL    = H2             = {_sl:.2f}"
                                _tp_calc    = f"TP    = Entry - Risk×{rr_ratio:.1f} = {_tp:.2f}"
                            else:
                                _entry_calc = f"Entry = H2 + buffer   = {_h:.2f} + {_buf_offset:.2f} = {_ep:.2f}"
                                _sl_calc    = f"SL    = L2             = {_sl:.2f}"
                                _tp_calc    = f"TP    = Entry + Risk×{rr_ratio:.1f} = {_tp:.2f}"
                            _calc_block = (
                                f"C2: H={_h:.2f} L={_l:.2f}\n"
                                f"pip_value = {_pv} ({_sym_tag})\n"
                                f"Buffer_k = {buffer_k} → buffer_offset = Buffer_k × pip_value = ${_buf_offset:.2f}\n"
                                f"{_ema_str}\n"
                                f"---\n"
                                f"{_entry_calc}\n"
                                f"{_sl_calc}\n"
                                f"Risk  = {_sl_pips:.2f} pips\n"
                                f"{_tp_calc}"
                            )
                            send_telegram(f"<b>FEG SO Signal (stop): {signal['direction']}</b>\n"
                                          f"ID: <code>{order_id}</code>\n"
                                          f"Symbol: {args.symbol} | Lot: {trade_lot} | Ticket: {mt5_ticket} | Chờ: {limit_order_candles} nến\n\n"
                                          f"<pre>{_calc_block}</pre>")
                            pending_orders.append({
                                "signal": signal,
                                "trade_lot": trade_lot,
                                "candles_left": limit_order_candles,
                                "order_id": order_id,
                                "mt5_ticket": mt5_ticket,
                            })

                last_candle_time = candle_time

                _write_bot_state(os.getpid(), args.symbol, args.strategy,
                                 len(active_trades), len(pending_orders))

                # Graceful restart: if flagged and idle, raise sentinel so __main__ re-runs bot
                if _check_pending_restart(os.getpid()) and not active_trades and not pending_orders:
                    log("Pending restart flag detected and bot is idle — restarting with new code")
                    _clear_pending_restart(os.getpid())
                    _write_bot_state(os.getpid(), args.symbol, args.strategy, 0, 0)
                    _unregister_from_running_bots(os.getpid())
                    close_session(_session_id)
                    raise _GracefulRestart()

            time.sleep(args.interval)

    except KeyboardInterrupt:
        log("FEG Stop Order Bot stopped by user")
        _write_bot_state(os.getpid(), args.symbol, args.strategy, 0, 0)
        _unregister_from_running_bots(os.getpid())
        close_session(_session_id)
        if not args.managed_by_ui:
            send_telegram("FEG Stop Order Bot Stopped (manual)")
    except _GracefulRestart:
        raise
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log(f"FEG Stop Order Bot error: {e}", "ERROR")
        _write_bot_state(os.getpid(), args.symbol, args.strategy, 0, 0)
        _unregister_from_running_bots(os.getpid())
        close_session(_session_id)
        send_telegram(f"❌ FEG SO Bot crashed\nSymbol: {args.symbol}\nError: {e}\n\n<pre>{tb[-800:]}</pre>", is_error=True)
        raise
    finally:
        # Shutdown MT5 once when the bot loop exits (any reason)
        try:
            import MetaTrader5 as _mt5_mod
            _mt5_mod.shutdown()
        except Exception:
            pass


def run_feg_reverse_bot(args, strategy, params, credentials,
                        entry_start_time: _time = _time(0, 0),
                        entry_end_time: _time = _time(23, 59)):
    """Vòng lặp live cho strategy FEG Reverse (pattern + EMA21, nhiều pending orders + trades cùng lúc)."""
    from src.orders import place_order, close_position, place_limit_order, cancel_pending_order

    timeframe = params.get('timeframe', 'M5')
    ema_period = args.ema_period or params.get('ema_period', 21)
    rr_ratio = args.rr_ratio or params.get('rr_ratio', 2.0)
    buffer_k = args.buffer_k if args.buffer_k is not None else params.get('buffer_k', 5)
    lot_size = args.lot_size or params.get('lot_size', 0.01)
    max_candles = args.max_candles if args.max_candles is not None else params.get('max_candles', 7)
    h2_exceed_pips = args.h2_exceed_pips if args.h2_exceed_pips else params.get('h2_exceed_pips', 0.0)
    c2_gap_pips    = args.c2_gap_pips    if args.c2_gap_pips    else params.get('c2_gap_pips',    0.0)
    ema_margin_pips = args.ema_margin_pips if args.ema_margin_pips else params.get('ema_margin_pips', 0.0)
    ema_filter_enabled = bool(args.ema_filter_enabled)
    buy_ema_side  = args.buy_ema_side  or params.get('buy_ema_side',  'below_ema')
    sell_ema_side = args.sell_ema_side or params.get('sell_ema_side', 'above_ema')
    limit_order_candles = args.limit_order_candles if args.limit_order_candles else params.get('limit_order_candles', 1)
    entry_mode = args.entry_mode or params.get('entry_mode', 'close')
    entry_percent = args.entry_percent if args.entry_percent is not None else params.get('entry_percent', 0.0)
    tp_type = args.tp_type or params.get('tp_type', 'price_based')
    sl_type = args.sl_type or params.get('sl_type', 'close_based')
    lot_mode = args.lot_mode or 'fixed'
    risk_mode = args.risk_mode or 'percent'
    risk_percent = args.risk_percent
    risk_amount = args.risk_amount
    re_entry_after_sl = bool(args.re_entry_after_sl)
    c2_buy_upper_wick_max_pct  = args.c2_buy_upper_wick_max_pct
    c2_buy_lower_wick_max_pct  = args.c2_buy_lower_wick_max_pct
    c2_sell_upper_wick_max_pct = args.c2_sell_upper_wick_max_pct
    c2_sell_lower_wick_max_pct = args.c2_sell_lower_wick_max_pct
    c2_buy_upper_wick_cmp  = args.c2_buy_upper_wick_cmp  or "lt"
    c2_buy_lower_wick_cmp  = args.c2_buy_lower_wick_cmp  or "lt"
    c2_sell_upper_wick_cmp = args.c2_sell_upper_wick_cmp or "lt"
    c2_sell_lower_wick_cmp = args.c2_sell_lower_wick_cmp or "lt"

    # Auto-detect symbol min lot and clamp (only for fixed mode)
    mt5_tmp, err_tmp = get_mt5_connection(credentials)
    if not err_tmp:
        sym_info = mt5_tmp.symbol_info(args.symbol)
        if sym_info and lot_mode == "fixed" and lot_size < sym_info.volume_min:
            log(f"lot_size {lot_size} < symbol min {sym_info.volume_min} — using {sym_info.volume_min}", "WARN")
            lot_size = sym_info.volume_min
        mt5_tmp.shutdown()

    lot_log = f"flex({risk_mode} {risk_percent}%/{risk_amount}$)" if lot_mode == "flex" else f"fixed={lot_size}"
    be_log = f"BE=ON(r={args.be_r})" if args.be_enabled else "BE=OFF"
    ema_filter_str = f"EMA_filter=ON(buy={buy_ema_side},sell={sell_ema_side},margin={ema_margin_pips}p)" if ema_filter_enabled else "EMA_filter=OFF"
    re_entry_log = "ReEntry=ON" if re_entry_after_sl else "ReEntry=OFF"
    _wb = []
    if c2_buy_upper_wick_max_pct is not None: _wb.append(f"upper{c2_buy_upper_wick_cmp}{c2_buy_upper_wick_max_pct}%")
    if c2_buy_lower_wick_max_pct is not None: _wb.append(f"lower{c2_buy_lower_wick_cmp}{c2_buy_lower_wick_max_pct}%")
    _ws = []
    if c2_sell_upper_wick_max_pct is not None: _ws.append(f"upper{c2_sell_upper_wick_cmp}{c2_sell_upper_wick_max_pct}%")
    if c2_sell_lower_wick_max_pct is not None: _ws.append(f"lower{c2_sell_lower_wick_cmp}{c2_sell_lower_wick_max_pct}%")
    wick_log = f"WickFilter=BUY({','.join(_wb) or 'OFF'}) SELL({','.join(_ws) or 'OFF'})"
    log(f"FEG Reverse params: EMA{ema_period}, RR={rr_ratio}, buffer_k={buffer_k}, "
        f"lot={lot_log}, max_candles={max_candles or 'unlimited'}, "
        f"h2_exceed={h2_exceed_pips}p, c2_gap={c2_gap_pips}p, {ema_filter_str}, {be_log}, {re_entry_log}, {wick_log}")

    send_telegram(f"FEG Reverse Bot Started\nSymbol: {args.symbol}\nUser: {args.user}\n"
                  f"Test: {'Yes' if args.test else 'No'}")

    from src.bot_history_manager import create_session, close_session, record_trade as _record_trade
    _now_str = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    _session_id = create_session(
        strategy=args.strategy,
        symbol=args.symbol,
        mode="test" if args.test else "live",
        user=args.user,
        log_path=args.log_file or "",
    )
    _register_in_running_bots(
        pid=os.getpid(),
        symbol=args.symbol,
        strategy=args.strategy,
        user=args.user,
        test=bool(args.test),
        log_path=args.log_file or "",
        started_at=_now_str,
    )

    # pending_orders: list of {signal, trade_lot, candles_left, order_id}
    # active_trades: list of {direction, entry, sl, tp, ticket, candles, order_id}
    pending_orders = []
    active_trades  = []
    last_candle_time = None
    _mt5_ref = [None]  # persistent MT5 connection — reconnects only when terminal disconnects

    try:
        while True:
            mt5, error = _ensure_mt5_connected(_mt5_ref, credentials)
            if error:
                log(f"MT5 connection failed: {error}", "ERROR")
                send_telegram(f"MT5 Error: {error}", is_error=True)
                time.sleep(args.interval)
                continue

            df = get_recent_candles(mt5, args.symbol, timeframe, count=max(120, ema_period * 4))
            if df is None or len(df) < ema_period + 2:
                log(f"Insufficient candle data for {args.symbol} (got {len(df) if df is not None else 0})", "ERROR")
                send_telegram(f"❌ Insufficient candle data\nSymbol: {args.symbol}", is_error=True)
                time.sleep(args.interval)
                continue

            ema = df["close"].ewm(span=ema_period, adjust=False).mean().tolist()
            last = df.iloc[-1]
            prev = df.iloc[-2]
            candle_time = datetime.fromtimestamp(int(last["time"]), tz=TIMEZONE)
            is_new_candle = (last_candle_time is None) or (candle_time > last_candle_time)

            if pending_orders or active_trades:
                log(f"Tick check @ {datetime.now(TIMEZONE).strftime('%H:%M:%S')} | "
                    f"last candle: {candle_time.strftime('%H:%M')} "
                    f"O={last['open']:.2f} H={last['high']:.2f} L={last['low']:.2f} C={last['close']:.2f} | "
                    f"EMA={ema[-1]:.2f} | new_candle={is_new_candle} | "
                    f"pending={len(pending_orders)} active={len(active_trades)}")

            if is_new_candle:
                from src.utils import check_exit
                candle = {"high": last["high"], "low": last["low"], "close": last["close"]}

                # 1. Check pending orders — poll MT5 ticket each candle
                still_pending = []
                for order in pending_orders:
                    oid = order["order_id"]
                    mt5_ticket = order.get("mt5_ticket")
                    _sig = order["signal"]

                    # Test mode: simulate fill by candle low/high (unchanged behaviour)
                    if args.test or mt5_ticket is None:
                        filled = candle["low"] <= _sig["entry_price"] <= candle["high"]
                        if filled:
                            log(f"[{oid}] [TEST] Limit order filled @ {_sig['entry_price']:.2f}")
                            send_telegram(f"<b>FEG Reverse Limit Filled (TEST): {_sig['direction']}</b>\n"
                                          f"ID: <code>{oid}</code>\nEntry: {_sig['entry_price']:.2f}\n"
                                          f"SL: {_sig['stop_loss']:.2f} TP: {_sig['take_profit']:.2f}\n"
                                          f"Lot: {order['trade_lot']}")
                            active_trades.append({
                                "direction": _sig["direction"],
                                "entry": _sig["entry_price"],
                                "sl": _sig["stop_loss"],
                                "tp": _sig["take_profit"],
                                "ticket": None, "candles": 0, "order_id": oid,
                                "lot": order.get("trade_lot", lot_size),
                            })
                        else:
                            order["candles_left"] -= 1
                            if order["candles_left"] > 0:
                                still_pending.append(order)
                            else:
                                log(f"[{oid}] [TEST] Limit order expired (no fill)")
                                send_telegram(
                                    f"⏰ <b>Limit order hết hạn (không khớp) [TEST]</b>\n"
                                    f"ID: <code>{oid}</code>\nSymbol: {args.symbol}\n"
                                    f"Direction: {_sig['direction']}\nEntry: {_sig['entry_price']:.2f}\n"
                                    f"SL: {_sig['stop_loss']:.2f} TP: {_sig['take_profit']:.2f}"
                                )
                        continue  # skip live logic below

                    # Live: poll MT5 pending orders by ticket
                    pending_on_mt5 = mt5.orders_get(ticket=mt5_ticket)
                    if pending_on_mt5:
                        # Still pending on broker — decrement counter
                        order["candles_left"] -= 1
                        if order["candles_left"] > 0:
                            still_pending.append(order)
                        else:
                            # Timeout — cancel the pending order on MT5
                            log(f"[{oid}] Limit order timed out (ticket={mt5_ticket}) — cancelling")
                            ok_cancel, cancel_msg = cancel_pending_order(mt5_ticket, credentials=credentials)
                            if not ok_cancel:
                                log(f"[{oid}] Cancel FAILED: {cancel_msg} — retrying next candle", "ERROR")
                                send_telegram(f"❌ Cancel failed — order still live\nID: <code>{oid}</code>\nReason: {cancel_msg}", is_error=True)
                                # Keep in still_pending so next candle retries the cancel
                                still_pending.append(order)
                            else:
                                log(f"[{oid}] Cancel result: {cancel_msg}")
                                send_telegram(
                                    f"⏰ <b>Limit order hết hạn (không khớp)</b>\n"
                                    f"ID: <code>{oid}</code>\nSymbol: {args.symbol}\n"
                                    f"Direction: {_sig['direction']}\nEntry: {_sig['entry_price']:.2f}\n"
                                    f"SL: {_sig['stop_loss']:.2f} TP: {_sig['take_profit']:.2f}"
                                )
                    else:
                        # Order gone from MT5 pending list — check if it became a position (filled)
                        pos = mt5.positions_get(ticket=mt5_ticket)
                        if pos:
                            position = pos[0]
                            fill_price = position.price_open
                            log(f"[{oid}] Limit order filled by broker @ {fill_price:.5f} (ticket={mt5_ticket})")
                            send_telegram(f"<b>FEG Reverse Limit Filled: {_sig['direction']}</b>\n"
                                          f"ID: <code>{oid}</code>\nFill: {fill_price:.2f}\n"
                                          f"SL: {_sig['stop_loss']:.2f} TP: {_sig['take_profit']:.2f}\n"
                                          f"Lot: {order['trade_lot']} | Ticket: {mt5_ticket}")
                            active_trades.append({
                                "direction": _sig["direction"],
                                "entry": fill_price,          # actual fill price from MT5
                                "sl": _sig["stop_loss"],
                                "tp": _sig["take_profit"],
                                "ticket": mt5_ticket, "candles": 0, "order_id": oid,
                                "lot": order.get("trade_lot", lot_size),
                            })
                        else:
                            # Disappeared without becoming a position — cancelled externally or rejected
                            log(f"[{oid}] Pending order {mt5_ticket} no longer on MT5 (cancelled externally or rejected)")
                            send_telegram(f"⚠️ Pending order removed externally\nID: <code>{oid}</code>\nTicket: {mt5_ticket}")
                pending_orders = still_pending

                # 2. Check active trades — exit
                feg_be_enabled = bool(args.be_enabled)
                still_active = []
                for trade in active_trades:
                    trade["candles"] += 1
                    # Break-even: move SL to entry when profit >= be_r * sl_dist
                    if feg_be_enabled and not trade.get('be_triggered'):
                        entry_p = trade["entry"]
                        sl_dist = abs(entry_p - trade["sl"])
                        if trade["direction"] == "BUY" and candle["high"] >= entry_p + args.be_r * sl_dist:
                            trade["sl"] = entry_p
                            trade["be_triggered"] = True
                            log(f"[{trade.get('order_id','')}] BE triggered — SL → {entry_p:.2f}")
                        elif trade["direction"] == "SELL" and candle["low"] <= entry_p - args.be_r * sl_dist:
                            trade["sl"] = entry_p
                            trade["be_triggered"] = True
                            log(f"[{trade.get('order_id','')}] BE triggered — SL → {entry_p:.2f}")
                    exit_type, exit_price = check_exit(
                        trade["direction"], candle, trade["tp"], trade["sl"], tp_type, sl_type,
                    )
                    if not exit_type and max_candles > 0 and trade["candles"] >= max_candles:
                        exit_type, exit_price = "TIME", last["close"]
                    if exit_type:
                        pv = get_pip_value(args.symbol)
                        trade_lot = trade.get("lot", lot_size)
                        oid = trade.get("order_id", "")
                        ticket = trade.get("ticket")

                        # Step 1: Close position if still open (live mode only)
                        if not args.test and ticket:
                            _pos = mt5.positions_get(ticket=ticket)
                            if not _pos:
                                log(f"[{oid}] Position already closed by broker (TP/SL hit server-side)")
                            else:
                                closed_ok, close_msg = close_position(ticket, credentials=credentials)
                                if not closed_ok:
                                    if "not found" in close_msg.lower():
                                        # Race: broker closed between positions_get check and close call
                                        log(f"[{oid}] Position closed by broker between check and close (race)")
                                    else:
                                        log(f"[{oid}] Close failed: {close_msg}", "ERROR")
                                        send_telegram(f"❌ Close failed\nID: <code>{oid}</code>\nReason: {close_msg}", is_error=True)
                                        still_active.append(trade)
                                        continue

                        # Step 2: Verify exit from MT5 deal history (live mode only)
                        # deal.profit = net P&L from broker (after spread); swap = overnight fee
                        deal = None
                        if not args.test and ticket:
                            deal = _get_exit_deal(mt5, ticket)
                            if deal is None:
                                log(f"[{oid}] Could not verify exit from deal history — using estimated price", "WARN")

                        # Step 3: Use verified data if available, else fall back to candle estimate
                        if deal:
                            actual_price = deal["price"]
                            actual_pnl_usd = deal["profit"] + deal["swap"]  # net USD after overnight
                            verified = True
                        else:
                            actual_price = exit_price  # candle-based estimate
                            actual_pnl_usd = _estimate_pnl_usd(
                                mt5, args.symbol, trade["direction"],
                                trade["entry"], exit_price, trade_lot, pv,
                            )  # None when symbol info unavailable
                            verified = False
                            if actual_pnl_usd is None:
                                log(f"[{oid}] USD P&L unavailable from MT5 symbol info; recording 0.00 estimate", "WARN")
                                actual_pnl_usd = 0.0

                        actual_pips = (
                            (actual_price - trade["entry"]) / pv if trade["direction"] == "BUY"
                            else (trade["entry"] - actual_price) / pv
                        )

                        # Step 4: Log, Telegram, record — mark estimated data clearly
                        price_str = f"{actual_price:.2f}"
                        usd_part = f" (${actual_pnl_usd:.2f})" if actual_pnl_usd is not None else ""
                        pnl_str = f"{actual_pips:.1f} pips{usd_part}"
                        if not verified:
                            price_str += " ~est"
                            pnl_str = "~" + pnl_str + " ⚠️"

                        log(f"[{oid}] FEG Reverse Exit: {exit_type} @ {price_str}, P&L: {pnl_str}")
                        send_telegram(f"<b>FEG Reverse Exit: {exit_type}</b>\nID: <code>{oid}</code>\nPrice: {price_str}\nP&L: {pnl_str}")
                        _record_trade(_session_id, oid, trade["direction"],
                                      trade["entry"], actual_price, exit_type,
                                      actual_pnl_usd, trade_lot, verified=verified)
                    else:
                        still_active.append(trade)
                active_trades = still_active

                # 3. Scan FEG Reverse signal → tạo pending order mới
                now_hcm = datetime.now(TIMEZONE)
                in_window = _in_time_window(now_hcm, entry_start_time, entry_end_time)
                can_scan = re_entry_after_sl or not active_trades
                log(f"New candle {candle_time.strftime('%H:%M')} | "
                    f"C1: O={prev['open']:.2f} H={prev['high']:.2f} L={prev['low']:.2f} C={prev['close']:.2f} | "
                    f"C2: O={last['open']:.2f} H={last['high']:.2f} L={last['low']:.2f} C={last['close']:.2f} | "
                    f"EMA={ema[-1]:.2f} | in_window={in_window} can_scan={can_scan}")
                if in_window and can_scan:
                    c1 = {"open": prev["open"], "high": prev["high"], "low": prev["low"], "close": prev["close"]}
                    c2 = {"open": last["open"], "high": last["high"], "low": last["low"], "close": last["close"]}
                    signal = feg_reverse_entry_decision(
                        None, c1, c2, ema[-1], args.symbol,
                        rr_ratio, buffer_k, lot_size, entry_mode, entry_percent,
                        h2_exceed_pips, c2_gap_pips, ema_margin_pips,
                        ema_filter_enabled, buy_ema_side, sell_ema_side,
                        c2_buy_upper_wick_max_pct, c2_buy_lower_wick_max_pct,
                        c2_sell_upper_wick_max_pct, c2_sell_lower_wick_max_pct,
                        c2_buy_upper_wick_cmp, c2_buy_lower_wick_cmp,
                        c2_sell_upper_wick_cmp, c2_sell_lower_wick_cmp,
                    )
                    log(f"Signal scan: {signal['direction'] if signal else 'NO SIGNAL'}"
                        + (f" entry={signal['entry_price']:.2f} sl={signal['stop_loss']:.2f} tp={signal['take_profit']:.2f}" if signal else ""))
                    if signal:
                        trade_lot = lot_size
                        if lot_mode == "flex":
                            trade_lot = _calc_flex_lot(
                                mt5, args.symbol, risk_mode, risk_percent, risk_amount,
                                signal["entry_price"], signal["stop_loss"],
                            )
                        import uuid as _uuid
                        _candle_dt = datetime.fromtimestamp(int(last['time']), tz=TIMEZONE)
                        order_id = f"ORD-{_candle_dt.strftime('%y%m%d-%H%M%S')}-{args.symbol}-{_uuid.uuid4().hex[:4].upper()}"
                        log(f"[{order_id}] FEG Reverse Signal: {signal['direction']} @ {signal['entry_price']:.2f}, "
                            f"SL={signal['stop_loss']:.2f}, TP={signal['take_profit']:.2f}, lot={trade_lot}, "
                            f"limit_timeout={limit_order_candles}c")
                        # Place real MT5 pending limit order
                        ok_limit, msg_limit, mt5_ticket = place_limit_order(
                            args.symbol, signal["direction"], trade_lot, signal["entry_price"],
                            sl=signal["stop_loss"], tp=signal["take_profit"],
                            credentials=credentials, test=bool(args.test),
                            magic=212300, comment=f"FEGREV-{order_id[-4:]}",
                        )
                        if not ok_limit:
                            log(f"[{order_id}] Failed to place limit order: {msg_limit}", "ERROR")
                            send_telegram(f"❌ Limit order failed\nID: <code>{order_id}</code>\nReason: {msg_limit}", is_error=True)
                        else:
                            log(f"[{order_id}] Limit order placed on MT5 ticket={mt5_ticket}")
                            _pv = get_pip_value(args.symbol)
                            _sym_tag = "BTC" if "BTC" in args.symbol else "ETH" if "ETH" in args.symbol else "XAU" if "XAU" in args.symbol else "FX"
                            _o, _h, _l, _c = c2["open"], c2["high"], c2["low"], c2["close"]
                            _body = abs(_c - _o)
                            _buf_offset = buffer_k * _pv
                            _em_str = f"Body {entry_percent:.0f}%" if entry_mode == "range_percent" else "Close"
                            _ep = signal["entry_price"]
                            _sl = signal["stop_loss"]
                            _tp = signal["take_profit"]
                            _sl_pips = signal["sl_pips"]
                            if signal["direction"] == "SELL":
                                _entry_calc = f"Entry = C + {entry_percent:.0f}%×body = {_c:.2f} + {(entry_percent/100*_body):.2f} = {_ep:.2f}" if entry_mode == "range_percent" else f"Entry = C = {_ep:.2f}"
                                _sl_calc   = f"SL    = H + buffer   = {_h:.2f} + {_buf_offset:.2f} = {_sl:.2f}"
                                _tp_calc   = f"TP    = Entry - Risk×{rr_ratio:.1f} = {_tp:.2f}"
                            else:
                                _entry_calc = f"Entry = C - {entry_percent:.0f}%×body = {_c:.2f} - {(entry_percent/100*_body):.2f} = {_ep:.2f}" if entry_mode == "range_percent" else f"Entry = C = {_ep:.2f}"
                                _sl_calc   = f"SL    = L - buffer   = {_l:.2f} - {_buf_offset:.2f} = {_sl:.2f}"
                                _tp_calc   = f"TP    = Entry + Risk×{rr_ratio:.1f} = {_tp:.2f}"
                            _calc_block = (
                                f"C2: O={_o:.2f} H={_h:.2f} L={_l:.2f} C={_c:.2f}\n"
                                f"Entry Mode: {_em_str}\n"
                                f"pip_value = {_pv} ({_sym_tag})\n"
                                f"Buffer_k = {buffer_k} → buffer_offset = Buffer_k × pip_value = ${_buf_offset:.2f}\n"
                                f"---\n"
                                f"Body = |C - O| = |{_c:.2f} - {_o:.2f}| = {_body:.2f}\n"
                                f"{_entry_calc}\n"
                                f"{_sl_calc}\n"
                                f"Risk  = {_sl_pips:.2f} pips\n"
                                f"{_tp_calc}"
                            )
                            send_telegram(f"<b>FEG Reverse Signal (pending): {signal['direction']}</b>\n"
                                          f"ID: <code>{order_id}</code>\n"
                                          f"Symbol: {args.symbol} | Lot: {trade_lot} | Ticket: {mt5_ticket} | Chờ: {limit_order_candles} nến\n\n"
                                          f"<pre>{_calc_block}</pre>")
                            pending_orders.append({
                                "signal": signal,
                                "trade_lot": trade_lot,
                                "candles_left": limit_order_candles,
                                "order_id": order_id,
                                "mt5_ticket": mt5_ticket,
                            })

                last_candle_time = candle_time

                _write_bot_state(os.getpid(), args.symbol, args.strategy,
                                 len(active_trades), len(pending_orders))

                # Graceful restart: if flagged and idle, raise sentinel so __main__ re-runs bot
                if _check_pending_restart(os.getpid()) and not active_trades and not pending_orders:
                    log("Pending restart flag detected and bot is idle — restarting with new code")
                    _clear_pending_restart(os.getpid())
                    _write_bot_state(os.getpid(), args.symbol, args.strategy, 0, 0)
                    _unregister_from_running_bots(os.getpid())
                    close_session(_session_id)
                    raise _GracefulRestart()

            time.sleep(args.interval)

    except KeyboardInterrupt:
        log("FEG Reverse Bot stopped by user")
        _write_bot_state(os.getpid(), args.symbol, args.strategy, 0, 0)
        _unregister_from_running_bots(os.getpid())
        close_session(_session_id)
        if not args.managed_by_ui:
            send_telegram("FEG Reverse Bot Stopped (manual)")
    except _GracefulRestart:
        raise
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log(f"FEG Reverse Bot error: {e}", "ERROR")
        _write_bot_state(os.getpid(), args.symbol, args.strategy, 0, 0)
        _unregister_from_running_bots(os.getpid())
        close_session(_session_id)
        send_telegram(f"❌ FEG Reverse Bot crashed\nSymbol: {args.symbol}\nError: {e}\n\n<pre>{tb[-800:]}</pre>", is_error=True)
        raise
    finally:
        # Shutdown MT5 once when the bot loop exits (any reason)
        try:
            import MetaTrader5 as _mt5_mod
            _mt5_mod.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    args = get_args()

    # Setup logger: write to --log-file (if given) + stderr, not stdout
    _fmt = _logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s",
                               datefmt="%Y-%m-%d %H:%M:%S")
    _logger.setLevel(_logging.DEBUG)
    _sh = _logging.StreamHandler(sys.stderr)
    _sh.setFormatter(_fmt)
    _logger.addHandler(_sh)
    if args.log_file:
        _log_dir = os.path.dirname(os.path.abspath(args.log_file))
        os.makedirs(_log_dir, exist_ok=True)
        from logging.handlers import RotatingFileHandler as _RFH
        _fh = _RFH(args.log_file, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
        _fh.setFormatter(_fmt)
        _logger.addHandler(_fh)

    RESTART_DELAY = 30
    while True:
        try:
            run_bot(args)
            break  # clean exit (KeyboardInterrupt bên trong đã xử lý)
        except KeyboardInterrupt:
            break
        except _GracefulRestart:
            log("Restarting bot with new code after graceful restart...")
            # loop continues — run_bot(args) called again with fresh state
        except Exception as e:
            import traceback as _tb
            _trace = _tb.format_exc()
            log(f"Bot crashed, restarting in {RESTART_DELAY}s: {e}\n{_trace}", "ERROR")
            send_telegram(f"🔄 <b>Bot restart sau crash</b>\nSymbol: {args.symbol}\nLý do: {e}\nRestart sau {RESTART_DELAY}s...", is_error=True)
            time.sleep(RESTART_DELAY)
