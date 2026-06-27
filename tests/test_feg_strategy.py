from src.feg_strategy import detect_feg_signal, analyze_feg

PIP = 0.1  # XAU

# SELL fixtures: c1 bearish, c2 bearish, body2>body1
# c1: open=101.0, close=100.5 -> bearish, body=0.5, high=101.5, low=99.5
# c2: open=101.5, close=98.0 -> bearish, body=3.5 > 0.5, high=102.0, low=97.5
#     H2=102.0 > H1=101.5 ✓, C2=98.0 < L1=99.5 ✓

_C1_SELL = {"open": 101.0, "high": 101.5, "low": 99.5, "close": 100.5}
_C2_SELL = {"open": 101.5, "high": 102.0, "low": 97.5, "close": 98.0}

# BUY fixtures: c1 bullish, c2 bullish, body2>body1
# c1: open=100.0, close=100.5 -> bullish, body=0.5, high=101.5, low=99.5
# c2: open=99.5, close=102.5 -> bullish, body=3.0 > 0.5, high=103.0, low=98.5
#     L2=98.5 < L1=99.5 ✓, C2=102.5 > H1=101.5 ✓

_C1_BUY = {"open": 100.0, "high": 101.5, "low": 99.5, "close": 100.5}
_C2_BUY = {"open": 99.5,  "high": 103.0, "low": 98.5, "close": 102.5}


# ── Basic signal ──────────────────────────────────────────────────────────────

def test_sell_signal_default_filter():
    ema2 = 97.0  # L2(97.5) > ema2(97.0) ✓
    assert detect_feg_signal(_C1_SELL, _C2_SELL, ema2, PIP) == "SELL"

def test_sell_blocked_when_low2_below_ema():
    ema2 = 98.0  # L2(97.5) NOT > ema2(98.0)
    assert detect_feg_signal(_C1_SELL, _C2_SELL, ema2, PIP) is None

def test_sell_blocked_when_body2_not_greater_than_body1():
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
    c1 = {"open": 100.0, "high": 101.5, "low": 99.5, "close": 100.5}  # body=0.5
    c2 = {"open": 99.5,  "high": 103.0, "low": 98.5, "close": 99.7}   # body=0.2 < 0.5
    assert detect_feg_signal(c1, c2, 104.0, PIP) is None

def test_no_signal_when_no_gap():
    c1 = {"open": 101.0, "high": 101.5, "low": 99.5, "close": 100.5}
    c2 = {"open": 101.5, "high": 102.0, "low": 99.8, "close": 99.8}   # C2 NOT < L1(99.5)
    assert detect_feg_signal(c1, c2, 95.0, PIP) is None


# ── h2_exceed_pips (điều kiện 4) ──────────────────────────────────────────────
# _C2_SELL: H2=102.0, H1=101.5 → margin available = 0.5 price = 5 pips

def test_sell_h2_exceed_pass():
    # need H2 > H1 + 4p*0.1=0.4 → 102.0 > 101.9 ✓
    assert detect_feg_signal(_C1_SELL, _C2_SELL, 97.0, PIP, h2_exceed_pips=4.0) == "SELL"

def test_sell_h2_exceed_blocked():
    # need H2 > H1 + 6p*0.1=0.6 → 102.0 NOT > 102.1
    assert detect_feg_signal(_C1_SELL, _C2_SELL, 97.0, PIP, h2_exceed_pips=6.0) is None

# _C2_BUY: L2=98.5, L1=99.5 → margin = 1.0 price = 10 pips

def test_buy_h2_exceed_pass():
    # need L2 < L1 - 8p*0.1=0.8 → 98.5 < 98.7 ✓
    assert detect_feg_signal(_C1_BUY, _C2_BUY, 104.0, PIP, h2_exceed_pips=8.0) == "BUY"

def test_buy_h2_exceed_blocked():
    # need L2 < L1 - 12p*0.1=1.2 → 98.5 NOT < 98.3
    assert detect_feg_signal(_C1_BUY, _C2_BUY, 104.0, PIP, h2_exceed_pips=12.0) is None


# ── c2_gap_pips (điều kiện 5) ─────────────────────────────────────────────────
# _C2_SELL: C2=98.0, L1=99.5 → gap = 1.5 price = 15 pips

def test_sell_c2_gap_pass():
    # need C2 < L1 - 10p*0.1=1.0 → 98.0 < 98.5 ✓
    assert detect_feg_signal(_C1_SELL, _C2_SELL, 97.0, PIP, c2_gap_pips=10.0) == "SELL"

def test_sell_c2_gap_blocked():
    # need C2 < L1 - 20p*0.1=2.0 → 98.0 NOT < 97.5
    assert detect_feg_signal(_C1_SELL, _C2_SELL, 97.0, PIP, c2_gap_pips=20.0) is None

# _C2_BUY: C2=102.5, H1=101.5 → gap = 1.0 price = 10 pips

def test_buy_c2_gap_pass():
    # need C2 > H1 + 8p*0.1=0.8 → 102.5 > 102.3 ✓
    assert detect_feg_signal(_C1_BUY, _C2_BUY, 104.0, PIP, c2_gap_pips=8.0) == "BUY"

def test_buy_c2_gap_blocked():
    # need C2 > H1 + 12p*0.1=1.2 → 102.5 NOT > 102.7
    assert detect_feg_signal(_C1_BUY, _C2_BUY, 104.0, PIP, c2_gap_pips=12.0) is None


# ── ema_margin_pips (điều kiện 6) ─────────────────────────────────────────────
# _C2_SELL: L2=97.5, ema2=97.0 → margin = 0.5 price = 5 pips

def test_sell_ema_margin_pass():
    # need L2 > ema + 4p*0.1=0.4 → 97.5 > 97.4 ✓
    assert detect_feg_signal(_C1_SELL, _C2_SELL, 97.0, PIP, ema_margin_pips=4.0) == "SELL"

def test_sell_ema_margin_blocked():
    # need L2 > ema + 6p*0.1=0.6 → 97.5 NOT > 97.6
    assert detect_feg_signal(_C1_SELL, _C2_SELL, 97.0, PIP, ema_margin_pips=6.0) is None

# _C2_BUY: H2=103.0, ema2=103.6 → margin = 0.6 price = 6 pips

def test_buy_ema_margin_pass():
    # need H2 < ema - 5p*0.1=0.5 → 103.0 < 103.1 ✓
    assert detect_feg_signal(_C1_BUY, _C2_BUY, 103.6, PIP, ema_margin_pips=5.0) == "BUY"

def test_buy_ema_margin_blocked():
    # need H2 < ema - 7p*0.1=0.7 → 103.0 NOT < 102.9 (ema=103.6 → threshold=102.9)
    assert detect_feg_signal(_C1_BUY, _C2_BUY, 103.6, PIP, ema_margin_pips=7.0) is None


# ── analyze_feg ───────────────────────────────────────────────────────────────

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
