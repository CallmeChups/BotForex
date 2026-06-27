from src.feg_strategy import detect_feg_signal, analyze_feg

PIP = 0.1  # XAU

# SELL fixtures: c1 bearish (open>close), c2 bearish (open>close), body2>body1
# H2>H1, C2<L1, L2>EMA21
# c1: open=101.0, close=100.5 -> bearish, body=0.5, high=101.5, low=99.5
# c2: open=101.5, close=98.0 -> bearish, body=3.5 > 0.5, high=102.0, low=97.5
#     H2=102.0 > H1=101.5 ✓, C2=98.0 < L1=99.5 ✓

_C1_SELL = {"open": 101.0, "high": 101.5, "low": 99.5, "close": 100.5}
_C2_SELL = {"open": 101.5, "high": 102.0, "low": 97.5, "close": 98.0}

# BUY fixtures: c1 bullish (close>open), c2 bullish (close>open), body2>body1
# L2<L1, C2>H1, H2<EMA21
# c1: open=100.0, close=100.5 -> bullish, body=0.5, high=101.5, low=99.5
# c2: open=99.5, close=102.5 -> bullish, body=3.0 > 0.5, high=103.0, low=98.5
#     L2=98.5 < L1=99.5 ✓, C2=102.5 > H1=101.5 ✓

_C1_BUY = {"open": 100.0, "high": 101.5, "low": 99.5, "close": 100.5}
_C2_BUY = {"open": 99.5,  "high": 103.0, "low": 98.5, "close": 102.5}


def test_sell_signal_default_filter():
    ema2 = 97.0  # L2(97.5) > ema2(97.0) ✓
    assert detect_feg_signal(_C1_SELL, _C2_SELL, ema2, PIP) == "SELL"

def test_sell_blocked_when_low2_below_ema():
    ema2 = 98.0  # L2(97.5) NOT > ema2(98.0)
    assert detect_feg_signal(_C1_SELL, _C2_SELL, ema2, PIP) is None

def test_sell_blocked_when_body2_not_greater_than_body1():
    # c2 body = 0.3 < c1 body = 0.5
    c1 = {"open": 101.0, "high": 101.5, "low": 99.5, "close": 100.5}  # body=0.5
    c2 = {"open": 101.5, "high": 102.0, "low": 97.5, "close": 101.2}  # body=0.3 < 0.5
    assert detect_feg_signal(c1, c2, 97.0, PIP) is None

def test_buy_signal_default_filter():
    ema2 = 104.0  # H2(103.0) < ema2(104.0) ✓
    assert detect_feg_signal(_C1_BUY, _C2_BUY, ema2, PIP) == "BUY"

def test_buy_blocked_when_high2_above_ema():
    ema2 = 102.0  # H2(103.0) NOT < ema2(102.0)
    assert detect_feg_signal(_C1_BUY, _C2_BUY, ema2, PIP) is None

def test_buy_blocked_when_body2_not_greater_than_body1():
    # c2 body = 0.2 < c1 body = 0.5
    c1 = {"open": 100.0, "high": 101.5, "low": 99.5, "close": 100.5}  # body=0.5
    c2 = {"open": 99.5,  "high": 103.0, "low": 98.5, "close": 99.7}   # body=0.2 < 0.5
    assert detect_feg_signal(c1, c2, 104.0, PIP) is None

def test_no_signal_when_no_gap():
    # C2 does not cross L1 (SELL) or H1 (BUY)
    c1 = {"open": 101.0, "high": 101.5, "low": 99.5, "close": 100.5}
    c2 = {"open": 101.5, "high": 102.0, "low": 99.8, "close": 99.8}   # C2 NOT < L1(99.5)
    assert detect_feg_signal(c1, c2, 95.0, PIP) is None

def test_sell_distance_filter_enabled_boundary():
    ema2 = 97.0  # L2=97.5
    # threshold 4 pips × 0.1 = 0.4 -> need L2 > 97.4 ; 97.5 > 97.4 -> SELL
    assert detect_feg_signal(_C1_SELL, _C2_SELL, ema2, PIP, True, 4.0) == "SELL"
    # threshold 6 pips × 0.1 = 0.6 -> need L2 > 97.6 ; 97.5 NOT > 97.6 -> None
    assert detect_feg_signal(_C1_SELL, _C2_SELL, ema2, PIP, True, 6.0) is None

def test_buy_distance_filter_enabled_boundary():
    ema2 = 103.6  # H2=103.0
    # threshold 5 pips × 0.1 = 0.5 -> need H2 < 103.1 ; 103.0 < 103.1 -> BUY
    assert detect_feg_signal(_C1_BUY, _C2_BUY, ema2, PIP, True, 5.0) == "BUY"
    # ema2=103.4, threshold 5 -> need H2 < 102.9 ; 103.0 NOT < 102.9 -> None
    assert detect_feg_signal(_C1_BUY, _C2_BUY, 103.4, PIP, True, 5.0) is None

def test_analyze_feg_sell_levels():
    ema2 = 97.0
    sig = analyze_feg("XAUUSD", _C1_SELL, _C2_SELL, ema2, rr_ratio=2.0, buffer_k=5.0, lot_size=0.02)
    assert sig["direction"] == "SELL"
    assert sig["entry_price"] == 98.0
    assert round(sig["stop_loss"], 4) == 102.5   # high(102.0) + 5*0.1
    assert round(sig["take_profit"], 4) == 89.0   # risk=4.5 -> 98 - 9.0
    assert round(sig["sl_pips"], 1) == 45.0
    assert sig["lot_size"] == 0.02
    assert sig["symbol"] == "XAUUSD"

def test_analyze_feg_returns_none_when_no_signal():
    c1 = {"open": 101.0, "high": 101.5, "low": 99.5, "close": 100.5}
    c2 = {"open": 101.5, "high": 102.0, "low": 99.8, "close": 99.8}  # C2 not < L1
    assert analyze_feg("XAUUSD", c1, c2, 95.0) is None
