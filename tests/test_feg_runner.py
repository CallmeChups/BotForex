"""Unit tests for feg_entry_decision in bot_runner."""

from src.bot_runner import feg_entry_decision

C1 = {"open": 101.0, "high": 101.0, "low": 99.0, "close": 100.5}  # bearish: c<o
C2 = {"open": 100.8, "high": 102.0, "low": 98.5, "close": 98.0}  # bearish: c<o; SELL khi ema2<98.5
EMA2 = 98.0


def test_entry_when_flat_and_pattern():
    sig = feg_entry_decision(
        None, C1, C2, EMA2, "XAUUSD",
        rr_ratio=2.0, buffer_k=5.0, lot_size=0.01,
        entry_mode="close", entry_percent=0.0,
        ema_distance_enabled=False, ema_distance_pips=0.0,
    )
    assert sig is not None
    assert sig["direction"] == "SELL"


def test_no_entry_when_already_in_trade():
    active = {"direction": "SELL", "entry": 98.0}
    sig = feg_entry_decision(
        active, C1, C2, EMA2, "XAUUSD",
        rr_ratio=2.0, buffer_k=5.0, lot_size=0.01,
        entry_mode="close", entry_percent=0.0,
        ema_distance_enabled=False, ema_distance_pips=0.0,
    )
    assert sig is None  # 1 lệnh tại 1 thời điểm
