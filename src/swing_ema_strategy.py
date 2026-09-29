"""
Module: swing_ema_strategy.py
Purpose: Swing structure and EMA filters for stop-order signals.
"""

from __future__ import annotations

from typing import Literal, Sequence, TypedDict

import pandas as pd

from src.zigzag_swing import Pivot, detect_confirmed_pivots


Direction = Literal["BUY", "SELL"]
StructureLabel = Literal["HH", "HL", "LH", "LL"]


class StructuredPivot(Pivot, total=False):
    """Pivot enriched with same-side structure label."""

    structure_label: StructureLabel | None


class EmaCross(TypedDict):
    """Latest EMA cross metadata."""

    direction: Direction
    cross_index: int
    bars_since_cross: int


def _coerce_close_values(close_values) -> list[float]:
    """Return close values from a pandas-compatible input."""
    if hasattr(close_values, "columns") and "close" in close_values:
        values = close_values["close"]
    else:
        values = close_values
    if hasattr(values, "tolist"):
        raw_values = values.tolist()
    else:
        raw_values = list(values)
    return [float(value) for value in raw_values]


def _latest_pivot(pivots: Sequence[Pivot], kind: str) -> Pivot | None:
    for pivot in reversed(pivots):
        if pivot["kind"] == kind:
            return pivot
    return None


def annotate_structure(pivots: Sequence[Pivot]) -> list[StructuredPivot]:
    """Label each pivot against the previous pivot of the same side."""
    previous_high: Pivot | None = None
    previous_low: Pivot | None = None
    structured: list[StructuredPivot] = []

    for pivot in pivots:
        label: StructureLabel | None = None
        if pivot["kind"] == "high":
            if previous_high is not None:
                if pivot["price"] > previous_high["price"]:
                    label = "HH"
                elif pivot["price"] < previous_high["price"]:
                    label = "LH"
            previous_high = pivot
        else:
            if previous_low is not None:
                if pivot["price"] > previous_low["price"]:
                    label = "HL"
                elif pivot["price"] < previous_low["price"]:
                    label = "LL"
            previous_low = pivot

        structured.append(
            {
                "index": pivot["index"],
                "kind": pivot["kind"],
                "price": pivot["price"],
                "confirmed_index": pivot["confirmed_index"],
                "structure_label": label,
            }
        )

    return structured


def detect_structure_bias(pivots: Sequence[Pivot]) -> Direction | None:
    """Return BUY for HH+HL, SELL for LH+LL, else None."""
    structured = annotate_structure(pivots)
    latest_high = next(
        (pivot for pivot in reversed(structured) if pivot["kind"] == "high"),
        None,
    )
    latest_low = next(
        (pivot for pivot in reversed(structured) if pivot["kind"] == "low"),
        None,
    )
    latest_high_label = None if latest_high is None else latest_high.get("structure_label")
    latest_low_label = None if latest_low is None else latest_low.get("structure_label")
    if latest_high_label == "HH" and latest_low_label == "HL":
        return "BUY"
    if latest_high_label == "LH" and latest_low_label == "LL":
        return "SELL"
    return None


def calculate_ema_series(close_values, period: int, adjust: bool = False) -> list[float]:
    """Calculate a pandas-compatible EMA series."""
    if period <= 0:
        raise ValueError("period must be positive")
    values = _coerce_close_values(close_values)
    if not values:
        return []
    series = pd.Series(values, dtype=float)
    return series.ewm(span=period, adjust=adjust).mean().tolist()


def calculate_ema_snapshot(
    close_values,
    periods: dict[str, int] | None = None,
) -> dict[str, float]:
    """Return latest EMA values for fast/medium/slow periods."""
    periods = periods or {"fast": 13, "medium": 21, "slow": 55}
    values = _coerce_close_values(close_values)
    if not values:
        raise ValueError("close_values cannot be empty")
    snapshot: dict[str, float] = {}
    for slot in ("fast", "medium", "slow"):
        if slot not in periods:
            raise ValueError(f"missing EMA period: {slot}")
        series = calculate_ema_series(values, int(periods[slot]))
        snapshot[slot] = series[-1]
    return snapshot


def build_swing_chart_overlays(
    data,
    symbol_point_size: float,
    ema_periods: dict[str, int],
    zigzag_depth: int,
    zigzag_deviation_points: float,
    zigzag_back_step: int,
) -> tuple[dict[str, list[float]], list[Pivot]]:
    """Calculate the configured EMA lines and confirmed ZigZag pivots for charts."""
    if len(data) == 0:
        return ({slot: [] for slot in ("fast", "medium", "slow")}, [])

    close_values = data["close"]
    ema_values = {
        slot: calculate_ema_series(close_values, int(ema_periods[slot]))
        for slot in ("fast", "medium", "slow")
    }
    pivots = detect_confirmed_pivots(
        data,
        point_size=symbol_point_size,
        depth=zigzag_depth,
        deviation_points=zigzag_deviation_points,
        back_step=zigzag_back_step,
    )
    return ema_values, pivots


def passes_ema_consensus(direction: Direction, ema_values: dict[str, float]) -> bool:
    """Validate aligned EMA order for the requested direction."""
    fast = float(ema_values["fast"])
    medium = float(ema_values["medium"])
    slow = float(ema_values["slow"])
    if direction == "BUY":
        return fast > medium > slow
    return fast < medium < slow


def find_latest_ema_cross(
    close_values,
    fast_period: int = 13,
    slow_period: int = 21,
) -> EmaCross | None:
    """Return latest fast/slow EMA cross metadata."""
    fast_values = calculate_ema_series(close_values, fast_period)
    slow_values = calculate_ema_series(close_values, slow_period)
    if len(fast_values) != len(slow_values):
        raise ValueError("EMA series length mismatch")

    latest_cross: EmaCross | None = None
    last_index = len(fast_values) - 1
    previous_relation = 0
    for index in range(1, len(fast_values)):
        fast = fast_values[index]
        slow = slow_values[index]
        current_relation = 1 if fast > slow else -1 if fast < slow else 0
        if previous_relation == -1 and current_relation == 1:
            latest_cross = {
                "direction": "BUY",
                "cross_index": index,
                "bars_since_cross": last_index - index,
            }
        elif previous_relation == 1 and current_relation == -1:
            latest_cross = {
                "direction": "SELL",
                "cross_index": index,
                "bars_since_cross": last_index - index,
            }
        if current_relation != 0:
            previous_relation = current_relation
    return latest_cross


def passes_ema_cross_window(
    direction: Direction,
    close_values,
    fast_period: int = 13,
    slow_period: int = 21,
    window: int = 3,
) -> bool:
    """Require a matching EMA cross within the latest `window` bars."""
    if window < 0:
        raise ValueError("window cannot be negative")
    cross = find_latest_ema_cross(close_values, fast_period, slow_period)
    if cross is None:
        return False
    return cross["direction"] == direction and cross["bars_since_cross"] <= window


def build_stop_order_signal(
    direction: Direction,
    swing_high: Pivot,
    swing_low: Pivot,
    point_size: float,
    buffer_price: float = 0.0,
    rr_ratio: float = 2.0,
    expiry_bars: int = 3,
    created_bar_index: int | None = None,
    activation_previous_low: float | None = None,
    activation_previous_high: float | None = None,
    entry_buffer_price: float = 0.0,
) -> dict:
    """Build exact pivot stop levels and deferred activation-candle SL metadata."""
    if point_size <= 0:
        raise ValueError("point_size must be positive")
    if expiry_bars <= 0:
        raise ValueError("expiry_bars must be positive")
    if rr_ratio <= 0:
        raise ValueError("rr_ratio must be positive")

    if buffer_price < 0:
        raise ValueError("buffer_price cannot be negative")
    if entry_buffer_price < 0:
        raise ValueError("entry_buffer_price cannot be negative")
    if direction == "BUY":
        pivot_level = float(swing_high["price"])
        trigger_level = pivot_level + entry_buffer_price
        entry_price = trigger_level
        stop_loss = (
            None
            if activation_previous_low is None
            else float(activation_previous_low) - buffer_price
        )
        order_type = "BUY_STOP"
    else:
        pivot_level = float(swing_low["price"])
        trigger_level = pivot_level - entry_buffer_price
        entry_price = trigger_level
        stop_loss = (
            None
            if activation_previous_high is None
            else float(activation_previous_high) + buffer_price
        )
        order_type = "SELL_STOP"

    risk = None
    take_profit = None
    if stop_loss is not None:
        risk = (
            entry_price - stop_loss
            if direction == "BUY"
            else stop_loss - entry_price
        )
        if risk <= 0:
            raise ValueError("activation candle stop must leave positive risk")
        take_profit = (
            entry_price + risk * rr_ratio
            if direction == "BUY"
            else entry_price - risk * rr_ratio
        )

    return {
        "direction": direction,
        "order_type": order_type,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_price": risk,
        "risk_points": None if risk is None else risk / point_size,
        "pivot_level": pivot_level,
        "trigger_level": trigger_level,
        "buffer_price": buffer_price,
        "entry_buffer_price": entry_buffer_price,
        "expiry_bars": expiry_bars,
        "created_bar_index": created_bar_index,
        "expires_at_bar": (
            None if created_bar_index is None else created_bar_index + expiry_bars
        ),
        "swing_high_index": swing_high["index"],
        "swing_low_index": swing_low["index"],
        "activation_previous_low": activation_previous_low,
        "activation_previous_high": activation_previous_high,
    }


def is_pending_signal_expired(signal: dict, current_bar_index: int) -> bool:
    """Return True when current_bar_index passed the expiry bar."""
    expires_at_bar = signal.get("expires_at_bar")
    if expires_at_bar is None:
        return False
    return current_bar_index > int(expires_at_bar)


def evaluate_ema_exit(
    direction: Direction,
    candle: dict,
    ema_value: float,
    use_close: bool = True,
) -> dict[str, object]:
    """Check whether price crossed the exit EMA."""
    price = float(candle["close"] if use_close else candle["open"])
    if direction == "BUY":
        exit_now = price < ema_value
    else:
        exit_now = price > ema_value
    return {
        "exit": exit_now,
        "reason": "ema_exit" if exit_now else None,
        "price": price,
        "ema_value": float(ema_value),
    }


def evaluate_swing_ema_signal(
    pivots: Sequence[Pivot],
    close_values,
    point_size: float,
    ema_periods: dict[str, int] | None = None,
    cross_fast_period: int = 13,
    cross_slow_period: int = 21,
    cross_window: int = 3,
    buffer_price: float = 0.0,
    rr_ratio: float = 2.0,
    expiry_bars: int = 7,
    created_bar_index: int | None = None,
    entry_buffer_price: float = 0.0,
) -> dict | None:
    """Build a signal only when structure and EMA filters align."""
    direction = detect_structure_bias(pivots)
    if direction is None:
        return None

    try:
        ema_snapshot = calculate_ema_snapshot(close_values, ema_periods)
    except ValueError:
        return None
    if not passes_ema_consensus(direction, ema_snapshot):
        return None

    if not passes_ema_cross_window(
        direction,
        close_values,
        fast_period=cross_fast_period,
        slow_period=cross_slow_period,
        window=cross_window,
    ):
        return None

    swing_high = _latest_pivot(pivots, "high")
    swing_low = _latest_pivot(pivots, "low")
    if swing_high is None or swing_low is None:
        return None

    swing_high = _latest_pivot(pivots, "high")
    swing_low = _latest_pivot(pivots, "low")
    if swing_high is None or swing_low is None:
        return None

    signal = build_stop_order_signal(
        direction=direction,
        swing_high=swing_high,
        swing_low=swing_low,
        point_size=point_size,
        buffer_price=buffer_price,
        entry_buffer_price=entry_buffer_price,
        rr_ratio=rr_ratio,
        expiry_bars=expiry_bars,
        created_bar_index=created_bar_index,
    )
    pivot_close_values = _coerce_close_values(close_values)
    pivot_index = swing_high["index"] if direction == "BUY" else swing_low["index"]
    if pivot_index >= len(pivot_close_values):
        return None
    pivot_ema_snapshot = {}
    for slot, period in (ema_periods or {"fast": 13, "medium": 21, "slow": 55}).items():
        series = calculate_ema_series(pivot_close_values[: pivot_index + 1], int(period))
        pivot_ema_snapshot[slot] = series[-1]
    pivot_price = swing_high["price"] if direction == "BUY" else swing_low["price"]
    if direction == "BUY" and not all(pivot_price > value for value in pivot_ema_snapshot.values()):
        return None
    if direction == "SELL" and not all(pivot_price < value for value in pivot_ema_snapshot.values()):
        return None
    signal["ema_snapshot"] = ema_snapshot
    signal["pivot_ema_snapshot"] = pivot_ema_snapshot
    signal["ema_cross"] = find_latest_ema_cross(
        close_values,
        fast_period=cross_fast_period,
        slow_period=cross_slow_period,
    )
    signal["structure"] = annotate_structure(pivots)
    return signal


def latest_structure_span(structured_pivots: Sequence[StructuredPivot]) -> int | None:
    """Return the candle span across the latest two highs and lows."""
    high_indices = [
        pivot["index"] for pivot in structured_pivots if pivot["kind"] == "high"
    ][-2:]
    low_indices = [
        pivot["index"] for pivot in structured_pivots if pivot["kind"] == "low"
    ][-2:]
    if len(high_indices) < 2 or len(low_indices) < 2:
        return None
    indices = high_indices + low_indices
    return max(indices) - min(indices)


def build_swing_ema_entry_signal(
    data,
    symbol_point_size: float,
    ema_periods: dict[str, int],
    zigzag_depth: int,
    zigzag_deviation_points: float,
    zigzag_back_step: int,
    min_structure_candles: int,
    max_structure_candles: int,
    ema_cross_window_candles: int,
    rr_ratio: float,
    pending_expiry_candles: int,
    sl_buffer_price: float,
    entry_buffer_price: float = 0.0,
) -> dict | None:
    """Create a buffered stop-entry signal from confirmed pivots and EMA filters."""
    if len(data) == 0:
        return None
    pivots = detect_confirmed_pivots(
        data,
        point_size=symbol_point_size,
        depth=zigzag_depth,
        deviation_points=zigzag_deviation_points,
        back_step=zigzag_back_step,
    )
    if len(pivots) < 4:
        return None

    base_signal = evaluate_swing_ema_signal(
        pivots=pivots,
        close_values=data["close"],
        point_size=symbol_point_size,
        ema_periods=ema_periods,
        cross_fast_period=ema_periods["fast"],
        cross_slow_period=ema_periods["medium"],
        cross_window=ema_cross_window_candles,
        rr_ratio=rr_ratio,
        expiry_bars=pending_expiry_candles,
        created_bar_index=len(data) - 1,
        entry_buffer_price=entry_buffer_price,
    )
    if base_signal is None:
        return None

    structure_span = latest_structure_span(base_signal["structure"])
    if (
        structure_span is None
        or structure_span < min_structure_candles
        or structure_span > max_structure_candles
    ):
        return None

    pivot_map = {pivot["index"]: pivot for pivot in pivots}
    swing_high = pivot_map.get(base_signal["swing_high_index"])
    swing_low = pivot_map.get(base_signal["swing_low_index"])
    if swing_high is None or swing_low is None:
        return None

    latest_high = float(data["high"].iloc[-1])
    latest_low = float(data["low"].iloc[-1])
    if base_signal["direction"] == "BUY":
        entry_price = float(swing_high["price"]) + entry_buffer_price
        if latest_high >= entry_price:
            return None
        activation_stop = latest_low - sl_buffer_price
        if activation_stop >= entry_price:
            return None
    else:
        entry_price = float(swing_low["price"]) - entry_buffer_price
        if latest_low <= entry_price:
            return None
        activation_stop = latest_high + sl_buffer_price
        if activation_stop <= entry_price:
            return None

    signal = build_stop_order_signal(
        direction=base_signal["direction"],
        swing_high=swing_high,
        swing_low=swing_low,
        point_size=symbol_point_size,
        buffer_price=sl_buffer_price,
        entry_buffer_price=entry_buffer_price,
        rr_ratio=rr_ratio,
        expiry_bars=pending_expiry_candles,
        created_bar_index=len(data) - 1,
        activation_previous_low=float(data["low"].iloc[-1]),
        activation_previous_high=float(data["high"].iloc[-1]),
    )
    signal.update(
        {
            "ema_snapshot": base_signal["ema_snapshot"],
            "pivot_ema_snapshot": base_signal["pivot_ema_snapshot"],
            "ema_cross": base_signal["ema_cross"],
            "structure": base_signal["structure"],
            "structure_span": structure_span,
            "pivot_high_price": float(swing_high["price"]),
            "pivot_low_price": float(swing_low["price"]),
        }
    )
    last_time = data["time"].iloc[-1] if "time" in data else None
    if last_time is not None:
        signal["signal_candle_time"] = (
            int(last_time.timestamp())
            if hasattr(last_time, "timestamp")
            else int(last_time)
        )
    return signal
