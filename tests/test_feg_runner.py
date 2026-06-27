"""Unit tests for feg_entry_decision in bot_runner."""

from src.bot_runner import feg_entry_decision

# C1 bearish (same-type rule for SELL), C2 bearish với H2>H1, C2<L1, body2>body1
C1 = {"open": 101.0, "high": 101.0, "low": 99.0, "close": 100.5}  # bearish, body=0.5
C2 = {"open": 100.8, "high": 102.0, "low": 98.5, "close": 98.0}   # bearish, body=2.8 > 0.5
EMA2 = 98.0  # L2(98.5) > EMA2(98.0) -> SELL valid


def test_entry_when_flat_and_pattern():
    sig = feg_entry_decision(
        None, C1, C2, EMA2, "XAUUSD",
        rr_ratio=2.0, buffer_k=5.0, lot_size=0.01,
        entry_mode="close", entry_percent=0.0,
        h2_exceed_pips=0.0, c2_gap_pips=0.0, ema_margin_pips=0.0,
    )
    assert sig is not None
    assert sig["direction"] == "SELL"


def test_no_signal_when_ema_too_high():
    """EMA above L2 -> SELL blocked."""
    sig = feg_entry_decision(
        None, C1, C2, 99.0, "XAUUSD",  # EMA=99.0 > L2=98.5 -> blocked
        rr_ratio=2.0, buffer_k=5.0, lot_size=0.01,
        entry_mode="close", entry_percent=0.0,
        h2_exceed_pips=0.0, c2_gap_pips=0.0, ema_margin_pips=0.0,
    )
    assert sig is None
