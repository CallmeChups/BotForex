"""Pivot detector implementations used by the Swing EMA strategy."""

from __future__ import annotations

from typing import TypedDict

from src.zigzag_swing import Pivot


class SwingLine(TypedDict):
    """A rendered segment between two same-side fractals."""

    kind: str
    start_index: int
    start_price: float
    end_index: int
    end_price: float


class BreakoutEvent(TypedDict):
    """A confirmed break of the latest confirmed fractal level."""

    direction: str
    index: int
    pivot_index: int
    price: float
    confirmed_index: int


def _values(data, column: str) -> list[float]:
    values = data[column]
    raw_values = values.tolist() if hasattr(values, "tolist") else list(values)
    return [float(value) for value in raw_values]


def _fractal_at(
    highs: list[float],
    lows: list[float],
    index: int,
    strength: int,
) -> tuple[bool, bool]:
    high = highs[index]
    low = lows[index]
    is_high = all(
        high > highs[index - offset] and high >= highs[index + offset]
        for offset in range(1, strength + 1)
    )
    is_low = all(
        low < lows[index - offset] and low <= lows[index + offset]
        for offset in range(1, strength + 1)
    )
    return is_high, is_low


def _collect_fractal_pivots(
    highs: list[float],
    lows: list[float],
    strength: int,
) -> list[Pivot]:
    pivots: list[Pivot] = []
    for index in range(strength, len(highs) - strength):
        is_high, is_low = _fractal_at(highs, lows, index, strength)
        if is_high:
            pivots.append({
                "index": index,
                "kind": "high",
                "price": highs[index],
                "confirmed_index": index + strength,
            })
        if is_low:
            pivots.append({
                "index": index,
                "kind": "low",
                "price": lows[index],
                "confirmed_index": index + strength,
            })
    return pivots


def detect_fractal_pivots(
    data,
    strength: int = 2,
    candidate_pivots: list[Pivot] | None = None,
    index_offset: int = 0,
) -> list[Pivot]:
    """Return non-repainting fractal pivots in local data coordinates."""
    if strength <= 0:
        raise ValueError("Fractal strength must be positive")

    if candidate_pivots is None:
        pivots = _collect_fractal_pivots(
            _values(data, "high"),
            _values(data, "low"),
            strength,
        )
    else:
        first_index = index_offset + strength
        last_index = index_offset + len(data) - strength
        pivots = [
            {
                **pivot,
                "index": int(pivot["index"]) - index_offset,
                "confirmed_index": int(pivot["confirmed_index"]) - index_offset,
            }
            for pivot in candidate_pivots
            if first_index <= int(pivot["index"]) < last_index
        ]
    return sorted(pivots, key=lambda pivot: (pivot["index"], pivot["kind"]))


def precompute_fractal_pivots(data, strength: int = 2) -> list[Pivot]:
    """Precompute global fractal candidates for rolling backtest windows."""
    if strength <= 0:
        raise ValueError("Fractal strength must be positive")
    highs = _values(data, "high")
    lows = _values(data, "low")
    if len(highs) != len(lows):
        raise ValueError("high and low series must have the same length")
    if len(highs) < (strength * 2) + 1:
        return []
    return _collect_fractal_pivots(highs, lows, strength)


def _line_end_at_cross(
    data,
    kind: str,
    start_index: int,
    end_index: int,
    level: float,
) -> int:
    """Return the first bar that crosses a reset SwingTrend level."""
    if data is None:
        return end_index
    values = _values(data, "high" if kind == "high" else "low")
    upper = min(int(end_index), len(values) - 1)
    for index in range(int(start_index) + 1, upper + 1):
        if (
            kind == "high" and values[index] > level
        ) or (
            kind == "low" and values[index] < level
        ):
            return index
    return upper


def build_swing_trend_lines(
    pivots: list[Pivot],
    data=None,
) -> list[SwingLine]:
    """Build diagonal chains and horizontal reset segments from fractals."""
    lines: list[SwingLine] = []
    sorted_pivots = sorted(pivots, key=lambda item: item["index"])
    for kind in ("high", "low"):
        same_kind = [pivot for pivot in sorted_pivots if pivot["kind"] == kind]
        previous: Pivot | None = None
        chain_length = 0
        for position, pivot in enumerate(same_kind):
            if previous is None:
                chain_length = 1
            else:
                continues = (
                    pivot["price"] < previous["price"]
                    if kind == "high"
                    else pivot["price"] > previous["price"]
                )
                if continues:
                    lines.append({
                        "kind": kind,
                        "start_index": int(previous["index"]),
                        "start_price": float(previous["price"]),
                        "end_index": int(pivot["index"]),
                        "end_price": float(pivot["price"]),
                    })
                    chain_length += 1
                else:
                    if chain_length >= 2:
                        line_end = _line_end_at_cross(
                            data,
                            kind,
                            int(previous["index"]),
                            int(pivot["index"]),
                            float(previous["price"]),
                        )
                        lines.append({
                            "kind": kind,
                            "start_index": int(previous["index"]),
                            "start_price": float(previous["price"]),
                            "end_index": line_end,
                            "end_price": float(previous["price"]),
                        })
                    chain_length = 1
            previous = pivot

            if position == len(same_kind) - 1 and previous is not None:
                if chain_length >= 2 and data is not None:
                    last_index = (
                        len(data) - 1
                        if data is not None
                        else int(previous["index"])
                    )
                    line_end = _line_end_at_cross(
                        data,
                        kind,
                        int(previous["index"]),
                        last_index,
                        float(previous["price"]),
                    )
                    lines.append({
                        "kind": kind,
                        "start_index": int(previous["index"]),
                        "start_price": float(previous["price"]),
                        "end_index": line_end,
                        "end_price": float(previous["price"]),
                    })
    return sorted(lines, key=lambda line: (line["start_index"], line["kind"]))


def detect_fractal_breakouts(
    data,
    pivots: list[Pivot],
    breakout_by_close: bool = False,
) -> list[BreakoutEvent]:
    """Return first breaks after each confirmed nearest fractal level."""
    highs = _values(data, "high")
    lows = _values(data, "low")
    closes = _values(data, "close")
    sorted_pivots = sorted(pivots, key=lambda item: item["confirmed_index"])
    active: dict[str, Pivot | None] = {"high": None, "low": None}
    broken: dict[str, bool] = {"high": True, "low": True}
    events: list[BreakoutEvent] = []
    pivot_position = 0

    def install_confirmed_pivot(pivot: Pivot) -> None:
        active[pivot["kind"]] = pivot
        broken[pivot["kind"]] = False

    for index in range(len(data)):
        while (
            pivot_position < len(sorted_pivots)
            and sorted_pivots[pivot_position]["confirmed_index"] < index
        ):
            install_confirmed_pivot(sorted_pivots[pivot_position])
            pivot_position += 1

        high_pivot = active["high"]
        if (
            high_pivot is not None
            and int(high_pivot["confirmed_index"]) < index
            and not broken["high"]
        ):
            value = closes[index] if breakout_by_close else highs[index]
            if value > high_pivot["price"]:
                events.append({
                    "direction": "BUY",
                    "index": index,
                    "pivot_index": int(high_pivot["index"]),
                    "price": float(high_pivot["price"]),
                    "confirmed_index": int(high_pivot["confirmed_index"]),
                })
                broken["high"] = True

        low_pivot = active["low"]
        if (
            low_pivot is not None
            and int(low_pivot["confirmed_index"]) < index
            and not broken["low"]
        ):
            value = closes[index] if breakout_by_close else lows[index]
            if value < low_pivot["price"]:
                events.append({
                    "direction": "SELL",
                    "index": index,
                    "pivot_index": int(low_pivot["index"]),
                    "price": float(low_pivot["price"]),
                    "confirmed_index": int(low_pivot["confirmed_index"]),
                })
                broken["low"] = True

        # A newly confirmed pivot becomes active only after the confirmation
        # candle has been checked against the previously active level.
        while (
            pivot_position < len(sorted_pivots)
            and sorted_pivots[pivot_position]["confirmed_index"] == index
        ):
            install_confirmed_pivot(sorted_pivots[pivot_position])
            pivot_position += 1

    return events


def precompute_swing_trend_data(
    data,
    strength: int = 2,
    breakout_by_close: bool = False,
) -> tuple[list[Pivot], list[SwingLine], list[BreakoutEvent]]:
    """Precompute fractals, trend segments, and breakouts for a full dataset."""
    pivots = precompute_fractal_pivots(data, strength)
    return (
        pivots,
        build_swing_trend_lines(pivots, data=data),
        detect_fractal_breakouts(data, pivots, breakout_by_close),
    )
