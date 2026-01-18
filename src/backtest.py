"""
Backtest Module for Master Candle Strategy

Fetches historical M5 data from MT5 and simulates trades.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def get_pip_value(symbol: str) -> float:
    """Get pip value for symbol"""
    if "BTC" in symbol:
        return 1.0
    elif "ETH" in symbol:
        return 0.1
    elif "XAU" in symbol:
        return 0.1
    elif "JPY" in symbol:
        return 0.01
    return 0.0001


def fetch_historical_data(symbol: str, start_date: datetime, end_date: datetime, credentials: dict = None) -> tuple:
    """
    Fetch historical M5 candles from MT5

    Args:
        symbol: Trading symbol
        start_date: Start date
        end_date: End date
        credentials: MT5 credentials dict

    Returns:
        (DataFrame with OHLC data, error message)
    """
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return None, "MT5 not available (Windows only)"

    # Initialize and login
    if not mt5.initialize():
        return None, "MT5 initialization failed"

    if credentials:
        login = int(credentials.get('login') or 0)
        password = credentials.get('password', '')
        server = credentials.get('server', '')

        if not login or not password or not server:
            mt5.shutdown()
            return None, "MT5 credentials not configured"

        if not mt5.login(login=login, password=password, server=server):
            error = mt5.last_error()
            mt5.shutdown()
            return None, f"MT5 login failed: {error}"

    # Fetch M5 candles
    try:
        rates = mt5.copy_rates_range(
            symbol,
            mt5.TIMEFRAME_M5,
            start_date,
            end_date
        )

        mt5.shutdown()

        if rates is None or len(rates) == 0:
            return None, f"No data found for {symbol}"

        # Convert to DataFrame
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df['time'] = df['time'].dt.tz_convert(TIMEZONE)

        return df, None

    except Exception as e:
        mt5.shutdown()
        return None, str(e)


def check_exit(direction: str, candle: dict, tp: float, sl: float) -> tuple:
    """
    Check exit conditions for a candle.

    TP: Price-based (immediate) - check High/Low
    SL: Close-based - check Close only

    Returns:
        (exit_type, exit_price) or (None, None)
    """
    h, l, c = candle["high"], candle["low"], candle["close"]

    if direction == "BUY":
        if h >= tp:
            return ("TP", tp)
        if c <= sl:
            return ("SL", c)
    else:  # SELL
        if l <= tp:
            return ("TP", tp)
        if c >= sl:
            return ("SL", c)

    return (None, None)


def run_backtest(
    df: pd.DataFrame,
    symbol: str,
    entry_hour: int = 21,
    entry_minute: int = 5,
    sl_pips: float = 30,
    rr_ratio: float = 2.0,
    max_candles: int = 7
) -> dict:
    """
    Run backtest on historical data

    Args:
        df: DataFrame with OHLC data
        symbol: Trading symbol
        entry_hour: Entry candle hour (default 21)
        entry_minute: Entry candle minute (default 5)
        sl_pips: Stop loss in pips
        rr_ratio: Risk:Reward ratio
        max_candles: Max candles before time exit

    Returns:
        dict with results
    """
    pip_value = get_pip_value(symbol)
    sl_distance = sl_pips * pip_value

    trades = []
    equity_curve = [0]  # Start at 0

    # Group by date to find entry candles
    df['date'] = df['time'].dt.date
    df['hour'] = df['time'].dt.hour
    df['minute'] = df['time'].dt.minute

    # Find all entry candles (21:05)
    entry_candles = df[(df['hour'] == entry_hour) & (df['minute'] == entry_minute)]

    for idx, entry_row in entry_candles.iterrows():
        entry_time = entry_row['time']
        o, h, l, c = entry_row['open'], entry_row['high'], entry_row['low'], entry_row['close']

        # Determine direction
        if c > o:
            direction = "BUY"
            entry_price = c
            stop_loss = l - sl_distance
            risk = entry_price - stop_loss
            take_profit = entry_price + (risk * rr_ratio)
        elif c < o:
            direction = "SELL"
            entry_price = c
            stop_loss = h + sl_distance
            risk = stop_loss - entry_price
            take_profit = entry_price - (risk * rr_ratio)
        else:
            # Doji - skip
            continue

        # Get next candles for exit check
        entry_idx = df.index.get_loc(idx)
        next_candles = df.iloc[entry_idx + 1: entry_idx + 1 + max_candles]

        exit_type = None
        exit_price = None
        exit_time = None
        candles_held = 0

        for candle_idx, candle_row in next_candles.iterrows():
            candles_held += 1
            candle = {
                "high": candle_row['high'],
                "low": candle_row['low'],
                "close": candle_row['close']
            }

            exit_type, exit_price = check_exit(direction, candle, take_profit, stop_loss)

            if exit_type:
                exit_time = candle_row['time']
                break

        # Time exit if no TP/SL hit
        if not exit_type and len(next_candles) > 0:
            exit_type = "TIME"
            last_candle = next_candles.iloc[-1]
            exit_price = last_candle['close']
            exit_time = last_candle['time']
            candles_held = len(next_candles)

        # Skip if no exit data (end of dataset)
        if not exit_type:
            continue

        # Calculate P&L in pips
        if direction == "BUY":
            pnl_pips = (exit_price - entry_price) / pip_value
        else:
            pnl_pips = (entry_price - exit_price) / pip_value

        trades.append({
            "date": entry_time.strftime("%Y-%m-%d"),
            "time": entry_time.strftime("%H:%M"),
            "direction": direction,
            "entry": entry_price,
            "sl": stop_loss,
            "tp": take_profit,
            "exit_type": exit_type,
            "exit_price": exit_price,
            "exit_time": exit_time.strftime("%H:%M") if exit_time else "",
            "candles": candles_held,
            "pnl_pips": round(pnl_pips, 1)
        })

        # Update equity curve
        equity_curve.append(equity_curve[-1] + pnl_pips)

    # Calculate statistics
    stats = calculate_stats(trades)
    stats["equity_curve"] = equity_curve
    stats["trades"] = trades

    return stats


def calculate_stats(trades: list) -> dict:
    """Calculate backtest statistics"""
    if not trades:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "avg_pnl": 0,
            "best_trade": 0,
            "worst_trade": 0,
            "profit_factor": 0,
            "max_consecutive_wins": 0,
            "max_consecutive_losses": 0,
            "tp_exits": 0,
            "sl_exits": 0,
            "time_exits": 0
        }

    pnls = [t["pnl_pips"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    total_trades = len(trades)
    win_count = len(wins)
    loss_count = len(losses)

    # Profit factor
    total_wins = sum(wins) if wins else 0
    total_losses = abs(sum(losses)) if losses else 0
    profit_factor = total_wins / total_losses if total_losses > 0 else float('inf') if total_wins > 0 else 0

    # Max consecutive wins/losses
    max_consec_wins = 0
    max_consec_losses = 0
    current_wins = 0
    current_losses = 0

    for pnl in pnls:
        if pnl > 0:
            current_wins += 1
            current_losses = 0
            max_consec_wins = max(max_consec_wins, current_wins)
        elif pnl < 0:
            current_losses += 1
            current_wins = 0
            max_consec_losses = max(max_consec_losses, current_losses)
        else:
            current_wins = 0
            current_losses = 0

    # Exit type counts
    tp_exits = len([t for t in trades if t["exit_type"] == "TP"])
    sl_exits = len([t for t in trades if t["exit_type"] == "SL"])
    time_exits = len([t for t in trades if t["exit_type"] == "TIME"])

    return {
        "total_trades": total_trades,
        "wins": win_count,
        "losses": loss_count,
        "win_rate": round(win_count / total_trades * 100, 1) if total_trades > 0 else 0,
        "total_pnl": round(sum(pnls), 1),
        "avg_pnl": round(sum(pnls) / total_trades, 1) if total_trades > 0 else 0,
        "best_trade": round(max(pnls), 1) if pnls else 0,
        "worst_trade": round(min(pnls), 1) if pnls else 0,
        "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else "Inf",
        "max_consecutive_wins": max_consec_wins,
        "max_consecutive_losses": max_consec_losses,
        "tp_exits": tp_exits,
        "sl_exits": sl_exits,
        "time_exits": time_exits
    }
