import pytest
from datetime import time
import pandas as pd
from zoneinfo import ZoneInfo

from src.utils import _in_time_window

_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _ts(hour, minute):
    """Helper: pd.Timestamp at given HCM local hour:minute."""
    return pd.Timestamp(f"2026-01-15 {hour:02d}:{minute:02d}:00", tz=_TZ)


def test_in_time_window_inside():
    assert _in_time_window(_ts(10, 30), time(9, 0), time(12, 0)) is True


def test_in_time_window_before_start():
    assert _in_time_window(_ts(8, 59), time(9, 0), time(12, 0)) is False


def test_in_time_window_after_end():
    assert _in_time_window(_ts(12, 1), time(9, 0), time(12, 0)) is False


def test_in_time_window_at_start_boundary():
    assert _in_time_window(_ts(9, 0), time(9, 0), time(12, 0)) is True


def test_in_time_window_at_end_boundary():
    assert _in_time_window(_ts(12, 0), time(9, 0), time(12, 0)) is True


def test_in_time_window_default_no_filter():
    # Default 00:00-23:59 should pass any time
    assert _in_time_window(_ts(0, 0), time(0, 0), time(23, 59)) is True
    assert _in_time_window(_ts(23, 58), time(0, 0), time(23, 59)) is True
    assert _in_time_window(_ts(23, 59), time(0, 0), time(23, 59)) is True


def test_in_time_window_utc_input_converts_to_hcm():
    # 02:00 UTC = 09:00 HCM (UTC+7) - should be inside 09:00-12:00 window
    ts_utc = pd.Timestamp("2026-01-15 02:00:00", tz="UTC")
    assert _in_time_window(ts_utc, time(9, 0), time(12, 0)) is True
