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
    parser.add_argument("--ema_period", type=int, default=None,
                        help="EMA period for pattern strategies (default: from strategy)")
    parser.add_argument("--ema_distance_enabled", type=int, default=0,
                        help="Enable EMA distance filter: 1=yes, 0=no")
    parser.add_argument("--ema_distance_pips", type=float, default=0.0,
                        help="EMA distance in pips when filter enabled")
    parser.add_argument("--entry_mode", type=str, default=None,
                        help="Entry mode: 'close' or 'range_percent' (default: from strategy)")
    parser.add_argument("--entry_percent", type=float, default=None,
                        help="Entry percent for range_percent mode (default: from strategy)")
    parser.add_argument("--tp_type", type=str, default=None,
                        help="TP exit type: 'price_based' or 'close_based' (default: from strategy)")
    parser.add_argument("--sl_type", type=str, default=None,
                        help="SL exit type: 'close_based' or 'price_based' (default: from strategy)")
    parser.add_argument("--buffer_k", type=float, default=None,
                        help="SL buffer in pips beyond candle extreme (default: from strategy)")
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

    # Dispatch theo entry type
    if params.get('entry_type', 'time') == 'pattern':
        credentials = get_user_mt5_credentials(args.user)
        if not credentials.get('login'):
            msg = f"MT5 credentials not configured for user: {args.user}"
            log(msg, "ERROR")
            send_telegram(f"❌ Bot startup failed\n{msg}", is_error=True)
            return
        run_feg_bot(args, strategy, params, credentials)
        return

    # Override with command line args if provided
    sl_pips = args.sl_pips or params.get('sl_pips', 30)
    rr_ratio = args.rr_ratio or params.get('rr_ratio', 2.0)
    lot_size = args.lot_size or params.get('lot_size', 0.01)
    max_candles = args.max_candles or params.get('max_candles', 7)
    entry_time = params.get('entry_time', '21:05')
    timeframe = params.get('timeframe', 'M5')

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
        import traceback
        tb = traceback.format_exc()
        log(f"Bot error: {e}", "ERROR")
        send_telegram(f"❌ Bot crashed\nStrategy: {args.strategy}\nSymbol: {args.symbol}\nError: {e}\n\n<pre>{tb[-800:]}</pre>", is_error=True)
        raise


def feg_entry_decision(
    active_trade, candle1, candle2, ema2, symbol,
    rr_ratio, buffer_k, lot_size, entry_mode, entry_percent,
    ema_distance_enabled, ema_distance_pips,
):
    """Quyết định vào lệnh FEG. None nếu đang có lệnh (1 lệnh/lúc) hoặc không có pattern."""
    from src.feg_strategy import analyze_feg
    if active_trade is not None:
        return None
    return analyze_feg(
        symbol, candle1, candle2, ema2,
        rr_ratio=rr_ratio, buffer_k=buffer_k, lot_size=lot_size,
        entry_mode=entry_mode, entry_percent=entry_percent,
        ema_distance_enabled=ema_distance_enabled, ema_distance_pips=ema_distance_pips,
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


def run_feg_bot(args, strategy, params, credentials):
    """Vòng lặp live cho strategy FEG (pattern + EMA21, 1 lệnh/lúc)."""
    from src.orders import place_order, close_position

    timeframe = params.get('timeframe', 'M5')
    ema_period = args.ema_period or params.get('ema_period', 21)
    rr_ratio = args.rr_ratio or params.get('rr_ratio', 2.0)
    buffer_k = args.buffer_k if args.buffer_k is not None else params.get('buffer_k', 5)
    lot_size = args.lot_size or params.get('lot_size', 0.01)
    max_candles = args.max_candles if args.max_candles is not None else params.get('max_candles', 7)
    ema_dist_enabled = bool(args.ema_distance_enabled) or params.get('ema_distance_enabled', False)
    ema_dist_pips = args.ema_distance_pips or params.get('ema_distance_pips', 0)
    entry_mode = args.entry_mode or params.get('entry_mode', 'close')
    entry_percent = args.entry_percent if args.entry_percent is not None else params.get('entry_percent', 0.0)
    tp_type = args.tp_type or params.get('tp_type', 'price_based')
    sl_type = args.sl_type or params.get('sl_type', 'close_based')
    lot_mode = args.lot_mode or 'fixed'
    risk_mode = args.risk_mode or 'percent'
    risk_percent = args.risk_percent
    risk_amount = args.risk_amount

    # Auto-detect symbol min lot and clamp (only for fixed mode)
    mt5_tmp, err_tmp = get_mt5_connection(credentials)
    if not err_tmp:
        sym_info = mt5_tmp.symbol_info(args.symbol)
        if sym_info and lot_mode == "fixed" and lot_size < sym_info.volume_min:
            log(f"lot_size {lot_size} < symbol min {sym_info.volume_min} — using {sym_info.volume_min}", "WARN")
            lot_size = sym_info.volume_min
        mt5_tmp.shutdown()

    lot_log = f"flex({risk_mode} {risk_percent}%/{risk_amount}$)" if lot_mode == "flex" else f"fixed={lot_size}"
    log(f"FEG params: EMA{ema_period}, RR={rr_ratio}, buffer_k={buffer_k}, "
        f"lot={lot_log}, max_candles={max_candles or 'unlimited'}, "
        f"dist={'ON ' + str(ema_dist_pips) + 'p' if ema_dist_enabled else 'OFF'}")

    send_telegram(f"FEG Bot Started\nSymbol: {args.symbol}\nUser: {args.user}\n"
                  f"Test: {'Yes' if args.test else 'No'}")

    active_trade = None
    last_candle_time = None

    try:
        while True:
            mt5, error = get_mt5_connection(credentials)
            if error:
                log(f"MT5 connection failed: {error}", "ERROR")
                send_telegram(f"MT5 Error: {error}", is_error=True)
                time.sleep(args.interval)
                continue

            df = get_recent_candles(mt5, args.symbol, timeframe, count=max(120, ema_period * 4))
            if df is None or len(df) < ema_period + 2:
                log(f"Insufficient candle data for {args.symbol} (got {len(df) if df is not None else 0})", "ERROR")
                send_telegram(f"❌ Insufficient candle data\nSymbol: {args.symbol}", is_error=True)
                mt5.shutdown()
                time.sleep(args.interval)
                continue

            ema = df["close"].ewm(span=ema_period, adjust=False).mean().tolist()
            last = df.iloc[-1]
            prev = df.iloc[-2]
            candle_time = datetime.fromtimestamp(int(last["time"]), tz=TIMEZONE)

            # chỉ xử lý khi có nến đóng mới
            is_new_candle = (last_candle_time is None) or (candle_time > last_candle_time)

            if active_trade is None and is_new_candle:
                c1 = {"open": prev["open"], "high": prev["high"], "low": prev["low"], "close": prev["close"]}
                c2 = {"open": last["open"], "high": last["high"], "low": last["low"], "close": last["close"]}
                signal = feg_entry_decision(
                    None, c1, c2, ema[-1], args.symbol,
                    rr_ratio, buffer_k, lot_size, entry_mode, entry_percent,
                    ema_dist_enabled, ema_dist_pips,
                )
                if signal:
                    # Calculate flex lot if needed
                    trade_lot = lot_size
                    if lot_mode == "flex":
                        trade_lot = _calc_flex_lot(
                            mt5, args.symbol, risk_mode, risk_percent, risk_amount,
                            signal["entry_price"], signal["stop_loss"],
                        )
                    import uuid as _uuid
                    order_id = f"ORD-{last['time'].strftime('%y%m%d-%H%M%S')}-{args.symbol}-{_uuid.uuid4().hex[:4].upper()}"
                    log(f"[{order_id}] FEG Signal: {signal['direction']} @ {signal['entry_price']:.2f}, "
                        f"SL={signal['stop_loss']:.2f}, TP={signal['take_profit']:.2f}, lot={trade_lot}")
                    send_telegram(f"<b>FEG Signal: {signal['direction']}</b>\n"
                                  f"ID: <code>{order_id}</code>\n"
                                  f"Symbol: {args.symbol}\nEntry: {signal['entry_price']:.2f}\n"
                                  f"SL: {signal['stop_loss']:.2f}\nTP: {signal['take_profit']:.2f}\n"
                                  f"Lot: {trade_lot}")
                    ok, msg, ticket = place_order(
                        args.symbol, signal["direction"], trade_lot,
                        sl=signal["stop_loss"], tp=signal["take_profit"],
                        credentials=credentials, test=bool(args.test),
                        magic=212100, comment=f"FEG-{order_id[-4:]}",
                    )
                    log(f"[{order_id}] Order result: {msg}")
                    if ok:
                        active_trade = {
                            "direction": signal["direction"], "entry": signal["entry_price"],
                            "sl": signal["stop_loss"], "tp": signal["take_profit"],
                            "ticket": ticket, "candles": 0, "order_id": order_id,
                        }
                    else:
                        log(f"[{order_id}] Order failed — will retry next signal", "WARN")
                        send_telegram(f"❌ Order failed\nID: <code>{order_id}</code>\nReason: {msg}", is_error=True)

            elif active_trade is not None and is_new_candle:
                active_trade["candles"] += 1
                candle = {"high": last["high"], "low": last["low"], "close": last["close"]}
                from src.utils import check_exit
                exit_type, exit_price = check_exit(
                    active_trade["direction"], candle,
                    active_trade["tp"], active_trade["sl"],
                    tp_type,
                    sl_type,
                )
                if not exit_type and max_candles > 0 and active_trade["candles"] >= max_candles:
                    exit_type, exit_price = "TIME", last["close"]

                if exit_type:
                    pip_value = get_pip_value(args.symbol)
                    if active_trade["direction"] == "BUY":
                        pnl = (exit_price - active_trade["entry"]) / pip_value
                    else:
                        pnl = (active_trade["entry"] - exit_price) / pip_value
                    oid = active_trade.get("order_id", "")
                    log(f"[{oid}] FEG Exit: {exit_type} @ {exit_price:.2f}, P&L: {pnl:.1f} pips")
                    send_telegram(f"<b>FEG Exit: {exit_type}</b>\nID: <code>{oid}</code>\nPrice: {exit_price:.2f}\nP&L: {pnl:.1f} pips")
                    if not args.test and active_trade.get("ticket"):
                        closed_ok, close_msg = close_position(active_trade["ticket"], credentials=credentials)
                        if not closed_ok:
                            log(f"[{oid}] Close position failed: {close_msg}", "ERROR")
                            send_telegram(f"❌ Close position failed\nID: <code>{oid}</code>\nTicket: {active_trade['ticket']}\nReason: {close_msg}", is_error=True)
                    active_trade = None

            if is_new_candle:
                last_candle_time = candle_time

            mt5.shutdown()
            time.sleep(args.interval)

    except KeyboardInterrupt:
        log("FEG Bot stopped by user")
        send_telegram("FEG Bot Stopped (manual)")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log(f"FEG Bot error: {e}", "ERROR")
        send_telegram(f"❌ FEG Bot crashed\nSymbol: {args.symbol}\nError: {e}\n\n<pre>{tb[-800:]}</pre>", is_error=True)
        raise


if __name__ == "__main__":
    args = get_args()
    RESTART_DELAY = 30
    while True:
        try:
            run_bot(args)
            break  # clean exit (KeyboardInterrupt bên trong đã xử lý)
        except KeyboardInterrupt:
            break
        except Exception as e:
            import traceback
            log(f"Bot crashed, restarting in {RESTART_DELAY}s: {e}", "ERROR")
            time.sleep(RESTART_DELAY)
