import pandas as pd

from src.pivot_detectors import (
    build_swing_trend_lines,
    detect_fractal_breakouts,
    detect_fractal_pivots,
)


def _candles(highs, lows, closes=None):
    return pd.DataFrame({
        "high": highs,
        "low": lows,
        "close": closes or [(high + low) / 2 for high, low in zip(highs, lows)],
    })


def test_fractal_pivots_use_strength_bars_and_confirm_on_right_side():
    data = _candles(
        [10, 11, 12, 11, 10, 9, 8],
        [5, 4, 3, 4, 5, 6, 7],
    )

    pivots = detect_fractal_pivots(data, strength=2)

    assert pivots == [
        {"index": 2, "kind": "high", "price": 12.0, "confirmed_index": 4},
        {"index": 2, "kind": "low", "price": 3.0, "confirmed_index": 4},
    ]


def test_swing_trend_lines_keep_lower_highs_and_higher_lows():
    pivots = [
        {"index": 2, "kind": "high", "price": 110.0, "confirmed_index": 4},
        {"index": 5, "kind": "high", "price": 105.0, "confirmed_index": 7},
        {"index": 8, "kind": "high", "price": 108.0, "confirmed_index": 10},
        {"index": 2, "kind": "low", "price": 90.0, "confirmed_index": 4},
        {"index": 5, "kind": "low", "price": 95.0, "confirmed_index": 7},
        {"index": 8, "kind": "low", "price": 92.0, "confirmed_index": 10},
    ]

    lines = build_swing_trend_lines(pivots)

    assert [(line["kind"], line["start_index"], line["end_index"]) for line in lines] == [
        ("high", 2, 5),
        ("low", 2, 5),
        ("high", 5, 8),
        ("low", 5, 8),
    ]


def test_breakout_can_use_wick_or_close_after_fractal_confirmation():
    data = _candles(
        [10, 11, 12, 11, 13, 13],
        [5, 4, 3, 4, 5, 5],
        closes=[7, 8, 9, 8, 11, 13],
    )
    pivots = [
        {"index": 2, "kind": "high", "price": 12.0, "confirmed_index": 4},
        {"index": 2, "kind": "low", "price": 3.0, "confirmed_index": 4},
    ]

    wick_events = detect_fractal_breakouts(data, pivots, breakout_by_close=False)
    close_events = detect_fractal_breakouts(data, pivots, breakout_by_close=True)

    assert [event["direction"] for event in wick_events] == ["BUY"]
    assert wick_events[0]["index"] == 5
    assert [event["direction"] for event in close_events] == ["BUY"]
    assert close_events[0]["index"] == 5


def test_breakout_checks_old_level_before_new_confirmation_replaces_it():
    data = _candles(
        [9, 10, 9, 9, 9, 11, 9],
        [5, 4, 5, 5, 5, 5, 5],
    )
    pivots = [
        {"index": 1, "kind": "high", "price": 10.0, "confirmed_index": 1},
        {"index": 3, "kind": "high", "price": 9.0, "confirmed_index": 5},
    ]

    events = detect_fractal_breakouts(data, pivots, breakout_by_close=False)

    assert events == [{
        "direction": "BUY",
        "index": 5,
        "pivot_index": 1,
        "price": 10.0,
        "confirmed_index": 1,
    }]


def test_fractal_pivots_shift_global_candidates_to_local_window():
    data = _candles([10, 11, 12, 11, 10], [5, 4, 3, 4, 5])
    global_pivots = [
        {"index": 12, "kind": "high", "price": 12.0, "confirmed_index": 14},
    ]

    pivots = detect_fractal_pivots(
        data,
        strength=2,
        candidate_pivots=global_pivots,
        index_offset=10,
    )

    assert pivots == [
        {"index": 2, "kind": "high", "price": 12.0, "confirmed_index": 4},
    ]
