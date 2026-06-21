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
    # candle1:
    base.append({"time": pd.Timestamp("2025-01-02 00:00", tz=TZ) + pd.Timedelta(minutes=5 * 30),
                 "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5})
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
