"""
Module: zigzag_swing.py
Purpose: Confirmed non-repainting swing pivot detection.
"""

from __future__ import annotations

from typing import Literal, TypedDict


PivotKind = Literal["high", "low"]


class Pivot(TypedDict):
    """Confirmed swing pivot."""

    index: int
    kind: PivotKind
    price: float
    confirmed_index: int


def _coerce_price_list(data, column: str) -> list[float]:
    """Return a float list from a pandas-like column source."""
    if isinstance(data, dict):
        values = data[column]
    else:
        values = data[column]
    if hasattr(values, "tolist"):
        raw_values = values.tolist()
    else:
        raw_values = list(values)
    return [float(value) for value in raw_values]


def _is_confirmed_high(highs: list[float], index: int, depth: int) -> bool:
    candidate = highs[index]
    left = highs[index - depth:index]
    right = highs[index + 1:index + depth + 1]
    return candidate > max(left) and candidate >= max(right)


def _is_confirmed_low(lows: list[float], index: int, depth: int) -> bool:
    candidate = lows[index]
    left = lows[index - depth:index]
    right = lows[index + 1:index + depth + 1]
    return candidate < min(left) and candidate <= min(right)


def _collect_candidate_pivots(highs: list[float], lows: list[float], depth: int) -> list[Pivot]:
    candidates: list[Pivot] = []
    last_index = len(highs) - depth
    for index in range(depth, last_index):
        is_high = _is_confirmed_high(highs, index, depth)
        is_low = _is_confirmed_low(lows, index, depth)
        if is_high == is_low:
            continue
        if is_high:
            candidates.append(
                {
                    "index": index,
                    "kind": "high",
                    "price": highs[index],
                    "confirmed_index": index + depth,
                }
            )
        else:
            candidates.append(
                {
                    "index": index,
                    "kind": "low",
                    "price": lows[index],
                    "confirmed_index": index + depth,
                }
            )
    return candidates


def detect_confirmed_pivots(
    data,
    point_size: float,
    depth: int = 3,
    deviation_points: float = 3.0,
    back_step: int = 3,
) -> list[Pivot]:
    """
    Detect confirmed non-repainting zigzag-style pivots.

    A pivot is confirmed only after `depth` bars have closed to the right, so
    the final `depth` bars are never emitted as pivots.
    """
    if point_size <= 0:
        raise ValueError("point_size must be positive")
    if depth <= 0:
        raise ValueError("depth must be positive")
    if deviation_points < 0:
        raise ValueError("deviation_points cannot be negative")
    if back_step < 0:
        raise ValueError("back_step cannot be negative")

    highs = _coerce_price_list(data, "high")
    lows = _coerce_price_list(data, "low")
    if len(highs) != len(lows):
        raise ValueError("high and low series must have the same length")
    if len(highs) < (depth * 2) + 1:
        return []

    deviation = deviation_points * point_size
    candidates = _collect_candidate_pivots(highs, lows, depth)
    pivots: list[Pivot] = []

    for candidate in candidates:
        if not pivots:
            pivots.append(candidate)
            continue

        previous = pivots[-1]
        if candidate["kind"] == previous["kind"]:
            if candidate["index"] - previous["index"] <= back_step:
                continue
            pivots.append(candidate)
            continue

        if abs(candidate["price"] - previous["price"]) < deviation:
            continue
        pivots.append(candidate)

    return pivots
