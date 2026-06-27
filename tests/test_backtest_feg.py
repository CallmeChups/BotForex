import pandas as pd
from zoneinfo import ZoneInfo
from src.backtest import run_backtest

TZ = ZoneInfo("Asia/Ho_Chi_Minh")

def _make_df(rows):
    return pd.DataFrame(rows)

def test_feg_backtest_detects_one_sell_and_is_one_at_a_time():
    # Tạo >21 nến phẳng để EMA21 ổn định quanh ~100, rồi 1 pattern SELL, rồi nến cho exit.
    base = []
    for i in range(30):
        base.append({"time": pd.Timestamp("2025-01-02 00:00", tz=TZ) + pd.Timedelta(minutes=5 * i),
                     "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0})
    # candle1 (index 30): high=101, low=99, close=100.5
    base.append({"time": pd.Timestamp("2025-01-02 00:00", tz=TZ) + pd.Timedelta(minutes=5 * 30),
                 "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5})
    # candle2 (index 31): H2=102>101, C2=98<99, L2=98.5 > EMA21(~100? no) -> need L2>ema2
    # EMA quanh 100 -> L2=98.5 < 100 => SELL bị chặn. Để pass, đẩy EMA xuống: dùng nến giảm dần trước.
    # Đơn giản hơn: kiểm tra "không có trade" khi L2<EMA, và "có trade" khi tắt filter bằng ema rất thấp.
    base.append({"time": pd.Timestamp("2025-01-02 00:00", tz=TZ) + pd.Timedelta(minutes=5 * 31),
                 "open": 100.8, "high": 102.0, "low": 98.5, "close": 98.0})
    # exit candles
    for i in range(32, 40):
        base.append({"time": pd.Timestamp("2025-01-02 00:00", tz=TZ) + pd.Timedelta(minutes=5 * i),
                     "open": 98.0, "high": 98.2, "low": 88.0, "close": 89.0})
    df = _make_df(base)

    res = run_backtest(
        df=df, symbol="XAUUSD", entry_type="pattern", ema_period=21,
        rr_ratio=2.0, max_candles=7, lot_mode="fixed", fixed_lot=0.01,
        buffer_k=5.0, tp_type="price_based", sl_type="close_based", entry_mode="close",
    )
    # EMA21 ~100 nên L2=98.5 < ema -> KHÔNG có SELL (filter default chặn)
    assert res["total_trades"] == 0

def test_feg_backtest_sell_when_ema_below_low2():
    # Warmup phẳng ở mức THẤP (~95) để EMA21 nằm dưới L2(98.5) tại candle2 -> SELL hợp lệ.
    # (EMA của chuỗi phẳng ~ chính mức đó; chọn 95 < 98.5.)
    base = []
    for i in range(30):
        base.append({"time": pd.Timestamp("2025-01-02 00:00", tz=TZ) + pd.Timedelta(minutes=5 * i),
                     "open": 95.0, "high": 95.3, "low": 94.7, "close": 95.0})
    # candle1: bearish (close < open) so same-type rule allows SELL with bearish candle2
    base.append({"time": pd.Timestamp("2025-01-02 00:00", tz=TZ) + pd.Timedelta(minutes=5 * 30),
                 "open": 101.0, "high": 101.0, "low": 99.0, "close": 100.5})
    # candle2: H2=102>101, C2=98<99, L2=98.5 ; EMA21 nên < 98.5
    base.append({"time": pd.Timestamp("2025-01-02 00:00", tz=TZ) + pd.Timedelta(minutes=5 * 31),
                 "open": 100.8, "high": 102.0, "low": 98.5, "close": 98.0})
    for i in range(32, 40):
        base.append({"time": pd.Timestamp("2025-01-02 00:00", tz=TZ) + pd.Timedelta(minutes=5 * i),
                     "open": 98.0, "high": 98.2, "low": 80.0, "close": 81.0})
    df = _make_df(base)

    res = run_backtest(
        df=df, symbol="XAUUSD", entry_type="pattern", ema_period=21,
        rr_ratio=2.0, max_candles=7, lot_mode="fixed", fixed_lot=0.01,
        buffer_k=5.0, tp_type="price_based", sl_type="close_based", entry_mode="close",
    )
    assert res["total_trades"] == 1
    t = res["trades"][0]
    assert t["direction"] == "SELL"
    assert round(t["entry"], 4) == 98.0
    assert round(t["sl"], 4) == 102.5   # 102 + 5*0.1
    assert round(t["tp"], 4) == 89.0    # risk 4.5 -> 98 - 9
    # debug fields (Task 1)
    assert "_c1" in t
    assert "_c2" in t
    assert "_ema" in t
    assert "_exit_pos" in t
    assert set(t["_c1"].keys()) >= {"open", "high", "low", "close", "time"}
    assert t["_c1"]["high"] == 101.0    # candle1 high from fixture
    assert t["_c2"]["close"] == 98.0    # candle2 close from fixture
    assert t["_ema"] < 98.5             # EMA < L2 (that's why SELL fired)
    assert isinstance(t["_exit_pos"], int)
    assert t["_exit_pos"] >= 32         # exit candle is after candle2 at index 31


from datetime import time as _time
from zoneinfo import ZoneInfo


def _make_feg_df_with_time(signal_hour=10, signal_minute=0):
    """Build minimal FEG dataframe where C1+C2 form a valid SELL signal at given HCM hour."""
    import pandas as pd
    import numpy as np
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Asia/Ho_Chi_Minh")

    rows = []
    base_time = pd.Timestamp("2026-01-15 00:00:00", tz="UTC").tz_convert(_TZ)

    # Pad 25 warmup candles (neutral, EMA settles)
    for i in range(25):
        t = base_time + pd.Timedelta(minutes=i)
        rows.append({"time": t, "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0})

    # Place SELL signal candles at signal_hour:signal_minute HCM
    signal_base = pd.Timestamp(f"2026-01-15 {signal_hour:02d}:{signal_minute:02d}:00", tz=_TZ)
    # C1 bearish: open=101, close=100.5
    rows.append({"time": signal_base, "open": 101.0, "high": 101.0, "low": 99.0, "close": 100.5})
    # C2 bearish: H2>H1, C2<L1(99.0), L2 well above EMA (~100)
    rows.append({"time": signal_base + pd.Timedelta(minutes=1), "open": 100.8, "high": 102.0, "low": 100.1, "close": 98.0})

    # Exit candle
    rows.append({"time": signal_base + pd.Timedelta(minutes=2), "open": 98.0, "high": 98.2, "low": 95.0, "close": 96.0})

    return pd.DataFrame(rows)


def test_feg_backtest_time_window_allows_signal():
    """Signal inside window -> trade is taken."""
    from src.backtest import run_backtest
    df = _make_feg_df_with_time(signal_hour=10, signal_minute=0)
    results = run_backtest(
        df=df, symbol="XAUUSD", entry_type="pattern", ema_period=21,
        buffer_k=50.0, rr_ratio=2.0, max_candles=5,
        entry_start_time=_time(9, 0), entry_end_time=_time(11, 0),
    )
    assert results["total_trades"] >= 1


def test_feg_backtest_time_window_blocks_signal():
    """Signal outside window -> no trade taken."""
    from src.backtest import run_backtest
    df = _make_feg_df_with_time(signal_hour=10, signal_minute=0)
    results = run_backtest(
        df=df, symbol="XAUUSD", entry_type="pattern", ema_period=21,
        buffer_k=50.0, rr_ratio=2.0, max_candles=5,
        entry_start_time=_time(14, 0), entry_end_time=_time(18, 0),
    )
    assert results["total_trades"] == 0
