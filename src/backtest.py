"""
Backtest Module for Master Candle Strategy

Fetches historical M5 data from MT5 and simulates trades.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd

from src.utils import get_pip_value, get_point_value, get_pip_value_per_lot, check_exit

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def calculate_flex_lot_size(
    equity: float,
    risk_percent: float,
    sl_pips: float,
    symbol: str,
    min_lot: float = 0.01,
    lot_step: float = 0.01,
    risk_amount: float = 0.0
) -> float:
    """
    Calculate lot size based on risk percentage or fixed amount.

    Formula: lot_size = risk_amount / (sl_pips × pip_value_per_lot)

    Example (XAUUSD):
        equity = $1000, risk = 0.5%, sl_pips = 50.5
        risk_amount = $1000 × 0.5% = $5
        lot_size = $5 / (50.5 × $10) = 0.0099 ≈ 0.01 lots
        Verify: 0.01 lots × 50.5 pips × $10/pip = $5.05 ✓

    Args:
        equity: Current account equity in USD
        risk_percent: Risk percentage per trade (e.g., 0.5 for 0.5%)
        sl_pips: Stop loss distance in pips
        symbol: Trading symbol
        min_lot: Minimum lot size (default 0.01)
        lot_step: Lot step increment (default 0.01)
        risk_amount: Fixed risk amount in USD (if > 0, overrides risk_percent)

    Returns:
        Calculated lot size (rounded down to lot_step)
    """
    if sl_pips <= 0:
        return min_lot

    # Use fixed risk_amount if provided, otherwise calculate from equity and percent
    if risk_amount > 0:
        actual_risk = risk_amount
    else:
        actual_risk = equity * (risk_percent / 100)

    # Get pip value per lot for symbol
    pip_value_per_lot = get_pip_value_per_lot(symbol)

    # lot_size = risk_amount / (sl_pips × pip_value_per_lot)
    lot_size = actual_risk / (sl_pips * pip_value_per_lot)

    # Round down to lot step
    lot_size = max(min_lot, (lot_size // lot_step) * lot_step)

    return round(lot_size, 2)


def get_mt5_timeframe(timeframe: str):
    """Convert timeframe string to MT5 constant"""
    try:
        import MetaTrader5 as mt5
        mapping = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }
        return mapping.get(timeframe, mt5.TIMEFRAME_M5)
    except ImportError:
        return None


def fetch_historical_data(symbol: str, start_date: datetime, end_date: datetime, credentials: dict = None, timeframe: str = "M5") -> tuple:
    """
    Fetch historical candles from MT5

    Args:
        symbol: Trading symbol
        start_date: Start date
        end_date: End date
        credentials: MT5 credentials dict
        timeframe: Timeframe string (M1, M5, M15, M30, H1, H4, D1)

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

    # Get MT5 timeframe constant
    mt5_timeframe = get_mt5_timeframe(timeframe)

    # Fetch candles
    try:
        rates = mt5.copy_rates_range(
            symbol,
            mt5_timeframe,
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


def run_backtest(
    df: pd.DataFrame,
    symbol: str,
    entry_hour: int = 21,
    entry_minute: int = 5,
    sl_pips: float = 0,
    rr_ratio: float = 2.0,
    max_candles: int = 7,
    lot_mode: str = "fixed",
    fixed_lot: float = 0.01,
    risk_percent: float = 0.5,
    risk_amount: float = 0.0,
    risk_mode: str = "percent",
    risk_compounding: bool = True,
    buffer_k: float = 5.0,
    starting_equity: float = 1000.0,
    tp_type: str = "price_based",
    sl_type: str = "close_based",
    entry_mode: str = "close",
    entry_percent: float = 0.0,
    move_sl_to_breakeven: bool = False,
    breakeven_trigger_percent: float = 50.0,
    pending_order_max_candles: int = 3
) -> dict:
    """
    Run backtest on historical data

    Args:
        df: DataFrame with OHLC data
        symbol: Trading symbol
        entry_hour: Entry candle hour (default 21)
        entry_minute: Entry candle minute (default 5)
        sl_pips: Deprecated, not used (kept for compatibility)
        rr_ratio: Risk:Reward ratio
        max_candles: Max candles before time exit (0 = no limit)
        lot_mode: "fixed" or "flex"
        fixed_lot: Lot size for fixed mode
        risk_percent: Risk % for flex mode (e.g., 0.5 = 0.5%)
        risk_amount: Fixed risk amount in USD for flex mode
        risk_mode: "percent" or "fixed_amount"
        risk_compounding: If True, % risk based on current equity. If False, % risk based on starting equity
        buffer_k: Buffer points added to SL beyond candle wick
        starting_equity: Starting equity in USD for flex mode
        tp_type: "price_based" (immediate on wick) or "close_based" (delayed on close)
        sl_type: "close_based" (delayed on close) or "price_based" (immediate on wick)
        entry_mode: "close" (enter at close) or "range_percent" (enter at % of H-L range)
        entry_percent: For range_percent mode - BUY: High - X%(H-L), SELL: Low + X%(H-L)
        move_sl_to_breakeven: If True, move SL to entry when price reaches breakeven_trigger_percent of TP
        breakeven_trigger_percent: % of TP distance to trigger SL move (default 50%)

    SL Calculation (both modes):
        BUY: SL pips = (Close - Low) / pip_value + buffer_k
        SELL: SL pips = (High - Close) / pip_value + buffer_k

    Returns:
        dict with results
    """
    # Normalize risk_mode for backward compatibility
    if risk_mode == "amount":
        risk_mode = "fixed_amount"

    pip_value = get_pip_value(symbol)
    point_value = get_point_value(symbol)

    trades = []
    equity_curve_pips = [0]  # P&L in pips
    equity_curve_usd = [starting_equity]  # Equity in USD

    # Current equity for flex mode
    current_equity = starting_equity

    # Group by date to find entry candles
    df['date'] = df['time'].dt.date
    df['hour'] = df['time'].dt.hour
    df['minute'] = df['time'].dt.minute

    # Find all entry candles (21:05)
    entry_candles = df[(df['hour'] == entry_hour) & (df['minute'] == entry_minute)]

    for idx, entry_row in entry_candles.iterrows():
        entry_time = entry_row['time']
        o, h, l, c = entry_row['open'], entry_row['high'], entry_row['low'], entry_row['close']

        # Determine direction and calculate entry/SL/TP
        # SL price = Low - buffer_k (BUY) or High + buffer_k (SELL)
        candle_body = abs(c - o)

        if c > o:
            direction = "BUY"

            # Calculate entry price based on entry_mode
            if entry_mode == "range_percent":
                # BUY: Close - X% of body (Close - Open)
                entry_price = c - (entry_percent / 100) * candle_body
            else:
                entry_price = c

            # buffer_k * point_value = price offset (uses point, not pip)
            buffer_offset = buffer_k * point_value

            # SL is placed buffer_offset below the Low
            stop_loss = l - buffer_offset

            # SL pips from entry to SL
            candle_sl_pips = (entry_price - stop_loss) / pip_value

            risk = entry_price - stop_loss
            take_profit = entry_price + (risk * rr_ratio)

        elif c < o:
            direction = "SELL"

            # Calculate entry price based on entry_mode
            if entry_mode == "range_percent":
                # SELL: Close + X% of body (Open - Close)
                entry_price = c + (entry_percent / 100) * candle_body
            else:
                entry_price = c

            # buffer_k * point_value = price offset (uses point, not pip)
            buffer_offset = buffer_k * point_value

            # SL is placed buffer_offset above the High
            stop_loss = h + buffer_offset

            # SL pips from entry to SL
            candle_sl_pips = (stop_loss - entry_price) / pip_value

            risk = stop_loss - entry_price
            take_profit = entry_price - (risk * rr_ratio)
        else:
            # Doji - skip
            continue

        # Calculate lot size
        if lot_mode == "flex":
            if risk_mode == "fixed_amount":
                # Fixed dollar amount risk - constant per trade
                lot_size = calculate_flex_lot_size(
                    equity=current_equity,
                    risk_percent=0,
                    sl_pips=candle_sl_pips,
                    symbol=symbol,
                    risk_amount=risk_amount
                )
            else:
                # Percentage risk
                # Use starting_equity if not compounding, current_equity if compounding
                equity_for_risk = starting_equity if not risk_compounding else current_equity
                lot_size = calculate_flex_lot_size(
                    equity=equity_for_risk,
                    risk_percent=risk_percent,
                    sl_pips=candle_sl_pips,
                    symbol=symbol
                )
        else:
            lot_size = fixed_lot

        # Simulate pending order for range_percent mode (LIMIT only, no market fallback)
        if entry_mode == "range_percent":
            # Get entry index
            entry_idx = df.index.get_loc(idx)

            # Check next candles to see if price touches entry_price
            # pending_order_max_candles=0 means unlimited wait (check all remaining)
            order_filled = False
            fill_candle_idx = None
            if pending_order_max_candles > 0:
                pending_candles_to_check = df.iloc[entry_idx + 1: entry_idx + 1 + pending_order_max_candles]
            else:
                pending_candles_to_check = df.iloc[entry_idx + 1:]

            for check_idx, check_candle in pending_candles_to_check.iterrows():
                # Safety: if price moved past SL before filling, invalidate
                if direction == "BUY" and check_candle['low'] <= stop_loss:
                    break  # Price hit SL zone before entry — skip
                elif direction == "SELL" and check_candle['high'] >= stop_loss:
                    break  # Price hit SL zone before entry — skip

                # Check if price touched entry_price
                if direction == "BUY":
                    # BUY LIMIT: price must go down to entry_price (or below)
                    if check_candle['low'] <= entry_price:
                        order_filled = True
                        fill_candle_idx = check_idx
                        break
                else:  # SELL
                    # SELL LIMIT: price must go up to entry_price (or above)
                    if check_candle['high'] >= entry_price:
                        order_filled = True
                        fill_candle_idx = check_idx
                        break

            # If order not filled within max candles, mark as MISSED
            if not order_filled:
                miss_reason = f"LIMIT not filled after {pending_order_max_candles} candles" if pending_order_max_candles > 0 else "LIMIT never filled (unlimited wait)"
                trades.append({
                    "date": entry_time.strftime("%Y-%m-%d"),
                    "time": entry_time.strftime("%H:%M"),
                    "direction": direction,
                    "entry": entry_price,
                    "sl": stop_loss,
                    "tp": take_profit,
                    "sl_pips": round(candle_sl_pips, 1),
                    "tp_pips": round(candle_sl_pips * rr_ratio, 1),
                    "exit_type": "MISSED",
                    "exit_price": None,
                    "pnl_pips": 0,
                    "pnl_usd": 0,
                    "lot": lot_size,
                    "candles": 0,
                    "sl_moved_to_breakeven": False,
                    "final_sl": stop_loss,
                    "status": "MISSED",
                    "miss_reason": miss_reason
                })
                continue  # Skip to next entry candle

            # Order filled - use fill_candle_idx as new entry point
            idx = fill_candle_idx

        # Get next candles for exit check
        entry_idx = df.index.get_loc(idx)

        # max_candles=0 means no limit - get all remaining candles
        if max_candles > 0:
            next_candles = df.iloc[entry_idx + 1: entry_idx + 1 + max_candles]
        else:
            next_candles = df.iloc[entry_idx + 1:]

        exit_type = None
        exit_price = None
        exit_time = None
        candles_held = 0
        sl_moved_to_breakeven = False
        current_sl = stop_loss  # Track current SL (may change if moved to breakeven)

        for candle_idx, candle_row in next_candles.iterrows():
            candles_held += 1
            candle = {
                "high": candle_row['high'],
                "low": candle_row['low'],
                "close": candle_row['close']
            }

            # Check if we should move SL to breakeven
            if move_sl_to_breakeven and not sl_moved_to_breakeven:
                if direction == "BUY":
                    tp_distance = take_profit - entry_price
                    trigger_price = entry_price + (tp_distance * breakeven_trigger_percent / 100)
                    # Check if price reached trigger (use HIGH for BUY)
                    if candle['high'] >= trigger_price:
                        current_sl = entry_price  # Move SL to breakeven
                        sl_moved_to_breakeven = True
                else:  # SELL
                    tp_distance = entry_price - take_profit
                    trigger_price = entry_price - (tp_distance * breakeven_trigger_percent / 100)
                    # Check if price reached trigger (use LOW for SELL)
                    if candle['low'] <= trigger_price:
                        current_sl = entry_price  # Move SL to breakeven
                        sl_moved_to_breakeven = True

            exit_type, exit_price = check_exit(direction, candle, take_profit, current_sl, tp_type, sl_type)

            if exit_type:
                exit_time = candle_row['time']
                break

        # Time exit if no TP/SL hit (only when max_candles is enabled)
        if not exit_type and len(next_candles) > 0 and max_candles > 0:
            exit_type = "TIME"
            last_candle = next_candles.iloc[-1]
            exit_price = last_candle['close']
            exit_time = last_candle['time']
            candles_held = len(next_candles)

        # Skip if no exit data (end of dataset or no TP/SL hit when max_candles disabled)
        if not exit_type:
            continue

        # Calculate P&L in pips
        if direction == "BUY":
            pnl_pips = (exit_price - entry_price) / pip_value
        else:
            pnl_pips = (entry_price - exit_price) / pip_value

        # Calculate P&L in USD
        # pnl_usd = lot_size * pnl_pips * pip_value_per_lot
        pip_value_per_lot = get_pip_value_per_lot(symbol)
        pnl_usd = lot_size * pnl_pips * pip_value_per_lot

        # Update equity
        current_equity += pnl_usd

        trades.append({
            "date": entry_time.strftime("%Y-%m-%d"),
            "time": entry_time.strftime("%H:%M"),
            "direction": direction,
            "entry": entry_price,
            "sl": stop_loss,
            "tp": take_profit,
            "sl_pips": round(candle_sl_pips, 1),
            "lot": lot_size,
            "exit_type": exit_type,
            "exit_price": exit_price,
            "exit_time": exit_time.strftime("%H:%M") if exit_time else "",
            "candles": candles_held,
            "pnl_pips": round(pnl_pips, 1),
            "pnl_usd": round(pnl_usd, 2),
            "sl_moved_to_breakeven": sl_moved_to_breakeven,
            "final_sl": current_sl
        })

        # Update equity curves
        equity_curve_pips.append(equity_curve_pips[-1] + pnl_pips)
        equity_curve_usd.append(current_equity)

    # Calculate statistics
    stats = calculate_stats(trades, lot_mode)
    stats["equity_curve"] = equity_curve_pips
    stats["equity_curve_usd"] = equity_curve_usd
    stats["trades"] = trades
    stats["lot_mode"] = lot_mode
    stats["final_equity"] = current_equity
    stats["starting_equity"] = starting_equity
    stats["ohlc_data"] = df  # Include OHLC data for interactive charts

    return stats


def calculate_stats(trades: list, lot_mode: str = "fixed") -> dict:
    """Calculate backtest statistics"""
    if not trades:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "total_pnl_usd": 0,
            "avg_pnl": 0,
            "avg_pnl_usd": 0,
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
    pnls_usd = [t.get("pnl_usd", 0) for t in trades]
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
        "total_pnl_usd": round(sum(pnls_usd), 2),
        "avg_pnl": round(sum(pnls) / total_trades, 1) if total_trades > 0 else 0,
        "avg_pnl_usd": round(sum(pnls_usd) / total_trades, 2) if total_trades > 0 else 0,
        "best_trade": round(max(pnls), 1) if pnls else 0,
        "worst_trade": round(min(pnls), 1) if pnls else 0,
        "best_trade_usd": round(max(pnls_usd), 2) if pnls_usd else 0,
        "worst_trade_usd": round(min(pnls_usd), 2) if pnls_usd else 0,
        "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else "Inf",
        "max_consecutive_wins": max_consec_wins,
        "max_consecutive_losses": max_consec_losses,
        "tp_exits": tp_exits,
        "sl_exits": sl_exits,
        "time_exits": time_exits
    }
