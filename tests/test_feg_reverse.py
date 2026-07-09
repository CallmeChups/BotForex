# tests/test_feg_reverse.py
import pytest
from src.feg_reverse_strategy import detect_feg_reverse_signal, analyze_feg_reverse

# Minimal candle helpers
def _sell_candle(high, low, open_, close):
    return {"high": high, "low": low, "open": open_, "close": close}

def _buy_candle(high, low, open_, close):
    return {"high": high, "low": low, "open": open_, "close": close}

PIP = 0.1  # XAUUSDm pip

# SELL pattern (2 bearish candles) → FEG Reverse should return "BUY"
C1_SELL = _sell_candle(1950, 1940, 1949, 1941)  # bearish body=8
C2_SELL = _sell_candle(1955, 1930, 1954, 1931)  # bearish body=23, H2>H1, C2<L1
EMA_ABOVE = 1960.0  # L2=1930 > EMA=1960? No. Try EMA below candles

def test_sell_pattern_returns_buy():
    """FEG SELL pattern detected → reverse → direction is BUY."""
    c1 = _sell_candle(1950, 1940, 1949, 1941)
    c2 = _sell_candle(1955, 1930, 1954, 1931)
    ema = 1920.0  # L2=1930 > EMA=1920 → sell_ema_side="above_ema" passes
    sig = detect_feg_reverse_signal(c1, c2, ema, PIP, sell_ema_side="above_ema")
    assert sig == "BUY"

def test_buy_pattern_returns_sell():
    """FEG BUY pattern detected → reverse → direction is SELL."""
    c1 = _buy_candle(1950, 1940, 1941, 1949)   # bullish body=8
    c2 = _buy_candle(1970, 1935, 1936, 1969)   # bullish body=33, L2<L1, C2>H1
    ema = 1980.0  # H2=1970 < EMA=1980 → buy_ema_side="below_ema" passes
    sig = detect_feg_reverse_signal(c1, c2, ema, PIP, buy_ema_side="below_ema")
    assert sig == "SELL"

def test_no_pattern_returns_none():
    """No FEG pattern → None."""
    c1 = _sell_candle(1950, 1940, 1949, 1941)
    c2 = _buy_candle(1960, 1942, 1943, 1958)   # mixed directions
    sig = detect_feg_reverse_signal(c1, c2, 1970.0, PIP)
    assert sig is None

def test_analyze_feg_reverse_buy_direction():
    """analyze_feg_reverse on SELL pattern returns dict with direction=BUY."""
    c1 = _sell_candle(1950, 1940, 1949, 1941)
    c2 = _sell_candle(1955, 1930, 1954, 1931)
    ema = 1920.0
    result = analyze_feg_reverse(
        "XAUUSDm", c1, c2, ema,
        rr_ratio=2.0, buffer_k=5.0, lot_size=0.01,
        entry_mode="close", entry_percent=0.0,
        sell_ema_side="above_ema",
    )
    assert result is not None
    assert result["direction"] == "BUY"
    # SL must be below entry for BUY
    assert result["stop_loss"] < result["entry_price"]
    assert result["take_profit"] > result["entry_price"]

def test_wick_filter_rejects_on_pattern_side():
    """Wick filter uses pattern params, not flipped-direction params."""
    c1 = _sell_candle(1950, 1940, 1949, 1941)
    c2 = _sell_candle(1955, 1900, 1954, 1931)  # lower wick = 1931-1900 = 31, body=23
    ema = 1880.0  # L2=1900 > EMA=1880 passes above_ema
    # c2_sell_lower_wick_cmp="lt", pct=50 → reject if wick >= 50% body = 11.5 → wick=31 >= 11.5 → reject
    sig = detect_feg_reverse_signal(
        c1, c2, ema, PIP,
        sell_ema_side="above_ema",
        c2_sell_lower_wick_max_pct=50.0,
        c2_sell_lower_wick_cmp="lt",
    )
    assert sig is None
