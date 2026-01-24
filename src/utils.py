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
    Get pip size (price movement per 1 pip) - Industry Standard.

    XAUUSD: 1 pip = 0.01 ($1 move = 100 pips)
    BTCUSD: 1 pip = 1.0 ($100 move = 100 pips)
    ETHUSD: 1 pip = 0.01 ($1 move = 100 pips)
    JPY pairs: 1 pip = 0.01
    Other forex: 1 pip = 0.0001
    """
    symbol_upper = symbol.upper()
    if "XAU" in symbol_upper:
        return 0.01  # Gold: 1 pip = $0.01
    elif "BTC" in symbol_upper:
        return 1.0   # Bitcoin: 1 pip = $1.00
    elif "ETH" in symbol_upper:
        return 0.01  # Ethereum: 1 pip = $0.01
    elif "JPY" in symbol_upper:
        return 0.01  # JPY pairs: 1 pip = 0.01
    return 0.0001    # Standard forex: 1 pip = 0.0001


def get_pip_value_per_lot(symbol: str) -> float:
    """
    Get USD value per pip per 1 standard lot - Industry Standard.

    Formula: pip_value_per_lot = contract_size * pip_size

    XAUUSD: 100 oz * $0.01 = $1.00 per pip per lot
    BTCUSD: 1 BTC * $1.00 = $1.00 per pip per lot
    ETHUSD: 1 ETH * $0.01 = $0.01 per pip per lot
    Forex: 100,000 units * 0.0001 = $10.00 per pip per lot
    """
    symbol_upper = symbol.upper()
    if "XAU" in symbol_upper:
        return 1.0   # 100 oz × $0.01 pip = $1 per pip per lot
    elif "BTC" in symbol_upper:
        return 1.0   # 1 BTC × $1 pip = $1 per pip per lot
    elif "ETH" in symbol_upper:
        return 0.01  # 1 ETH × $0.01 pip = $0.01 per pip per lot
    elif "JPY" in symbol_upper:
        # For USD/JPY: 100,000 * 0.01 / ~150 (rate) ≈ $6.67, but simplified to $10
        return 10.0
    return 10.0      # Standard forex: 100,000 × 0.0001 = $10 per pip per lot


def get_contract_size(symbol: str) -> float:
    """
    Get contract size (units per 1 standard lot).

    XAUUSD: 100 oz
    BTCUSD: 1 BTC
    ETHUSD: 1 ETH
    Forex: 100,000 units
    """
    symbol_upper = symbol.upper()
    if "XAU" in symbol_upper:
        return 100.0     # 100 oz per lot
    elif "BTC" in symbol_upper:
        return 1.0       # 1 BTC per lot
    elif "ETH" in symbol_upper:
        return 1.0       # 1 ETH per lot
    return 100000.0      # 100,000 units per lot


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