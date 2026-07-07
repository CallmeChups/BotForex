"""
FEG Stop Order Strategy

Pattern 2 nến + EMA optional filter, quét liên tục.
Điều kiện chung: C1/C2 cùng hướng, body C2 > body C1.
SELL: H2>H1, C2<L1. BUY: L2<L1, C2>H1.

Entry dùng Stop Order (breakout):
  BUY:  Entry = H2 + buffer_k*pip, SL = L2
  SELL: Entry = L2 - buffer_k*pip, SL = H2
  TP = Entry ± Risk * rr_ratio

EMA filter (optional, per-direction):
  ema_filter_enabled: bật/tắt toàn bộ EMA check
  buy_ema_side:  "above_ema" → H2 > EMA | "below_ema" → H2 < EMA
  sell_ema_side: "above_ema" → L2 > EMA | "below_ema" → L2 < EMA
"""

from src.utils import get_pip_value


def detect_feg_stop_order_signal(
    candle1: dict,
    candle2: dict,
    ema2: float,
    pip_value: float,
    h2_exceed_pips: float = 0.0,
    c2_gap_pips: float = 0.0,
    ema_filter_enabled: bool = True,
    buy_ema_side: str = "below_ema",
    sell_ema_side: str = "above_ema",
    ema_margin_pips: float = 0.0,
    c2_buy_upper_wick_max_pct: float | None = None,
    c2_buy_lower_wick_max_pct: float | None = None,
    c2_sell_upper_wick_max_pct: float | None = None,
    c2_sell_lower_wick_max_pct: float | None = None,
) -> str | None:
    """
    Phát hiện tín hiệu FEG Stop Order từ 2 nến đã đóng.

    Args:
        candle1: nến đóng trước (dict open/high/low/close)
        candle2: nến vừa đóng (dict open/high/low/close)
        ema2: giá trị EMA tại close candle2
        pip_value: giá trị 1 pip của symbol
        h2_exceed_pips: H2 > H1 + N pips / L2 < L1 - N pips
        c2_gap_pips: C2 < L1 - N pips / C2 > H1 + N pips
        ema_filter_enabled: bật/tắt EMA filter
        buy_ema_side: "above_ema" | "below_ema" — điều kiện EMA cho BUY
        sell_ema_side: "above_ema" | "below_ema" — điều kiện EMA cho SELL
        ema_margin_pips: khoảng cách tối thiểu từ candle đến EMA
        c2_buy_upper_wick_max_pct:  BUY — râu trên (high-close) phải < n% body C2. None = tắt.
        c2_buy_lower_wick_max_pct:  BUY — wick dưới (open-low) < n% body C2. None = tắt.
        c2_sell_upper_wick_max_pct: SELL — wick trên (high-open) < n% body C2. None = tắt.
        c2_sell_lower_wick_max_pct: SELL — râu dưới (close-low)  phải < n% body C2. None = tắt.

    Returns:
        "BUY", "SELL", hoặc None
    """
    h1, l1, o1, c1 = candle1["high"], candle1["low"], candle1["open"], candle1["close"]
    h2, l2, o2, c2 = candle2["high"], candle2["low"], candle2["open"], candle2["close"]

    h2_exceed  = h2_exceed_pips  * pip_value
    c2_gap     = c2_gap_pips     * pip_value
    ema_margin = ema_margin_pips * pip_value

    bullish1, bullish2 = c1 > o1, c2 > o2
    body1, body2 = abs(c1 - o1), abs(c2 - o2)

    # SELL: cả 2 nến giảm, body C2 > C1, H2>H1, C2<L1
    if not bullish1 and not bullish2 and body2 > body1:
        if h2 > h1 + h2_exceed and c2 < l1 - c2_gap:
            if body2 > 0:
                if c2_sell_upper_wick_max_pct is not None and (h2 - o2) >= body2 * (c2_sell_upper_wick_max_pct / 100.0):
                    return None
                if c2_sell_lower_wick_max_pct is not None and (c2 - l2) >= body2 * (c2_sell_lower_wick_max_pct / 100.0):
                    return None
            if not ema_filter_enabled:
                return "SELL"
            if sell_ema_side == "above_ema" and l2 > ema2 + ema_margin:
                return "SELL"
            if sell_ema_side == "below_ema" and l2 < ema2 - ema_margin:
                return "SELL"

    # BUY: cả 2 nến tăng, body C2 > C1, L2<L1, C2>H1
    if bullish1 and bullish2 and body2 > body1:
        if l2 < l1 - h2_exceed and c2 > h1 + c2_gap:
            if body2 > 0:
                if c2_buy_upper_wick_max_pct is not None and (h2 - c2) >= body2 * (c2_buy_upper_wick_max_pct / 100.0):
                    return None
                if c2_buy_lower_wick_max_pct is not None and (o2 - l2) >= body2 * (c2_buy_lower_wick_max_pct / 100.0):
                    return None
            if not ema_filter_enabled:
                return "BUY"
            if buy_ema_side == "below_ema" and h2 < ema2 - ema_margin:
                return "BUY"
            if buy_ema_side == "above_ema" and h2 > ema2 + ema_margin:
                return "BUY"

    return None


def analyze_feg_stop_order(
    symbol: str,
    candle1: dict,
    candle2: dict,
    ema2: float,
    rr_ratio: float = 2.0,
    buffer_k: float = 5.0,
    lot_size: float = 0.01,
    h2_exceed_pips: float = 0.0,
    c2_gap_pips: float = 0.0,
    ema_filter_enabled: bool = True,
    buy_ema_side: str = "below_ema",
    sell_ema_side: str = "above_ema",
    ema_margin_pips: float = 0.0,
    c2_buy_upper_wick_max_pct: float | None = None,
    c2_buy_lower_wick_max_pct: float | None = None,
    c2_sell_upper_wick_max_pct: float | None = None,
    c2_sell_lower_wick_max_pct: float | None = None,
) -> dict | None:
    """
    Dựng signal đầy đủ (entry/SL/TP) từ pattern FEG Stop Order.

    BUY:  Entry = H2 + buffer_k*pip, SL = L2, TP = Entry + Risk*rr
    SELL: Entry = L2 - buffer_k*pip, SL = H2, TP = Entry - Risk*rr

    Trả None nếu không có tín hiệu.
    """
    pip_value = get_pip_value(symbol)
    direction = detect_feg_stop_order_signal(
        candle1, candle2, ema2, pip_value,
        h2_exceed_pips, c2_gap_pips,
        ema_filter_enabled, buy_ema_side, sell_ema_side, ema_margin_pips,
        c2_buy_upper_wick_max_pct, c2_buy_lower_wick_max_pct,
        c2_sell_upper_wick_max_pct, c2_sell_lower_wick_max_pct,
    )
    if direction is None:
        return None

    h2, l2 = candle2["high"], candle2["low"]
    buffer_offset = buffer_k * pip_value

    if direction == "BUY":
        entry_price = h2 + buffer_offset
        stop_loss   = l2
        risk        = entry_price - stop_loss
        take_profit = entry_price + risk * rr_ratio
    else:  # SELL
        entry_price = l2 - buffer_offset
        stop_loss   = h2
        risk        = stop_loss - entry_price
        take_profit = entry_price - risk * rr_ratio

    sl_pips = risk / pip_value

    return {
        "symbol": symbol,
        "direction": direction,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "sl_pips": sl_pips,
        "lot_size": lot_size,
        "candle1": candle1,
        "candle2": candle2,
    }
