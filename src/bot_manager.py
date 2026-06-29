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


def is_process_running(pid: int) -> bool:
    """Check if process is running"""
    if platform.system() == "Windows":
        try:
            # Use tasklist on Windows
            output = subprocess.check_output(
                f'tasklist /FI "PID eq {pid}"',
                shell=True,
                stderr=subprocess.DEVNULL
            ).decode()
            return str(pid) in output
        except Exception:
            return False
    else:
        # Unix: check /proc
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def build_bot_command(
    python_exe, script_path, strategy, symbol, user, test, interval,
    lot_size=None, sl_pips=None, rr_ratio=None, max_candles=None,
    ema_period=None, h2_exceed_pips=0.0, c2_gap_pips=0.0, ema_margin_pips=0.0,
    entry_mode=None, entry_percent=None, tp_type=None, sl_type=None,
    buffer_k=None, lot_mode=None, risk_mode=None, risk_percent=None, risk_amount=None,
    entry_start_time='00:00', entry_end_time='23:59',
    limit_order_candles=1,
    be_enabled=False, be_r=1.0,
):
    """Build command list to run bot_runner (separated for testability)."""
    cmd = [
        python_exe, script_path,
        "--strategy", strategy,
        "--symbol", symbol,
        "--user", user,
        "--test", "1" if test else "0",
        "--interval", str(interval),
        "--h2_exceed_pips", str(h2_exceed_pips),
        "--c2_gap_pips", str(c2_gap_pips),
        "--ema_margin_pips", str(ema_margin_pips),
    ]
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
    cmd.extend(["--be_enabled", "1" if be_enabled else "0"])
    cmd.extend(["--be_r", str(be_r)])
    return cmd


def start_bot(
    strategy: str,
    symbol: str,
    user: str,
    test: bool = True,
    lot_size: float = None,
    sl_pips: float = None,
    rr_ratio: float = None,
    max_candles: int = None,
    interval: int = 60,
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
            is_process_running(bot['pid'])):
            return False, f"Bot already running for {strategy}/{symbol}/{user}", None

    # Build command
    python_exe = sys.executable
    script_path = os.path.abspath(BOT_SCRIPT)
    cmd = build_bot_command(
        python_exe, script_path, strategy, symbol, user, test, interval,
        lot_size, sl_pips, rr_ratio, max_candles,
        ema_period, h2_exceed_pips, c2_gap_pips, ema_margin_pips,
        entry_mode, entry_percent, tp_type, sl_type,
        buffer_k, lot_mode, risk_mode, risk_percent, risk_amount,
        entry_start_time, entry_end_time, limit_order_candles,
        be_enabled, be_r,
    )

    try:
        # Start process
        if platform.system() == "Windows":
            # Windows: use CREATE_NEW_PROCESS_GROUP
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            )
        else:
            # Unix: use nohup-like behavior
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
            'lot_size': lot_size,
            'sl_pips': sl_pips,
            'rr_ratio': rr_ratio,
            'max_candles': max_candles,
            'interval': interval,
            'ema_period': ema_period,
            'h2_exceed_pips': h2_exceed_pips,
            'c2_gap_pips': c2_gap_pips,
            'ema_margin_pips': ema_margin_pips,
            'limit_order_candles': limit_order_candles,
            'be_enabled': be_enabled,
            'be_r': be_r,
            'started_at': datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S'),
            'command': ' '.join(cmd)
        }

        bots.append(bot_info)
        save_bots(bots)

        return True, f"Bot started with PID {pid}", bot_info

    except Exception as e:
        return False, str(e), None


def stop_bot(pid: int) -> tuple:
    """
    Stop a bot by PID

    Returns:
        (success, message)
    """
    if not is_process_running(pid):
        # Remove from list anyway
        bots = load_bots()
        bots = [b for b in bots if b['pid'] != pid]
        save_bots(bots)
        return True, f"Process {pid} not running (removed from list)"

    try:
        if platform.system() == "Windows":
            # Windows: use taskkill
            subprocess.run(
                f'taskkill /PID {pid} /F',
                shell=True,
                check=True,
                capture_output=True
            )
        else:
            # Unix: send SIGTERM
            os.kill(pid, signal.SIGTERM)

        # Remove from list
        bots = load_bots()
        bots = [b for b in bots if b['pid'] != pid]
        save_bots(bots)

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
            if is_process_running(bot['pid']):
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
        lot_size=bot.get('lot_size'),
        sl_pips=bot.get('sl_pips'),
        rr_ratio=bot.get('rr_ratio'),
        max_candles=bot.get('max_candles'),
        interval=bot.get('interval', 60),
        ema_period=bot.get('ema_period'),
        h2_exceed_pips=bot.get('h2_exceed_pips', 0.0),
        c2_gap_pips=bot.get('c2_gap_pips', 0.0),
        ema_margin_pips=bot.get('ema_margin_pips', 0.0),
        limit_order_candles=bot.get('limit_order_candles', 1),
        be_enabled=bot.get('be_enabled', False),
        be_r=bot.get('be_r', 1.0),
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
