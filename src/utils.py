"""
Shared utility functions for BotForex
"""

from pandas import Series
from sys import float_info as sflt


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


def check_exit(direction: str, candle: dict, tp: float, sl: float) -> tuple:
    """
    Check exit conditions for a candle.

    TP: Price-based (immediate) - check High/Low
    SL: Close-based - check Close only

    Args:
        direction: "BUY" or "SELL"
        candle: dict with "high", "low", "close"
        tp: Take profit level
        sl: Stop loss level

    Returns:
        (exit_type, exit_price) or (None, None)
        exit_type: "TP", "SL", or None
    """
    h, l, c = candle["high"], candle["low"], candle["close"]

    if direction == "BUY":
        # TP: Price touches (High >= TP) - immediate
        if h >= tp:
            return ("TP", tp)
        # SL: Close-based (Close <= SL) - delayed
        if c <= sl:
            return ("SL", c)
    else:  # SELL
        # TP: Price touches (Low <= TP) - immediate
        if l <= tp:
            return ("TP", tp)
        # SL: Close-based (Close >= SL) - delayed
        if c >= sl:
            return ("SL", c)

    return (None, None)