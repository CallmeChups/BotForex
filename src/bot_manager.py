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
    """Save bots to file with atomic write"""
    import time
    import tempfile
    import shutil

    bots_file = get_bots_file()

    # Atomic write: write to temp file then move
    # This prevents corrupted file if interrupted
    temp_fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(bots_file), suffix='.tmp')
    try:
        with os.fdopen(temp_fd, 'w') as f:
            json.dump(bots, f, indent=2)

        # Atomic move (rename is atomic on both Windows and Unix)
        shutil.move(temp_path, bots_file)
    except Exception as e:
        # Clean up temp file on error
        try:
            os.unlink(temp_path)
        except:
            pass
        raise e


def is_process_running(pid: int) -> bool:
    """Check if process is running (more reliable implementation)"""
    if platform.system() == "Windows":
        try:
            # Use psutil if available (more reliable)
            try:
                import psutil
                return psutil.pid_exists(pid)
            except ImportError:
                # Fallback to tasklist
                output = subprocess.check_output(
                    f'tasklist /FI "PID eq {pid}"',
                    shell=True,
                    stderr=subprocess.DEVNULL,
                    timeout=5  # Timeout to prevent hanging
                ).decode()
                # Check for actual PID in output, not just string match
                # Output format: "python.exe    12345 Console    1   123,456 K"
                lines = output.strip().split('\n')
                for line in lines:
                    if str(pid) in line and line.strip():
                        # Verify it's the actual PID column, not just substring
                        parts = line.split()
                        if len(parts) >= 2 and parts[1] == str(pid):
                            return True
                return False
        except Exception:
            # If check fails, assume process is still running to be safe
            # Better to keep a dead bot in list than accidentally remove a live one
            return True
    else:
        # Unix: check /proc
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def start_bot(
    strategy: str,
    symbol: str,
    user: str,
    test: bool = True,
    lot_size: float = None,
    sl_pips: float = None,
    rr_ratio: float = None,
    max_candles: int = None,
    interval: int = 1,
    # New parameters matching backtest config
    timeframe: str = None,
    entry_time: str = None,
    entry_mode: str = None,
    entry_percent: float = None,
    buffer_k: float = None,
    lot_mode: str = None,
    starting_equity: float = None,
    risk_mode: str = None,
    risk_percent: float = None,
    risk_amount: float = None,
    risk_compounding: bool = None,
    tp_type: str = None,
    sl_type: str = None,
    # Move SL to Breakeven parameters
    move_sl_to_breakeven: bool = None,
    breakeven_trigger_percent: float = None,
    # Pending order parameters
    pending_order_max_candles: int = None
) -> tuple:
    """
    Start a new bot process

    Returns:
        (success, message, bot_info)
    """
    # Load existing bots
    bots = load_bots()

    # Build command
    python_exe = sys.executable
    script_path = os.path.abspath(BOT_SCRIPT)

    cmd = [
        python_exe,
        script_path,
        "--strategy", strategy,
        "--symbol", symbol,
        "--user", user,
        "--test", "1" if test else "0",
        "--interval", str(interval)
    ]

    if lot_size:
        cmd.extend(["--lot_size", str(lot_size)])
    if sl_pips:
        cmd.extend(["--sl_pips", str(sl_pips)])
    if rr_ratio:
        cmd.extend(["--rr_ratio", str(rr_ratio)])
    if max_candles:
        cmd.extend(["--max_candles", str(max_candles)])

    # New parameters
    if timeframe:
        cmd.extend(["--timeframe", timeframe])
    if entry_time:
        cmd.extend(["--entry_time", entry_time])
    if entry_mode:
        cmd.extend(["--entry_mode", entry_mode])
    if entry_percent is not None:
        cmd.extend(["--entry_percent", str(entry_percent)])
    if buffer_k is not None:
        cmd.extend(["--buffer_k", str(buffer_k)])
    if lot_mode:
        cmd.extend(["--lot_mode", lot_mode])
    if starting_equity:
        cmd.extend(["--starting_equity", str(starting_equity)])
    if risk_mode:
        cmd.extend(["--risk_mode", risk_mode])
    if risk_percent is not None:
        cmd.extend(["--risk_percent", str(risk_percent)])
    if risk_amount is not None:
        cmd.extend(["--risk_amount", str(risk_amount)])
    if risk_compounding is not None:
        cmd.extend(["--risk_compounding", "1" if risk_compounding else "0"])
    if tp_type:
        cmd.extend(["--tp_type", tp_type])
    if sl_type:
        cmd.extend(["--sl_type", sl_type])

    # Move SL to Breakeven parameters
    if move_sl_to_breakeven is not None:
        cmd.extend(["--move_sl_to_breakeven", "1" if move_sl_to_breakeven else "0"])
    if breakeven_trigger_percent is not None:
        cmd.extend(["--breakeven_trigger_percent", str(breakeven_trigger_percent)])

    # Pending order parameters
    if pending_order_max_candles is not None:
        cmd.extend(["--pending_order_max_candles", str(pending_order_max_candles)])

    try:
        # Create logs directory
        os.makedirs("logs", exist_ok=True)

        # Create log file for this bot (temporary name, will rename after getting PID)
        temp_log = f"logs/bot_temp_{datetime.now(TIMEZONE).strftime('%Y%m%d_%H%M%S')}.log"
        log_file = open(temp_log, 'w', buffering=1)  # Line buffered

        # Start process
        if platform.system() == "Windows":
            # Windows: use CREATE_NEW_PROCESS_GROUP
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            )
        else:
            # Unix: use nohup-like behavior
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True
            )

        pid = process.pid

        # Rename log file with actual PID
        final_log = f"logs/bot_{pid}.log"
        log_file.close()

        # Rename temp log to final log
        import shutil
        try:
            shutil.move(temp_log, final_log)
        except Exception as e:
            # If rename fails, keep temp log
            final_log = temp_log

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
            'timeframe': timeframe,
            'entry_time': entry_time,
            'entry_mode': entry_mode,
            'entry_percent': entry_percent,
            'buffer_k': buffer_k,
            'lot_mode': lot_mode,
            'starting_equity': starting_equity,
            'risk_mode': risk_mode,
            'risk_percent': risk_percent,
            'risk_amount': risk_amount,
            'risk_compounding': risk_compounding,
            'tp_type': tp_type,
            'sl_type': sl_type,
            'move_sl_to_breakeven': move_sl_to_breakeven,
            'breakeven_trigger_percent': breakeven_trigger_percent,
            'pending_order_max_candles': pending_order_max_candles,
            'started_at': datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S'),
            'log_file': final_log,
            'command': ' '.join(cmd)
        }

        # Reload bots before saving to prevent race condition in batch creation
        bots = load_bots()
        bots.append(bot_info)
        save_bots(bots)

        # Save config to history for preset reuse
        try:
            from src.bot_config_history import save_bot_config as _save_config
            _save_config(bot_info)
        except Exception:
            pass  # Non-critical — don't block bot start

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


def list_bots(user: str = None, refresh: bool = True, cleanup: bool = False) -> list:
    """
    List running bots

    Args:
        user: Filter by user (None = all)
        refresh: Check if processes are still running (update status in-memory)
        cleanup: Remove dead bots from file (only when user explicitly requests)

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

        # Only update file if cleanup is explicitly requested
        # This prevents accidental removal of bots on page refresh
        if cleanup:
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
        interval=bot.get('interval', 1),
        timeframe=bot.get('timeframe'),
        entry_time=bot.get('entry_time'),
        entry_mode=bot.get('entry_mode'),
        entry_percent=bot.get('entry_percent'),
        buffer_k=bot.get('buffer_k'),
        lot_mode=bot.get('lot_mode'),
        starting_equity=bot.get('starting_equity'),
        risk_mode=bot.get('risk_mode'),
        risk_percent=bot.get('risk_percent'),
        risk_amount=bot.get('risk_amount'),
        risk_compounding=bot.get('risk_compounding'),
        tp_type=bot.get('tp_type'),
        sl_type=bot.get('sl_type'),
        move_sl_to_breakeven=bot.get('move_sl_to_breakeven'),
        breakeven_trigger_percent=bot.get('breakeven_trigger_percent'),
        pending_order_max_candles=bot.get('pending_order_max_candles')
    )


def get_bot_stats() -> dict:
    """Get bot statistics"""
    # Don't cleanup on stats check - just refresh status in-memory
    bots = list_bots(refresh=True, cleanup=False)

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
