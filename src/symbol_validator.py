"""
Symbol Validation Module
Validates trading parameters before placing orders
"""

from typing import Dict, List, Tuple


def validate_symbol_and_params(
    symbol: str,
    lot_size: float,
    entry_price: float,
    sl_price: float,
    tp_price: float,
    credentials: dict
) -> Tuple[bool, List[str]]:
    """
    Validate symbol and trading parameters

    Args:
        symbol: Trading symbol
        lot_size: Lot size
        entry_price: Entry price
        sl_price: Stop loss price
        tp_price: Take profit price
        credentials: MT5 credentials

    Returns:
        (is_valid, list_of_warnings/errors)
    """
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return False, ["MT5 not available (Windows only)"]

    from src.orders import get_mt5_connection

    warnings = []
    errors = []

    # Connect to MT5
    mt5_conn, error = get_mt5_connection(credentials)
    if error:
        return False, [f"MT5 connection failed: {error}"]

    # Get symbol info
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        mt5.shutdown()
        return False, [f"[ERROR] Symbol '{symbol}' not found on broker"]

    # Check if symbol is visible/tradable
    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            mt5.shutdown()
            return False, [f"[ERROR] Symbol '{symbol}' is not tradable"]

    # Check trade mode
    if symbol_info.trade_mode == 0:  # TRADE_MODE_DISABLED
        errors.append(f"[ERROR] Trading is disabled for '{symbol}'")
    elif symbol_info.trade_mode == 2:  # TRADE_MODE_CLOSEONLY
        warnings.append(f"[WARN] Symbol '{symbol}' is in close-only mode")

    # Validate lot size
    volume_min = symbol_info.volume_min
    volume_max = symbol_info.volume_max
    volume_step = symbol_info.volume_step

    if lot_size < volume_min:
        errors.append(
            f"[ERROR] Lot size {lot_size} is below minimum {volume_min} for {symbol}\n"
            f"   Minimum allowed: {volume_min}"
        )

    if lot_size > volume_max:
        errors.append(
            f"[ERROR] Lot size {lot_size} exceeds maximum {volume_max} for {symbol}\n"
            f"   Maximum allowed: {volume_max}"
        )

    # Check volume step (e.g., ETHUSD requires 0.1 increments)
    if volume_step > 0:
        # Round to match step precision
        remainder = round((lot_size % volume_step), 10)
        if remainder > 0.0000001:  # Tolerance for floating point
            suggested_lot = round(lot_size - remainder + volume_step, 2)
            errors.append(
                f"[ERROR] Lot size {lot_size} doesn't match step size {volume_step} for {symbol}\n"
                f"   Example valid lots: {volume_min}, {volume_min + volume_step}, {suggested_lot}"
            )

    # Validate SL/TP distance (minimum stop level)
    stops_level = symbol_info.trade_stops_level
    point = symbol_info.point

    if stops_level > 0:
        min_distance = stops_level * point

        sl_distance = abs(entry_price - sl_price)
        tp_distance = abs(entry_price - tp_price)

        if sl_distance < min_distance:
            errors.append(
                f"[ERROR] SL too close to entry: {sl_distance:.5f}\n"
                f"   Minimum distance: {min_distance:.5f} ({stops_level} points)"
            )

        if tp_distance < min_distance:
            errors.append(
                f"[ERROR] TP too close to entry: {tp_distance:.5f}\n"
                f"   Minimum distance: {min_distance:.5f} ({stops_level} points)"
            )

    # Check if trading is allowed (AutoTrading)
    terminal_info = mt5.terminal_info()
    if terminal_info and not terminal_info.trade_allowed:
        errors.append(
            "[ERROR] AutoTrading is disabled in MT5\n"
            "   Enable: Tools → Options → Expert Advisors → Allow automated trading"
        )

    # Display symbol info as warnings
    warnings.append(
        f"[INFO] Symbol Info: {symbol}\n"
        f"   • Lot range: {volume_min} - {volume_max} (step: {volume_step})\n"
        f"   • Min stop distance: {stops_level} points ({stops_level * point:.5f})\n"
        f"   • Spread: {symbol_info.spread} points"
    )

    mt5.shutdown()

    all_messages = errors + warnings
    is_valid = len(errors) == 0

    return is_valid, all_messages


def get_symbol_info_dict(symbol: str, credentials: dict) -> Dict:
    """
    Get symbol information as a dictionary

    Returns:
        dict with symbol info or None if error
    """
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return None

    from src.orders import get_mt5_connection

    mt5_conn, error = get_mt5_connection(credentials)
    if error:
        return None

    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        mt5.shutdown()
        return None

    info = {
        'symbol': symbol,
        'volume_min': symbol_info.volume_min,
        'volume_max': symbol_info.volume_max,
        'volume_step': symbol_info.volume_step,
        'stops_level': symbol_info.trade_stops_level,
        'point': symbol_info.point,
        'digits': symbol_info.digits,
        'spread': symbol_info.spread,
        'trade_mode': symbol_info.trade_mode,
        'visible': symbol_info.visible
    }

    mt5.shutdown()
    return info
