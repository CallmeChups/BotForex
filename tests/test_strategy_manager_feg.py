from src.strategy_manager import get_strategy_parameters, is_flappy_strategy

def test_feg_params():
    p = get_strategy_parameters("feg_ema21")
    assert p["entry_type"] == "pattern"
    assert p["ema_period"] == 21
    assert p["h2_exceed_pips"] == 0.0
    assert p["c2_gap_pips"] == 0.0
    assert p["ema_margin_pips"] == 0.0
    assert p["buffer_k"] == 50
    assert p["rr_ratio"] == 2.0
    assert "XAUUSD" in p["symbols"]

def test_master_candle_defaults_to_time():
    p = get_strategy_parameters("master_candle")
    assert p["entry_type"] == "time"
    assert p["entry_time"] == "21:05"


def test_multi_flappy_bird_is_independent_flappy_strategy_clone():
    params = get_strategy_parameters("multi_flappy_bird")

    assert is_flappy_strategy("multi_flappy_bird")
    assert params["entry_type"] == "pattern"
    assert params["ema_consensus"] == {"short": 13, "medium": 21, "long": 55}
    assert params["ema_fallback"] == {"short": 13, "medium": 21, "long": 55}
    assert params["magic"] == 212401
