import pandas as pd
from zoneinfo import ZoneInfo

from src import backtest
from src.utils import get_pip_value


def _candles(*, fill_bar=None, exit_bar=None, late_touch_bar=None):
    rows = []
    timezone = ZoneInfo("Asia/Ho_Chi_Minh")
    for index in range(125):
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
    assert trade["sl"] == 99.8 - 5.0 * pip_value
    assert trade["exit_type"] == "TP"


def test_swing_pending_order_does_not_fill_after_expiry(monkeypatch):
    df = _candles(late_touch_bar=122)
    _patch_signal_builder(monkeypatch, df)

    result = _run(df, swing_pending_expiry_candles=1)

    assert result["total_trades"] == 0
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
