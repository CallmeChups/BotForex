"""
Bot History Manager

Tracks bot sessions (start → stop) with trade stats and PNL.
Stored in data/bot_history.json as a list of session dicts.

Session schema:
{
    "id": "feg_ema21_XAUUSDm_20260701_082700",
    "name": null,               # user-defined rename
    "strategy": "feg_ema21",
    "symbol": "XAUUSDm",
    "mode": "live",             # "live" | "test"
    "user": "admin",
    "started_at": "2026-07-01 08:27:00",
    "stopped_at": null,         # filled on stop
    "log_path": "logs/bot_...",
    "trades": [
        {"order_id": "ORD-...", "direction": "BUY", "entry": 3300.0,
         "exit_price": 3310.0, "exit_type": "TP", "pnl_usd": 1.23,
         "lot": 0.01, "closed_at": "2026-07-01 09:00:00"}
    ],
    "stats": {
        "total": 0, "win": 0, "loss": 0, "pnl_usd": 0.0
    },
    "deleted": false            # soft delete flag
}
"""

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

HISTORY_FILE = "data/bot_history.json"
TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def _load() -> list:
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save(sessions: list):
    os.makedirs("data", exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(sessions, f, indent=2, ensure_ascii=False)


def create_session(strategy: str, symbol: str, mode: str, user: str, log_path: str) -> str:
    """Create a new session on bot start. Returns session_id."""
    sessions = _load()
    now = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    tag = datetime.now(TIMEZONE).strftime("%Y%m%d_%H%M%S")
    session_id = f"{strategy}_{symbol}_{tag}"
    sessions.append({
        "id": session_id,
        "name": None,
        "strategy": strategy,
        "symbol": symbol,
        "mode": mode,
        "user": user,
        "started_at": now,
        "stopped_at": None,
        "log_path": log_path,
        "trades": [],
        "stats": {"total": 0, "win": 0, "loss": 0, "pnl_usd": 0.0},
        "deleted": False,
    })
    _save(sessions)
    return session_id


def close_session(session_id: str):
    """Mark session as stopped with current timestamp."""
    sessions = _load()
    now = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    for s in sessions:
        if s["id"] == session_id:
            s["stopped_at"] = now
            break
    _save(sessions)


def record_trade(session_id: str, order_id: str, direction: str,
                 entry: float, exit_price: float, exit_type: str,
                 pnl_usd: float, lot: float, verified: bool = True):
    """Append a completed trade to the session and update stats.

    verified=True means exit_price and pnl_usd came from MT5 deal history (broker-confirmed).
    verified=False means they are candle-based estimates (deal history unavailable).
    """
    sessions = _load()
    now = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    for s in sessions:
        if s["id"] == session_id:
            trade = {
                "order_id": order_id,
                "direction": direction,
                "entry": entry,
                "exit_price": exit_price,
                "exit_type": exit_type,
                "pnl_usd": round(pnl_usd, 2),
                "lot": lot,
                "closed_at": now,
                "verified": verified,  # False = estimated, not confirmed from broker deal history
            }
            s["trades"].append(trade)
            s["stats"]["total"] += 1
            if pnl_usd >= 0:
                s["stats"]["win"] += 1
            else:
                s["stats"]["loss"] += 1
            s["stats"]["pnl_usd"] = round(s["stats"]["pnl_usd"] + pnl_usd, 2)
            break
    _save(sessions)


def rename_session(session_id: str, name: str):
    """Set user-defined name for a session."""
    sessions = _load()
    for s in sessions:
        if s["id"] == session_id:
            s["name"] = name.strip() or None
            break
    _save(sessions)


def delete_session(session_id: str):
    """Soft delete a session."""
    sessions = _load()
    for s in sessions:
        if s["id"] == session_id:
            s["deleted"] = True
            break
    _save(sessions)


def cleanup_orphaned_sessions():
    """Mark sessions as stopped if their bot PID is no longer running.

    Called on UI load. Sessions with stopped_at=None are checked against
    running_bots.json — if the PID is gone, we stamp stopped_at now.
    """
    import platform as _platform
    import subprocess as _subprocess

    sessions = _load()
    open_sessions = [s for s in sessions if not s.get("stopped_at") and not s.get("deleted")]
    if not open_sessions:
        return

    # Load running PIDs from running_bots.json
    bots_file = os.path.join("data", "running_bots.json")
    running_pids: set = set()
    if os.path.exists(bots_file):
        try:
            with open(bots_file, "r", encoding="utf-8") as f:
                bots = json.load(f)
            running_pids = {b["pid"] for b in bots if "pid" in b}
        except Exception:
            pass

    def _is_running(pid: int) -> bool:
        if pid in running_pids:
            return True
        # Double-check OS process table (handles stale running_bots.json)
        if _platform.system() == "Windows":
            try:
                out = _subprocess.check_output(
                    f'tasklist /FI "PID eq {pid}"',
                    shell=True, stderr=_subprocess.DEVNULL,
                ).decode()
                return str(pid) in out
            except Exception:
                return False
        else:
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                return False

    # Session ID encodes strategy_symbol_YYYYMMDD_HHMMSS — no PID.
    # Match by checking all running_bots entries: a session is alive if
    # any running bot's started_at matches the session's started_at.
    running_start_times: set = set()
    if os.path.exists(bots_file):
        try:
            with open(bots_file, "r", encoding="utf-8") as f:
                bots = json.load(f)
            for b in bots:
                if "started_at" in b and _is_running(b.get("pid", -1)):
                    running_start_times.add(b["started_at"])
        except Exception:
            pass

    now = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    changed = False
    for s in sessions:
        if s.get("stopped_at") or s.get("deleted"):
            continue
        # Session is live only if a running bot started at the same time
        if s.get("started_at") not in running_start_times:
            s["stopped_at"] = now
            changed = True

    if changed:
        _save(sessions)


def get_sessions(include_deleted: bool = False, user: str = None) -> list:
    """Return sessions, newest first. Optionally filter by user."""
    sessions = _load()
    if not include_deleted:
        sessions = [s for s in sessions if not s.get("deleted", False)]
    if user:
        sessions = [s for s in sessions if s.get("user") == user]
    return list(reversed(sessions))
