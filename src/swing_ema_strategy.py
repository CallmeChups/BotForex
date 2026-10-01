"""
Module: swing_ema_strategy.py
Purpose: Swing structure and EMA filters for stop-order signals.
"""

from __future__ import annotations

import math
from typing import Literal, Sequence, TypedDict

import pandas as pd

from src.zigzag_swing import (
    Pivot,
    detect_confirmed_pivots,
)
from src.pivot_detectors import (
    BreakoutEvent,
    detect_fractal_breakouts,
    detect_fractal_pivots,
)


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


def _pullback_structure(
    pivots: Sequence[Pivot],
    direction: Direction,
) -> list[Pivot] | None:
    """Return the three pivots defining the latest directional pullback."""
    if direction == "BUY":
        same_side = [pivot for pivot in pivots if pivot["kind"] == "low"]
        if len(same_side) < 2:
            return None
        first_low, second_low = same_side[-2:]
        middle_high = next(
            (
                pivot
                for pivot in reversed(pivots)
                if pivot["kind"] == "high"
                and first_low["index"] < pivot["index"] < second_low["index"]
            ),
            None,
        )
        if middle_high is None:
            return None
        return [first_low, middle_high, second_low]

    same_side = [pivot for pivot in pivots if pivot["kind"] == "high"]
    if len(same_side) < 2:
        return None
    first_high, second_high = same_side[-2:]
    middle_low = next(
        (
            pivot
            for pivot in reversed(pivots)
            if pivot["kind"] == "low"
            and first_high["index"] < pivot["index"] < second_high["index"]
        ),
        None,
    )
    if middle_low is None:
        return None
    return [first_high, middle_low, second_high]


def detect_structure_bias(
    pivots: Sequence[Pivot],
    use_pivot2_for_buy: bool = True,
    use_pivot2_for_sell: bool = True,
) -> Direction | None:
    """Return directional structure bias, optionally omitting Pivot 2."""
    buy_structure = _pullback_structure(pivots, "BUY")
    sell_structure = _pullback_structure(pivots, "SELL")
    buy_second_high = (
        next(
            (
                pivot
                for pivot in reversed(pivots)
                if buy_structure is not None
                and pivot["kind"] == "high"
                and pivot["index"] > buy_structure[2]["index"]
            ),
            None,
        )
        if use_pivot2_for_buy
        else None
    )
    sell_second_low = (
        next(
            (
                pivot
                for pivot in reversed(pivots)
                if sell_structure is not None
                and pivot["kind"] == "low"
                and pivot["index"] > sell_structure[2]["index"]
            ),
            None,
        )
        if use_pivot2_for_sell
        else None
    )
    buy_valid = (
        buy_structure is not None
        and buy_structure[2]["price"] > buy_structure[0]["price"]
        and (
            not use_pivot2_for_buy
            or (
                buy_second_high is not None
                and buy_second_high["price"] > buy_structure[1]["price"]
            )
        )
    )
    sell_valid = (
        sell_structure is not None
        and sell_structure[2]["price"] < sell_structure[0]["price"]
        and (
            not use_pivot2_for_sell
            or (
                sell_second_low is not None
                and sell_second_low["price"] < sell_structure[1]["price"]
            )
        )
    )
    if buy_valid == sell_valid:
        return None
    return "BUY" if buy_valid else "SELL"


def calculate_ema_series(close_values, period: int, adjust: bool = False) -> list[float]:
    """Calculate a pandas-compatible EMA series."""
    if period <= 0:
        raise ValueError("period must be positive")
    values = _coerce_close_values(close_values)
    if not values:
        return []
    if not adjust:
        if not math.isfinite(values[0]):
            series = pd.Series(values, dtype=float)
            return series.ewm(span=period, adjust=adjust).mean().tolist()
        alpha = 2.0 / (period + 1.0)
        decay = 1.0 - alpha
        result = [values[0]]
        for value in values[1:]:
            if not math.isfinite(value):
                series = pd.Series(values, dtype=float)
                return series.ewm(span=period, adjust=adjust).mean().tolist()
            result.append(alpha * value + decay * result[-1])
        return result
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


def passes_swing_ema_fallback(
    direction: Direction,
    ema_values: dict[str, float],
    signal_candle: dict[str, float],
) -> bool:
    """Apply Multi Flappy's fallback EMA order and signal-candle cross rule."""
    fast = float(ema_values["fast"])
    medium = float(ema_values["medium"])
    slow = float(ema_values["slow"])
    candle_open = float(signal_candle["open"])
    candle_close = float(signal_candle["close"])
    if direction == "BUY":
        return fast > medium and fast < slow and candle_open < slow < candle_close
    return fast < medium and fast > slow and candle_open > slow > candle_close


def passes_swing_ema_filters(
    direction: Direction,
    consensus_values: dict[str, float],
    fallback_values: dict[str, float],
    signal_candle: dict[str, float] | None,
    consensus_enabled: bool,
    fallback_enabled: bool,
    consensus_cross_valid: bool,
) -> bool:
    """Accept either enabled EMA route; no enabled routes means no EMA filtering."""
    if not consensus_enabled and not fallback_enabled:
        return True
    consensus_passes = (
        consensus_enabled
        and passes_ema_consensus(direction, consensus_values)
        and consensus_cross_valid
    )
    fallback_passes = (
        fallback_enabled
        and signal_candle is not None
        and passes_swing_ema_fallback(direction, fallback_values, signal_candle)
    )
    return consensus_passes or fallback_passes


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
    """Build a pivot stop entry and provisional signal-time SL/TP estimates."""
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


def calculate_swing_exit_levels(
    direction: Direction,
    entry_price: float,
    previous_candle: dict,
    buffer_price: float,
    rr_ratio: float,
) -> dict[str, float]:
    """Calculate SL/TP from the last closed candle before a stop-order fill."""
    if buffer_price < 0:
        raise ValueError("buffer_price cannot be negative")
    if rr_ratio <= 0:
        raise ValueError("rr_ratio must be positive")

    if direction == "BUY":
        stop_loss = float(previous_candle["low"]) - buffer_price
        risk = entry_price - stop_loss
        take_profit = entry_price + risk * rr_ratio
    else:
        stop_loss = float(previous_candle["high"]) + buffer_price
        risk = stop_loss - entry_price
        take_profit = entry_price - risk * rr_ratio

    if risk <= 0:
        raise ValueError("previous closed candle stop must leave positive risk")

    return {
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_price": risk,
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
    fallback_ema_periods: dict[str, int] | None = None,
    ema_consensus_enabled: bool = True,
    ema_fallback_enabled: bool = False,
    use_pivot2_for_buy: bool = True,
    use_pivot2_for_sell: bool = True,
    signal_candle: dict[str, float] | None = None,
) -> dict | None:
    """Build a signal only when structure and EMA filters align."""
    direction = detect_structure_bias(
        pivots,
        use_pivot2_for_buy=use_pivot2_for_buy,
        use_pivot2_for_sell=use_pivot2_for_sell,
    )
    if direction is None:
        return None

    try:
        ema_snapshot = (
            calculate_ema_snapshot(close_values, ema_periods)
            if ema_consensus_enabled
            else {}
        )
    except ValueError:
        return None
    cross = None
    if ema_consensus_enabled:
        cross = find_latest_ema_cross(
            close_values,
            fast_period=cross_fast_period,
            slow_period=cross_slow_period,
        )
    consensus_cross_valid = (
        cross is not None
        and cross["direction"] == direction
        and cross["bars_since_cross"] <= cross_window
    )
    fallback_snapshot = (
        calculate_ema_snapshot(close_values, fallback_ema_periods or ema_periods)
        if ema_fallback_enabled
        else {}
    )
    pullback = _pullback_structure(pivots, direction)
    if pullback is None:
        return None
    pivot1, middle_pivot, pivot2 = pullback
    use_pivot2 = use_pivot2_for_buy if direction == "BUY" else use_pivot2_for_sell
    entry_pivot = (
        _latest_pivot(pivots, "high" if direction == "BUY" else "low")
        if use_pivot2
        else middle_pivot
    )
    if entry_pivot is None:
        return None

    pivot_ema_snapshot = {}
    consensus_pivot_valid = True
    if use_pivot2 and ema_consensus_enabled:
        pivot_close_values = _coerce_close_values(close_values)
        pivot_index = entry_pivot["index"]
        if pivot_index >= len(pivot_close_values):
            consensus_pivot_valid = False
        else:
            for slot, period in (
                ema_periods or {"fast": 13, "medium": 21, "slow": 55}
            ).items():
                series = calculate_ema_series(
                    pivot_close_values[: pivot_index + 1],
                    int(period),
                )
                pivot_ema_snapshot[slot] = series[-1]
            pivot_price = entry_pivot["price"]
            consensus_pivot_valid = (
                all(pivot_price > value for value in pivot_ema_snapshot.values())
                if direction == "BUY"
                else all(pivot_price < value for value in pivot_ema_snapshot.values())
            )

    if not passes_swing_ema_filters(
        direction,
        ema_snapshot,
        fallback_snapshot,
        signal_candle,
        ema_consensus_enabled,
        ema_fallback_enabled,
        consensus_cross_valid and consensus_pivot_valid,
    ):
        return None

    swing_high = entry_pivot if direction == "BUY" else middle_pivot
    swing_low = middle_pivot if direction == "BUY" else entry_pivot
    if direction == "BUY":
        swing_low = pivot2
    else:
        swing_high = pivot2

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
    signal["ema_snapshot"] = ema_snapshot
    signal["fallback_ema_snapshot"] = fallback_snapshot
    signal["pivot_ema_snapshot"] = pivot_ema_snapshot
    signal["ema_cross"] = cross or {}
    signal["structure"] = annotate_structure(pivots)
    signal["pullback_structure"] = pullback
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


def _bar_identity(data, index: int) -> str:
    if "time" not in data:
        return f"index:{index}"
    value = data["time"].iloc[index]
    if hasattr(value, "timestamp"):
        return str(int(value.timestamp()))
    return str(int(value))


def get_swing_setup_pivots(signal: dict) -> list[dict]:
    """Return labeled setup pivots, deriving them for signals without metadata."""
    setup_pivots = signal.get("setup_pivots")
    if setup_pivots:
        return list(setup_pivots)

    direction = signal.get("direction")
    structure = signal.get("structure")
    if direction not in {"BUY", "SELL"} or not isinstance(structure, list):
        return []

    side_kind = "low" if direction == "BUY" else "high"
    middle_kind = "high" if direction == "BUY" else "low"
    side_pivots = [
        pivot for pivot in structure
        if isinstance(pivot, dict) and pivot.get("kind") == side_kind
    ]
    if len(side_pivots) < 2:
        return []

    first, second = side_pivots[-2:]
    middle = next(
        (
            pivot for pivot in reversed(structure)
            if isinstance(pivot, dict)
            and pivot.get("kind") == middle_kind
            and first["index"] < pivot["index"] < second["index"]
        ),
        None,
    )
    if middle is None:
        return []

    if direction == "BUY":
        labels = [("Đáy 1", first), ("Đỉnh 1", middle), ("Đáy 2", second)]
        entry_index = signal.get("swing_high_index")
        entry_label = "Đỉnh 2"
    else:
        labels = [("Đỉnh 1", first), ("Đáy 1", middle), ("Đỉnh 2", second)]
        entry_index = signal.get("swing_low_index")
        entry_label = "Đáy 2"

    entry_pivot = next(
        (
            pivot for pivot in structure
            if isinstance(pivot, dict) and pivot.get("index") == entry_index
        ),
        None,
    )
    if entry_pivot is not None and entry_pivot["index"] != middle["index"]:
        labels.append((entry_label, entry_pivot))

    return [
        {
            "label": label,
            "index": int(pivot["index"]),
            "kind": pivot["kind"],
            "price": float(pivot["price"]),
            "confirmed_index": int(pivot.get("confirmed_index", pivot["index"])),
        }
        for label, pivot in labels
    ]


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
    pivot_candidates: Sequence[Pivot] | None = None,
    data_index_offset: int = 0,
    use_pivot2_for_buy: bool = True,
    use_pivot2_for_sell: bool = True,
    ema_consensus_enabled: bool = True,
    ema_fallback_enabled: bool = False,
    fallback_ema_periods: dict[str, int] | None = None,
    min_pivot_distance_candles: int = 5,
    max_pivot_distance_candles: int = 15,
    pivot_detector: str = "zigzag",
    fractal_strength: int = 2,
    breakout_enabled: bool = True,
    breakout_by_close: bool = False,
    breakout_candidates: Sequence[BreakoutEvent] | None = None,
) -> dict | None:
    """Create a buffered stop-entry signal from confirmed pivots and EMA filters."""
    if len(data) == 0:
        return None
    if pivot_detector == "swing_trend_line_td":
        pivots = detect_fractal_pivots(
            data,
            strength=fractal_strength,
            candidate_pivots=pivot_candidates,
            index_offset=data_index_offset,
        )
    elif pivot_detector == "zigzag":
        pivots = detect_confirmed_pivots(
            data,
            point_size=symbol_point_size,
            depth=zigzag_depth,
            deviation_points=zigzag_deviation_points,
            back_step=zigzag_back_step,
            candidate_pivots=pivot_candidates,
            index_offset=data_index_offset,
        )
    else:
        raise ValueError(f"Unsupported pivot detector: {pivot_detector}")
    if len(pivots) < 3:
        return None
    if min_pivot_distance_candles <= 0:
        raise ValueError("Minimum pivot distance must be positive")
    if max_pivot_distance_candles < min_pivot_distance_candles:
        raise ValueError("Maximum pivot distance must be >= minimum")

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
        fallback_ema_periods=fallback_ema_periods,
        ema_consensus_enabled=ema_consensus_enabled,
        ema_fallback_enabled=ema_fallback_enabled,
        use_pivot2_for_buy=use_pivot2_for_buy,
        use_pivot2_for_sell=use_pivot2_for_sell,
        signal_candle=(
            {
                "open": float(data["open"].iloc[-1]),
                "close": float(data["close"].iloc[-1]),
            }
            if ema_fallback_enabled
            else None
        ),
    )
    if base_signal is None:
        return None

    breakout_event = None
    if pivot_detector == "swing_trend_line_td":
        if breakout_candidates is None:
            local_breakouts = detect_fractal_breakouts(
                data,
                pivots,
                breakout_by_close=breakout_by_close,
            )
            current_index = len(data) - 1
            breakout_event = next(
                (
                    event for event in local_breakouts
                    if event["index"] == current_index
                ),
                None,
            )
        else:
            current_index = len(data) - 1 + data_index_offset
            breakout_event = next(
                (
                    event for event in breakout_candidates
                    if int(event["index"]) == current_index
                ),
                None,
            )
        if breakout_enabled and breakout_event is None:
            return None
        if (
            breakout_enabled
            and breakout_event is not None
            and breakout_event["direction"] != base_signal["direction"]
        ):
            return None

    pullback_structure = base_signal.get("pullback_structure")
    if pullback_structure is None:
        return None
    structure_pivots = pullback_structure
    pivot_distance = (
        int(pullback_structure[2]["index"])
        - int(pullback_structure[0]["index"])
    )
    if not (
        min_pivot_distance_candles
        <= pivot_distance
        <= max_pivot_distance_candles
    ):
        return None
    use_pivot2 = (
        use_pivot2_for_buy
        if base_signal["direction"] == "BUY"
        else use_pivot2_for_sell
    )
    entry_pivot = (
        _latest_pivot(
            base_signal["structure"],
            "high" if base_signal["direction"] == "BUY" else "low",
        )
        if use_pivot2
        else pullback_structure[1]
    )
    if entry_pivot is None:
        return None
    if use_pivot2:
        structure_pivots = [*structure_pivots, entry_pivot]
    structure_span = (
        max(pivot["index"] for pivot in structure_pivots)
        - min(pivot["index"] for pivot in structure_pivots)
    )
    if (
        structure_span is None
        or structure_span < min_structure_candles
        or structure_span > max_structure_candles
    ):
        return None

    pivot_map = {pivot["index"]: pivot for pivot in pivots}
    swing_high = (
        pivot_map.get(entry_pivot["index"])
        if base_signal["direction"] == "BUY"
        else pivot_map.get(pullback_structure[1]["index"])
    )
    swing_low = (
        pivot_map.get(pullback_structure[2]["index"])
        if base_signal["direction"] == "BUY"
        else pivot_map.get(entry_pivot["index"])
    )
    if swing_high is None or swing_low is None:
        return None

    if base_signal["direction"] == "BUY":
        setup_pivots = [
            ("Đáy 1", pullback_structure[0]),
            ("Đỉnh 1", pullback_structure[1]),
            ("Đáy 2", pullback_structure[2]),
        ]
        if use_pivot2:
            setup_pivots.append(("Đỉnh 2", entry_pivot))
    else:
        setup_pivots = [
            ("Đỉnh 1", pullback_structure[0]),
            ("Đáy 1", pullback_structure[1]),
            ("Đỉnh 2", pullback_structure[2]),
        ]
        if use_pivot2:
            setup_pivots.append(("Đáy 2", entry_pivot))

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
            "swing_high_index": int(swing_high["index"]),
            "swing_low_index": int(swing_low["index"]),
            "swing_high_time": _bar_identity(data, int(swing_high["index"])),
            "swing_low_time": _bar_identity(data, int(swing_low["index"])),
            "setup_pivots": [
                {
                    "label": label,
                    "index": int(pivot["index"]),
                    "kind": pivot["kind"],
                    "price": float(pivot["price"]),
                    "confirmed_index": int(pivot["confirmed_index"]),
                }
                for label, pivot in setup_pivots
            ],
            "pivot_detector": pivot_detector,
            "breakout_event": breakout_event,
        }
    )
    structure_identity = ":".join(
        f"{pivot['kind']}:{_bar_identity(data, int(pivot['index']))}"
        for pivot in pullback_structure
    )
    signal["setup_id"] = f"{signal['direction']}:{structure_identity}"

    if data_index_offset:
        # Pivot/structure indices above are local to the rolling `data`
        # window passed in; shift them back to absolute indices so callers
        # (e.g. the chart) can look them up against the full dataset.
        def _shift_pivot(pivot: dict) -> dict:
            shifted = dict(pivot)
            shifted["index"] = int(pivot["index"]) + data_index_offset
            if "confirmed_index" in pivot:
                shifted["confirmed_index"] = (
                    int(pivot["confirmed_index"]) + data_index_offset
                )
            return shifted

        signal["structure"] = [_shift_pivot(p) for p in signal["structure"]]
        signal["setup_pivots"] = [_shift_pivot(p) for p in signal["setup_pivots"]]
        signal["swing_high_index"] += data_index_offset
        signal["swing_low_index"] += data_index_offset
        if signal.get("breakout_event") is not None and breakout_candidates is None:
            signal["breakout_event"] = {
                **signal["breakout_event"],
                "index": (
                    int(signal["breakout_event"]["index"]) + data_index_offset
                ),
            }
    last_time = data["time"].iloc[-1] if "time" in data else None
    if last_time is not None:
        signal["signal_candle_time"] = (
            int(last_time.timestamp())
            if hasattr(last_time, "timestamp")
            else int(last_time)
        )
        signal["signal_candle_index"] = len(data) - 1 + data_index_offset
    return signal
