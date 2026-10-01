import json

from src import state_file
from src.state_file import remove_bot_state, update_bot_state


def test_swing_setup_ids_are_reserved_once_and_persisted(tmp_path):
    reserve = getattr(state_file, "reserve_swing_setup_id", None)
    load = getattr(state_file, "load_swing_setup_ids", None)
    release = getattr(state_file, "release_swing_setup_id", None)
    assert callable(reserve) and callable(load) and callable(release)

    state_path = str(tmp_path / "swing_setup_state.json")
    key = "swing_ema_zigzag:XAUUSDm:admin:212500:live"

    assert reserve(state_path, key, "BUY:pullback-1")
    assert not reserve(state_path, key, "BUY:pullback-1")
    assert load(state_path, key) == {"BUY:pullback-1"}

    release(state_path, key, "BUY:pullback-1")

    assert load(state_path, key) == set()


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
