import pytest

from src import strategy_manager
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


def test_swing_ema_zigzag_params_have_runtime_defaults():
    params = get_strategy_parameters("swing_ema_zigzag")

    assert params["entry_type"] == "pattern"
    assert params["swing_ema_periods"] == {"fast": 13, "medium": 21, "slow": 55}
    assert params["zigzag_depth"] == 3
    assert params["zigzag_deviation_points"] == 3.0
    assert params["zigzag_back_step"] == 3
    assert params["min_structure_candles"] == 10
    assert params["max_structure_candles"] == 20
    assert params["ema_cross_window_candles"] == 15
    assert params["use_pivot2_for_buy"] is True
    assert params["use_pivot2_for_sell"] is True
    assert params["ema_consensus_enabled"] is True
    assert params["ema_fallback_enabled"] is False
    assert params["swing_fallback_ema_periods"] == {
        "fast": 13, "medium": 21, "slow": 55
    }
    assert params["ema_exit_enabled"] is True
    assert params["ema_exit_period"] == 21
    assert params["pending_expiry_candles"] == 7
    assert params["max_pending_orders_per_symbol"] == 0
    assert params["sl_buffer_pips"] == 5.0
    assert params["entry_buffer_pips"] == 2.0
    assert params["magic"] == 212500


def test_swing_fallback_defaults_off_when_config_omits_switch(monkeypatch):
    monkeypatch.setattr(
        strategy_manager,
        "get_strategy",
        lambda _strategy_id: {
            "id": "swing_ema_zigzag",
            "entry": {"type": "pattern", "ema_periods": [13, 21, 55]},
            "exit": {"ema_exit": {}},
            "parameters": {},
        },
    )

    params = get_strategy_parameters("swing_ema_zigzag")

    assert params["ema_fallback_enabled"] is False


def test_swing_ema_zigzag_rejects_invalid_pending_limit(monkeypatch):
    monkeypatch.setattr(
        strategy_manager,
        "get_strategy",
        lambda _strategy_id: {
            "id": "swing_ema_zigzag",
            "entry": {
                "type": "pattern",
                "ema_periods": [13, 21, 55],
                "zigzag": {"depth": 3, "deviation_points": 3, "back_step": 3},
                "min_structure_candles": 10,
                "max_structure_candles": 20,
                "ema_cross_window_candles": 15,
            },
            "exit": {"ema_exit": {"enabled": True, "period": 21}},
            "parameters": {"pending_expiry_candles": 7, "max_pending_orders_per_symbol": -1},
            "symbols": ["XAUUSD"],
        },
    )

    with pytest.raises(ValueError, match="max_pending_orders_per_symbol"):
        get_strategy_parameters("swing_ema_zigzag")


def test_swing_ema_zigzag_rejects_negative_entry_buffer(monkeypatch):
    monkeypatch.setattr(
        strategy_manager,
        "get_strategy",
        lambda _strategy_id: {
            "id": "swing_ema_zigzag",
            "entry": {
                "type": "pattern",
                "ema_periods": [13, 21, 55],
                "zigzag": {"depth": 3, "deviation_points": 3, "back_step": 3},
                "min_structure_candles": 10,
                "max_structure_candles": 20,
                "ema_cross_window_candles": 15,
            },
            "exit": {"ema_exit": {"enabled": True, "period": 21}},
            "parameters": {"entry_buffer_pips": -1},
            "symbols": ["XAUUSD"],
        },
    )

    with pytest.raises(ValueError, match="entry_buffer_pips"):
        get_strategy_parameters("swing_ema_zigzag")
