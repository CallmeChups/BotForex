import pandas as pd
from zoneinfo import ZoneInfo

from src import backtest
from src.utils import get_pip_value


def _candles(*, fill_bar=None, exit_bar=None, late_touch_bar=None, count=125):
    rows = []
    timezone = ZoneInfo("Asia/Ho_Chi_Minh")
    for index in range(count):
        price = 100.0
        candle = {
            "time": pd.Timestamp("2025-01-01", tz=timezone)
            + pd.Timedelta(minutes=5 * index),
            "open": price,
            "high": price + 0.05,
            "low": price - 0.05,
            "close": price,
        }
        if index == fill_bar:
            candle.update(open=100.0, high=100.3, low=100.1, close=100.1)
        if index == exit_bar:
            candle.update(open=100.1, high=102.5, low=99.0, close=101.0)
        if index == late_touch_bar:
            candle.update(open=100.0, high=100.3, low=100.0, close=100.2)
        rows.append(candle)
    return pd.DataFrame(rows)


def _patch_signal_builder(monkeypatch, df, *, capture=None):
    signal_time = df.iloc[119]["time"]
    pip_value = get_pip_value("XAUUSD")

    def build_signal(*, data, **kwargs):
        if capture is not None:
            capture.update(kwargs)
        if data.iloc[-1]["time"] != signal_time:
            return None
        entry = 100.0 + kwargs["entry_buffer_price"]
        stop = 99.8 - kwargs["sl_buffer_price"]
        target = entry + (entry - stop) * kwargs["rr_ratio"]
        return {
            "direction": "BUY",
            "entry_price": entry,
            "stop_loss": stop,
            "take_profit": target,
            "pending_expiry_candles": kwargs["pending_expiry_candles"],
        }

    monkeypatch.setattr(
        "src.swing_ema_strategy.build_swing_ema_entry_signal",
        build_signal,
    )
    return pip_value


def _run(df, **overrides):
    options = {
        "df": df,
        "symbol": "XAUUSD",
        "entry_type": "pattern",
        "strategy": "swing_ema_zigzag",
        "swing_ema_periods": {"fast": 2, "medium": 3, "slow": 4},
        "swing_ema_exit_enabled": False,
        "swing_pending_expiry_candles": 7,
        "swing_entry_buffer_pips": 2.0,
        "swing_sl_buffer_pips": 5.0,
        "rr_ratio": 2.0,
        **overrides,
    }
    return backtest.run_backtest(**options)


def test_swing_stop_fills_only_after_signal_and_keeps_entry_sl_buffers_independent(
    monkeypatch,
):
    df = _candles(fill_bar=120, exit_bar=121)
    captured = {}
    pip_value = _patch_signal_builder(monkeypatch, df, capture=captured)

    result = _run(df)

    assert captured["entry_buffer_price"] == 2.0 * pip_value
    assert captured["sl_buffer_price"] == 5.0 * pip_value
    assert result["total_trades"] == 1
    trade = result["trades"][0]
    assert trade["_entry_pos"] == 120
    assert trade["entry"] == 100.0 + 2.0 * pip_value
    assert trade["sl"] == 99.95 - 5.0 * pip_value
    assert trade["exit_type"] == "TP"


def test_swing_backtest_passes_pivot_and_parallel_ema_routes_to_signal_builder(
    monkeypatch,
):
    df = _candles()
    captured = {}
    _patch_signal_builder(monkeypatch, df, capture=captured)

    _run(
        df,
        swing_use_pivot2_for_buy=False,
        swing_use_pivot2_for_sell=True,
        swing_ema_consensus_enabled=False,
        swing_ema_fallback_enabled=True,
        swing_fallback_ema_periods={"fast": 8, "medium": 13, "slow": 21},
    )

    assert captured["use_pivot2_for_buy"] is False
    assert captured["use_pivot2_for_sell"] is True
    assert captured["ema_consensus_enabled"] is False
    assert captured["ema_fallback_enabled"] is True
    assert captured["fallback_ema_periods"] == {
        "fast": 8, "medium": 13, "slow": 21
    }


def test_swing_backtest_lookback_includes_enabled_fallback_ema_periods(monkeypatch):
    df = _candles(count=150)
    signal_bar = 135
    captured = {}

    def build_signal(*, data, **kwargs):
        if data.iloc[-1]["time"] == df.iloc[signal_bar]["time"]:
            captured["bar_count"] = len(data)
        return None

    monkeypatch.setattr(
        "src.swing_ema_strategy.build_swing_ema_entry_signal",
        build_signal,
    )

    _run(
        df,
        swing_ema_fallback_enabled=True,
        swing_fallback_ema_periods={"fast": 8, "medium": 13, "slow": 34},
    )

    assert captured["bar_count"] == 34 * 4


def test_swing_pending_order_does_not_fill_after_expiry(monkeypatch):
    df = _candles(late_touch_bar=122)
    _patch_signal_builder(monkeypatch, df)

    result = _run(df, swing_pending_expiry_candles=1)

    assert result["total_trades"] == 0
    assert result["pending_orders_at_end"] == 0


def test_expired_swing_setup_does_not_place_a_second_stop_order(monkeypatch):
    df = _candles(late_touch_bar=122)

    def build_signal(*, data, **kwargs):
        if data.iloc[-1]["time"] < df.iloc[119]["time"]:
            return None
        return {
            "direction": "BUY",
            "entry_price": 100.2,
            "stop_loss": 99.5,
            "take_profit": 101.6,
            "setup_id": "BUY:pivot-high-1:pivot-low-1",
        }

    monkeypatch.setattr(
        "src.swing_ema_strategy.build_swing_ema_entry_signal",
        build_signal,
    )

    result = _run(df, swing_pending_expiry_candles=1)

    assert result["total_trades"] == 0
    assert result["pending_orders_at_end"] == 0


def test_swing_backtest_does_not_queue_same_setup_with_changed_entry_or_sl(monkeypatch):
    df = _candles(fill_bar=121, exit_bar=122)
    signal_times = {df.iloc[119]["time"], df.iloc[120]["time"]}
    generated_signals = 0

    def build_signal(*, data, **kwargs):
        nonlocal generated_signals
        if data.iloc[-1]["time"] not in signal_times:
            return None
        generated_signals += 1
        return {
            "direction": "BUY",
            "entry_price": 100.2 + (generated_signals - 1) * 0.1,
            "stop_loss": 99.5 - generated_signals * 0.01,
            "take_profit": 101.6 - generated_signals * 0.02,
            "setup_id": "BUY:pivot-high-1:pivot-low-1",
        }

    monkeypatch.setattr(
        "src.swing_ema_strategy.build_swing_ema_entry_signal",
        build_signal,
    )

    result = _run(df, swing_sl_buffer_pips=0.0)

    assert generated_signals == 2
    assert result["total_trades"] == 1
    assert result["trades"][0]["sl"] == 99.95


def test_swing_backtest_does_not_queue_same_entry_from_different_setup_ids(monkeypatch):
    df = _candles(fill_bar=121, exit_bar=122)
    signal_times = {df.iloc[119]["time"], df.iloc[120]["time"]}
    generated_signals = 0

    def build_signal(*, data, **kwargs):
        nonlocal generated_signals
        if data.iloc[-1]["time"] not in signal_times:
            return None
        generated_signals += 1
        return {
            "direction": "SELL",
            "entry_price": 99.8,
            "stop_loss": 100.5,
            "take_profit": 98.4,
            "setup_id": f"SELL:setup-{generated_signals}",
        }

    monkeypatch.setattr(
        "src.swing_ema_strategy.build_swing_ema_entry_signal",
        build_signal,
    )

    result = _run(df)

    assert generated_signals == 2
    assert result["total_trades"] == 1


def test_swing_setup_is_not_reused_after_its_order_fills_and_trade_closes(monkeypatch):
    df = _candles(fill_bar=120, exit_bar=121)

    def build_signal(*, data, **kwargs):
        if data.iloc[-1]["time"] < df.iloc[119]["time"]:
            return None
        return {
            "direction": "BUY",
            "entry_price": 100.2,
            "stop_loss": 99.5,
            "take_profit": 101.6,
            "setup_id": "BUY:pivot-high-1:pivot-low-1",
        }

    monkeypatch.setattr(
        "src.swing_ema_strategy.build_swing_ema_entry_signal",
        build_signal,
    )

    result = _run(df)

    assert result["total_trades"] == 1
    assert result["pending_orders_at_end"] == 0


def test_swing_ema_exit_uses_close_when_tp_sl_are_not_hit(monkeypatch):
    df = _candles(fill_bar=120)
    df.loc[121, ["open", "high", "low", "close"]] = [100.0, 100.1, 99.8, 99.9]
    _patch_signal_builder(monkeypatch, df)
    monkeypatch.setattr(
        "src.swing_ema_strategy.calculate_ema_series",
        lambda close_values, period: [100.0],
    )

    result = _run(
        df,
        swing_ema_exit_enabled=True,
        swing_ema_exit_period=2,
    )

    assert result["total_trades"] == 1
    trade = result["trades"][0]
    assert trade["exit_type"] == "EMA"
    assert trade["exit_price"] == 99.9
