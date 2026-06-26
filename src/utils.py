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

    Metals & Crypto:
        XAUUSD: 1 pip = 0.01 ($1 move = 100 pips)
        BTCUSD: 1 pip = 1.0 ($100 move = 100 pips)
        ETHUSD: 1 pip = 0.01 ($1 move = 100 pips)

    JPY pairs (2 decimal places):
        USDJPY, AUDJPY, etc: 1 pip = 0.01

    Standard Forex (4 decimal places):
        EURUSD, GBPUSD, AUDUSD: 1 pip = 0.0001
        USDCHF, USDCAD: 1 pip = 0.0001
    """
    symbol_upper = symbol.upper()
    if "XAU" in symbol_upper:
        return 0.01  # Gold: 1 pip = $0.01
    elif "BTC" in symbol_upper:
        return 1.0   # Bitcoin: 1 pip = $1.00
    elif "ETH" in symbol_upper:
        return 0.01  # Ethereum: 1 pip = $0.01
    elif "JPY" in symbol_upper:
        return 0.01  # JPY pairs: 1 pip = 0.01 (USDJPY, AUDJPY, etc.)
    return 0.0001    # Standard forex: 1 pip = 0.0001 (EURUSD, GBPUSD, etc.)


def get_point_value(symbol: str) -> float:
    """
    Get point size (smallest price increment) for buffer/offset calculations.

    On 5-digit brokers (like Exness), the MT5 "point" is the smallest
    price increment (last displayed decimal). For forex, 1 pip = 10 points.

    Forex (5-digit):
        EURUSD, GBPUSD, AUDUSD, etc: 1 point = 0.00001
    JPY pairs (3-digit):
        USDJPY, AUDJPY: 1 point = 0.001
    Gold (2-digit standard):
        XAUUSD: 1 point = 0.01 (pip = point)
    Crypto:
        BTCUSD: 1 point = 1.0 (practical: MT5 point 0.01 too small for buffer)
        ETHUSD: 1 point = 0.01 (pip = point)
    """
    symbol_upper = symbol.upper()
    if "XAU" in symbol_upper:
        return 0.01   # Gold: point = pip = 0.01
    elif "BTC" in symbol_upper:
        return 1.0    # Bitcoin: use pip (MT5 point 0.01 too small for buffer)
    elif "ETH" in symbol_upper:
        return 0.01   # Ethereum: point = pip = 0.01
    elif "JPY" in symbol_upper:
        return 0.001  # JPY 3-digit: point = pip/10
    return 0.00001    # Forex 5-digit: point = pip/10


def get_pip_value_per_lot(symbol: str) -> float:
    """
    Get USD value per pip per 1 standard lot - Industry Standard.

    Formula: pip_value_per_lot = contract_size * pip_size

    Metals & Crypto:
        XAUUSD: 100 oz * $0.01 = $1.00 per pip per lot
        BTCUSD: 1 BTC * $1.00 = $1.00 per pip per lot
        ETHUSD: 1 ETH * $0.01 = $0.01 per pip per lot

    Forex (USD is quote currency - fixed pip value):
        EURUSD, GBPUSD, AUDUSD: 100,000 * 0.0001 = $10.00 per pip per lot

    Forex (USD is base currency - pip value varies with exchange rate):
        USDJPY: ~$6.67 per pip at rate 150 (simplified to $10)
        USDCHF: ~$11.36 per pip at rate 0.88 (simplified to $10)
        USDCAD: ~$7.41 per pip at rate 1.35 (simplified to $10)

    Cross pairs:
        AUDJPY: ~$6.67 per pip at USDJPY rate 150 (simplified to $10)

    Note: For backtesting, we use $10 as standard approximation for all forex pairs.
    """
    symbol_upper = symbol.upper()
    if "XAU" in symbol_upper:
        return 1.0   # 100 oz * $0.01 pip = $1 per pip per lot
    elif "BTC" in symbol_upper:
        return 1.0   # 1 BTC * $1 pip = $1 per pip per lot
    elif "ETH" in symbol_upper:
        return 0.01  # 1 ETH * $0.01 pip = $0.01 per pip per lot
    elif "JPY" in symbol_upper:
        # JPY pairs: 100,000 * 0.01 / ~150 (rate) ≈ $6.67, but simplified to $10
        return 10.0
    return 10.0      # Standard forex: 100,000 * 0.0001 = $10 per pip per lot


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
        candle: dict with "high", "low", "close", and optionally "open"
        tp: Take profit level
        sl: Stop loss level
        tp_type: "price_based" (immediate on wick) or "close_based" (delayed on close)
        sl_type: "close_based" (delayed on close) or "price_based" (immediate on wick)

    Returns:
        (exit_type, exit_price) or (None, None)
        exit_type: "TP", "SL", or None

    Same-candle priority (both price_based):
        When a candle's wick hits BOTH TP and SL on the same candle (rare but possible),
        we compare distance from candle open to each level.
        The level closer to open is assumed to have been hit first (shorter travel = earlier).
        If open is not provided in candle dict, TP takes priority (original behavior).
    """
    h, l, c = candle["high"], candle["low"], candle["close"]
    candle_open = candle.get("open")  # optional — used for same-candle priority

    if direction == "BUY":
        tp_hit = (tp_type == "price_based" and h >= tp) or (tp_type == "close_based" and c >= tp)
        sl_hit = (sl_type == "price_based" and l <= sl) or (sl_type == "close_based" and c <= sl)

        if tp_hit and sl_hit:
            # Both hit on same candle — determine which fired first via distance from open
            if candle_open is not None and tp_type == "price_based" and sl_type == "price_based":
                dist_to_sl = candle_open - sl  # downward distance
                dist_to_tp = tp - candle_open  # upward distance
                if dist_to_sl < dist_to_tp:
                    return ("SL", sl)   # SL closer to open → hit first
                else:
                    return ("TP", tp)   # TP closer to open → hit first
            # Fallback (close_based, or no open provided): TP wins
            if tp_type == "price_based":
                return ("TP", tp)
            elif tp_type == "close_based":
                return ("TP", c)

        if tp_hit:
            return ("TP", tp) if tp_type == "price_based" else ("TP", c)
        if sl_hit:
            return ("SL", sl) if sl_type == "price_based" else ("SL", c)

    else:  # SELL
        tp_hit = (tp_type == "price_based" and l <= tp) or (tp_type == "close_based" and c <= tp)
        sl_hit = (sl_type == "price_based" and h >= sl) or (sl_type == "close_based" and c >= sl)

        if tp_hit and sl_hit:
            # Both hit on same candle — determine which fired first via distance from open
            if candle_open is not None and tp_type == "price_based" and sl_type == "price_based":
                dist_to_sl = sl - candle_open  # upward distance
                dist_to_tp = candle_open - tp  # downward distance
                if dist_to_sl < dist_to_tp:
                    return ("SL", sl)   # SL closer to open → hit first
                else:
                    return ("TP", tp)   # TP closer to open → hit first
            # Fallback: TP wins
            if tp_type == "price_based":
                return ("TP", tp)
            elif tp_type == "close_based":
                return ("TP", c)

        if tp_hit:
            return ("TP", tp) if tp_type == "price_based" else ("TP", c)
        if sl_hit:
            return ("SL", sl) if sl_type == "price_based" else ("SL", c)

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