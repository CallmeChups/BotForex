import json

from src.state_file import remove_bot_state, update_bot_state


def test_update_bot_state_preserves_other_bots(tmp_path):
    state_path = str(tmp_path / "bot_state.json")
    update_bot_state(state_path, {"pid": 1, "symbol": "EURUSDm"})
    update_bot_state(state_path, {"pid": 2, "symbol": "XAUUSDm"})
    update_bot_state(state_path, {"pid": 1, "symbol": "GBPUSDm"})

    with open(state_path, encoding="utf-8") as state_file:
        states = json.load(state_file)

    assert states == [
        {"pid": 2, "symbol": "XAUUSDm"},
        {"pid": 1, "symbol": "GBPUSDm"},
    ]


def test_remove_bot_state_preserves_other_bots(tmp_path):
    state_path = str(tmp_path / "bot_state.json")
    update_bot_state(state_path, {"pid": 1})
    update_bot_state(state_path, {"pid": 2})

    remove_bot_state(state_path, 1)

    with open(state_path, encoding="utf-8") as state_file:
        assert json.load(state_file) == [{"pid": 2}]
