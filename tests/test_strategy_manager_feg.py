from src.strategy_manager import get_strategy_parameters

def test_feg_params():
    p = get_strategy_parameters("feg_ema21")
    assert p["entry_type"] == "pattern"
    assert p["ema_period"] == 21
    assert p["ema_distance_enabled"] is False
    assert p["ema_distance_pips"] == 0
    assert p["buffer_k"] == 50
    assert p["rr_ratio"] == 2.0
    assert "XAUUSD" in p["symbols"]

def test_master_candle_defaults_to_time():
    p = get_strategy_parameters("master_candle")
    assert p["entry_type"] == "time"
    assert p["entry_time"] == "21:05"
