"""
FEG EMA21 Strategy

Pattern 2 nến + filter EMA21, quét liên tục.
SELL: H2 > H1, C2 < L1, L2 > EMA21 (+dist pips nếu bật filter).
BUY:  L2 < L1, C2 > H1, H2 < EMA21 (-dist pips nếu bật filter).
TP/SL neo vào candle2 (giống master_candle): SL = candle2 high/low ± buffer_k,
TP = entry ± risk × rr_ratio.
"""

from src.utils import get_pip_value


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
    h1, l1 = candle1["high"], candle1["low"]
    h2, l2, c2 = candle2["high"], candle2["low"], candle2["close"]
    dist = ema_distance_pips * pip_value if ema_distance_enabled else 0.0

    # SELL: FEG giảm
    if h2 > h1 and c2 < l1:
        if l2 > ema2 + dist:
            return "SELL"

    # BUY: FEG tăng
    if l2 < l1 and c2 > h1:
        if h2 < ema2 - dist:
            return "BUY"

    return None
