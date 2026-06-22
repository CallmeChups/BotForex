import pandas as pd
from zoneinfo import ZoneInfo
from src.backtest import run_backtest

TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _df():
    # Entry candle at 21:05 bullish (close>open) + a few exit candles
    rows = [
        {"time": pd.Timestamp("2025-01-02 21:05", tz=TZ), "open": 100.0, "high": 101.0, "low": 99.5, "close": 100.8},
        {"time": pd.Timestamp("2025-01-02 21:10", tz=TZ), "open": 100.8, "high": 103.5, "low": 100.7, "close": 103.0},
        {"time": pd.Timestamp("2025-01-02 21:15", tz=TZ), "open": 103.0, "high": 104.0, "low": 102.5, "close": 103.5},
    ]
    return pd.DataFrame(rows)


def test_time_backtest_produces_one_bullish_trade():
    df = _df()
    res = run_backtest(
        df=df, symbol="XAUUSD", entry_hour=21, entry_minute=5,
        rr_ratio=2.0, max_candles=7, lot_mode="fixed", fixed_lot=0.01,
        buffer_k=5.0, tp_type="price_based", sl_type="close_based",
        entry_mode="close",
    )
    assert res["total_trades"] == 1
    t = res["trades"][0]
    assert t["direction"] == "BUY"
    # entry = close = 100.8 ; SL = low(99.5) - 5*0.1 = 99.0 ; risk=1.8 ; TP=100.8+3.6=104.4
    assert round(t["entry"], 4) == 100.8
    assert round(t["sl"], 4) == 99.0
    assert round(t["tp"], 4) == 104.4
    # debug fields (Task 1)
    assert "_candle" in t
    assert t["_candle"] == {"open": 100.0, "high": 101.0, "low": 99.5, "close": 100.8}
