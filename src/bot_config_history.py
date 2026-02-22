"""
Bot Config History Storage Module
- Stores bot configurations for reuse as presets
- Mirrors backtest_history.py pattern
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent.parent / "data"
HISTORY_FILE = DATA_DIR / "bot_config_history.json"


def _ensure_data_dir():
    """Ensure data directory exists"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_history() -> list:
    """Load history from JSON file"""
    _ensure_data_dir()
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_history(history: list):
    """Save history to JSON file"""
    _ensure_data_dir()
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def save_bot_config(bot_info: dict, preset_name: str = None) -> str:
    """
    Save a bot config to history.

    Args:
        bot_info: Bot info dict from start_bot() or manual preset
        preset_name: Optional custom name for the preset

    Returns:
        ID of the saved record
    """
    history = _load_history()

    user = bot_info.get('user', 'unknown')
    symbol = bot_info.get('symbol', 'UNKNOWN')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    record_id = f"{user}_{symbol}_{timestamp}"

    # Extract config fields (exclude runtime fields like pid, log_file, command)
    config_keys = [
        'strategy', 'symbol', 'test', 'lot_size', 'sl_pips', 'rr_ratio',
        'max_candles', 'interval', 'timeframe', 'entry_time', 'entry_mode',
        'entry_percent', 'buffer_k', 'lot_mode', 'starting_equity',
        'risk_mode', 'risk_percent', 'risk_amount', 'risk_compounding',
        'tp_type', 'sl_type', 'move_sl_to_breakeven',
        'breakeven_trigger_percent', 'pending_order_max_candles',
    ]
    config = {k: bot_info.get(k) for k in config_keys if bot_info.get(k) is not None}

    record = {
        'id': record_id,
        'timestamp': datetime.now().isoformat(),
        'user': user,
        'strategy': bot_info.get('strategy', ''),
        'symbol': symbol,
        'preset_name': preset_name,
        'config': config,
    }

    history.append(record)
    _save_history(history)

    return record_id


def get_config_history(username: str = None) -> list:
    """
    Get config history records (newest first).

    Args:
        username: Optional filter by user

    Returns:
        List of history records, newest first
    """
    history = _load_history()

    if username:
        history = [r for r in history if r.get('user') == username]

    # Newest first
    history.reverse()
    return history


def delete_config_record(record_id: str) -> bool:
    """Delete a config record by ID"""
    history = _load_history()
    original_len = len(history)
    history = [r for r in history if r['id'] != record_id]

    if len(history) < original_len:
        _save_history(history)
        return True
    return False
