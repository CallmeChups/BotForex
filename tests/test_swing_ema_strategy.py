import pandas as pd
import pytest

import src.swing_ema_strategy as swing_strategy
from src.swing_ema_strategy import (
    annotate_structure,
    build_swing_chart_overlays,
    build_swing_ema_entry_signal,
    build_stop_order_signal,
    calculate_ema_series,
    calculate_swing_exit_levels,
    detect_structure_bias,
    evaluate_ema_exit,
    evaluate_swing_ema_signal,
    find_latest_ema_cross,
    get_swing_setup_pivots,
    is_pending_signal_expired,
    passes_ema_consensus,
    passes_ema_cross_window,
)


BUY_PIVOTS = [
    {"index": 2, "kind": "low", "price": 100.0, "confirmed_index": 5},
    {"index": 5, "kind": "high", "price": 110.0, "confirmed_index": 8},
    {"index": 8, "kind": "low", "price": 104.0, "confirmed_index": 11},
    {"index": 11, "kind": "high", "price": 115.0, "confirmed_index": 14},
]

SELL_PIVOTS = [
    {"index": 2, "kind": "high", "price": 110.0, "confirmed_index": 5},
    {"index": 5, "kind": "low", "price": 100.0, "confirmed_index": 8},
    {"index": 8, "kind": "high", "price": 105.0, "confirmed_index": 11},
    {"index": 11, "kind": "low", "price": 95.0, "confirmed_index": 14},
]


def test_calculate_ema_series_uses_lightweight_path_for_adjust_false(monkeypatch):
    values = [1.0, 2.5, -1.0, 3.0, 4.5]
    expected = pd.Series(values, dtype=float).ewm(
        span=3, adjust=False
    ).mean().tolist()

    def pandas_ewm_must_not_be_used(*args, **kwargs):
        pytest.fail("adjust=False should not construct a pandas EWM")

    monkeypatch.setattr(pd.Series, "ewm", pandas_ewm_must_not_be_used)

    assert calculate_ema_series(values, period=3) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("direction", "high", "low", "swing_high", "swing_low"),
    [
        ("BUY", 101.0, 100.5, 100.0, 99.0),
        ("SELL", 99.5, 98.0, 101.0, 100.0),
    ],
)
def test_entry_builder_rejects_already_triggered_entry_before_sl_calculation(
    monkeypatch, direction, high, low, swing_high, swing_low
):
    pivots = [
        {"index": 1, "kind": "low", "price": 95.0, "confirmed_index": 2},
        {"index": 4, "kind": "high", "price": 105.0, "confirmed_index": 5},
        {"index": 7, "kind": "low", "price": swing_low, "confirmed_index": 8},
        {"index": 10, "kind": "high", "price": swing_high, "confirmed_index": 11},
    ]
    structured = pivots
    monkeypatch.setattr(swing_strategy, "detect_confirmed_pivots", lambda *args, **kwargs: pivots)
    monkeypatch.setattr(
        swing_strategy,
        "evaluate_swing_ema_signal",
        lambda **kwargs: {
            "direction": direction,
            "structure": structured,
            "swing_high_index": 10,
            "swing_low_index": 7,
        },
    )
    monkeypatch.setattr(
        swing_strategy,
        "build_stop_order_signal",
        lambda **kwargs: pytest.fail("Must reject a triggered entry before building SL/TP"),
    )
    candles = pd.DataFrame([{"high": high, "low": low, "close": 100.0}])

    signal = build_swing_ema_entry_signal(
        data=candles,
        symbol_point_size=0.1,
        ema_periods={"fast": 13, "medium": 21, "slow": 55},
        zigzag_depth=3,
        zigzag_deviation_points=3.0,
        zigzag_back_step=3,
        min_structure_candles=1,
        max_structure_candles=20,
        ema_cross_window_candles=15,
        rr_ratio=2.0,
        pending_expiry_candles=7,
        sl_buffer_price=0.1,
        entry_buffer_price=0.0,
    )

    assert signal is None


@pytest.mark.parametrize("direction", ["BUY", "SELL"])
def test_entry_builder_filters_same_kind_pivot_distance(monkeypatch, direction):
    pivots = [
        {"index": 1, "kind": "low" if direction == "BUY" else "high", "price": 95.0, "confirmed_index": 2},
        {"index": 4, "kind": "high" if direction == "BUY" else "low", "price": 105.0, "confirmed_index": 5},
        {"index": 7, "kind": "low" if direction == "BUY" else "high", "price": 98.0, "confirmed_index": 8},
        {"index": 10, "kind": "high" if direction == "BUY" else "low", "price": 110.0, "confirmed_index": 11},
    ]
    monkeypatch.setattr(
        swing_strategy, "detect_confirmed_pivots", lambda *args, **kwargs: pivots
    )
    monkeypatch.setattr(
        swing_strategy,
        "evaluate_swing_ema_signal",
        lambda **kwargs: {
            "direction": direction,
            "structure": pivots,
            "pullback_structure": pivots[:3],
            "ema_snapshot": {},
            "pivot_ema_snapshot": {},
            "ema_cross": {},
        },
    )

    signal = build_swing_ema_entry_signal(
        data=pd.DataFrame({
            "time": pd.date_range("2026-01-01", periods=12, freq="min"),
            "open": [100.0] * 12,
            "high": [111.0] * 12,
            "low": [94.0] * 12,
            "close": [100.0] * 12,
        }),
        symbol_point_size=0.1,
        ema_periods={"fast": 13, "medium": 21, "slow": 55},
        zigzag_depth=2,
        zigzag_deviation_points=3.0,
        zigzag_back_step=3,
        min_structure_candles=1,
        max_structure_candles=20,
        ema_cross_window_candles=15,
        rr_ratio=2.0,
        pending_expiry_candles=7,
        sl_buffer_price=0.1,
        min_pivot_distance_candles=7,
        max_pivot_distance_candles=15,
    )

    assert signal is None


def test_annotate_structure_labels_higher_highs_and_higher_lows():
    structured = annotate_structure(BUY_PIVOTS)

    assert structured[2]["structure_label"] == "HL"
    assert structured[3]["structure_label"] == "HH"
    assert detect_structure_bias(BUY_PIVOTS) == "BUY"


@pytest.mark.parametrize(
    ("signal", "expected"),
    [
        (
            {
                "direction": "SELL",
                "structure": SELL_PIVOTS,
                "swing_low_index": 11,
            },
            ["Đỉnh 1", "Đáy 1", "Đỉnh 2", "Đáy 2"],
        ),
        (
            {
                "direction": "BUY",
                "structure": BUY_PIVOTS,
                "swing_high_index": 5,
            },
            ["Đáy 1", "Đỉnh 1", "Đáy 2"],
        ),
    ],
)
def test_setup_pivot_labels_fallback_for_legacy_signal(signal, expected):
    assert [
        pivot["label"] for pivot in get_swing_setup_pivots(signal)
    ] == expected


def test_structure_bias_can_omit_second_high_for_buy():
    buy_structure_without_high2 = BUY_PIVOTS[:3]

    assert detect_structure_bias(
        buy_structure_without_high2,
        use_pivot2_for_buy=False,
    ) == "BUY"
    assert detect_structure_bias(buy_structure_without_high2) is None


def test_structure_bias_can_omit_second_low_for_sell():
    sell_structure_without_low2 = [
        {"index": 2, "kind": "high", "price": 110.0, "confirmed_index": 5},
        {"index": 5, "kind": "low", "price": 95.0, "confirmed_index": 8},
        {"index": 8, "kind": "high", "price": 105.0, "confirmed_index": 11},
    ]

    assert detect_structure_bias(
        sell_structure_without_low2,
        use_pivot2_for_sell=False,
    ) == "SELL"
    assert detect_structure_bias(sell_structure_without_low2) is None


def test_structure_bias_requires_ordered_second_pivot_for_enabled_routes():
    buy_without_high2 = BUY_PIVOTS + [
        {"index": 14, "kind": "low", "price": 106.0, "confirmed_index": 17},
    ]
    sell_without_low2 = [
        {"index": 0, "kind": "high", "price": 120.0, "confirmed_index": 3},
        {"index": 2, "kind": "low", "price": 100.0, "confirmed_index": 5},
        {"index": 5, "kind": "high", "price": 110.0, "confirmed_index": 8},
        {"index": 8, "kind": "low", "price": 95.0, "confirmed_index": 11},
        {"index": 11, "kind": "high", "price": 105.0, "confirmed_index": 14},
    ]

    assert detect_structure_bias(buy_without_high2) is None
    assert detect_structure_bias(sell_without_low2) is None


def test_buy_without_high2_uses_high1_and_skips_pivot_ema_filter(monkeypatch):
    pivots = BUY_PIVOTS[:3]
    monkeypatch.setattr(
        swing_strategy,
        "detect_confirmed_pivots",
        lambda *args, **kwargs: pivots,
    )
    monkeypatch.setattr(
        swing_strategy,
        "evaluate_swing_ema_signal",
        lambda **kwargs: {
            "direction": "BUY",
            "structure": pivots,
            "pullback_structure": pivots,
            "swing_high_index": pivots[1]["index"],
            "swing_low_index": pivots[2]["index"],
            "ema_snapshot": {},
            "fallback_ema_snapshot": {},
            "pivot_ema_snapshot": {},
            "ema_cross": {},
        },
    )
    candles = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=15, freq="min"),
        "open": [100.0] * 15,
        "high": [101.0] * 15,
        "low": [99.0] * 15,
        "close": [100.0] * 15,
    })

    signal = build_swing_ema_entry_signal(
        data=candles,
        symbol_point_size=0.01,
        ema_periods={"fast": 13, "medium": 21, "slow": 55},
        zigzag_depth=3,
        zigzag_deviation_points=3.0,
        zigzag_back_step=3,
        min_structure_candles=1,
        max_structure_candles=20,
        ema_cross_window_candles=15,
        rr_ratio=2.0,
        pending_expiry_candles=7,
        sl_buffer_price=0.05,
        entry_buffer_price=0.02,
        use_pivot2_for_buy=False,
    )

    assert signal is not None
    assert signal["entry_price"] == pytest.approx(110.02)
    assert signal["pivot_ema_snapshot"] == {}
    assert [pivot["label"] for pivot in signal["setup_pivots"]] == [
        "Đáy 1",
        "Đỉnh 1",
        "Đáy 2",
    ]


def test_sell_without_low2_uses_low1_and_skips_pivot_ema_filter(monkeypatch):
    pivots = [
        {"index": 2, "kind": "high", "price": 120.0, "confirmed_index": 5},
        {"index": 5, "kind": "low", "price": 100.0, "confirmed_index": 8},
        {"index": 8, "kind": "high", "price": 110.0, "confirmed_index": 11},
    ]
    monkeypatch.setattr(
        swing_strategy,
        "detect_confirmed_pivots",
        lambda *args, **kwargs: pivots,
    )
    monkeypatch.setattr(
        swing_strategy,
        "evaluate_swing_ema_signal",
        lambda **kwargs: {
            "direction": "SELL",
            "structure": pivots,
            "pullback_structure": pivots,
            "ema_snapshot": {},
            "fallback_ema_snapshot": {},
            "pivot_ema_snapshot": {},
            "ema_cross": {},
        },
    )
    candles = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=15, freq="min"),
        "open": [105.0] * 15,
        "high": [106.0] * 15,
        "low": [104.0] * 15,
        "close": [105.0] * 15,
    })

    signal = build_swing_ema_entry_signal(
        data=candles,
        symbol_point_size=0.01,
        ema_periods={"fast": 13, "medium": 21, "slow": 55},
        zigzag_depth=3,
        zigzag_deviation_points=3.0,
        zigzag_back_step=3,
        min_structure_candles=1,
        max_structure_candles=20,
        ema_cross_window_candles=15,
        rr_ratio=2.0,
        pending_expiry_candles=7,
        sl_buffer_price=0.05,
        entry_buffer_price=0.02,
        use_pivot2_for_sell=False,
    )

    assert signal is not None
    assert signal["entry_price"] == pytest.approx(99.98)
    assert signal["pivot_ema_snapshot"] == {}
    assert [pivot["label"] for pivot in signal["setup_pivots"]] == [
        "Đỉnh 1",
        "Đáy 1",
        "Đỉnh 2",
    ]


@pytest.mark.parametrize(
    ("direction", "fallback_values", "candle", "expected"),
    [
        ("BUY", {"fast": 13.0, "medium": 12.0, "slow": 15.0},
         {"open": 14.0, "close": 16.0}, True),
        ("BUY", {"fast": 13.0, "medium": 12.0, "slow": 15.0},
         {"open": 14.0, "close": 14.5}, False),
        ("SELL", {"fast": 12.0, "medium": 13.0, "slow": 10.0},
         {"open": 11.0, "close": 9.0}, True),
        ("SELL", {"fast": 12.0, "medium": 13.0, "slow": 10.0},
         {"open": 11.0, "close": 10.5}, False),
    ],
)
def test_swing_ema_fallback_matches_multi_flappy_candle_rule(
    direction, fallback_values, candle, expected
):
    assert swing_strategy.passes_swing_ema_fallback(
        direction,
        fallback_values,
        candle,
    ) is expected


def test_swing_ema_filters_allow_either_enabled_consensus_or_fallback():
    consensus_values = {"fast": 12.0, "medium": 13.0, "slow": 11.0}
    fallback_values = {"fast": 13.0, "medium": 12.0, "slow": 15.0}
    candle = {"open": 14.0, "close": 16.0}

    assert swing_strategy.passes_swing_ema_filters(
        "BUY",
        consensus_values,
        fallback_values,
        candle,
        consensus_enabled=True,
        fallback_enabled=True,
        consensus_cross_valid=False,
    )
    assert not swing_strategy.passes_swing_ema_filters(
        "BUY",
        consensus_values,
        fallback_values,
        candle,
        consensus_enabled=True,
        fallback_enabled=False,
        consensus_cross_valid=False,
    )
    assert swing_strategy.passes_swing_ema_filters(
        "BUY",
        consensus_values,
        fallback_values,
        candle,
        consensus_enabled=False,
        fallback_enabled=True,
        consensus_cross_valid=False,
    )
    assert swing_strategy.passes_swing_ema_filters(
        "BUY",
        consensus_values,
        fallback_values,
        candle,
        consensus_enabled=False,
        fallback_enabled=False,
        consensus_cross_valid=False,
    )


def test_fallback_only_does_not_apply_consensus_pivot_ema_filter(monkeypatch):
    snapshots = iter(({"fast": 13.0, "medium": 12.0, "slow": 15.0},))
    monkeypatch.setattr(
        swing_strategy,
        "calculate_ema_snapshot",
        lambda *args, **kwargs: next(snapshots),
    )
    monkeypatch.setattr(
        swing_strategy,
        "calculate_ema_series",
        lambda *args, **kwargs: [120.0] * len(args[0]),
    )

    signal = evaluate_swing_ema_signal(
        pivots=BUY_PIVOTS,
        close_values=[100.0] * 20,
        point_size=0.01,
        ema_periods={"fast": 13, "medium": 21, "slow": 55},
        fallback_ema_periods={"fast": 8, "medium": 13, "slow": 34},
        ema_consensus_enabled=False,
        ema_fallback_enabled=True,
        signal_candle={"open": 14.0, "close": 16.0},
    )

    assert signal is not None
    assert signal["pivot_ema_snapshot"] == {}


def test_fallback_can_pass_when_consensus_pivot_ema_check_fails(monkeypatch):
    snapshots = iter((
        {"fast": 12.0, "medium": 13.0, "slow": 11.0},
        {"fast": 13.0, "medium": 12.0, "slow": 15.0},
    ))
    monkeypatch.setattr(
        swing_strategy,
        "calculate_ema_snapshot",
        lambda *args, **kwargs: next(snapshots),
    )
    monkeypatch.setattr(
        swing_strategy,
        "calculate_ema_series",
        lambda *args, **kwargs: [120.0] * len(args[0]),
    )

    signal = evaluate_swing_ema_signal(
        pivots=BUY_PIVOTS,
        close_values=[100.0] * 20,
        point_size=0.01,
        ema_periods={"fast": 13, "medium": 21, "slow": 55},
        fallback_ema_periods={"fast": 8, "medium": 13, "slow": 34},
        ema_consensus_enabled=True,
        ema_fallback_enabled=True,
        signal_candle={"open": 14.0, "close": 16.0},
    )

    assert signal is not None
    assert signal["pivot_ema_snapshot"] == {
        "fast": 120.0,
        "medium": 120.0,
        "slow": 120.0,
    }


def test_swing_chart_overlays_include_configured_emas_and_only_confirmed_pivots():
    data = pd.DataFrame({
        "high": [2.0, 4.0, 3.0, 5.0, 2.0, 4.0, 3.0],
        "low": [1.0, 2.0, 1.5, 2.0, 0.5, 2.0, 1.5],
        "close": [1.5, 3.0, 2.0, 4.0, 1.0, 3.0, 2.0],
    })

    ema_values, pivots = build_swing_chart_overlays(
        data,
        symbol_point_size=0.1,
        ema_periods={"fast": 2, "medium": 3, "slow": 4},
        zigzag_depth=1,
        zigzag_deviation_points=0.0,
        zigzag_back_step=0,
    )

    assert set(ema_values) == {"fast", "medium", "slow"}
    assert all(len(values) == len(data) for values in ema_values.values())
    assert ema_values["fast"][-1] == pytest.approx(
        data["close"].ewm(span=2, adjust=False).mean().iloc[-1]
    )
    assert pivots
    assert all(pivot["confirmed_index"] < len(data) for pivot in pivots)


def test_swing_setup_identity_is_stable_as_rolling_window_advances(monkeypatch):
    pivots_by_call = iter((
        [
            {"index": 2, "kind": "low", "price": 95.0, "confirmed_index": 3},
            {"index": 5, "kind": "high", "price": 105.0, "confirmed_index": 6},
            {"index": 8, "kind": "low", "price": 98.0, "confirmed_index": 9},
            {"index": 11, "kind": "high", "price": 110.0, "confirmed_index": 12},
        ],
        [
            {"index": 1, "kind": "low", "price": 95.0, "confirmed_index": 2},
            {"index": 4, "kind": "high", "price": 105.0, "confirmed_index": 5},
            {"index": 7, "kind": "low", "price": 98.0, "confirmed_index": 8},
            {"index": 10, "kind": "high", "price": 110.0, "confirmed_index": 11},
        ],
    ))
    current_pivots = [None]

    def detect_pivots(*args, **kwargs):
        current_pivots[0] = next(pivots_by_call)
        return current_pivots[0]

    monkeypatch.setattr(swing_strategy, "detect_confirmed_pivots", detect_pivots)
    monkeypatch.setattr(
        swing_strategy,
        "evaluate_swing_ema_signal",
        lambda **kwargs: {
            "direction": "BUY",
            "structure": current_pivots[0],
            "pullback_structure": current_pivots[0][-4:-1],
            "swing_high_index": current_pivots[0][-1]["index"],
            "swing_low_index": current_pivots[0][-2]["index"],
            "ema_snapshot": {},
            "pivot_ema_snapshot": {},
            "ema_cross": {},
        },
    )
    candles = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=21, freq="min"),
        "high": [101.0] * 21,
        "low": [99.0] * 21,
        "close": [100.0] * 21,
    })
    common_args = {
        "symbol_point_size": 0.01,
        "ema_periods": {"fast": 13, "medium": 21, "slow": 55},
        "zigzag_depth": 3,
        "zigzag_deviation_points": 3.0,
        "zigzag_back_step": 3,
        "min_structure_candles": 1,
        "max_structure_candles": 20,
        "ema_cross_window_candles": 15,
        "rr_ratio": 2.0,
        "pending_expiry_candles": 7,
        "sl_buffer_price": 0.05,
        "entry_buffer_price": 0.02,
    }

    first = build_swing_ema_entry_signal(candles.iloc[:20], **common_args)
    next_window = pd.concat(
        [candles.iloc[1:20], candles.iloc[[20]]],
        ignore_index=True,
    )
    second = build_swing_ema_entry_signal(next_window, **common_args)

    assert first is not None and second is not None
    assert first["setup_id"] == second["setup_id"]


def test_swing_setup_identity_includes_both_pivot_pairs(monkeypatch):
    pivot_sets = iter((
        [
            {"index": 2, "kind": "low", "price": 90.0, "confirmed_index": 3},
            {"index": 5, "kind": "high", "price": 100.0, "confirmed_index": 6},
            {"index": 8, "kind": "low", "price": 95.0, "confirmed_index": 9},
            {"index": 11, "kind": "high", "price": 105.0, "confirmed_index": 12},
            {"index": 14, "kind": "low", "price": 98.0, "confirmed_index": 15},
            {"index": 17, "kind": "high", "price": 110.0, "confirmed_index": 18},
        ],
        [
            {"index": 2, "kind": "low", "price": 90.0, "confirmed_index": 3},
            {"index": 5, "kind": "high", "price": 100.0, "confirmed_index": 6},
            {"index": 9, "kind": "low", "price": 95.0, "confirmed_index": 10},
            {"index": 11, "kind": "high", "price": 105.0, "confirmed_index": 12},
            {"index": 14, "kind": "low", "price": 98.0, "confirmed_index": 15},
            {"index": 17, "kind": "high", "price": 110.0, "confirmed_index": 18},
        ],
    ))
    current_pivots = [None]

    def detect_pivots(*args, **kwargs):
        current_pivots[0] = next(pivot_sets)
        return current_pivots[0]

    monkeypatch.setattr(swing_strategy, "detect_confirmed_pivots", detect_pivots)
    monkeypatch.setattr(
        swing_strategy,
        "evaluate_swing_ema_signal",
        lambda **kwargs: {
            "direction": "BUY",
            "structure": current_pivots[0],
            "pullback_structure": current_pivots[0][2:5],
            "swing_high_index": 17,
            "swing_low_index": 14,
            "ema_snapshot": {},
            "pivot_ema_snapshot": {},
            "ema_cross": {},
        },
    )
    candles = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=21, freq="min"),
        "high": [101.0] * 21,
        "low": [99.0] * 21,
        "close": [100.0] * 21,
    })
    common_args = {
        "symbol_point_size": 0.01,
        "ema_periods": {"fast": 13, "medium": 21, "slow": 55},
        "zigzag_depth": 3,
        "zigzag_deviation_points": 3.0,
        "zigzag_back_step": 3,
        "min_structure_candles": 1,
        "max_structure_candles": 20,
        "ema_cross_window_candles": 15,
        "rr_ratio": 2.0,
        "pending_expiry_candles": 7,
        "sl_buffer_price": 0.05,
        "entry_buffer_price": 0.02,
    }

    first = build_swing_ema_entry_signal(candles, **common_args)
    second = build_swing_ema_entry_signal(candles, **common_args)

    assert first is not None and second is not None
    assert first["entry_price"] == second["entry_price"]
    assert first["setup_id"] != second["setup_id"]


def test_swing_setup_identity_is_shared_by_trigger_highs_from_same_pullback(
    monkeypatch,
):
    pivot_sets = iter((
        [
            {"index": 2, "kind": "low", "price": 90.0, "confirmed_index": 3},
            {"index": 5, "kind": "high", "price": 100.0, "confirmed_index": 6},
            {"index": 8, "kind": "low", "price": 95.0, "confirmed_index": 9},
            {"index": 11, "kind": "high", "price": 105.0, "confirmed_index": 12},
            {"index": 14, "kind": "low", "price": 98.0, "confirmed_index": 15},
            {"index": 17, "kind": "high", "price": 110.0, "confirmed_index": 18},
        ],
        [
            {"index": 2, "kind": "low", "price": 90.0, "confirmed_index": 3},
            {"index": 5, "kind": "high", "price": 100.0, "confirmed_index": 6},
            {"index": 8, "kind": "low", "price": 95.0, "confirmed_index": 9},
            {"index": 11, "kind": "high", "price": 105.0, "confirmed_index": 12},
            {"index": 14, "kind": "low", "price": 98.0, "confirmed_index": 15},
            {"index": 18, "kind": "high", "price": 111.0, "confirmed_index": 19},
        ],
    ))
    current_pivots = [None]

    def detect_pivots(*args, **kwargs):
        current_pivots[0] = next(pivot_sets)
        return current_pivots[0]

    monkeypatch.setattr(swing_strategy, "detect_confirmed_pivots", detect_pivots)
    monkeypatch.setattr(
        swing_strategy,
        "evaluate_swing_ema_signal",
        lambda **kwargs: {
            "direction": "BUY",
            "structure": current_pivots[0],
            "pullback_structure": current_pivots[0][2:5],
            "swing_high_index": current_pivots[0][-1]["index"],
            "swing_low_index": current_pivots[0][-2]["index"],
            "ema_snapshot": {},
            "pivot_ema_snapshot": {},
            "ema_cross": {},
        },
    )
    candles = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=21, freq="min"),
        "high": [101.0] * 21,
        "low": [99.0] * 21,
        "close": [100.0] * 21,
    })
    common_args = {
        "symbol_point_size": 0.01,
        "ema_periods": {"fast": 13, "medium": 21, "slow": 55},
        "zigzag_depth": 3,
        "zigzag_deviation_points": 3.0,
        "zigzag_back_step": 3,
        "min_structure_candles": 1,
        "max_structure_candles": 20,
        "ema_cross_window_candles": 15,
        "rr_ratio": 2.0,
        "pending_expiry_candles": 7,
        "sl_buffer_price": 0.05,
        "entry_buffer_price": 0.02,
    }

    first = build_swing_ema_entry_signal(candles, **common_args)
    second = build_swing_ema_entry_signal(candles, **common_args)

    assert first is not None and second is not None
    assert first["entry_price"] != second["entry_price"]
    assert first["setup_id"] == second["setup_id"]
    assert [
        (pivot["label"], pivot["index"])
        for pivot in first["setup_pivots"]
    ] == [
        ("Đáy 1", 8),
        ("Đỉnh 1", 11),
        ("Đáy 2", 14),
        ("Đỉnh 2", 17),
    ]
    assert first["signal_candle_index"] == len(candles) - 1


def test_setup_pivot_indices_are_shifted_to_absolute_position_with_offset(
    monkeypatch,
):
    # Simulate the backtest loop, which only passes in a rolling slice of the
    # full dataset (`data_index_offset` = slice start). Pivot indices coming
    # back from `detect_confirmed_pivots`/`evaluate_swing_ema_signal` are
    # local to that slice and must be shifted back to absolute positions so
    # downstream chart code can index into the full dataset correctly.
    local_pivots = [
        {"index": 2, "kind": "low", "price": 90.0, "confirmed_index": 3},
        {"index": 5, "kind": "high", "price": 100.0, "confirmed_index": 6},
        {"index": 8, "kind": "low", "price": 95.0, "confirmed_index": 9},
        {"index": 11, "kind": "high", "price": 105.0, "confirmed_index": 12},
    ]

    monkeypatch.setattr(
        swing_strategy, "detect_confirmed_pivots", lambda *a, **k: local_pivots
    )
    monkeypatch.setattr(
        swing_strategy,
        "evaluate_swing_ema_signal",
        lambda **kwargs: {
            "direction": "BUY",
            "structure": local_pivots,
            "pullback_structure": local_pivots[0:3],
            "swing_high_index": local_pivots[-1]["index"],
            "swing_low_index": local_pivots[2]["index"],
            "ema_snapshot": {},
            "pivot_ema_snapshot": {},
            "ema_cross": {},
        },
    )
    window = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=12, freq="min"),
        "high": [101.0] * 12,
        "low": [99.0] * 12,
        "close": [100.0] * 12,
    })
    offset = 100

    signal = build_swing_ema_entry_signal(
        window,
        symbol_point_size=0.01,
        ema_periods={"fast": 13, "medium": 21, "slow": 55},
        zigzag_depth=3,
        zigzag_deviation_points=3.0,
        zigzag_back_step=3,
        min_structure_candles=1,
        max_structure_candles=20,
        ema_cross_window_candles=15,
        rr_ratio=2.0,
        pending_expiry_candles=7,
        sl_buffer_price=0.05,
        entry_buffer_price=0.02,
        data_index_offset=offset,
    )

    assert signal is not None
    assert signal["swing_high_index"] == local_pivots[-1]["index"] + offset
    assert signal["swing_low_index"] == local_pivots[2]["index"] + offset
    assert [pivot["index"] for pivot in signal["structure"]] == [
        pivot["index"] + offset for pivot in local_pivots
    ]
    assert [pivot["index"] for pivot in signal["setup_pivots"]] == [
        local_pivots[0]["index"] + offset,
        local_pivots[1]["index"] + offset,
        local_pivots[2]["index"] + offset,
        local_pivots[3]["index"] + offset,
    ]
    assert signal["signal_candle_index"] == len(window) - 1 + offset


def test_swing_setup_identity_is_shared_by_trigger_lows_from_same_pullback(
    monkeypatch,
):
    pivot_sets = iter((
        [
            {"index": 2, "kind": "high", "price": 110.0, "confirmed_index": 3},
            {"index": 5, "kind": "low", "price": 100.0, "confirmed_index": 6},
            {"index": 8, "kind": "high", "price": 105.0, "confirmed_index": 9},
            {"index": 11, "kind": "low", "price": 95.0, "confirmed_index": 12},
            {"index": 14, "kind": "high", "price": 102.0, "confirmed_index": 15},
            {"index": 17, "kind": "low", "price": 90.0, "confirmed_index": 18},
        ],
        [
            {"index": 2, "kind": "high", "price": 110.0, "confirmed_index": 3},
            {"index": 5, "kind": "low", "price": 100.0, "confirmed_index": 6},
            {"index": 8, "kind": "high", "price": 105.0, "confirmed_index": 9},
            {"index": 11, "kind": "low", "price": 95.0, "confirmed_index": 12},
            {"index": 14, "kind": "high", "price": 102.0, "confirmed_index": 15},
            {"index": 18, "kind": "low", "price": 89.0, "confirmed_index": 19},
        ],
    ))
    current_pivots = [None]

    def detect_pivots(*args, **kwargs):
        current_pivots[0] = next(pivot_sets)
        return current_pivots[0]

    monkeypatch.setattr(swing_strategy, "detect_confirmed_pivots", detect_pivots)
    monkeypatch.setattr(
        swing_strategy,
        "evaluate_swing_ema_signal",
        lambda **kwargs: {
            "direction": "SELL",
            "structure": current_pivots[0],
            "pullback_structure": current_pivots[0][2:5],
            "swing_high_index": current_pivots[0][-2]["index"],
            "swing_low_index": current_pivots[0][-1]["index"],
            "ema_snapshot": {},
            "pivot_ema_snapshot": {},
            "ema_cross": {},
        },
    )
    candles = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=21, freq="min"),
        "high": [101.0] * 21,
        "low": [99.0] * 21,
        "close": [100.0] * 21,
    })
    common_args = {
        "symbol_point_size": 0.01,
        "ema_periods": {"fast": 13, "medium": 21, "slow": 55},
        "zigzag_depth": 3,
        "zigzag_deviation_points": 3.0,
        "zigzag_back_step": 3,
        "min_structure_candles": 1,
        "max_structure_candles": 20,
        "ema_cross_window_candles": 15,
        "rr_ratio": 2.0,
        "pending_expiry_candles": 7,
        "sl_buffer_price": 0.05,
        "entry_buffer_price": 0.02,
    }

    first = build_swing_ema_entry_signal(candles, **common_args)
    second = build_swing_ema_entry_signal(candles, **common_args)

    assert first is not None and second is not None
    assert first["entry_price"] != second["entry_price"]
    assert first["setup_id"] == second["setup_id"]


def test_entry_builder_rejects_buy_structure_without_intervening_high(monkeypatch):
    pivots = [
        {"index": 2, "kind": "low", "price": 90.0, "confirmed_index": 3},
        {"index": 5, "kind": "high", "price": 100.0, "confirmed_index": 6},
        {"index": 8, "kind": "low", "price": 95.0, "confirmed_index": 9},
        {"index": 11, "kind": "low", "price": 96.0, "confirmed_index": 12},
        {"index": 14, "kind": "high", "price": 105.0, "confirmed_index": 15},
        {"index": 17, "kind": "high", "price": 110.0, "confirmed_index": 18},
    ]
    monkeypatch.setattr(
        swing_strategy,
        "detect_confirmed_pivots",
        lambda *args, **kwargs: pivots,
    )
    monkeypatch.setattr(
        swing_strategy,
        "evaluate_swing_ema_signal",
        lambda **kwargs: {
            "direction": "BUY",
            "structure": pivots,
            "swing_high_index": 17,
            "swing_low_index": 11,
            "ema_snapshot": {},
            "pivot_ema_snapshot": {},
            "ema_cross": {},
        },
    )
    candles = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=21, freq="min"),
        "high": [101.0] * 21,
        "low": [99.0] * 21,
        "close": [100.0] * 21,
    })

    signal = build_swing_ema_entry_signal(
        data=candles,
        symbol_point_size=0.01,
        ema_periods={"fast": 13, "medium": 21, "slow": 55},
        zigzag_depth=3,
        zigzag_deviation_points=3.0,
        zigzag_back_step=3,
        min_structure_candles=1,
        max_structure_candles=20,
        ema_cross_window_candles=15,
        rr_ratio=2.0,
        pending_expiry_candles=7,
        sl_buffer_price=0.05,
        entry_buffer_price=0.02,
    )

    assert signal is None


def test_annotate_structure_labels_lower_highs_and_lower_lows():
    structured = annotate_structure(SELL_PIVOTS)

    assert structured[2]["structure_label"] == "LH"
    assert structured[3]["structure_label"] == "LL"
    assert detect_structure_bias(SELL_PIVOTS) == "SELL"


def test_detect_structure_bias_ignores_equal_highs_and_lows():
    pivots = [
        {"index": 2, "kind": "low", "price": 100.0, "confirmed_index": 5},
        {"index": 5, "kind": "high", "price": 110.0, "confirmed_index": 8},
        {"index": 8, "kind": "low", "price": 95.0, "confirmed_index": 11},
        {"index": 11, "kind": "high", "price": 110.0, "confirmed_index": 14},
    ]

    structured = annotate_structure(pivots)

    assert structured[3]["structure_label"] is None
    assert detect_structure_bias(pivots) is None


def test_detect_structure_bias_does_not_reuse_stale_labels_after_equal_pivot():
    pivots = [
        {"index": 1, "kind": "low", "price": 90.0, "confirmed_index": 4},
        {"index": 3, "kind": "high", "price": 100.0, "confirmed_index": 6},
        {"index": 5, "kind": "low", "price": 95.0, "confirmed_index": 8},
        {"index": 7, "kind": "high", "price": 110.0, "confirmed_index": 10},
        {"index": 9, "kind": "low", "price": 100.0, "confirmed_index": 12},
        {"index": 11, "kind": "high", "price": 110.0, "confirmed_index": 14},
    ]

    assert annotate_structure(pivots)[-1]["structure_label"] is None
    assert detect_structure_bias(pivots) is None


def test_passes_ema_consensus_checks_directional_order():
    assert passes_ema_consensus(
        "BUY",
        {"fast": 109.0, "medium": 106.0, "slow": 102.0},
    )
    assert passes_ema_consensus(
        "SELL",
        {"fast": 91.0, "medium": 95.0, "slow": 99.0},
    )
    assert not passes_ema_consensus(
        "BUY",
        {"fast": 106.0, "medium": 109.0, "slow": 102.0},
    )


def test_ema_cross_window_detects_recent_cross_and_rejects_stale_cross():
    buy_close_values = pd.DataFrame({"close": [10, 9, 8, 7, 6, 7, 8, 9, 10]})
    stale_close_values = pd.DataFrame({"close": [10, 9, 8, 7, 6, 7, 8, 9, 10, 11, 12]})

    buy_cross = find_latest_ema_cross(buy_close_values, fast_period=2, slow_period=4)

    assert buy_cross == {"direction": "BUY", "cross_index": 6, "bars_since_cross": 2}
    assert passes_ema_cross_window(
        "BUY",
        buy_close_values,
        fast_period=2,
        slow_period=4,
        window=2,
    )
    assert not passes_ema_cross_window(
        "BUY",
        stale_close_values,
        fast_period=2,
        slow_period=4,
        window=1,
    )


def test_ema_cross_window_does_not_count_startup_divergence_as_cross():
    close_values = pd.DataFrame({"close": [1, 2, 3, 4, 5]})

    assert find_latest_ema_cross(close_values, fast_period=2, slow_period=4) is None
    assert not passes_ema_cross_window(
        "BUY",
        close_values,
        fast_period=2,
        slow_period=4,
        window=10,
    )


def test_build_stop_order_signal_sets_levels_and_pending_expiry_metadata():
    signal = build_stop_order_signal(
        direction="BUY",
        swing_high=BUY_PIVOTS[-1],
        swing_low=BUY_PIVOTS[-2],
        point_size=0.1,
        buffer_price=0.3,
        rr_ratio=2.0,
        expiry_bars=4,
        created_bar_index=20,
        activation_previous_low=104.0,
    )

    assert signal["order_type"] == "BUY_STOP"
    assert signal["trigger_level"] == pytest.approx(115.0)
    assert signal["entry_price"] == pytest.approx(115.0)
    assert signal["stop_loss"] == pytest.approx(103.7)
    assert signal["take_profit"] == pytest.approx(137.6)
    assert signal["risk_points"] == pytest.approx(113.0)
    assert signal["expires_at_bar"] == 24
    assert not is_pending_signal_expired(signal, current_bar_index=24)
    assert is_pending_signal_expired(signal, current_bar_index=25)


def test_build_stop_order_signal_offsets_buy_and_sell_entry_by_entry_buffer():
    buy_signal = build_stop_order_signal(
        direction="BUY",
        swing_high=BUY_PIVOTS[-1],
        swing_low=BUY_PIVOTS[-2],
        point_size=0.1,
        entry_buffer_price=0.2,
        rr_ratio=2.0,
    )
    sell_signal = build_stop_order_signal(
        direction="SELL",
        swing_high=SELL_PIVOTS[-2],
        swing_low=SELL_PIVOTS[-1],
        point_size=0.1,
        entry_buffer_price=0.2,
        rr_ratio=2.0,
    )

    assert buy_signal["pivot_level"] == pytest.approx(115.0)
    assert buy_signal["entry_price"] == pytest.approx(115.2)
    assert buy_signal["trigger_level"] == pytest.approx(115.2)
    assert sell_signal["pivot_level"] == pytest.approx(95.0)
    assert sell_signal["entry_price"] == pytest.approx(94.8)
    assert sell_signal["trigger_level"] == pytest.approx(94.8)


def test_entry_buffer_does_not_change_stop_loss_buffer():
    signal = build_stop_order_signal(
        direction="BUY",
        swing_high=BUY_PIVOTS[-1],
        swing_low=BUY_PIVOTS[-2],
        point_size=0.1,
        buffer_price=0.3,
        entry_buffer_price=0.2,
        activation_previous_low=104.0,
    )

    assert signal["entry_price"] == pytest.approx(115.2)
    assert signal["stop_loss"] == pytest.approx(103.7)


@pytest.mark.parametrize(
    ("direction", "entry_price", "previous_candle", "expected_sl", "expected_tp"),
    [
        ("BUY", 105.0, {"low": 100.0, "high": 106.0}, 99.0, 117.0),
        ("SELL", 95.0, {"low": 94.0, "high": 100.0}, 101.0, 83.0),
    ],
)
def test_swing_exit_levels_use_last_closed_candle_before_fill(
    direction, entry_price, previous_candle, expected_sl, expected_tp
):
    levels = calculate_swing_exit_levels(
        direction=direction,
        entry_price=entry_price,
        previous_candle=previous_candle,
        buffer_price=1.0,
        rr_ratio=2.0,
    )

    assert levels["stop_loss"] == pytest.approx(expected_sl)
    assert levels["take_profit"] == pytest.approx(expected_tp)


def test_evaluate_ema_exit_checks_close_side_of_exit_ema():
    assert evaluate_ema_exit(
        "BUY",
        {"open": 116.0, "close": 105.0},
        ema_value=106.0,
    )["exit"]
    assert evaluate_ema_exit(
        "SELL",
        {"open": 95.0, "close": 101.0},
        ema_value=100.0,
    )["exit"]
    assert not evaluate_ema_exit(
        "BUY",
        {"open": 105.0, "close": 107.0},
        ema_value=106.0,
    )["exit"]


def test_evaluate_swing_ema_signal_combines_structure_and_ema_filters():
    close_values = pd.DataFrame({"close": [10, 9, 8, 7, 6, 7, 8, 9, 10, 11, 12, 13]})

    signal = evaluate_swing_ema_signal(
        pivots=BUY_PIVOTS,
        close_values=close_values,
        point_size=0.1,
        ema_periods={"fast": 2, "medium": 3, "slow": 5},
        cross_fast_period=2,
        cross_slow_period=4,
        cross_window=5,
        buffer_price=0.3,
        entry_buffer_price=0.2,
        rr_ratio=2.0,
        expiry_bars=4,
        created_bar_index=20,
    )

    assert signal is not None
    assert signal["direction"] == "BUY"
    assert signal["order_type"] == "BUY_STOP"
    assert signal["entry_price"] == pytest.approx(115.2)
    assert signal["expires_at_bar"] == 24
    assert signal["ema_cross"] == {
        "direction": "BUY",
        "cross_index": 6,
        "bars_since_cross": 5,
    }


def test_evaluate_swing_ema_signal_calculates_latest_cross_once(monkeypatch):
    close_values = pd.DataFrame({"close": [10, 9, 8, 7, 6, 7, 8, 9, 10, 11, 12, 13]})
    original = swing_strategy.find_latest_ema_cross
    calls = []

    def count_cross_calculations(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(
        swing_strategy, "find_latest_ema_cross", count_cross_calculations
    )

    evaluate_swing_ema_signal(
        pivots=BUY_PIVOTS,
        close_values=close_values,
        point_size=0.1,
        ema_periods={"fast": 2, "medium": 3, "slow": 5},
        cross_fast_period=2,
        cross_slow_period=4,
        cross_window=5,
    )

    assert len(calls) == 1


def test_evaluate_swing_ema_signal_returns_none_when_ema_consensus_fails():
    close_values = pd.DataFrame({"close": [10, 9, 8, 7, 6, 7, 8, 7, 6]})

    signal = evaluate_swing_ema_signal(
        pivots=BUY_PIVOTS,
        close_values=close_values,
        point_size=0.1,
        ema_periods={"fast": 2, "medium": 3, "slow": 5},
        cross_fast_period=2,
        cross_slow_period=4,
        cross_window=2,
    )

    assert signal is None


def test_evaluate_swing_ema_signal_returns_none_for_empty_close_values():
    signal = evaluate_swing_ema_signal(
        pivots=BUY_PIVOTS,
        close_values=[],
        point_size=0.1,
    )

    assert signal is None
