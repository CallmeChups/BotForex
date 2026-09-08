from src.backtest_history import history_to_dataframe, HISTORY_COLUMNS

def test_history_includes_ema_columns():
    history = [{
        "id": "x", "timestamp": "2026-06-21T10:00:00", "strategy": "FEG Classic",
        "symbol": "XAUUSD",
        "config": {"entry_type": "pattern", "ema_period": 21, "ema_dist_enabled": True,
                   "ema_dist_pips": 5, "timeframe": "M5"},
        "summary": {"total_trades": 3, "win_rate": 66.7},
    }]
    df = history_to_dataframe(history)
    assert df.iloc[0]["Entry Type"] == "pattern"
    assert df.iloc[0]["EMA Period"] == 21
    assert "Entry Type" in HISTORY_COLUMNS["config"]
    assert "EMA Period" in HISTORY_COLUMNS["config"]


def test_history_max_candles_is_arrow_compatible_string():
    history = [
        {
            "id": "BT-1",
            "timestamp": "2026-09-08T10:00:00",
            "strategy": "flappy_bird",
            "symbol": "XAUUSD",
            "config": {"max_candles": 0},
            "summary": {},
        },
        {
            "id": "BT-2",
            "timestamp": "2026-09-08T11:00:00",
            "strategy": "feg_ema21",
            "symbol": "XAUUSD",
            "config": {"max_candles": 7},
            "summary": {},
        },
    ]

    df = history_to_dataframe(history)

    assert df["Max Candles"].tolist() == ["Off", "7"]
    assert df["Max Candles"].dtype == "object"
