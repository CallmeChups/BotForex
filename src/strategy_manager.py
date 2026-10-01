"""
Strategy Manager Module

Load, save, list, and validate trading strategies from YAML files.
"""

import os
import yaml
from datetime import datetime
from typing import Optional

STRATEGIES_DIR = "strategies"
FLAPPY_STRATEGY_IDS = frozenset({"flappy_bird", "multi_flappy_bird"})
SWING_STRATEGY_IDS = frozenset({"swing_ema_zigzag"})


def is_flappy_strategy(strategy_id: str) -> bool:
    """Return whether a strategy uses the Flappy Bird engine."""
    return strategy_id in FLAPPY_STRATEGY_IDS


def is_multi_flappy_strategy(strategy_id: str) -> bool:
    """Return whether a strategy uses the higher-timeframe Multi engine."""
    return strategy_id == "multi_flappy_bird"


def is_swing_strategy(strategy_id: str) -> bool:
    """Return whether a strategy uses the swing EMA zigzag engine."""
    return strategy_id in SWING_STRATEGY_IDS


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

    legacy_ema = entry.get('ema_periods', [13, 21, 55])
    consensus = entry.get('ema_consensus', {})
    fallback = entry.get('ema_fallback', {})
    if not isinstance(legacy_ema, list) or len(legacy_ema) != 3:
        legacy_ema = [13, 21, 55]

    def _ema_group(group):
        return {
            'short': int(group.get('short', legacy_ema[0])),
            'medium': int(group.get('medium', legacy_ema[1])),
            'long': int(group.get('long', legacy_ema[2])),
        }

    ema_consensus = _ema_group(consensus)
    ema_fallback = _ema_group(fallback)
    for name, group in (('consensus', ema_consensus), ('fallback', ema_fallback)):
        values = [group['short'], group['medium'], group['long']]
        if any(value < 2 for value in values) or not values[0] < values[1] < values[2]:
            raise ValueError(f"Flappy {name} EMA periods must satisfy 2 <= short < medium < long")

    higher_consensus = _ema_group(entry.get('higher_ema_consensus', {}))
    higher_fallback = _ema_group(entry.get('higher_ema_fallback', {}))
    for name, group in (('higher consensus', higher_consensus), ('higher fallback', higher_fallback)):
        values = [group['short'], group['medium'], group['long']]
        if any(value < 2 for value in values) or not values[0] < values[1] < values[2]:
            raise ValueError(f"Multi Flappy {name} EMA periods must satisfy 2 <= short < medium < long")

    swing_ema_periods = {
        'fast': int(legacy_ema[0]),
        'medium': int(legacy_ema[1]),
        'slow': int(legacy_ema[2]),
    }
    swing_fallback_config = entry.get('ema_fallback', {})
    if not isinstance(swing_fallback_config, dict):
        swing_fallback_config = {}
    swing_fallback_ema_periods = {
        slot: int(swing_fallback_config.get(slot, default))
        for slot, default in swing_ema_periods.items()
    }
    zigzag = entry.get('zigzag', {})
    zigzag_depth = int(zigzag.get('depth', 3))
    zigzag_deviation_points = float(zigzag.get('deviation_points', 3))
    zigzag_back_step = int(zigzag.get('back_step', 3))
    min_structure_candles = int(entry.get('min_structure_candles', 10))
    max_structure_candles = int(entry.get('max_structure_candles', 20))
    ema_cross_window_candles = int(entry.get('ema_cross_window_candles', 15))
    ema_exit_enabled = bool(exit_config.get('ema_exit', {}).get('enabled', True))
    ema_exit_period = int(exit_config.get('ema_exit', {}).get('period', 21))
    pending_expiry_candles = int(params.get('pending_expiry_candles', 7))
    max_pending_orders_per_symbol = int(params.get('max_pending_orders_per_symbol', 0))
    sl_buffer_pips = float(params.get('sl_buffer_pips', 5.0))
    entry_buffer_pips = float(params.get('entry_buffer_pips', 2.0))

    if is_swing_strategy(strategy_id):
        swing_values = [
            swing_ema_periods['fast'],
            swing_ema_periods['medium'],
            swing_ema_periods['slow'],
        ]
        if any(value < 2 for value in swing_values) or not swing_values[0] < swing_values[1] < swing_values[2]:
            raise ValueError("Swing EMA periods must satisfy 2 <= fast < medium < slow")
        fallback_values = [
            swing_fallback_ema_periods['fast'],
            swing_fallback_ema_periods['medium'],
            swing_fallback_ema_periods['slow'],
        ]
        if (
            any(value < 2 for value in fallback_values)
            or not fallback_values[0] < fallback_values[1] < fallback_values[2]
        ):
            raise ValueError(
                "Swing fallback EMA periods must satisfy 2 <= fast < medium < slow"
            )
        if zigzag_depth <= 0:
            raise ValueError("Swing zigzag depth must be positive")
        if zigzag_deviation_points < 0:
            raise ValueError("Swing zigzag deviation_points cannot be negative")
        if zigzag_back_step < 0:
            raise ValueError("Swing zigzag back_step cannot be negative")
        if min_structure_candles <= 0:
            raise ValueError("Swing min_structure_candles must be positive")
        if max_structure_candles < min_structure_candles:
            raise ValueError("Swing max_structure_candles must be >= min_structure_candles")
        if ema_cross_window_candles < 0:
            raise ValueError("Swing ema_cross_window_candles cannot be negative")
        if ema_exit_period <= 0:
            raise ValueError("Swing ema_exit period must be positive")
        if pending_expiry_candles <= 0:
            raise ValueError("Swing pending_expiry_candles must be positive")
        if max_pending_orders_per_symbol < 0:
            raise ValueError("Swing max_pending_orders_per_symbol cannot be negative")
        if sl_buffer_pips < 0:
            raise ValueError("Swing sl_buffer_pips cannot be negative")
        if entry_buffer_pips < 0:
            raise ValueError("Swing entry_buffer_pips cannot be negative")

    return {
        'timeframe': entry.get('timeframe', 'M5'),
        'entry_type': entry.get('type', 'time'),
        'entry_time': entry.get('time', '21:05'),
        'timezone': entry.get('timezone', 'Asia/Ho_Chi_Minh'),
        'pattern': entry.get('pattern', ''),
        'ema_period': entry.get('ema_period', 21),
        'ema_periods': legacy_ema,
        'swing_ema_periods': swing_ema_periods,
        'swing_fallback_ema_periods': swing_fallback_ema_periods,
        'use_pivot2_for_buy': bool(entry.get('use_pivot2_for_buy', True)),
        'use_pivot2_for_sell': bool(entry.get('use_pivot2_for_sell', True)),
        'ema_consensus_enabled': bool(entry.get('ema_consensus_enabled', True)),
        'ema_consensus': ema_consensus,
        'ema_fallback': ema_fallback,
        'ema_fallback_enabled': bool(
            entry.get('ema_fallback_enabled', not is_swing_strategy(strategy_id))
        ),
        'current_timeframe_filter_enabled': bool(entry.get('current_timeframe_filter_enabled', True)),
        'higher_timeframe': entry.get('higher_timeframe', 'M5'),
        'higher_timeframe_filter_enabled': bool(entry.get('higher_timeframe_filter_enabled', False)),
        'higher_ema_consensus': higher_consensus,
        'higher_ema_fallback': higher_fallback,
        'higher_ema_consensus_enabled': bool(entry.get('higher_ema_consensus_enabled', True)),
        'higher_ema_fallback_enabled': bool(entry.get('higher_ema_fallback_enabled', True)),
        'h2_exceed_pips': entry.get('h2_exceed_pips', 0.0),
        'c2_gap_pips': entry.get('c2_gap_pips', 0.0),
        'ema_margin_pips': entry.get('ema_margin_pips', 0.0),
        'ema_filter_enabled': entry.get('ema_filter_enabled', True),
        'buy_ema_side': entry.get('buy_ema_side', 'below_ema'),
        'sell_ema_side': entry.get('sell_ema_side', 'above_ema'),
        'sl_pips': params.get('sl_pips', 30),
        'rr_ratio': params.get('rr_ratio', 2.0),
        'buffer_k': params.get('buffer_k', 5),
        'lot_size': params.get('lot_size', 0.01),
        'entry_mode': params.get('entry_mode', 'close'),
        'entry_percent': params.get('entry_percent', 0.0),
        'entry_body_percent': params.get('entry_body_percent', 5.0),
        'sl_buffer_pips': sl_buffer_pips,
        'entry_buffer_pips': entry_buffer_pips,
        'min_father_body_points': params.get('min_father_body_points', 2.0),
        'min_child_candles': params.get('min_child_candles', 2),
        'max_child_candles': params.get('max_child_candles', 5),
        'max_child_body_points': params.get('max_child_body_points', 2.0),
        'cross_window_candles': params.get('cross_window_candles', 12),
        'zigzag_depth': zigzag_depth,
        'zigzag_deviation_points': zigzag_deviation_points,
        'zigzag_back_step': zigzag_back_step,
        'min_structure_candles': min_structure_candles,
        'max_structure_candles': max_structure_candles,
        'ema_cross_window_candles': ema_cross_window_candles,
        'ema_exit_enabled': ema_exit_enabled,
        'ema_exit_period': ema_exit_period,
        'pending_expiry_candles': pending_expiry_candles,
        'max_pending_orders_per_symbol': max_pending_orders_per_symbol,
        'mother_coverage_enabled': params.get('mother_coverage_enabled', True),
        'use_mother_candle': bool(params.get('use_mother_candle', True)),
        'no_mother_child_candles': int(params.get('no_mother_child_candles', 2)),
        'no_mother_child_body_ratio': float(params.get('no_mother_child_body_ratio', 1.5)),
        'no_mother_child_body_max_points': float(
            params.get('no_mother_child_body_max_points', 1.5)
        ),
        'no_mother_father_wick_max_pct': float(
            params.get('no_mother_father_wick_max_pct', 40.0)
        ),
        'no_mother_cross_window_candles': int(
            params.get('no_mother_cross_window_candles', 15)
        ),
        'no_mother_sl_buffer_pips': float(
            params.get('no_mother_sl_buffer_pips', 5.0)
        ),
        'limit_order_candles': params.get('limit_order_candles', 1),
        'magic': params.get('magic'),
        're_entry_after_sl': params.get('re_entry_after_sl', False),
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
