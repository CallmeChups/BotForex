"""
FEG EMA21 Strategy

Pattern 2 nến + filter EMA21, quét liên tục.
Điều kiện chung: C1/C2 cùng hướng, body C2 > body C1.
SELL: H2 > H1 + h2_exceed_pips, C2 < L1 - c2_gap_pips, L2 > EMA + ema_margin_pips.
BUY:  L2 < L1 - h2_exceed_pips, C2 > H1 + c2_gap_pips, H2 < EMA - ema_margin_pips.
TP/SL neo vào candle2: SL = candle2 high/low ± buffer_k, TP = entry ± risk × rr_ratio.
"""

from src.utils import get_pip_value, compute_trade_levels


def detect_feg_signal(
    candle1: dict,
    candle2: dict,
    ema2: float,
    pip_value: float,
    h2_exceed_pips: float = 0.0,
    c2_gap_pips: float = 0.0,
    ema_margin_pips: float = 0.0,
) -> str | None:
    """
    Phát hiện tín hiệu FEG từ 2 nến đã đóng + EMA21 tại close candle2.

    Args:
        candle1: nến đóng trước (dict open/high/low/close)
        candle2: nến vừa đóng (dict open/high/low/close)
        ema2: giá trị EMA21 tại close của candle2
        pip_value: giá trị 1 pip của symbol
        h2_exceed_pips: H2 > H1 + N pips / L2 < L1 - N pips (điều kiện 4)
        c2_gap_pips: C2 < L1 - N pips / C2 > H1 + N pips (điều kiện 5)
        ema_margin_pips: L2 > EMA + N pips / H2 < EMA - N pips (điều kiện 6)

    Returns:
        "BUY", "SELL", hoặc None
    """
    h1, l1, o1, c1 = candle1["high"], candle1["low"], candle1["open"], candle1["close"]
    h2, l2, o2, c2 = candle2["high"], candle2["low"], candle2["open"], candle2["close"]

    h2_exceed = h2_exceed_pips * pip_value
    c2_gap    = c2_gap_pips    * pip_value
    ema_margin = ema_margin_pips * pip_value

    bullish1, bullish2 = c1 > o1, c2 > o2  # True = nến tăng
    body1, body2 = abs(c1 - o1), abs(c2 - o2)

    # SELL: FEG giảm — cả 2 nến phải cùng loại (đều giảm), body C2 > body C1
    if not bullish1 and not bullish2 and body2 > body1:
        if h2 > h1 + h2_exceed and c2 < l1 - c2_gap:
            if l2 > ema2 + ema_margin:
                return "SELL"

    # BUY: FEG tăng — cả 2 nến phải cùng loại (đều tăng), body C2 > body C1
    if bullish1 and bullish2 and body2 > body1:
        if l2 < l1 - h2_exceed and c2 > h1 + c2_gap:
            if h2 < ema2 - ema_margin:
                return "BUY"

    return None


def analyze_feg(
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
) -> dict | None:
    """Dựng signal đầy đủ (entry/SL/TP) từ pattern FEG. Trả None nếu không có tín hiệu."""
    pip_value = get_pip_value(symbol)
    direction = detect_feg_signal(
        candle1, candle2, ema2, pip_value,
        h2_exceed_pips, c2_gap_pips, ema_margin_pips,
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
