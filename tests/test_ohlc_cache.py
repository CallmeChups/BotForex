from datetime import datetime, timezone

import pandas as pd

from src.ohlc_cache import append_candles, ensure_range, get_metadata, load_range


def _candles():
    return pd.DataFrame([
        {
            "time": datetime(2026, 1, 1, 0, minute, tzinfo=timezone.utc),
            "open": 100 + minute,
            "high": 101 + minute,
            "low": 99 + minute,
            "close": 100.5 + minute,
        }
        for minute in range(3)
    ])


def test_cache_appends_deduplicates_and_loads_local_range(tmp_path):
    path = tmp_path / "ohlc.sqlite3"
    candles = _candles()

    assert append_candles("XAUUSDm", "M1", candles, path) == 3
    assert append_candles("XAUUSDm", "M1", candles.iloc[[1]], path) == 1

    metadata = get_metadata("XAUUSDm", "M1", path)
    assert metadata["candle_count"] == 3

    loaded = load_range(
        "XAUUSDm",
        "M1",
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, 0, 1, 30, tzinfo=timezone.utc),
        path,
    )
    assert len(loaded) == 2
    assert loaded.iloc[0]["close"] == 100.5


def test_cache_metadata_tracks_only_distinct_candles(tmp_path):
    path = tmp_path / "ohlc.sqlite3"
    candles = _candles().drop(index=1)
    append_candles("XAUUSDm", "M1", candles, path)

    metadata = get_metadata("XAUUSDm", "M1", path)

    assert metadata["candle_count"] == 2


def test_ensure_range_does_not_fetch_active_candle(tmp_path, monkeypatch):
    path = tmp_path / "ohlc.sqlite3"
    candles = _candles()
    append_candles("XAUUSDm", "M1", candles, path)

    def fail_fetch(*args, **kwargs):
        raise AssertionError("active candle must not trigger an MT5 fetch")

    monkeypatch.setattr("src.ohlc_cache._fetch_mt5_range", fail_fetch)
    loaded, error, source = ensure_range(
        "XAUUSDm",
        "M1",
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, 0, 2, 45, tzinfo=timezone.utc),
        {},
        path,
    )

    assert error is None
    assert source == "cache"
    assert len(loaded) == 2


def test_ensure_range_ignores_leading_daily_session_break(tmp_path, monkeypatch):
    path = tmp_path / "ohlc.sqlite3"
    candles = pd.DataFrame([{
        "time": datetime(2026, 6, 1, 22, 0, tzinfo=timezone.utc),
        "open": 100,
        "high": 101,
        "low": 99,
        "close": 100.5,
    }])
    append_candles("XAUUSDm", "M5", candles, path)

    def fail_fetch(*args, **kwargs):
        return None, "normal session break"

    monkeypatch.setattr("src.ohlc_cache._fetch_mt5_range", fail_fetch)
    loaded, error, source = ensure_range(
        "XAUUSDm",
        "M5",
        datetime(2026, 6, 1, 17, 0, tzinfo=timezone.utc),
        datetime(2026, 6, 2, 0, 0, tzinfo=timezone.utc),
        {},
        path,
    )

    assert error is None
    assert source == "cache"
    assert len(loaded) == 1
