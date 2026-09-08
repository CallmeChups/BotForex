from src.bot_manager import build_bot_command
from src import bot_runner


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
