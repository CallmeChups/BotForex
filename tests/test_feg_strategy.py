from src.feg_strategy import detect_feg_signal, analyze_feg

PIP = 0.1  # XAU

def test_sell_signal_default_filter():
    # H2>H1, C2<L1, L2>EMA21
    c1 = {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5}
    c2 = {"open": 100.8, "high": 102.0, "low": 98.5, "close": 98.0}  # H2=102>101, C2=98<99, L2=98.5
    ema2 = 98.0  # L2(98.5) > ema2(98.0)
    assert detect_feg_signal(c1, c2, ema2, PIP) == "SELL"

def test_sell_blocked_when_low2_below_ema():
    c1 = {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5}
    c2 = {"open": 100.8, "high": 102.0, "low": 98.5, "close": 98.0}
    ema2 = 99.0  # L2(98.5) NOT > ema2(99.0)
    assert detect_feg_signal(c1, c2, ema2, PIP) is None

def test_buy_signal_default_filter():
    # L2<L1, C2>H1, H2<EMA21
    c1 = {"open": 100.0, "high": 101.0, "low": 99.0, "close": 99.5}
    c2 = {"open": 99.2, "high": 102.0, "low": 98.0, "close": 101.5}  # L2=98<99, C2=101.5>101, H2=102
    ema2 = 103.0  # H2(102) < ema2(103)
    assert detect_feg_signal(c1, c2, ema2, PIP) == "BUY"

def test_buy_blocked_when_high2_above_ema():
    c1 = {"open": 100.0, "high": 101.0, "low": 99.0, "close": 99.5}
    c2 = {"open": 99.2, "high": 102.0, "low": 98.0, "close": 101.5}
    ema2 = 101.0  # H2(102) NOT < ema2(101)
    assert detect_feg_signal(c1, c2, ema2, PIP) is None

def test_no_signal_when_no_gap():
    c1 = {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}
    c2 = {"open": 100.2, "high": 102.0, "low": 99.5, "close": 99.5}  # C2=99.5 NOT < L1=99.0
    assert detect_feg_signal(c1, c2, 95.0, PIP) is None

def test_sell_distance_filter_enabled_boundary():
    c1 = {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5}
    c2 = {"open": 100.8, "high": 102.0, "low": 98.5, "close": 98.0}  # L2=98.5
    ema2 = 98.0
    # threshold 4 pips × 0.1 = 0.4 -> need L2 > 98.4 ; 98.5 > 98.4 -> SELL
    assert detect_feg_signal(c1, c2, ema2, PIP, True, 4.0) == "SELL"
    # threshold 6 pips × 0.1 = 0.6 -> need L2 > 98.6 ; 98.5 NOT > 98.6 -> None
    assert detect_feg_signal(c1, c2, ema2, PIP, True, 6.0) is None

def test_buy_distance_filter_enabled_boundary():
    c1 = {"open": 100.0, "high": 101.0, "low": 99.0, "close": 99.5}
    c2 = {"open": 99.2, "high": 102.0, "low": 98.0, "close": 101.5}  # H2=102
    ema2 = 103.0
    # threshold 5 pips × 0.1 = 0.5 -> need H2 < 102.5 ; 102 < 102.5 -> BUY
    assert detect_feg_signal(c1, c2, ema2, PIP, True, 5.0) == "BUY"
    # ema2=102.3, threshold 5 pips -> need H2 < 101.8 ; 102 NOT < 101.8 -> None
    assert detect_feg_signal(c1, c2, 102.3, PIP, True, 5.0) is None

def test_analyze_feg_sell_levels():
    c1 = {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5}
    c2 = {"open": 100.8, "high": 102.0, "low": 98.5, "close": 98.0}
    ema2 = 98.0
    sig = analyze_feg("XAUUSD", c1, c2, ema2, rr_ratio=2.0, buffer_k=5.0, lot_size=0.02)
    assert sig["direction"] == "SELL"
    assert sig["entry_price"] == 98.0
    assert round(sig["stop_loss"], 4) == 102.5   # 102 + 5*0.1
    assert round(sig["take_profit"], 4) == 89.0   # risk 4.5 -> 98 - 9
    assert round(sig["sl_pips"], 1) == 45.0
    assert sig["lot_size"] == 0.02
    assert sig["symbol"] == "XAUUSD"

def test_analyze_feg_returns_none_when_no_signal():
    c1 = {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}
    c2 = {"open": 100.2, "high": 102.0, "low": 99.5, "close": 99.5}  # C2 not < L1
    assert analyze_feg("XAUUSD", c1, c2, 95.0) is None
