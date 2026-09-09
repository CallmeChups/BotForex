"""
Bot Manager Module

Start, stop, and list trading bot processes.
Works on Windows (subprocess) and Linux (nohup).
"""

import os
import sys
import subprocess
import json
import signal
import time as time_mod
import csv
from io import StringIO
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
import platform

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
BOTS_FILE = "data/running_bots.json"
BOT_SCRIPT = "src/bot_runner.py"


def get_bots_file() -> str:
    """Get bots file path"""
    os.makedirs("data", exist_ok=True)
    return BOTS_FILE


def load_bots() -> list:
    """Load running bots from file"""
    bots_file = get_bots_file()
    if os.path.exists(bots_file):
        try:
            with open(bots_file, 'r') as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_bots(bots: list):
    """Save bots to file"""
    bots_file = get_bots_file()
    with open(bots_file, 'w') as f:
        json.dump(bots, f, indent=2)


def _remove_bot_state(pid: int):
    """Remove pid entry from data/bot_state.json when bot stops."""
    state_path = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "bot_state.json")
    )
    if not os.path.exists(state_path):
        return
    try:
        from src.state_file import remove_bot_state
        remove_bot_state(state_path, pid)
    except OSError:
        pass


def _notify_bot_stopped(bot: dict) -> None:
    """Notify the main Telegram chat when a bot is stopped from the UI."""
    strategy_labels = {
        "flappy_bird": "Flappy Bird",
        "feg_ema21": "FEG EMA21",
        "feg_stop_order": "FEG Stop Order",
        "feg_reverse": "FEG Reverse",
    }
    label = strategy_labels.get(bot.get("strategy"), bot.get("strategy", "Bot"))
    try:
        from src.bot_runner import send_telegram
        send_telegram(
            f"⏹ <b>{label} Bot Stopped</b>\n"
            f"Symbol: {bot.get('symbol', '?')}\n"
            f"User: {bot.get('user', '?')}\n"
            "Reason: stopped from dashboard"
        )
    except (ImportError, OSError):
        # A notification failure must not make the UI report a failed stop.
        pass


def is_process_running(pid: int) -> bool:
    """Check if process is running"""
    if platform.system() == "Windows":
        try:
            # Use CSV output so a PID is matched as a field, not as a substring.
            output = subprocess.check_output(
                f'tasklist /FI "PID eq {pid}" /FO CSV /NH',
                shell=True,
                stderr=subprocess.DEVNULL
            ).decode()
            rows = list(csv.reader(StringIO(output)))
            return any(len(row) > 1 and row[1].strip() == str(pid) for row in rows)
        except Exception:
            return False
    else:
        # Unix: check /proc
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def _get_process_command_line(pid: int) -> str:
    """Return a Windows process command line for identity validation."""
    if platform.system() != "Windows":
        return ""
    try:
        command = (
            "(Get-CimInstance Win32_Process -Filter "
            f"'ProcessId = {int(pid)}').CommandLine"
        )
        return subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", command],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.SubprocessError, ValueError):
        return ""


def is_bot_process_running(bot: dict) -> bool:
    """Check that a PID is alive and still belongs to the recorded bot."""
    pid = bot.get("pid")
    if not isinstance(pid, int) or not is_process_running(pid):
        return False
    if platform.system() != "Windows":
        return True

    command_line = _get_process_command_line(pid).lower()
    if not command_line:
        return False
    return all(
        token.lower() in command_line
        for token in (
            "bot_runner.py",
            f"--strategy {bot.get('strategy', '')}",
            f"--symbol {bot.get('symbol', '')}",
            f"--user {bot.get('user', '')}",
        )
    )


def build_bot_command(
    python_exe, script_path, strategy, symbol, user, test, interval,
    timeframe=None,
    lot_size=None, sl_pips=None, rr_ratio=None, max_candles=None,
    ema_period=None, h2_exceed_pips=0.0, c2_gap_pips=0.0, ema_margin_pips=0.0,
    entry_mode=None, entry_percent=None, tp_type=None, sl_type=None,
    buffer_k=None, lot_mode=None, risk_mode=None, risk_percent=None, risk_amount=None,
    entry_start_time='00:00', entry_end_time='23:59',
    limit_order_candles=1,
    be_enabled=False, be_r=1.0,
    ema_filter_enabled=True, buy_ema_side="below_ema", sell_ema_side="above_ema",
    re_entry_after_sl=False,
    c2_buy_upper_wick_max_pct=None, c2_buy_lower_wick_max_pct=None,
    c2_sell_upper_wick_max_pct=None, c2_sell_lower_wick_max_pct=None,
    c2_buy_upper_wick_cmp="lt", c2_buy_lower_wick_cmp="lt",
    c2_sell_upper_wick_cmp="lt", c2_sell_lower_wick_cmp="lt",
    managed_by_ui=True,
    min_father_body_points=None,
    min_child_candles=None,
    max_child_candles=None,
    mother_coverage_enabled=None,
    flappy_consensus_short=None, flappy_consensus_medium=None, flappy_consensus_long=None,
    flappy_fallback_short=None, flappy_fallback_medium=None, flappy_fallback_long=None,
    flappy_consensus_enabled=None, flappy_fallback_enabled=None,
    flappy_entry_body_percent=None,
):
    """Build command list to run bot_runner (separated for testability)."""
    cmd = [
        python_exe, script_path,
        "--strategy", strategy,
        "--symbol", symbol,
        "--user", user,
        "--test", "1" if test else "0",
        "--managed_by_ui", "1" if managed_by_ui else "0",
        "--interval", str(interval),
        "--h2_exceed_pips", str(h2_exceed_pips),
        "--c2_gap_pips", str(c2_gap_pips),
        "--ema_margin_pips", str(ema_margin_pips),
    ]
    if timeframe:
        cmd.extend(["--timeframe", timeframe])
    if lot_size:
        cmd.extend(["--lot_size", str(lot_size)])
    if sl_pips:
        cmd.extend(["--sl_pips", str(sl_pips)])
    if rr_ratio:
        cmd.extend(["--rr_ratio", str(rr_ratio)])
    if max_candles:
        cmd.extend(["--max_candles", str(max_candles)])
    if ema_period:
        cmd.extend(["--ema_period", str(ema_period)])
    if entry_mode:
        cmd.extend(["--entry_mode", entry_mode])
    if entry_percent is not None:
        cmd.extend(["--entry_percent", str(entry_percent)])
    if tp_type:
        cmd.extend(["--tp_type", tp_type])
    if sl_type:
        cmd.extend(["--sl_type", sl_type])
    if buffer_k is not None:
        cmd.extend(["--buffer_k", str(buffer_k)])
    if lot_mode:
        cmd.extend(["--lot_mode", lot_mode])
    if risk_mode:
        cmd.extend(["--risk_mode", risk_mode])
    if risk_percent is not None:
        cmd.extend(["--risk_percent", str(risk_percent)])
    if risk_amount is not None:
        cmd.extend(["--risk_amount", str(risk_amount)])
    cmd.extend(["--entry_start_time", str(entry_start_time)])
    cmd.extend(["--entry_end_time", str(entry_end_time)])
    cmd.extend(["--limit_order_candles", str(limit_order_candles)])
    if min_father_body_points is not None:
        cmd.extend(["--min_father_body_points", str(min_father_body_points)])
    if min_child_candles is not None:
        cmd.extend(["--min_child_candles", str(min_child_candles)])
    if max_child_candles is not None:
        cmd.extend(["--max_child_candles", str(max_child_candles)])
    if mother_coverage_enabled is not None:
        cmd.extend(["--mother_coverage_enabled", "1" if mother_coverage_enabled else "0"])
    for name, value in (
        ("flappy_consensus_short", flappy_consensus_short),
        ("flappy_consensus_medium", flappy_consensus_medium),
        ("flappy_consensus_long", flappy_consensus_long),
        ("flappy_fallback_short", flappy_fallback_short),
        ("flappy_fallback_medium", flappy_fallback_medium),
        ("flappy_fallback_long", flappy_fallback_long),
    ):
        if value is not None:
            cmd.extend([f"--{name}", str(value)])
    for name, value in (
        ("flappy_consensus_enabled", flappy_consensus_enabled),
        ("flappy_fallback_enabled", flappy_fallback_enabled),
    ):
        if value is not None:
            cmd.extend([f"--{name}", "1" if value else "0"])
    if flappy_entry_body_percent is not None:
        cmd.extend(["--entry_body_percent", str(flappy_entry_body_percent)])
    cmd.extend(["--be_enabled", "1" if be_enabled else "0"])
    cmd.extend(["--be_r", str(be_r)])
    cmd.extend(["--ema_filter_enabled", "1" if ema_filter_enabled else "0"])
    cmd.extend(["--buy_ema_side", buy_ema_side])
    cmd.extend(["--sell_ema_side", sell_ema_side])
    cmd.extend(["--re_entry_after_sl", "1" if re_entry_after_sl else "0"])
    if c2_buy_upper_wick_max_pct is not None:
        cmd.extend(["--c2_buy_upper_wick_max_pct", str(c2_buy_upper_wick_max_pct)])
    if c2_buy_lower_wick_max_pct is not None:
        cmd.extend(["--c2_buy_lower_wick_max_pct", str(c2_buy_lower_wick_max_pct)])
    if c2_sell_upper_wick_max_pct is not None:
        cmd.extend(["--c2_sell_upper_wick_max_pct", str(c2_sell_upper_wick_max_pct)])
    if c2_sell_lower_wick_max_pct is not None:
        cmd.extend(["--c2_sell_lower_wick_max_pct", str(c2_sell_lower_wick_max_pct)])
    cmd.extend(["--c2_buy_upper_wick_cmp", c2_buy_upper_wick_cmp or "lt"])
    cmd.extend(["--c2_buy_lower_wick_cmp", c2_buy_lower_wick_cmp or "lt"])
    cmd.extend(["--c2_sell_upper_wick_cmp", c2_sell_upper_wick_cmp or "lt"])
    cmd.extend(["--c2_sell_lower_wick_cmp", c2_sell_lower_wick_cmp or "lt"])
    return cmd


def _start_bot_unlocked(
    strategy: str,
    symbol: str,
    user: str,
    test: bool = True,
    timeframe: str = None,
    lot_size: float = None,
    sl_pips: float = None,
    rr_ratio: float = None,
    max_candles: int = None,
    interval: float = 60.0,
    ema_period: int = None,
    h2_exceed_pips: float = 0.0,
    c2_gap_pips: float = 0.0,
    ema_margin_pips: float = 0.0,
    entry_mode: str = None,
    entry_percent: float = None,
    tp_type: str = None,
    sl_type: str = None,
    buffer_k: float = None,
    lot_mode: str = None,
    risk_mode: str = None,
    risk_percent: float = None,
    risk_amount: float = None,
    entry_start_time: str = '00:00',
    entry_end_time: str = '23:59',
    limit_order_candles: int = 1,
    be_enabled: bool = False,
    be_r: float = 1.0,
    ema_filter_enabled: bool = True,
    buy_ema_side: str = "below_ema",
    sell_ema_side: str = "above_ema",
    re_entry_after_sl: bool = False,
    c2_buy_upper_wick_max_pct: float | None = None,
    c2_buy_lower_wick_max_pct: float | None = None,
    c2_sell_upper_wick_max_pct: float | None = None,
    c2_sell_lower_wick_max_pct: float | None = None,
    c2_buy_upper_wick_cmp: str = "lt",
    c2_buy_lower_wick_cmp: str = "lt",
    c2_sell_upper_wick_cmp: str = "lt",
    c2_sell_lower_wick_cmp: str = "lt",
    managed_by_ui: bool = True,
    min_father_body_points: float = None,
    min_child_candles: int = None,
    max_child_candles: int = None,
    mother_coverage_enabled: bool = None,
    flappy_consensus_short: int = None,
    flappy_consensus_medium: int = None,
    flappy_consensus_long: int = None,
    flappy_fallback_short: int = None,
    flappy_fallback_medium: int = None,
    flappy_fallback_long: int = None,
    flappy_consensus_enabled: bool = None,
    flappy_fallback_enabled: bool = None,
    flappy_entry_body_percent: float = None,
) -> tuple:
    """
    Start a new bot process

    Returns:
        (success, message, bot_info)
    """
    # Check for duplicate
    bots = load_bots()
    for bot in bots:
        if (bot['strategy'] == strategy and
            bot['symbol'] == symbol and
            bot['user'] == user and
            is_bot_process_running(bot)):
            return False, f"Bot already running for {strategy}/{symbol}/{user}", None

    # Build command
    python_exe = sys.executable
    script_path = os.path.abspath(BOT_SCRIPT)
    cmd = build_bot_command(
        python_exe, script_path, strategy, symbol, user, test, interval,
        timeframe,
        lot_size, sl_pips, rr_ratio, max_candles,
        ema_period, h2_exceed_pips, c2_gap_pips, ema_margin_pips,
        entry_mode, entry_percent, tp_type, sl_type,
        buffer_k, lot_mode, risk_mode, risk_percent, risk_amount,
        entry_start_time, entry_end_time, limit_order_candles,
        be_enabled, be_r,
        ema_filter_enabled, buy_ema_side, sell_ema_side,
        re_entry_after_sl,
        c2_buy_upper_wick_max_pct, c2_buy_lower_wick_max_pct,
        c2_sell_upper_wick_max_pct, c2_sell_lower_wick_max_pct,
        c2_buy_upper_wick_cmp, c2_buy_lower_wick_cmp,
        c2_sell_upper_wick_cmp, c2_sell_lower_wick_cmp,
        managed_by_ui,
        min_father_body_points,
        min_child_candles,
        max_child_candles,
        mother_coverage_enabled,
        flappy_consensus_short, flappy_consensus_medium, flappy_consensus_long,
        flappy_fallback_short, flappy_fallback_medium, flappy_fallback_long,
        flappy_consensus_enabled, flappy_fallback_enabled,
        flappy_entry_body_percent,
    )

    try:
        # Log file per bot — named by strategy/symbol/start time for easy traceback
        os.makedirs("logs", exist_ok=True)
        started_tag = datetime.now(TIMEZONE).strftime('%Y%m%d_%H%M%S')
        log_path = os.path.abspath(f"logs/bot_{strategy}_{symbol}_{started_tag}.log")

        # Pass log path as arg so bot_runner writes via logging module (not stdout redirect)
        cmd = cmd + ["--log_file", log_path]

        # Start process
        if platform.system() == "Windows":
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )

        pid = process.pid

        # Save bot info
        bot_info = {
            'id': f"{strategy}_{symbol}_{user}_{pid}",
            'pid': pid,
            'strategy': strategy,
            'symbol': symbol,
            'user': user,
            'test': test,
            'managed_by_ui': managed_by_ui,
            'timeframe': timeframe,
            'lot_size': lot_size,
            'sl_pips': sl_pips,
            'rr_ratio': rr_ratio,
            'max_candles': max_candles,
            'interval': interval,
            'ema_period': ema_period,
            'h2_exceed_pips': h2_exceed_pips,
            'c2_gap_pips': c2_gap_pips,
            'ema_margin_pips': ema_margin_pips,
            'entry_mode': entry_mode,
            'entry_percent': entry_percent,
            'tp_type': tp_type,
            'sl_type': sl_type,
            'buffer_k': buffer_k,
            'lot_mode': lot_mode,
            'risk_mode': risk_mode,
            'risk_percent': risk_percent,
            'risk_amount': risk_amount,
            'entry_start_time': entry_start_time,
            'entry_end_time': entry_end_time,
            'limit_order_candles': limit_order_candles,
            'min_child_candles': min_child_candles,
            'max_child_candles': max_child_candles,
            'mother_coverage_enabled': mother_coverage_enabled,
            'flappy_entry_body_percent': flappy_entry_body_percent,
            'flappy_consensus_short': flappy_consensus_short,
            'flappy_consensus_medium': flappy_consensus_medium,
            'flappy_consensus_long': flappy_consensus_long,
            'flappy_fallback_short': flappy_fallback_short,
            'flappy_fallback_medium': flappy_fallback_medium,
            'flappy_fallback_long': flappy_fallback_long,
            'flappy_consensus_enabled': flappy_consensus_enabled,
            'flappy_fallback_enabled': flappy_fallback_enabled,
            'be_enabled': be_enabled,
            'be_r': be_r,
            'ema_filter_enabled': ema_filter_enabled,
            'buy_ema_side': buy_ema_side,
            'sell_ema_side': sell_ema_side,
            're_entry_after_sl': re_entry_after_sl,
            'c2_buy_upper_wick_max_pct': c2_buy_upper_wick_max_pct,
            'c2_buy_lower_wick_max_pct': c2_buy_lower_wick_max_pct,
            'c2_sell_upper_wick_max_pct': c2_sell_upper_wick_max_pct,
            'c2_sell_lower_wick_max_pct': c2_sell_lower_wick_max_pct,
            'c2_buy_upper_wick_cmp': c2_buy_upper_wick_cmp,
            'c2_buy_lower_wick_cmp': c2_buy_lower_wick_cmp,
            'c2_sell_upper_wick_cmp': c2_sell_upper_wick_cmp,
            'c2_sell_lower_wick_cmp': c2_sell_lower_wick_cmp,
            'started_at': datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S'),
            'log_path': log_path,
            'command': ' '.join(cmd)
        }

        bots.append(bot_info)
        save_bots(bots)

        return True, f"Bot started with PID {pid}", bot_info

    except Exception as e:
        return False, str(e), None


def start_bot(*args, **kwargs) -> tuple:
    """Start one bot while serializing duplicate check, spawn, and persistence."""
    from src.state_file import _file_lock

    lock_path = os.path.abspath(os.path.join("data", "start_bot.lock"))
    with _file_lock(lock_path):
        return _start_bot_unlocked(*args, **kwargs)


def stop_bot(pid: int) -> tuple:
    """
    Stop a bot by PID

    Returns:
        (success, message)
    """
    bots = load_bots()
    stopped_bot = next((bot for bot in bots if bot.get('pid') == pid), {'pid': pid})
    process_matches_bot = (
        is_bot_process_running(stopped_bot)
        if stopped_bot.get('strategy')
        else is_process_running(pid)
    )

    if not process_matches_bot:
        # Remove stale/dead records without ever killing a reused PID.
        bots = [b for b in bots if b['pid'] != pid]
        save_bots(bots)
        _remove_bot_state(pid)
        if stopped_bot.get('strategy'):
            return True, f"Bot process {pid} is no longer running (stale record removed)"
        _notify_bot_stopped(stopped_bot)
        return True, f"Process {pid} not running (removed from list)"

    try:
        bots = load_bots()
        stopped_bot = next((bot for bot in bots if bot.get("pid") == pid), {"pid": pid})
        if platform.system() == "Windows":
            # Send CTRL_BREAK_EVENT so the process can catch KeyboardInterrupt and send Telegram before dying
            import ctypes
            try:
                ctypes.windll.kernel32.GenerateConsoleCtrlEvent(1, pid)  # 1 = CTRL_BREAK_EVENT
            except Exception:
                pass
            # Give it up to 8s to clean up gracefully
            for _ in range(8):
                time_mod.sleep(1)
                if not is_process_running(pid):
                    break
            else:
                # Still alive — force kill
                subprocess.run(f'taskkill /PID {pid} /F', shell=True, capture_output=True)
        else:
            # Unix: SIGTERM allows cleanup; fallback SIGKILL after 8s
            os.kill(pid, signal.SIGTERM)
            for _ in range(8):
                time_mod.sleep(1)
                if not is_process_running(pid):
                    break
            else:
                os.kill(pid, signal.SIGKILL)

        # Remove from list
        bots = [b for b in bots if b['pid'] != pid]
        save_bots(bots)
        _remove_bot_state(pid)
        _notify_bot_stopped(stopped_bot)

        return True, f"Bot stopped (PID {pid})"

    except Exception as e:
        return False, str(e)


def stop_all_bots(user: str = None) -> tuple:
    """
    Stop all bots (optionally filtered by user)

    Returns:
        (stopped_count, message)
    """
    bots = load_bots()
    stopped = 0
    errors = []

    for bot in bots:
        if user and bot['user'] != user:
            continue

        success, msg = stop_bot(bot['pid'])
        if success:
            stopped += 1
        else:
            errors.append(msg)

    if errors:
        return stopped, f"Stopped {stopped}, Errors: {'; '.join(errors)}"
    return stopped, f"Stopped {stopped} bot(s)"


def _has_open_position(bot: dict) -> bool:
    """Check if the bot's symbol has any open MT5 positions (only relevant for live bots)."""
    if bot.get('test', True):
        return False
    try:
        from src.auth import get_user_mt5_credentials
        from src.orders import fetch_open_positions
        credentials = get_user_mt5_credentials(bot['user'])
        positions, _ = fetch_open_positions(credentials)
        symbol = bot['symbol']
        return any(p['symbol'] == symbol for p in positions)
    except Exception:
        return False


def switch_bot_mode(pid: int, live: bool) -> tuple:
    """Switch bot between test/live mode. Blocks Live→Test when symbol has open positions."""
    bot = get_bot(pid)
    if not bot:
        return False, f"Bot not found: {pid}", None

    # Chặn chuyển từ Live → Test nếu đang có lệnh mở
    if not live and _has_open_position(bot):
        return False, (
            f"Không thể chuyển sang Test — bot {bot['symbol']} đang có lệnh mở trên MT5. "
            "Vui lòng đóng lệnh trước khi chuyển chế độ."
        ), None

    stop_bot(pid)
    return start_bot(
        strategy=bot['strategy'],
        symbol=bot['symbol'],
        user=bot['user'],
        test=not live,
        lot_size=bot.get('lot_size'),
        sl_pips=bot.get('sl_pips'),
        rr_ratio=bot.get('rr_ratio'),
        max_candles=bot.get('max_candles'),
        interval=bot.get('interval', 60),
        ema_period=bot.get('ema_period'),
        h2_exceed_pips=bot.get('h2_exceed_pips', 0.0),
        c2_gap_pips=bot.get('c2_gap_pips', 0.0),
        ema_margin_pips=bot.get('ema_margin_pips', 0.0),
        entry_mode=bot.get('entry_mode'),
        entry_percent=bot.get('entry_percent'),
        tp_type=bot.get('tp_type'),
        sl_type=bot.get('sl_type'),
        buffer_k=bot.get('buffer_k'),
        lot_mode=bot.get('lot_mode'),
        risk_mode=bot.get('risk_mode'),
        risk_percent=bot.get('risk_percent'),
        risk_amount=bot.get('risk_amount'),
        entry_start_time=bot.get('entry_start_time', '00:00'),
        entry_end_time=bot.get('entry_end_time', '23:59'),
        limit_order_candles=bot.get('limit_order_candles', 1),
        be_enabled=bot.get('be_enabled', False),
        be_r=bot.get('be_r', 1.0),
        ema_filter_enabled=bot.get('ema_filter_enabled', True),
        buy_ema_side=bot.get('buy_ema_side', 'below_ema'),
        sell_ema_side=bot.get('sell_ema_side', 'above_ema'),
        re_entry_after_sl=bot.get('re_entry_after_sl', False),
        c2_buy_upper_wick_max_pct=bot.get('c2_buy_upper_wick_max_pct'),
        c2_buy_lower_wick_max_pct=bot.get('c2_buy_lower_wick_max_pct'),
        c2_sell_upper_wick_max_pct=bot.get('c2_sell_upper_wick_max_pct'),
        c2_sell_lower_wick_max_pct=bot.get('c2_sell_lower_wick_max_pct'),
        c2_buy_upper_wick_cmp=bot.get('c2_buy_upper_wick_cmp', 'lt'),
        c2_buy_lower_wick_cmp=bot.get('c2_buy_lower_wick_cmp', 'lt'),
        c2_sell_upper_wick_cmp=bot.get('c2_sell_upper_wick_cmp', 'lt'),
        c2_sell_lower_wick_cmp=bot.get('c2_sell_lower_wick_cmp', 'lt'),
        min_child_candles=bot.get('min_child_candles'),
        max_child_candles=bot.get('max_child_candles'),
        mother_coverage_enabled=bot.get('mother_coverage_enabled'),
        flappy_entry_body_percent=bot.get('flappy_entry_body_percent'),
    )


def restart_all_bots(user: str = None) -> tuple:
    """Restart all bots (optionally filtered by user). Returns (restarted_count, message)."""
    bots = load_bots()
    restarted = 0
    errors = []

    for bot in list(bots):
        if user and bot['user'] != user:
            continue
        success, msg, _ = restart_bot(bot['pid'])
        if success:
            restarted += 1
        else:
            errors.append(msg)

    if errors:
        return restarted, f"Restarted {restarted}, Errors: {'; '.join(errors)}"
    return restarted, f"Restarted {restarted} bot(s)"


def list_bots(user: str = None, refresh: bool = True) -> list:
    """
    List running bots

    Args:
        user: Filter by user (None = all)
        refresh: Check if processes are still running

    Returns:
        List of bot info dicts
    """
    bots = load_bots()

    if refresh:
        # Filter out dead processes
        alive_bots = []
        for bot in bots:
            if is_bot_process_running(bot):
                bot['status'] = 'running'
                alive_bots.append(bot)
            else:
                bot['status'] = 'stopped'
                # Optionally keep stopped bots for history
                # alive_bots.append(bot)

        # Update file with only alive bots
        save_bots(alive_bots)
        bots = alive_bots

    # Filter by user
    if user:
        bots = [b for b in bots if b['user'] == user]

    return bots


def get_bot(pid: int) -> Optional[dict]:
    """Get bot info by PID"""
    bots = load_bots()
    for bot in bots:
        if bot['pid'] == pid:
            bot['status'] = 'running' if is_process_running(pid) else 'stopped'
            return bot
    return None


def restart_bot(pid: int) -> tuple:
    """
    Restart a bot

    Returns:
        (success, message, new_bot_info)
    """
    bot = get_bot(pid)
    if not bot:
        return False, f"Bot not found: {pid}", None

    # Stop the bot
    stop_bot(pid)

    # Start with same parameters
    return start_bot(
        strategy=bot['strategy'],
        symbol=bot['symbol'],
        user=bot['user'],
        test=bot.get('test', True),
        timeframe=bot.get('timeframe'),
        lot_size=bot.get('lot_size'),
        sl_pips=bot.get('sl_pips'),
        rr_ratio=bot.get('rr_ratio'),
        max_candles=bot.get('max_candles'),
        interval=bot.get('interval', 60),
        ema_period=bot.get('ema_period'),
        h2_exceed_pips=bot.get('h2_exceed_pips', 0.0),
        c2_gap_pips=bot.get('c2_gap_pips', 0.0),
        ema_margin_pips=bot.get('ema_margin_pips', 0.0),
        entry_mode=bot.get('entry_mode'),
        entry_percent=bot.get('entry_percent'),
        tp_type=bot.get('tp_type'),
        sl_type=bot.get('sl_type'),
        buffer_k=bot.get('buffer_k'),
        lot_mode=bot.get('lot_mode'),
        risk_mode=bot.get('risk_mode'),
        risk_percent=bot.get('risk_percent'),
        risk_amount=bot.get('risk_amount'),
        entry_start_time=bot.get('entry_start_time', '00:00'),
        entry_end_time=bot.get('entry_end_time', '23:59'),
        limit_order_candles=bot.get('limit_order_candles', 1),
        be_enabled=bot.get('be_enabled', False),
        be_r=bot.get('be_r', 1.0),
        ema_filter_enabled=bot.get('ema_filter_enabled', True),
        buy_ema_side=bot.get('buy_ema_side', 'below_ema'),
        sell_ema_side=bot.get('sell_ema_side', 'above_ema'),
        re_entry_after_sl=bot.get('re_entry_after_sl', False),
        c2_buy_upper_wick_max_pct=bot.get('c2_buy_upper_wick_max_pct'),
        c2_buy_lower_wick_max_pct=bot.get('c2_buy_lower_wick_max_pct'),
        c2_sell_upper_wick_max_pct=bot.get('c2_sell_upper_wick_max_pct'),
        c2_sell_lower_wick_max_pct=bot.get('c2_sell_lower_wick_max_pct'),
        c2_buy_upper_wick_cmp=bot.get('c2_buy_upper_wick_cmp', 'lt'),
        c2_buy_lower_wick_cmp=bot.get('c2_buy_lower_wick_cmp', 'lt'),
        c2_sell_upper_wick_cmp=bot.get('c2_sell_upper_wick_cmp', 'lt'),
        c2_sell_lower_wick_cmp=bot.get('c2_sell_lower_wick_cmp', 'lt'),
        flappy_entry_body_percent=bot.get('flappy_entry_body_percent'),
    )


def get_bot_stats() -> dict:
    """Get bot statistics"""
    bots = list_bots(refresh=True)

    total = len(bots)
    test_mode = len([b for b in bots if b.get('test', True)])
    live_mode = total - test_mode

    strategies = set(b['strategy'] for b in bots)
    symbols = set(b['symbol'] for b in bots)
    users = set(b['user'] for b in bots)

    return {
        'total': total,
        'test_mode': test_mode,
        'live_mode': live_mode,
        'strategies': list(strategies),
        'symbols': list(symbols),
        'users': list(users)
    }
