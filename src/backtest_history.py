"""
Backtest History Storage and Export Module
- Stores backtest results for comparison
- Exports to Excel with multiple sheets
"""

import json
import os
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional
import pandas as pd


DATA_DIR = Path(__file__).parent.parent / "data"
HISTORY_FILE = DATA_DIR / "backtest_history.json"


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


def _strip_debug_fields(trade: dict) -> dict:
    """Remove underscore-prefixed debug keys that are not JSON-serializable."""
    return {k: v for k, v in trade.items() if not k.startswith("_")}


def save_backtest_result(
    config: dict,
    results: dict,
    strategy_name: str,
    symbol: str
) -> str:
    """
    Save a backtest result to history.

    Args:
        config: Backtest configuration parameters
        results: Backtest results dict
        strategy_name: Name of the strategy
        symbol: Trading symbol

    Returns:
        ID of the saved record
    """
    history = _load_history()

    # Generate unique ID
    record_id = datetime.now().strftime('%Y%m%d_%H%M%S')

    record = {
        'id': record_id,
        'timestamp': datetime.now().isoformat(),
        'strategy': strategy_name,
        'symbol': symbol,
        'config': config,
        'summary': {
            'total_trades': results.get('total_trades', 0),
            'wins': results.get('wins', 0),
            'losses': results.get('losses', 0),
            'win_rate': results.get('win_rate', 0),
            'profit_factor': results.get('profit_factor', 0),
            'total_pnl': results.get('total_pnl', 0),
            'total_pnl_usd': results.get('total_pnl_usd', 0),
            'avg_pnl': results.get('avg_pnl', 0),
            'best_trade': results.get('best_trade', 0),
            'worst_trade': results.get('worst_trade', 0),
            'max_consecutive_wins': results.get('max_consecutive_wins', 0),
            'max_consecutive_losses': results.get('max_consecutive_losses', 0),
            'tp_exits': results.get('tp_exits', 0),
            'sl_exits': results.get('sl_exits', 0),
            'time_exits': results.get('time_exits', 0),
            'starting_equity': results.get('starting_equity', 0),
            'final_equity': results.get('final_equity', 0),
        },
        'trades': [_strip_debug_fields(t) for t in results.get('trades', [])]
    }

    history.append(record)
    _save_history(history)

    return record_id


def get_history() -> list:
    """Get all backtest history records (without trades for performance)"""
    history = _load_history()
    # Return without trades for listing (lighter)
    return [
        {
            'id': r['id'],
            'timestamp': r['timestamp'],
            'strategy': r['strategy'],
            'symbol': r['symbol'],
            'config': r['config'],
            'summary': r['summary']
        }
        for r in history
    ]


def get_history_record(record_id: str) -> Optional[dict]:
    """Get a specific history record by ID (includes trades)"""
    history = _load_history()
    for record in history:
        if record['id'] == record_id:
            return record
    return None


def delete_history_record(record_id: str) -> bool:
    """Delete a history record by ID"""
    history = _load_history()
    original_len = len(history)
    history = [r for r in history if r['id'] != record_id]

    if len(history) < original_len:
        _save_history(history)
        return True
    return False


def clear_history():
    """Clear all history"""
    _save_history([])


def history_to_dataframe(history: list) -> pd.DataFrame:
    """Convert history to a comparison DataFrame"""
    if not history:
        return pd.DataFrame()

    rows = []
    for r in history:
        config = r.get('config', {})
        summary = r.get('summary', {})

        row = {
            # Core info
            'ID': r['id'],
            'Date': datetime.fromisoformat(r['timestamp']).strftime('%Y-%m-%d %H:%M'),
            'Strategy': r.get('strategy', ''),
            'Symbol': r.get('symbol', ''),

            # Config - Basic
            'Timeframe': config.get('timeframe', ''),
            'Entry Time': config.get('entry_time', ''),
            'Lot Mode': config.get('lot_mode', ''),
            'RR': round(float(config.get('rr_ratio', 0) or 0), 1),

            # Config - Optional
            'Date Range': f"{config.get('start_date', '')} ~ {config.get('end_date', '')}",
            'Start Time': config.get('entry_start_time', '00:00'),
            'End Time': config.get('entry_end_time', '23:59'),
            'Entry Mode': config.get('entry_mode', ''),
            'Entry %': round(float(config.get('entry_percent', 0) or 0), 1),
            'Max Candles': config.get('max_candles', '') or 'Off',
            'K': round(float(config.get('buffer_k', 0) or 0), 1),
            'Entry Type': config.get('entry_type', 'time'),
            'EMA Period': config.get('ema_period', ''),
            'EMA Dist': (f"{config.get('ema_dist_pips', 0)}p" if config.get('ema_dist_enabled') else 'Off'),
            'TP Type': config.get('tp_type', ''),
            'SL Type': config.get('sl_type', ''),
            'Fixed Lot': round(float(config.get('fixed_lot', 0) or 0), 2),
            'Start Equity': config.get('starting_equity', ''),
            'Risk Mode': config.get('risk_mode', ''),
            'Risk %': round(float(config.get('risk_percent', 0) or 0), 1),
            'Risk $': config.get('risk_amount', ''),

            # Summary - Core
            'Trades': summary.get('total_trades', 0),
            'Wins': summary.get('wins', 0),
            'Losses': summary.get('losses', 0),
            'Win %': round(float(summary.get('win_rate', 0) or 0), 1),
            'P/F': summary.get('profit_factor', 0),
            'Total Pips': summary.get('total_pnl', 0),

            # Summary - Optional
            'Avg Pips': summary.get('avg_pnl', 0),
            'Total USD': round(float(summary.get('total_pnl_usd', 0) or 0), 1),
            'Best': summary.get('best_trade', 0),
            'Worst': summary.get('worst_trade', 0),
            'Max Wins': summary.get('max_consecutive_wins', 0),
            'Max Losses': summary.get('max_consecutive_losses', 0),
            'TP Exits': summary.get('tp_exits', 0),
            'SL Exits': summary.get('sl_exits', 0),
            'Time Exits': summary.get('time_exits', 0),
            'Final Equity': summary.get('final_equity', 0),
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    return df


# Column definitions for UI
HISTORY_COLUMNS = {
    # Always shown (core) -- in this exact order
    'core': [
        'Date Range',
        'Start Time',
        'End Time',
        'Trades',
        'Win %',
        'Total USD',
        'RR',
        'Max Candles',
        'Entry %',
        'Risk %',
        'K',
        'Risk $',
        'Fixed Lot',
        'Risk Mode',
        'TP Exits',
        'SL Exits',
        'Time Exits',
        'Final Equity',
    ],

    # Config columns (optional, shown/hidden via multiselect)
    'config': [
        'Strategy', 'Symbol', 'Timeframe',
        'Entry Time', 'Entry Type', 'EMA Period', 'EMA Dist',
        'Entry Mode', 'Total Pips', 'Lot Mode', 'Start Equity',
        'TP Type', 'SL Type',
    ],

    # Summary columns (optional)
    'summary': [
        'Wins', 'Losses', 'Avg Pips', 'Best', 'Worst',
        'Max Wins', 'Max Losses', 'P/F',
    ],

    # Default optional columns to show in multiselect
    'default_optional': ['Strategy', 'Symbol', 'Timeframe', 'Entry Type', 'SL Type'],
}


def create_excel_export(
    config: dict,
    results: dict,
    trades_df: pd.DataFrame,
    strategy_name: str,
    symbol: str
) -> BytesIO:
    """
    Create Excel file with Config/Summary and Trades sheets.

    Args:
        config: Backtest configuration
        results: Backtest results
        trades_df: DataFrame of trades (already formatted)
        strategy_name: Strategy name
        symbol: Trading symbol

    Returns:
        BytesIO buffer containing the Excel file
    """
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Config & Summary
        config_summary_data = []

        # Header
        config_summary_data.append(['BACKTEST REPORT', ''])
        config_summary_data.append(['Generated', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        config_summary_data.append(['', ''])

        # Configuration section
        config_summary_data.append(['=== CONFIGURATION ===', ''])
        config_summary_data.append(['Strategy', strategy_name])
        config_summary_data.append(['Symbol', symbol])
        config_summary_data.append(['Timeframe', config.get('timeframe', '')])
        config_summary_data.append(['Date Range', f"{config.get('start_date', '')} to {config.get('end_date', '')}"])
        config_summary_data.append(['Entry Time', config.get('entry_time', '')])
        config_summary_data.append(['Entry Mode', config.get('entry_mode', '')])
        if config.get('entry_mode') == 'range_percent':
            config_summary_data.append(['Entry Percent', f"{config.get('entry_percent', 0)}%"])
        config_summary_data.append(['RR Ratio', config.get('rr_ratio', '')])
        config_summary_data.append(['Max Candles', config.get('max_candles', 0) or 'Disabled'])
        config_summary_data.append(['Buffer K', f"{config.get('buffer_k', 0)} pips"])
        config_summary_data.append(['Lot Mode', 'Fixed' if config.get('lot_mode') == 'fixed' else 'Flex (Risk-based)'])
        config_summary_data.append(['TP Type', 'Price-based' if config.get('tp_type') == 'price_based' else 'Close-based'])
        config_summary_data.append(['SL Type', 'Close-based' if config.get('sl_type') == 'close_based' else 'Price-based'])

        if config.get('lot_mode') == 'flex':
            config_summary_data.append(['Starting Equity', f"${config.get('starting_equity', 0):.2f}"])
            config_summary_data.append(['Risk Mode', config.get('risk_mode', '')])
            if config.get('risk_mode') == 'percent':
                config_summary_data.append(['Risk %', f"{config.get('risk_percent', 0)}%"])
            else:
                config_summary_data.append(['Risk Amount', f"${config.get('risk_amount', 0):.2f}"])
        else:
            config_summary_data.append(['Fixed Lot', config.get('fixed_lot', 0.01)])

        config_summary_data.append(['', ''])

        # Summary section
        config_summary_data.append(['=== SUMMARY ===', ''])
        config_summary_data.append(['Total Trades', results.get('total_trades', 0)])
        config_summary_data.append(['Wins', results.get('wins', 0)])
        config_summary_data.append(['Losses', results.get('losses', 0)])
        config_summary_data.append(['Win Rate', f"{results.get('win_rate', 0)}%"])
        config_summary_data.append(['Profit Factor', results.get('profit_factor', 0)])
        config_summary_data.append(['', ''])
        config_summary_data.append(['Total P&L (pips)', results.get('total_pnl', 0)])
        config_summary_data.append(['Avg P&L (pips)', results.get('avg_pnl', 0)])
        config_summary_data.append(['Best Trade (pips)', results.get('best_trade', 0)])
        config_summary_data.append(['Worst Trade (pips)', results.get('worst_trade', 0)])

        if config.get('lot_mode') == 'flex':
            config_summary_data.append(['', ''])
            config_summary_data.append(['Total P&L (USD)', f"${results.get('total_pnl_usd', 0):.2f}"])
            config_summary_data.append(['Starting Equity', f"${results.get('starting_equity', 0):.2f}"])
            config_summary_data.append(['Final Equity', f"${results.get('final_equity', 0):.2f}"])
            roi = 0
            if results.get('starting_equity', 0) > 0:
                roi = ((results.get('final_equity', 0) - results.get('starting_equity', 0)) / results.get('starting_equity', 0)) * 100
            config_summary_data.append(['ROI', f"{roi:.2f}%"])

        config_summary_data.append(['', ''])
        config_summary_data.append(['Max Consecutive Wins', results.get('max_consecutive_wins', 0)])
        config_summary_data.append(['Max Consecutive Losses', results.get('max_consecutive_losses', 0)])
        config_summary_data.append(['', ''])
        config_summary_data.append(['TP Exits', results.get('tp_exits', 0)])
        config_summary_data.append(['SL Exits', results.get('sl_exits', 0)])
        config_summary_data.append(['Time Exits', results.get('time_exits', 0)])

        config_df = pd.DataFrame(config_summary_data, columns=['Parameter', 'Value'])
        config_df.to_excel(writer, sheet_name='Config & Summary', index=False)

        # Sheet 2: Trades
        trades_df.to_excel(writer, sheet_name='Trades', index=False)

        # Auto-adjust column widths
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width

    output.seek(0)
    return output
