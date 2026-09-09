from src.bot_manager import build_bot_command
from src import bot_runner
from src import bot_manager


def test_command_includes_h2_flags():
    cmd = build_bot_command(
        "python", "bot_runner.py", "feg_ema21", "XAUUSD", "admin",
        test=False, interval=60, lot_size=0.02, sl_pips=None, rr_ratio=2.0,
        max_candles=7, ema_period=21,
        h2_exceed_pips=5.0, c2_gap_pips=2.0, ema_margin_pips=1.0,
    )
    assert "--strategy" in cmd and "feg_ema21" in cmd
    assert "--test" in cmd and cmd[cmd.index("--test") + 1] == "0"
    assert cmd[cmd.index("--ema_period") + 1] == "21"
    assert cmd[cmd.index("--h2_exceed_pips") + 1] == "5.0"
    assert cmd[cmd.index("--c2_gap_pips") + 1] == "2.0"
    assert cmd[cmd.index("--ema_margin_pips") + 1] == "1.0"


def test_command_default_h2_flags_are_zero():
    cmd = build_bot_command(
        "python", "bot_runner.py", "feg_ema21", "XAUUSD", "admin",
        test=True, interval=60, lot_size=None, sl_pips=None, rr_ratio=None,
        max_candles=None, ema_period=None,
    )
    assert cmd[cmd.index("--h2_exceed_pips") + 1] == "0.0"
    assert "--ema_period" not in cmd  # None -> not added


def test_windows_pid_check_requires_exact_pid(monkeypatch):
    monkeypatch.setattr(bot_manager.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        bot_manager.subprocess,
        "check_output",
        lambda *args, **kwargs: b'"Image Name","PID","Session Name","Session#","Mem Usage"\r\n'
        b'"python.exe","12345","Console","1","10,000 K"\r\n',
    )

    assert bot_manager.is_process_running(12345) is True
    assert bot_manager.is_process_running(2345) is False


def test_bot_process_check_requires_matching_identity(monkeypatch):
    bot = {
        "pid": 12345,
        "strategy": "flappy_bird",
        "symbol": "XAUUSDm",
        "user": "user",
    }
    monkeypatch.setattr(bot_manager, "is_process_running", lambda pid: True)
    monkeypatch.setattr(
        bot_manager,
        "_get_process_command_line",
        lambda pid: (
            "python src/bot_runner.py --strategy flappy_bird "
            "--symbol XAUUSDm --user user"
        ),
    )

    assert bot_manager.is_bot_process_running(bot) is True
    monkeypatch.setattr(
        bot_manager,
        "_get_process_command_line",
        lambda pid: "python unrelated.py",
    )
    assert bot_manager.is_bot_process_running(bot) is False


def test_stop_bot_notifies_with_saved_bot_metadata(monkeypatch):
    bots = [{
        "pid": 12345,
        "strategy": "flappy_bird",
        "symbol": "XAUUSD",
        "user": "admin",
    }]
    notifications = []
    monkeypatch.setattr(bot_manager, "is_process_running", lambda pid: True)
    monkeypatch.setattr(bot_manager, "load_bots", lambda: bots.copy())
    monkeypatch.setattr(bot_manager, "save_bots", lambda value: None)
    monkeypatch.setattr(bot_manager, "_remove_bot_state", lambda pid: None)
    monkeypatch.setattr(bot_manager, "_notify_bot_stopped", notifications.append)
    monkeypatch.setattr(bot_manager.platform, "system", lambda: "Linux")
    monkeypatch.setattr(bot_manager.signal, "SIGKILL", 9, raising=False)
    monkeypatch.setattr(bot_manager.os, "kill", lambda *args: None)
    monkeypatch.setattr(bot_manager.time_mod, "sleep", lambda seconds: None)

    success, message = bot_manager.stop_bot(12345)

    assert success is True
    assert message == "Bot stopped (PID 12345)"
    assert notifications == [bots[0]]


def test_command_supports_subsecond_interval():
    cmd = build_bot_command(
        "python", "bot_runner.py", "flappy_bird", "XAUUSD", "admin",
        test=True, interval=0.1,
    )
    assert cmd[cmd.index("--interval") + 1] == "0.1"


def test_command_includes_flappy_father_body_threshold():
    cmd = build_bot_command(
        "python", "bot_runner.py", "flappy_bird", "XAUUSD", "admin",
        test=True, interval=1, min_father_body_points=3.5,
    )
    assert cmd[cmd.index("--min_father_body_points") + 1] == "3.5"


def test_command_includes_flappy_child_count_range():
    cmd = build_bot_command(
        "python", "bot_runner.py", "flappy_bird", "XAUUSD", "admin",
        test=True, interval=1, min_child_candles=3, max_child_candles=6,
    )
    assert cmd[cmd.index("--min_child_candles") + 1] == "3"
    assert cmd[cmd.index("--max_child_candles") + 1] == "6"


def test_command_includes_flappy_ema_groups():
    cmd = bot_manager.build_bot_command(
        "python", "bot_runner.py", "flappy_bird", "XAUUSD", "admin",
        test=True, interval=1,
        flappy_consensus_short=8, flappy_consensus_medium=21,
        flappy_consensus_long=55, flappy_fallback_short=5,
        flappy_fallback_medium=13, flappy_fallback_long=34,
    )
    for flag, value in (
        ("--flappy_consensus_short", "8"),
        ("--flappy_consensus_medium", "21"),
        ("--flappy_consensus_long", "55"),
        ("--flappy_fallback_short", "5"),
        ("--flappy_fallback_medium", "13"),
        ("--flappy_fallback_long", "34"),
    ):
        assert cmd[cmd.index(flag) + 1] == value


def test_command_includes_mother_coverage_switch():
    cmd = build_bot_command(
        "python", "bot_runner.py", "flappy_bird", "XAUUSD", "admin",
        test=True, interval=1, mother_coverage_enabled=False,
    )
    assert cmd[cmd.index("--mother_coverage_enabled") + 1] == "0"


def test_ui_managed_command_enables_manager_stop_notification():
    cmd = build_bot_command(
        "python", "bot_runner.py", "flappy_bird", "XAUUSD", "admin",
        test=False, interval=1,
    )
    assert cmd[cmd.index("--managed_by_ui") + 1] == "1"


def test_send_telegram_logs_api_rejection(monkeypatch, caplog):
    class RejectedResponse:
        ok = False
        status_code = 400
        text = '{"ok":false,"description":"chat not found"}'

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")
    monkeypatch.setattr(bot_runner.requests, "post", lambda *args, **kwargs: RejectedResponse())

    with caplog.at_level("ERROR", logger="bot_runner"):
        assert bot_runner.send_telegram("test") is False

    assert "Telegram rejected message: HTTP 400" in caplog.text


def test_command_includes_timeframe_override():
    cmd = build_bot_command(
        "python", "bot_runner.py", "flappy_bird", "XAUUSD", "admin",
        test=False, interval=60, timeframe="M15",
    )
    assert cmd[cmd.index("--timeframe") + 1] == "M15"


def test_command_be_flags():
    cmd = build_bot_command(
        "python", "bot_runner.py", "feg_ema21", "XAUUSD", "admin",
        test=False, interval=60, be_enabled=True, be_r=1.5,
    )
    assert cmd[cmd.index("--be_enabled") + 1] == "1"
    assert cmd[cmd.index("--be_r") + 1] == "1.5"


def test_command_be_disabled_by_default():
    cmd = build_bot_command(
        "python", "bot_runner.py", "feg_ema21", "XAUUSD", "admin",
        test=True, interval=60,
    )
    assert cmd[cmd.index("--be_enabled") + 1] == "0"
    assert cmd[cmd.index("--be_r") + 1] == "1.0"
