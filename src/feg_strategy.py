"""
FEG EMA21 Strategy

Pattern 2 nến + filter EMA21, quét liên tục.
SELL: H2 > H1, C2 < L1, L2 > EMA21 (+dist pips nếu bật filter).
BUY:  L2 < L1, C2 > H1, H2 < EMA21 (-dist pips nếu bật filter).
TP/SL neo vào candle2 (giống master_candle): SL = candle2 high/low ± buffer_k,
TP = entry ± risk × rr_ratio.
"""

from src.utils import get_pip_value, compute_trade_levels


def detect_feg_signal(
    candle1: dict,
    candle2: dict,
    ema2: float,
    pip_value: float,
    ema_distance_enabled: bool = False,
    ema_distance_pips: float = 0.0,
) -> str | None:
    """
    Phát hiện tín hiệu FEG từ 2 nến đã đóng + EMA21 tại close candle2.

    Args:
        candle1: nến đóng trước (dict open/high/low/close)
        candle2: nến vừa đóng (dict open/high/low/close)
        ema2: giá trị EMA21 tại close của candle2
        pip_value: giá trị 1 pip của symbol
        ema_distance_enabled: bật filter khoảng cách EMA
        ema_distance_pips: khoảng cách (pips) khi filter bật

    Returns:
        "BUY", "SELL", hoặc None
    """
    h1, l1, o1, c1 = candle1["high"], candle1["low"], candle1["open"], candle1["close"]
    h2, l2, o2, c2 = candle2["high"], candle2["low"], candle2["open"], candle2["close"]
    dist = ema_distance_pips * pip_value if ema_distance_enabled else 0.0

    bullish1, bullish2 = c1 > o1, c2 > o2  # True = nến tăng
    body1, body2 = abs(c1 - o1), abs(c2 - o2)

    # SELL: FEG giảm — cả 2 nến phải cùng loại (đều giảm), body C2 > body C1
    if not bullish1 and not bullish2 and body2 > body1:
        if h2 > h1 and c2 < l1:
            if l2 > ema2 + dist:
                return "SELL"

    # BUY: FEG tăng — cả 2 nến phải cùng loại (đều tăng), body C2 > body C1
    if bullish1 and bullish2 and body2 > body1:
        if l2 < l1 and c2 > h1:
            if h2 < ema2 - dist:
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
    ema_distance_enabled: bool = False,
    ema_distance_pips: float = 0.0,
) -> dict | None:
    """Dựng signal đầy đủ (entry/SL/TP) từ pattern FEG. Trả None nếu không có tín hiệu."""
    pip_value = get_pip_value(symbol)
    direction = detect_feg_signal(
        candle1, candle2, ema2, pip_value, ema_distance_enabled, ema_distance_pips,
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
