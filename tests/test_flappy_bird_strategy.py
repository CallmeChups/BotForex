import pandas as pd
import pytest

from src.flappy_bird_strategy import (
    EMA_WARMUP_WINDOW,
    analyze_flappy_bird,
    calculate_flappy_ema_series,
    calculate_flappy_ema_cross_lifecycle,
    diagnose_flappy_higher_timeframe,
    diagnose_flappy_bird,
    detect_flappy_bird_signal,
)
from src.backtest import run_backtest


def _candle(open_, high, low, close):
    return {"open": open_, "high": high, "low": low, "close": close}


def _valid_parts():
    mother = _candle(99.0, 110.0, 98.0, 101.0)
    children = [
        _candle(101.0, 103.0, 100.0, 102.0),
        _candle(102.0, 104.0, 101.0, 103.0),
    ]
    father = _candle(105.0, 108.5, 104.0, 108.0)
    return mother, children, father


def test_flappy_ema_uses_bounded_window_like_live_bot():
    closes = list(range(1, EMA_WARMUP_WINDOW + 3))
    values = calculate_flappy_ema_series(closes, 13, EMA_WARMUP_WINDOW)
    generator_values = calculate_flappy_ema_series(iter(closes), 13, EMA_WARMUP_WINDOW)

    expected_initial = pd.Series(closes[:EMA_WARMUP_WINDOW]).ewm(
        span=13, adjust=False
    ).mean().iloc[-1]
    expected_rolling = pd.Series(closes[1:EMA_WARMUP_WINDOW + 1]).ewm(
        span=13, adjust=False
    ).mean().iloc[-1]

    assert values[EMA_WARMUP_WINDOW - 1] == pytest.approx(expected_initial)
    assert values[EMA_WARMUP_WINDOW] == pytest.approx(expected_rolling)
    assert generator_values == pytest.approx(values)


def test_flappy_bird_signal_and_levels():
    mother, children, father = _valid_parts()
    signal = analyze_flappy_bird(
        "XAUUSD", mother, children, father, 105.0, 103.0, 100.0,
    )

    assert signal["direction"] == "BUY"
    assert signal["order_type"] == "BUY_LIMIT"
    assert signal["entry_price"] == pytest.approx(107.85)
    assert signal["stop_loss"] == pytest.approx(100.5)
    assert signal["take_profit"] == pytest.approx(122.55)
    assert signal["debug"]["valid"] is True
    assert signal["debug"]["reason"] is None
    assert "checks" not in signal["debug"]
    assert len(diagnose_flappy_bird(
        mother, children, father, 105.0, 103.0, 100.0, include_checks=True
    )["checks"]) == 11


def test_flappy_bird_sell_signal_and_levels():
    mother = _candle(101.0, 102.0, 90.0, 99.0)
    children = [
        _candle(98.0, 100.0, 96.0, 97.0),
        _candle(97.0, 99.0, 95.0, 96.0),
    ]
    father = _candle(94.0, 95.0, 90.3, 91.0)
    signal = analyze_flappy_bird(
        "XAUUSD", mother, children, father, 95.0, 97.0, 100.0,
        direction="SELL",
    )

    assert signal["direction"] == "SELL"
    assert signal["order_type"] == "SELL_LIMIT"
    assert signal["entry_price"] == pytest.approx(91.15)
    assert signal["stop_loss"] == pytest.approx(99.5)
    assert signal["take_profit"] == pytest.approx(74.45)
    assert signal["debug"]["valid"] is True


def test_flappy_bird_rejects_invalid_boundaries():
    mother, children, father = _valid_parts()
    assert not detect_flappy_bird_signal(
        mother, children, father, 103.0, 103.0, 100.0,
    )
    assert not detect_flappy_bird_signal(
        mother, children, father, 105.0, 103.0, 100.0,
        min_father_body_points=3.0,
    )
    father["high"] = 109.3
    assert not detect_flappy_bird_signal(
        mother, children, father, 105.0, 103.0, 100.0,
    )
    assert diagnose_flappy_bird(
        mother, children, father, 105.0, 103.0, 100.0
    )["reason"] == "father_upper_wick_too_large"


def test_flappy_bird_accepts_ema55_breakout_fallback_and_caps_body():
    mother, children, father = _valid_parts()
    father["open"] = 105.0
    father["high"] = 111.2
    father["close"] = 111.0

    assert detect_flappy_bird_signal(
        mother, children, father, 104.0, 102.0, 110.0
    )

    father["close"] = 111.1
    father["high"] = 111.3
    assert diagnose_flappy_bird(
        mother, children, father, 104.0, 102.0, 110.0
    )["reason"] == "father_body_above_maximum"


def test_flappy_bird_uses_separate_fallback_ema_values():
    mother, children, father = _valid_parts()
    father["open"] = 105.0
    father["close"] = 111.0
    father["high"] = 111.2

    assert detect_flappy_bird_signal(
        mother, children, father,
        104.0, 102.0, 120.0,
        fallback_ema13=104.0,
        fallback_ema21=102.0,
        fallback_ema55=110.0,
    )


def test_flappy_bird_requires_mother_direction():
    mother, children, father = _valid_parts()
    mother["close"] = 98.0

    assert diagnose_flappy_bird(
        mother, children, father, 105.0, 103.0, 100.0
    )["reason"] == "mother_direction_failed"


def test_flappy_bird_child_count_is_configurable():
    mother, children, father = _valid_parts()
    assert not detect_flappy_bird_signal(
        mother, children, father, 105.0, 103.0, 100.0,
        min_child_candles=3,
    )
    assert detect_flappy_bird_signal(
        mother, children, father, 105.0, 103.0, 100.0,
        max_child_candles=2,
    )


def test_flappy_bird_validates_final_two_child_bodies_and_boundaries():
    mother, children, father = _valid_parts()
    children.insert(0, _candle(100.0, 109.0, 99.0, 101.0))
    assert detect_flappy_bird_signal(
        mother, children, father, 105.0, 103.0, 100.0
    )

    mother["close"] = 104.0
    children[-1]["close"] = 104.1
    assert diagnose_flappy_bird(
        mother, children, father, 105.0, 103.0, 100.0,
        max_child_body_points=2.0,
    )["reason"] == "child_body_above_maximum"

    mother = _candle(101.0, 102.0, 90.0, 99.0)
    children = [
        _candle(98.0, 101.0, 96.0, 97.0),
        _candle(97.0, 99.0, 95.0, 96.0),
    ]
    father = _candle(94.0, 95.0, 90.3, 91.0)
    assert detect_flappy_bird_signal(
        mother, children, father, 95.0, 97.0, 100.0, direction="SELL"
    )


def test_flappy_bird_mother_coverage_can_be_disabled():
    mother, children, father = _valid_parts()
    mother["high"] = 102.0

    assert not detect_flappy_bird_signal(
        mother, children, father, 105.0, 103.0, 100.0
    )
    assert detect_flappy_bird_signal(
        mother, children, father, 105.0, 103.0, 100.0,
        mother_coverage_enabled=False,
    )


def test_flappy_bird_consensus_accepts_two_children_without_mother():
    children = [
        _candle(101.0, 103.0, 100.0, 102.0),
        _candle(102.0, 104.0, 101.0, 103.0),
    ]
    father = _candle(105.0, 108.0, 99.0, 108.0)

    diagnostics = diagnose_flappy_bird(
        None, children, father, 104.0, 103.0, 100.0,
        direction="BUY",
        use_mother_candle=False,
        no_mother_child_body_ratio=1.5,
        no_mother_child_body_max_points=1.5,
        no_mother_father_wick_max_pct=40.0,
    )

    assert diagnostics["valid"] is True
    assert diagnostics["metrics"]["pattern_mode"] == "without_mother"


def test_flappy_bird_without_mother_uses_configured_child_body_limit():
    children = [
        _candle(101.0, 103.0, 100.0, 102.0),
        _candle(102.0, 104.0, 101.0, 103.0),
    ]
    father = _candle(105.0, 108.0, 99.0, 108.0)

    diagnostics = diagnose_flappy_bird(
        None, children, father, 104.0, 103.0, 100.0,
        direction="BUY",
        use_mother_candle=False,
        no_mother_child_body_ratio=3.0,
        no_mother_child_body_max_points=0.5,
    )

    assert diagnostics["valid"] is False
    assert diagnostics["reason"] == "no_mother_child_body_above_maximum"


def test_flappy_bird_without_mother_uses_all_children_for_stop_loss():
    children = [
        _candle(101.0, 103.0, 98.0, 102.0),
        _candle(102.0, 104.0, 101.0, 103.0),
    ]
    father = _candle(105.0, 108.0, 97.0, 108.0)

    signal = analyze_flappy_bird(
        "XAUUSD", None, children, father, 104.0, 103.0, 100.0,
        direction="BUY",
        use_mother_candle=False,
        no_mother_sl_buffer_pips=2.0,
    )

    assert signal["debug"]["metrics"]["pattern_mode"] == "without_mother"
    assert signal["stop_loss"] == pytest.approx(96.8)


def test_flappy_bird_limits_both_adjacent_child_bodies_and_breakout():
    mother, children, father = _valid_parts()
    assert not detect_flappy_bird_signal(
        mother, children, father, 105.0, 103.0, 100.0,
        max_child_body_points=0.9,
    )
    children[-1]["high"] = 109.0
    assert diagnose_flappy_bird(
        mother, children, father, 105.0, 103.0, 100.0
    )["reason"] == "father_close_not_above_children"


def test_flappy_ema_cross_lifecycle_tracks_direction_and_age():
    directions, ages = calculate_flappy_ema_cross_lifecycle(
        [3.0, 2.0, 1.0, 2.0, 3.0, 4.0],
        fast_period=2,
        slow_period=3,
        window=120,
    )
    assert directions[-1] == "BUY"
    assert ages[-1] == 1


def test_multi_higher_timeframe_consensus_and_fallback_filters():
    candle = _candle(110.0, 115.0, 109.0, 114.0)
    ema = {"short": 105.0, "medium": 103.0, "long": 100.0}

    assert diagnose_flappy_higher_timeframe(
        candle, ema, "BUY", "consensus"
    )["valid"] is True
    assert diagnose_flappy_higher_timeframe(
        candle, ema, "BUY", "fallback"
    )["valid"] is True
    candle_with_lower_open = _candle(99.0, 115.0, 98.0, 114.0)
    assert diagnose_flappy_higher_timeframe(
        candle_with_lower_open, ema, "BUY", "consensus"
    )["reason"] == "higher_timeframe_open_side_failed"
    assert diagnose_flappy_higher_timeframe(
        candle_with_lower_open, ema, "BUY", "fallback"
    )["valid"] is True
    assert diagnose_flappy_higher_timeframe(
        candle, ema, "SELL", "consensus"
    )["reason"] == "higher_timeframe_ema_order_failed"
    assert diagnose_flappy_higher_timeframe(
        candle, ema, "BUY", "fallback", mode_enabled=False
    )["reason"] == "higher_timeframe_mode_disabled"


def test_current_timeframe_filter_can_be_disabled_without_changing_pattern_checks():
    mother, children, father = _valid_parts()
    assert detect_flappy_bird_signal(
        mother, children, father, 1.0, 2.0, 3.0,
        current_timeframe_filter_enabled=False,
        requested_ema_mode="consensus",
    )


def test_flappy_bird_backtest_fills_limit_and_uses_sl_first():
    mother, children, father = _valid_parts()
    rows = [
        {"time": pd.Timestamp("2026-01-01", tz="Asia/Ho_Chi_Minh"), "open": 95, "high": 96, "low": 94, "close": 95}
        for _ in range(55)
    ]
    rows.extend([
        {"time": pd.Timestamp("2026-01-02", tz="Asia/Ho_Chi_Minh"), **mother},
        *[
            {"time": pd.Timestamp("2026-01-02", tz="Asia/Ho_Chi_Minh"), **child}
            for child in children
        ],
        {"time": pd.Timestamp("2026-01-02", tz="Asia/Ho_Chi_Minh"), **father},
        {"time": pd.Timestamp("2026-01-03", tz="Asia/Ho_Chi_Minh"), "open": 108, "high": 125, "low": 99, "close": 120},
    ])
    progress_updates = []
    result = run_backtest(
        pd.DataFrame(rows), "XAUUSD", entry_type="pattern",
        strategy="flappy_bird", limit_order_candles=7,
        flappy_min_father_body_points=1.5,
        progress_callback=progress_updates.append,
    )

    assert len(result["trades"]) == 1
    assert result["trades"][0]["exit_type"] == "SL"
    assert result["trades"][0]["_debug"]["valid"] is True
    assert result["trades"][0]["_min_father_body_points"] == pytest.approx(1.5)
    assert "checks" not in result["trades"][0]["_debug"]
    assert progress_updates[0]["phase"] == "scan"
    assert progress_updates[-1]["phase"] == "finalize"
    assert progress_updates[-1]["trades"] == 1
    assert result["trades"][0]["_mother"]["time"] is not None
    assert all(child["time"] is not None for child in result["trades"][0]["_children"])
    assert {"ema13", "ema21", "ema55"} <= set(result["ohlc_data"].columns)


def _multi_flappy_rows():
    """55-candle EMA warmup + one Mother/Children/Father window + an exit
    candle, shared by the Multi Flappy Bird single-shared-loop tests below."""
    mother, children, father = _valid_parts()
    rows = [
        {"time": pd.Timestamp("2026-01-01", tz="Asia/Ho_Chi_Minh"), "open": 95, "high": 96, "low": 94, "close": 95}
        for _ in range(55)
    ]
    rows.extend([
        {"time": pd.Timestamp("2026-01-02", tz="Asia/Ho_Chi_Minh"), **mother},
        *[
            {"time": pd.Timestamp("2026-01-02", tz="Asia/Ho_Chi_Minh"), **child}
            for child in children
        ],
        {"time": pd.Timestamp("2026-01-02", tz="Asia/Ho_Chi_Minh"), **father},
        {"time": pd.Timestamp("2026-01-03", tz="Asia/Ho_Chi_Minh"), "open": 108, "high": 125, "low": 99, "close": 120},
    ])
    return rows


def _trade_signature(trade):
    return (
        trade["date"], trade["time"], trade["direction"], trade["entry"],
        trade["sl"], trade["tp"], trade["exit_type"], trade["exit_price"],
        trade["_ema_mode"],
    )


def test_multi_flappy_bird_shared_loop_matches_independent_mode_runs():
    """Running consensus+fallback together in the shared candle loop must
    produce exactly the union of running each mode alone (independent
    signal evaluation, pending fills, exits and ema_mode are unaffected by
    sharing the loop)."""
    df = pd.DataFrame(_multi_flappy_rows())
    common_kwargs = dict(
        entry_type="pattern", strategy="multi_flappy_bird",
        limit_order_candles=7, flappy_min_father_body_points=1.5,
    )

    consensus_only = run_backtest(
        df.copy(), "XAUUSD", flappy_consensus_enabled=True,
        flappy_fallback_enabled=False, **common_kwargs,
    )
    fallback_only = run_backtest(
        df.copy(), "XAUUSD", flappy_consensus_enabled=False,
        flappy_fallback_enabled=True, **common_kwargs,
    )
    both = run_backtest(
        df.copy(), "XAUUSD", flappy_consensus_enabled=True,
        flappy_fallback_enabled=True, **common_kwargs,
    )

    expected_signatures = sorted(
        [_trade_signature(t) for t in consensus_only["trades"]]
        + [_trade_signature(t) for t in fallback_only["trades"]]
    )
    actual_signatures = sorted(_trade_signature(t) for t in both["trades"])
    assert actual_signatures == expected_signatures
    assert len(both["trades"]) == len(consensus_only["trades"]) + len(fallback_only["trades"])

    expected_final_equity = (
        consensus_only["final_equity"] + fallback_only["final_equity"]
        - consensus_only["starting_equity"]
    )
    assert both["final_equity"] == pytest.approx(expected_final_equity)
    assert both["equity_curve"][-1] == pytest.approx(
        sum(t["pnl_pips"] for t in both["trades"])
    )


def test_multi_flappy_bird_reports_single_continuous_scan_progress():
    """The dataframe must be scanned once, not once per mode: scan progress
    should never reset back to an earlier candle, and only one finalize
    message should be emitted for the whole (merged) run."""
    df = pd.DataFrame(_multi_flappy_rows())
    progress_updates = []
    run_backtest(
        df, "XAUUSD", entry_type="pattern", strategy="multi_flappy_bird",
        limit_order_candles=7, flappy_min_father_body_points=1.5,
        flappy_consensus_enabled=True, flappy_fallback_enabled=True,
        progress_callback=progress_updates.append,
    )

    scan_updates = [u for u in progress_updates if u["phase"] == "scan"]
    finalize_updates = [u for u in progress_updates if u["phase"] == "finalize"]
    assert len(finalize_updates) == 1
    currents = [u["current"] for u in scan_updates]
    assert currents == sorted(currents)


def test_multi_flappy_bird_single_mode_still_reports_per_trade_finalize_message():
    """With only one mode enabled, the merge summary message is skipped and
    the original single-mode finalize wording/trade count is preserved."""
    df = pd.DataFrame(_multi_flappy_rows())
    progress_updates = []
    result = run_backtest(
        df, "XAUUSD", entry_type="pattern", strategy="multi_flappy_bird",
        limit_order_candles=7, flappy_min_father_body_points=1.5,
        flappy_consensus_enabled=True, flappy_fallback_enabled=False,
        progress_callback=progress_updates.append,
    )
    finalize_updates = [u for u in progress_updates if u["phase"] == "finalize"]
    assert len(finalize_updates) == 1
    assert finalize_updates[0]["trades"] == len(result["trades"])
    assert "hợp nhất" not in finalize_updates[0]["message"]
