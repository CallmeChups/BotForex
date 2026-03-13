"""
Log Manager Module

Utilities for browsing, filtering, and cleaning bot log files.
Stdlib only — no external dependencies.
"""

import os
import re
import json
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

LOGS_DIR = Path("logs")
BOTS_FILE = Path("data/running_bots.json")
DEFAULT_MAX_AGE_DAYS = 7

# Regex for new-format filenames:
#   bot_{strategy}_{symbol}_{user}_{pid}_{YYYYMMDD_HHMMSS}.log
_NEW_FMT = re.compile(
    r"^bot_(.+?)_([A-Z]{3,10}(?:m)?)_(\w+)_(\d+)_(\d{8}_\d{6})\.log$"
)
# Old format: bot_{pid}.log
_OLD_FMT = re.compile(r"^bot_(\d+)\.log$")


def _parse_filename(name: str) -> dict:
    """Extract metadata from a log filename. Returns partial dict."""
    m = _NEW_FMT.match(name)
    if m:
        return {
            "strategy": m.group(1),
            "symbol": m.group(2),
            "user": m.group(3),
            "pid": int(m.group(4)),
        }
    m = _OLD_FMT.match(name)
    if m:
        return {"pid": int(m.group(1))}
    return {}


def get_log_files(user: str = None, max_age_days: int = None) -> list:
    """
    Return list of log file info dicts, newest first.

    Each dict: {path, filename, size_bytes, modified_dt, strategy, symbol, user, pid}
    Filters by user and/or age when provided.
    """
    if not LOGS_DIR.is_dir():
        return []

    cutoff = None
    if max_age_days is not None:
        cutoff = datetime.now() - timedelta(days=max_age_days)

    results = []
    for entry in os.scandir(LOGS_DIR):
        if not entry.name.endswith(".log") or not entry.is_file():
            continue

        stat = entry.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime)

        if cutoff and mtime < cutoff:
            continue

        meta = _parse_filename(entry.name)

        if user and meta.get("user") != user:
            continue

        results.append({
            "path": entry.path,
            "filename": entry.name,
            "size_bytes": stat.st_size,
            "modified_dt": mtime,
            **meta,
        })

    results.sort(key=lambda r: r["modified_dt"], reverse=True)
    return results


def get_log_summary() -> dict:
    """Single-pass summary: total_count, empty_count, total_size_mb, newest_dt."""
    if not LOGS_DIR.is_dir():
        return {"total_count": 0, "empty_count": 0, "total_size_mb": 0.0, "newest_dt": None}

    total = 0
    empty = 0
    size = 0
    newest = None

    for entry in os.scandir(LOGS_DIR):
        if not entry.name.endswith(".log") or not entry.is_file():
            continue
        total += 1
        stat = entry.stat()
        if stat.st_size == 0:
            empty += 1
        size += stat.st_size
        mtime = datetime.fromtimestamp(stat.st_mtime)
        if newest is None or mtime > newest:
            newest = mtime

    return {
        "total_count": total,
        "empty_count": empty,
        "total_size_mb": round(size / (1024 * 1024), 1),
        "newest_dt": newest,
    }


def _running_log_paths() -> set:
    """Load log_file paths from running_bots.json to avoid deleting active logs."""
    try:
        with open(BOTS_FILE, "r") as f:
            bots = json.load(f)
        return {b.get("log_file", "") for b in bots}
    except Exception:
        return set()


def cleanup_empty_logs() -> int:
    """Delete 0-byte .log files. Return count deleted."""
    if not LOGS_DIR.is_dir():
        return 0

    protected = _running_log_paths()
    count = 0
    for entry in os.scandir(LOGS_DIR):
        if not entry.name.endswith(".log") or not entry.is_file():
            continue
        if entry.stat().st_size == 0 and entry.path not in protected:
            try:
                os.remove(entry.path)
                count += 1
            except OSError:
                pass
    return count


def cleanup_old_logs(max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> int:
    """Delete logs older than N days (by mtime). Skip running bot logs. Return count."""
    if not LOGS_DIR.is_dir():
        return 0

    protected = _running_log_paths()
    cutoff = datetime.now() - timedelta(days=max_age_days)
    count = 0

    for entry in os.scandir(LOGS_DIR):
        if not entry.name.endswith(".log") or not entry.is_file():
            continue
        if entry.path in protected:
            continue
        mtime = datetime.fromtimestamp(entry.stat().st_mtime)
        if mtime < cutoff:
            try:
                os.remove(entry.path)
                count += 1
            except OSError:
                pass
    return count


def read_log_tail(log_path: str, n_lines: int = 100) -> str:
    """Return last N lines of a log file."""
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            tail = deque(f, maxlen=n_lines)
        return "".join(tail)
    except Exception:
        return ""


def read_log_errors(log_path: str, levels: list = None) -> list:
    """
    Return lines matching given log levels. Default: ERROR + WARNING.
    Caps at 500 lines.
    """
    if levels is None:
        levels = ["ERROR", "WARN"]

    patterns = [f"[{lv}]" for lv in levels]
    matches = []

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if any(p in line for p in patterns):
                    matches.append(line)
                    if len(matches) >= 500:
                        break
    except Exception:
        pass

    return matches
