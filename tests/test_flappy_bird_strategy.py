import pandas as pd
import pytest

from src.flappy_bird_strategy import (
    EMA_WARMUP_WINDOW,
    analyze_flappy_bird,
    calculate_flappy_ema_series,
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

    expected_initial = pd.Series(closes[:EMA_WARMUP_WINDOW]).ewm(
        span=13, adjust=False
    ).mean().iloc[-1]
    expected_rolling = pd.Series(closes[1:EMA_WARMUP_WINDOW + 1]).ewm(
        span=13, adjust=False
    ).mean().iloc[-1]

    assert values[EMA_WARMUP_WINDOW - 1] == pytest.approx(expected_initial)
    assert values[EMA_WARMUP_WINDOW] == pytest.approx(expected_rolling)


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
    )["checks"]) == 10


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
