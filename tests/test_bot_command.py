from src.bot_manager import build_bot_command


def test_command_includes_ema_flags_when_enabled():
    cmd = build_bot_command(
        "python", "bot_runner.py", "feg_ema21", "XAUUSD", "admin",
        test=False, interval=60, lot_size=0.02, sl_pips=None, rr_ratio=2.0,
        max_candles=7, ema_period=21, ema_distance_enabled=True, ema_distance_pips=5.0,
    )
    assert "--strategy" in cmd and "feg_ema21" in cmd
    assert "--test" in cmd and cmd[cmd.index("--test") + 1] == "0"
    assert cmd[cmd.index("--ema_period") + 1] == "21"
    assert cmd[cmd.index("--ema_distance_enabled") + 1] == "1"
    assert cmd[cmd.index("--ema_distance_pips") + 1] == "5.0"


def test_command_disabled_ema_flag_is_zero():
    cmd = build_bot_command(
        "python", "bot_runner.py", "feg_ema21", "XAUUSD", "admin",
        test=True, interval=60, lot_size=None, sl_pips=None, rr_ratio=None,
        max_candles=None, ema_period=None, ema_distance_enabled=False, ema_distance_pips=0.0,
    )
    assert cmd[cmd.index("--ema_distance_enabled") + 1] == "0"
    assert "--ema_period" not in cmd  # None -> not added
