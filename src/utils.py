"""
Shared utility functions for BotForex
"""

import os
import traceback as _traceback
import requests as _requests
from pandas import Series
from sys import float_info as sflt
from datetime import time as _time
from zoneinfo import ZoneInfo as _ZoneInfo

_TZ_HCM = _ZoneInfo("Asia/Ho_Chi_Minh")


def report_page_error(exc: Exception, context: str = "") -> None:
    """Log exception to Telegram ERROR_CHAT and re-raise nothing.

    Call inside except blocks on all Streamlit pages so bugs surface in
    the bug-error group automatically.  context = short label, e.g.
    "Backtest / fetch_historical_data".
    """
    tb = _traceback.format_exc()
    label = f"[{context}] " if context else ""
    msg = f"🐛 <b>PAGE ERROR</b> {label}\n<code>{type(exc).__name__}: {exc}</code>\n\n<pre>{tb[-2000:]}</pre>"

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_ERROR_CHAT_ID")
    if token and chat_id:
        try:
            _requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
                timeout=8,
            )
        except Exception:
            pass  # never let Telegram failure mask the original error


def non_zero_range(high: Series, low: Series) -> Series:
    """Returns the difference of two series and adds epsilon to any zero values.  This occurs commonly in crypto data when 'high' = 'low'."""
    diff = high - low
    if diff.eq(0).any().any():
        diff += sflt.epsilon
    return diff


def is_mt5_available() -> bool:
    """Check if MT5 is available (Windows only)"""
    try:
        import MetaTrader5
        return True
    except ImportError:
        return False


def get_pip_value(symbol: str) -> float:
    """
    Get pip value for symbol.

    Pip value = price movement per 1 pip
    - BTC: 1 pip = 1.0 price
    - ETH: 1 pip = 0.1 price
    - XAU: 1 pip = 0.1 price
    - JPY pairs: 1 pip = 0.01
    - Other forex: 1 pip = 0.0001
    """
    if "BTC" in symbol:
        return 1.0
    elif "ETH" in symbol:
        return 0.1
    elif "XAU" in symbol:
        return 0.1
    elif "JPY" in symbol:
        return 0.01
    return 0.0001


def check_exit(
    direction: str,
    candle: dict,
    tp: float,
    sl: float,
    tp_type: str = "price_based",
    sl_type: str = "close_based"
) -> tuple:
    """
    Check exit conditions for a candle.

    Args:
        direction: "BUY" or "SELL"
        candle: dict with "high", "low", "close"
        tp: Take profit level
        sl: Stop loss level
        tp_type: "price_based" (immediate on wick) or "close_based" (delayed on close)
        sl_type: "close_based" (delayed on close) or "price_based" (immediate on wick)

    Returns:
        (exit_type, exit_price) or (None, None)
        exit_type: "TP", "SL", or None
    """
    h, l, c = candle["high"], candle["low"], candle["close"]

    if direction == "BUY":
        # TP check
        if tp_type == "price_based":
            # Immediate: wick touches TP
            if h >= tp:
                return ("TP", tp)
        else:  # close_based
            # Delayed: close beyond TP
            if c >= tp:
                return ("TP", c)

        # SL check
        if sl_type == "close_based":
            # Delayed: close beyond SL
            if c <= sl:
                return ("SL", c)
        else:  # price_based
            # Immediate: wick touches SL
            if l <= sl:
                return ("SL", sl)

    else:  # SELL
        # TP check
        if tp_type == "price_based":
            # Immediate: wick touches TP
            if l <= tp:
                return ("TP", tp)
        else:  # close_based
            # Delayed: close beyond TP
            if c <= tp:
                return ("TP", c)

        # SL check
        if sl_type == "close_based":
            # Delayed: close beyond SL
            if c >= sl:
                return ("SL", c)
        else:  # price_based
            # Immediate: wick touches SL
            if h >= sl:
                return ("SL", sl)

    return (None, None)


def compute_trade_levels(
    direction: str,
    candle: dict,
    entry_mode: str,
    entry_percent: float,
    buffer_k: float,
    rr_ratio: float,
    pip_value: float,
) -> dict:
    """
    Tính entry / SL / TP / sl_pips neo vào 1 nến (anchor candle).

    BUY:  SL = low  - buffer_k*pip ; TP = entry + risk*rr
    SELL: SL = high + buffer_k*pip ; TP = entry - risk*rr
    entry_mode "close": entry = close
    entry_mode "range_percent": BUY entry = close - X%*body ; SELL entry = close + X%*body
        (body = |close - open|)
    """
    o, h, l, c = candle["open"], candle["high"], candle["low"], candle["close"]
    body = abs(c - o)
    buffer_offset = buffer_k * pip_value

    if direction == "BUY":
        entry = c - (entry_percent / 100) * body if entry_mode == "range_percent" else c
        stop_loss = l - buffer_offset
        sl_pips = (entry - stop_loss) / pip_value
        risk = entry - stop_loss
        take_profit = entry + risk * rr_ratio
    else:  # SELL
        entry = c + (entry_percent / 100) * body if entry_mode == "range_percent" else c
        stop_loss = h + buffer_offset
        sl_pips = (stop_loss - entry) / pip_value
        risk = stop_loss - entry
        take_profit = entry - risk * rr_ratio

    return {
        "entry_price": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "sl_pips": sl_pips,
    }


def _in_time_window(ts, start: _time, end: _time) -> bool:
    """True if ts (converted to Asia/Ho_Chi_Minh) falls within [start, end] inclusive."""
    local = ts.astimezone(_TZ_HCM).time().replace(second=0, microsecond=0)
    if start <= end:
        return start <= local <= end
    # overnight window (e.g. 22:00-02:00)
    return local >= start or local <= end