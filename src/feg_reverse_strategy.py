"""
FEG Reverse Strategy

Detects FEG Classic 2-candle pattern then inverts the trade direction.
SELL pattern → BUY order. BUY pattern → SELL order.

Wick filter uses pattern-side params (c2_sell_* for SELL pattern, c2_buy_* for BUY pattern).
SL/TP computed for the NEW (flipped) direction.
"""

from src.feg_strategy import detect_feg_signal
from src.utils import get_pip_value, compute_trade_levels


_FLIP = {"BUY": "SELL", "SELL": "BUY"}


def detect_feg_reverse_signal(
    candle1: dict,
    candle2: dict,
    ema2: float,
    pip_value: float,
    h2_exceed_pips: float = 0.0,
    c2_gap_pips: float = 0.0,
    ema_margin_pips: float = 0.0,
    ema_filter_enabled: bool = True,
    buy_ema_side: str = "below_ema",
    sell_ema_side: str = "above_ema",
    c2_buy_upper_wick_max_pct: float | None = None,
    c2_buy_lower_wick_max_pct: float | None = None,
    c2_sell_upper_wick_max_pct: float | None = None,
    c2_sell_lower_wick_max_pct: float | None = None,
    c2_buy_upper_wick_cmp: str = "lt",
    c2_buy_lower_wick_cmp: str = "lt",
    c2_sell_upper_wick_cmp: str = "lt",
    c2_sell_lower_wick_cmp: str = "lt",
) -> str | None:
    """
    Phát hiện pattern FEG rồi đảo chiều lệnh.
    SELL pattern → trả "BUY". BUY pattern → trả "SELL". None nếu không có pattern.
    Wick filter dùng params của pattern gốc (không phải chiều lệnh mới).
    """
    pattern = detect_feg_signal(
        candle1, candle2, ema2, pip_value,
        h2_exceed_pips=h2_exceed_pips,
        c2_gap_pips=c2_gap_pips,
        ema_margin_pips=ema_margin_pips,
        ema_filter_enabled=ema_filter_enabled,
        buy_ema_side=buy_ema_side,
        sell_ema_side=sell_ema_side,
        c2_buy_upper_wick_max_pct=c2_buy_upper_wick_max_pct,
        c2_buy_lower_wick_max_pct=c2_buy_lower_wick_max_pct,
        c2_sell_upper_wick_max_pct=c2_sell_upper_wick_max_pct,
        c2_sell_lower_wick_max_pct=c2_sell_lower_wick_max_pct,
        c2_buy_upper_wick_cmp=c2_buy_upper_wick_cmp,
        c2_buy_lower_wick_cmp=c2_buy_lower_wick_cmp,
        c2_sell_upper_wick_cmp=c2_sell_upper_wick_cmp,
        c2_sell_lower_wick_cmp=c2_sell_lower_wick_cmp,
    )
    return _FLIP.get(pattern)  # None stays None


def analyze_feg_reverse(
    symbol: str,
    candle1: dict,
    candle2: dict,
    ema2: float,
    rr_ratio: float = 2.0,
    buffer_k: float = 5.0,
    lot_size: float = 0.01,
    entry_mode: str = "close",
    entry_percent: float = 0.0,
    h2_exceed_pips: float = 0.0,
    c2_gap_pips: float = 0.0,
    ema_margin_pips: float = 0.0,
    ema_filter_enabled: bool = True,
    buy_ema_side: str = "below_ema",
    sell_ema_side: str = "above_ema",
    c2_buy_upper_wick_max_pct: float | None = None,
    c2_buy_lower_wick_max_pct: float | None = None,
    c2_sell_upper_wick_max_pct: float | None = None,
    c2_sell_lower_wick_max_pct: float | None = None,
    c2_buy_upper_wick_cmp: str = "lt",
    c2_buy_lower_wick_cmp: str = "lt",
    c2_sell_upper_wick_cmp: str = "lt",
    c2_sell_lower_wick_cmp: str = "lt",
) -> dict | None:
    """Dựng signal đầy đủ (entry/SL/TP) cho FEG Reverse. None nếu không có pattern."""
    pip_value = get_pip_value(symbol)
    direction = detect_feg_reverse_signal(
        candle1, candle2, ema2, pip_value,
        h2_exceed_pips=h2_exceed_pips,
        c2_gap_pips=c2_gap_pips,
        ema_margin_pips=ema_margin_pips,
        ema_filter_enabled=ema_filter_enabled,
        buy_ema_side=buy_ema_side,
        sell_ema_side=sell_ema_side,
        c2_buy_upper_wick_max_pct=c2_buy_upper_wick_max_pct,
        c2_buy_lower_wick_max_pct=c2_buy_lower_wick_max_pct,
        c2_sell_upper_wick_max_pct=c2_sell_upper_wick_max_pct,
        c2_sell_lower_wick_max_pct=c2_sell_lower_wick_max_pct,
        c2_buy_upper_wick_cmp=c2_buy_upper_wick_cmp,
        c2_buy_lower_wick_cmp=c2_buy_lower_wick_cmp,
        c2_sell_upper_wick_cmp=c2_sell_upper_wick_cmp,
        c2_sell_lower_wick_cmp=c2_sell_lower_wick_cmp,
    )
    if direction is None:
        return None

    levels = compute_trade_levels(
        direction, candle2, entry_mode, entry_percent, buffer_k, rr_ratio, pip_value,
    )
    return {
        "symbol": symbol,
        "direction": direction,
        "entry_price": levels["entry_price"],
        "stop_loss": levels["stop_loss"],
        "take_profit": levels["take_profit"],
        "sl_pips": levels["sl_pips"],
        "lot_size": lot_size,
        "candle1": candle1,
        "candle2": candle2,
    }
