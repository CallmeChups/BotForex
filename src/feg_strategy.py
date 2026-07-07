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
    ema_filter_enabled: bool = True,
    buy_ema_side: str = "below_ema",
    sell_ema_side: str = "above_ema",
    c2_buy_upper_wick_max_pct: float | None = None,
    c2_buy_lower_wick_max_pct: float | None = None,
    c2_sell_upper_wick_max_pct: float | None = None,
    c2_sell_lower_wick_max_pct: float | None = None,
) -> str | None:
    """
    Phát hiện tín hiệu FEG từ 2 nến đã đóng + EMA21 tại close candle2.

    EMA filter (optional, per-direction):
      ema_filter_enabled: bật/tắt toàn bộ EMA check
      buy_ema_side:  "below_ema" → H2 < EMA (default) | "above_ema" → H2 > EMA
      sell_ema_side: "above_ema" → L2 > EMA (default) | "below_ema" → L2 < EMA

    Wick filter (optional, per-direction):
      c2_buy_upper_wick_max_pct: BUY — wick trên (high-close) < n% body C2. None = tắt.
      c2_buy_lower_wick_max_pct: BUY — wick dưới (open-low) < n% body C2. None = tắt.
      c2_sell_upper_wick_max_pct: SELL — wick trên (high-open) < n% body C2. None = tắt.
      c2_sell_lower_wick_max_pct: SELL — wick dưới (close-low) < n% body C2. None = tắt.
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
    ema_filter_enabled: bool = True,
    buy_ema_side: str = "below_ema",
    sell_ema_side: str = "above_ema",
    c2_buy_upper_wick_max_pct: float | None = None,
    c2_buy_lower_wick_max_pct: float | None = None,
    c2_sell_upper_wick_max_pct: float | None = None,
    c2_sell_lower_wick_max_pct: float | None = None,
) -> dict | None:
    """Dựng signal đầy đủ (entry/SL/TP) từ pattern FEG. Trả None nếu không có tín hiệu."""
    pip_value = get_pip_value(symbol)
    direction = detect_feg_signal(
        candle1, candle2, ema2, pip_value,
        h2_exceed_pips, c2_gap_pips, ema_margin_pips,
        ema_filter_enabled, buy_ema_side, sell_ema_side,
        c2_buy_upper_wick_max_pct, c2_buy_lower_wick_max_pct,
        c2_sell_upper_wick_max_pct, c2_sell_lower_wick_max_pct,
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
