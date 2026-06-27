"""
Strategy Manager Module

Load, save, list, and validate trading strategies from YAML files.
"""

import os
import yaml
from datetime import datetime
from typing import Optional

STRATEGIES_DIR = "strategies"


def get_strategies_dir() -> str:
    """Get strategies directory path"""
    os.makedirs(STRATEGIES_DIR, exist_ok=True)
    return STRATEGIES_DIR


def list_strategies() -> list:
    """
    List all strategies

    Returns:
        List of strategy dicts with basic info
    """
    strategies = []
    strategies_dir = get_strategies_dir()

    for filename in os.listdir(strategies_dir):
        if filename.endswith('.yaml') or filename.endswith('.yml'):
            filepath = os.path.join(strategies_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    if data:
                        strategies.append({
                            'id': data.get('id', filename.replace('.yaml', '').replace('.yml', '')),
                            'name': data.get('name', 'Unnamed'),
                            'version': data.get('version', '1.0'),
                            'description': data.get('description', ''),
                            'author': data.get('author', 'Unknown'),
                            'enabled': data.get('enabled', True),
                            'timeframe': data.get('entry', {}).get('timeframe', ''),
                            'entry_time': data.get('entry', {}).get('time', ''),
                            'filename': filename
                        })
            except Exception as e:
                print(f"Error loading {filename}: {e}")

    return strategies


def get_strategy(strategy_id: str) -> Optional[dict]:
    """
    Get full strategy by ID

    Args:
        strategy_id: Strategy ID

    Returns:
        Full strategy dict or None
    """
    strategies_dir = get_strategies_dir()

    # Try exact filename match first
    for ext in ['.yaml', '.yml']:
        filepath = os.path.join(strategies_dir, f"{strategy_id}{ext}")
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)

    # Try matching by id field
    for filename in os.listdir(strategies_dir):
        if filename.endswith('.yaml') or filename.endswith('.yml'):
            filepath = os.path.join(strategies_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    if data and data.get('id') == strategy_id:
                        return data
            except Exception:
                pass

    return None


def save_strategy(strategy: dict) -> tuple:
    """
    Save strategy to YAML file

    Args:
        strategy: Strategy dict

    Returns:
        (success, message)
    """
    strategies_dir = get_strategies_dir()

    # Validate required fields
    required = ['id', 'name']
    for field in required:
        if not strategy.get(field):
            return False, f"Missing required field: {field}"

    # Sanitize ID for filename
    strategy_id = strategy['id'].lower().replace(' ', '_')
    strategy['id'] = strategy_id

    # Add metadata
    if not strategy.get('created'):
        strategy['created'] = datetime.now().strftime('%Y-%m-%d')
    if not strategy.get('version'):
        strategy['version'] = '1.0'
    if 'enabled' not in strategy:
        strategy['enabled'] = True

    # Save to file
    filepath = os.path.join(strategies_dir, f"{strategy_id}.yaml")

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(strategy, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return True, f"Strategy saved: {filepath}"
    except Exception as e:
        return False, str(e)


def delete_strategy(strategy_id: str) -> tuple:
    """
    Delete strategy file

    Args:
        strategy_id: Strategy ID

    Returns:
        (success, message)
    """
    strategies_dir = get_strategies_dir()

    for ext in ['.yaml', '.yml']:
        filepath = os.path.join(strategies_dir, f"{strategy_id}{ext}")
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                return True, f"Strategy deleted: {strategy_id}"
            except Exception as e:
                return False, str(e)

    return False, f"Strategy not found: {strategy_id}"


def toggle_strategy(strategy_id: str, enabled: bool) -> tuple:
    """
    Enable or disable strategy

    Args:
        strategy_id: Strategy ID
        enabled: True to enable, False to disable

    Returns:
        (success, message)
    """
    strategy = get_strategy(strategy_id)
    if not strategy:
        return False, f"Strategy not found: {strategy_id}"

    strategy['enabled'] = enabled
    return save_strategy(strategy)


def get_strategy_choices() -> list:
    """
    Get list of (id, name) tuples for dropdown

    Returns:
        List of tuples [(id, name), ...]
    """
    strategies = list_strategies()
    return [(s['id'], s['name']) for s in strategies if s.get('enabled', True)]


def get_strategy_parameters(strategy_id: str) -> dict:
    """
    Get strategy parameters for backtest/bot

    Args:
        strategy_id: Strategy ID

    Returns:
        dict with parameters
    """
    strategy = get_strategy(strategy_id)
    if not strategy:
        return {}

    entry = strategy.get('entry', {})
    exit_config = strategy.get('exit', {})
    params = strategy.get('parameters', {})

    return {
        'timeframe': entry.get('timeframe', 'M5'),
        'entry_type': entry.get('type', 'time'),
        'entry_time': entry.get('time', '21:05'),
        'timezone': entry.get('timezone', 'Asia/Ho_Chi_Minh'),
        'pattern': entry.get('pattern', ''),
        'ema_period': entry.get('ema_period', 21),
        'h2_exceed_pips': entry.get('h2_exceed_pips', 0.0),
        'c2_gap_pips': entry.get('c2_gap_pips', 0.0),
        'ema_margin_pips': entry.get('ema_margin_pips', 0.0),
        'sl_pips': params.get('sl_pips', 30),
        'rr_ratio': params.get('rr_ratio', 2.0),
        'buffer_k': params.get('buffer_k', 5),
        'lot_size': params.get('lot_size', 0.01),
        'entry_mode': params.get('entry_mode', 'close'),
        'entry_percent': params.get('entry_percent', 0.0),
        'max_candles': exit_config.get('time_limit', {}).get('max_candles', 7),
        'tp_type': exit_config.get('tp', {}).get('type', 'price_based'),
        'sl_type': exit_config.get('sl', {}).get('type', 'close_based'),
        'symbols': strategy.get('symbols', [])
    }


def create_default_strategy() -> dict:
    """
    Create a default strategy template

    Returns:
        dict with default strategy structure
    """
    return {
        'id': '',
        'name': '',
        'version': '1.0',
        'description': '',
        'author': '',
        'created': datetime.now().strftime('%Y-%m-%d'),
        'enabled': True,
        'entry': {
            'timeframe': 'M5',
            'time': '21:05',
            'timezone': 'Asia/Ho_Chi_Minh',
            'rules': {
                'bullish': 'close > open -> BUY',
                'bearish': 'close < open -> SELL',
                'doji': 'close == open -> SKIP'
            }
        },
        'exit': {
            'tp': {
                'type': 'price_based',
                'description': 'Immediate exit when price touches TP'
            },
            'sl': {
                'type': 'close_based',
                'description': 'Exit when candle closes beyond SL'
            },
            'time_limit': {
                'enabled': True,
                'max_candles': 7
            }
        },
        'parameters': {
            'sl_pips': 30,
            'rr_ratio': 2.0,
            'lot_size': 0.01
        },
        'symbols': ['XAUUSD', 'BTCUSD', 'ETHUSD']
    }
