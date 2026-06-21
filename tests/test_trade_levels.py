from src.utils import compute_trade_levels

PIP = 0.1  # XAU


def test_sell_levels_close_mode():
    # candle2: high=102, low=98.5, close=98.0, open=100.8
    c2 = {"open": 100.8, "high": 102.0, "low": 98.5, "close": 98.0}
    r = compute_trade_levels("SELL", c2, "close", 0.0, buffer_k=5.0, rr_ratio=2.0, pip_value=PIP)
    # SL = high + 5*0.1 = 102.5 ; entry = close = 98.0
    assert round(r["stop_loss"], 4) == 102.5
    assert r["entry_price"] == 98.0
    # risk = 102.5 - 98.0 = 4.5 ; TP = 98.0 - 9.0 = 89.0
    assert round(r["take_profit"], 4) == 89.0
    # sl_pips = (102.5 - 98.0)/0.1 = 45.0
    assert round(r["sl_pips"], 1) == 45.0


def test_buy_levels_close_mode():
    c2 = {"open": 99.2, "high": 102.0, "low": 98.0, "close": 101.5}
    r = compute_trade_levels("BUY", c2, "close", 0.0, buffer_k=5.0, rr_ratio=2.0, pip_value=PIP)
    # SL = low - 5*0.1 = 97.5 ; entry = 101.5 ; risk = 4.0 ; TP = 101.5 + 8.0 = 109.5
    assert round(r["stop_loss"], 4) == 97.5
    assert round(r["take_profit"], 4) == 109.5
    assert round(r["sl_pips"], 1) == 40.0


def test_buy_levels_range_percent():
    # body = |close-open| = |101.5-99.2| = 2.3 ; entry = close - 50%*body = 101.5 - 1.15 = 100.35
    c2 = {"open": 99.2, "high": 102.0, "low": 98.0, "close": 101.5}
    r = compute_trade_levels("BUY", c2, "range_percent", 50.0, buffer_k=5.0, rr_ratio=2.0, pip_value=PIP)
    assert round(r["entry_price"], 4) == 100.35
