import pandas as pd
import pytest

import src.swing_ema_strategy as swing_strategy
from src.swing_ema_strategy import (
    annotate_structure,
    build_swing_chart_overlays,
    build_swing_ema_entry_signal,
    build_stop_order_signal,
    detect_structure_bias,
    evaluate_ema_exit,
    evaluate_swing_ema_signal,
    find_latest_ema_cross,
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
    {"index": 2, "kind": "low", "price": 100.0, "confirmed_index": 5},
    {"index": 5, "kind": "high", "price": 110.0, "confirmed_index": 8},
    {"index": 8, "kind": "low", "price": 95.0, "confirmed_index": 11},
    {"index": 11, "kind": "high", "price": 105.0, "confirmed_index": 14},
]


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


def test_annotate_structure_labels_higher_highs_and_higher_lows():
    structured = annotate_structure(BUY_PIVOTS)

    assert structured[2]["structure_label"] == "HL"
    assert structured[3]["structure_label"] == "HH"
    assert detect_structure_bias(BUY_PIVOTS) == "BUY"


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


def test_annotate_structure_labels_lower_highs_and_lower_lows():
    structured = annotate_structure(SELL_PIVOTS)

    assert structured[2]["structure_label"] == "LL"
    assert structured[3]["structure_label"] == "LH"
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
        swing_high=SELL_PIVOTS[-1],
        swing_low=SELL_PIVOTS[-2],
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
