"""
Backtest Module for Master Candle Strategy

Fetches historical M5 data from MT5 and simulates trades.
Mirrors bot_runner.py fill/exit logic exactly.
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

    # Round down to lot step (floor, never round up — avoids over-risking)
    lot_size = (lot_size // lot_step) * lot_step

    # If calculated lot is below minimum, return min_lot but caller should be
    # aware actual risk will exceed target (can't size smaller than broker minimum)
    if lot_size < min_lot:
        lot_size = min_lot

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


def _check_limit_fill(direction: str, candle: dict, entry_price: float) -> tuple:
    """
    Check if a LIMIT order would fill on this candle. Mirrors bot_runner logic.

    Bot runner flow for LIMIT orders:
    1. LIMIT can only be PLACED when price is on the correct side of entry
       (BUY LIMIT: ask > entry, SELL LIMIT: bid < entry).
    2. If price is already past entry, bot WAITS for price to return.
    3. LIMIT fills when price touches entry from the correct side.

    So in backtest terms:
    BUY LIMIT: open >= entry AND low <= entry → fills at entry_price
    SELL LIMIT: open <= entry AND high >= entry → fills at entry_price

    If open is on the wrong side (below entry for BUY, above entry for SELL),
    that candle is a "waiting" candle — no fill, no gap-fill. The bot waits
    for price to return to the correct side before placing the LIMIT.

    Returns:
        (filled: bool, fill_price: float or None)
    """
    ck_open = candle['open']
    ck_high = candle['high']
    ck_low  = candle['low']

    if direction == "BUY":
        # BUY LIMIT can only be placed when price > entry (open >= entry)
        if ck_open >= entry_price and ck_low <= entry_price:
            return True, entry_price
    else:  # SELL
        # SELL LIMIT can only be placed when price < entry (open <= entry)
        if ck_open <= entry_price and ck_high >= entry_price:
            return True, entry_price

    return False, None


def _price_past_sl(direction: str, candle: dict, stop_loss: float) -> bool:
    """
    Check if price has moved past SL on a candle (trade invalidated before fill).
    Mirrors live bot's pre-fill SL check.
    """
    if direction == "BUY":
        return candle['low'] <= stop_loss
    else:
        return candle['high'] >= stop_loss


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
    breakeven_target: str = "entry",
    pending_order_max_candles: int = 3,
    pending_order_expire_candles: int = 0
) -> dict:
    """
    Run backtest on historical data.

    Mirrors bot_runner.py fill/exit logic exactly:

    Entry flow:
        1. Entry candle closes → compute direction, entry_price, SL, TP.
        2. For each subsequent candle, simulate bot_runner state machine:

        "close" mode (bot_runner market fallback):
            a. If open past entry AND past SL → MISSED.
            b. If open past entry but NOT past SL → MARKET fill at open price.
            c. If open on correct side, wick touches entry → LIMIT fill at entry_price.

        "range_percent" mode (bot_runner WAIT state):
            a. If open on wrong side and wick hits SL → MISSED.
            b. If open on wrong side, no SL → WAIT (continue to next candle).
            c. If open on correct side, wick touches entry → LIMIT fill at entry_price.

        3. pending_order_expire_candles: if not filled within N candles → MISSED.
           0 = wait indefinitely.

    Exit flow (after fill, from next candle onward):
        - check_exit() per candle (same as live bot test-mode monitoring).
        - Breakeven SL move: same trigger logic as live bot.
        - Time exit: after max_candles candles (counted from fill candle+1).

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
        entry_mode: "close" (LIMIT at close price) or "range_percent" (LIMIT at % of body)
        entry_percent: For range_percent mode - BUY: High - X%(H-L), SELL: Low + X%(H-L)
        move_sl_to_breakeven: If True, move SL to entry when price reaches breakeven_trigger_percent of TP
        breakeven_trigger_percent: % of TP distance to trigger SL move (default 50%)
        breakeven_target: "entry" or "close" (master candle close price)
        pending_order_max_candles: Not used in backtest (kept for API compatibility)
        pending_order_expire_candles: Cancel LIMIT if not filled after N candles (0 = unlimited)

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

    # Find all entry candles
    entry_candles = df[(df['hour'] == entry_hour) & (df['minute'] == entry_minute)]

    for idx, entry_row in entry_candles.iterrows():
        entry_time = entry_row['time']
        o, h, l, c = entry_row['open'], entry_row['high'], entry_row['low'], entry_row['close']

        # Determine direction
        candle_body = abs(c - o)

        if c > o:
            direction = "BUY"
        elif c < o:
            direction = "SELL"
        else:
            # Doji - skip
            continue

        # Calculate entry price based on entry_mode
        buffer_offset = buffer_k * point_value

        if direction == "BUY":
            if entry_mode == "range_percent":
                entry_price = c - (entry_percent / 100) * candle_body
            else:
                entry_price = c

            stop_loss = l - buffer_offset
            candle_sl_pips = (entry_price - stop_loss) / pip_value
            risk = entry_price - stop_loss
            take_profit = entry_price + (risk * rr_ratio)

        else:  # SELL
            if entry_mode == "range_percent":
                entry_price = c + (entry_percent / 100) * candle_body
            else:
                entry_price = c

            stop_loss = h + buffer_offset
            candle_sl_pips = (stop_loss - entry_price) / pip_value
            risk = stop_loss - entry_price
            take_profit = entry_price - (risk * rr_ratio)

        # Calculate lot size
        if lot_mode == "flex":
            if risk_mode == "fixed_amount":
                lot_size = calculate_flex_lot_size(
                    equity=current_equity,
                    risk_percent=0,
                    sl_pips=candle_sl_pips,
                    symbol=symbol,
                    risk_amount=risk_amount
                )
            else:
                equity_for_risk = starting_equity if not risk_compounding else current_equity
                lot_size = calculate_flex_lot_size(
                    equity=equity_for_risk,
                    risk_percent=risk_percent,
                    sl_pips=candle_sl_pips,
                    symbol=symbol
                )
        else:
            lot_size = fixed_lot

        # ── PHASE 1: LIMIT ORDER FILL ─────────────────────────────────────────
        # Both 'close' and 'range_percent' modes place a LIMIT order.
        # Mirrors bot_runner state machine:
        #
        # "close" mode:
        #   - Price still above entry → LIMIT at entry, wait for fill
        #   - Price already below entry → market fill at open (unless SL hit → SKIP)
        #   - expire counts from entry candle (LIMIT is placed immediately)
        #
        # "range_percent" mode:
        #   - Price on correct side → place LIMIT immediately, wait for fill
        #   - Price on wrong side (open < entry for BUY) → WAIT (no LIMIT placed yet)
        #   - expire counts only from when LIMIT IS PLACED (price returns to correct side)
        #   - WAIT candles do NOT count against expire

        entry_df_idx = df.index.get_loc(idx)
        expire = pending_order_expire_candles
        # Scan all candles from entry+1 (expire enforced per-mode below)
        fill_candles = df.iloc[entry_df_idx + 1:]

        order_filled = False
        fill_candle_iloc = None   # integer position in df for the fill candle
        actual_fill_price = entry_price  # may differ if gap fill

        # Mirrors bot_runner two-phase expire (both use pending_order_expire_candles):
        #   Phase 1 – WAIT state (range_percent only): counting candles while price is on
        #     wrong side and LIMIT not yet placed. Expire → MISSED (bot stops).
        #   Phase 2 – FILL state: counting candles after LIMIT is placed on broker.
        #     Expire → LIMIT cancelled → MISSED. Counter resets when LIMIT is placed.
        # "close" mode skips WAIT phase entirely (LIMIT placed immediately at entry close).
        limit_placed = (entry_mode == "close")  # close mode: no WAIT phase
        candles_waited = 0        # Phase-1 counter (WAIT phase)
        candles_since_limit_placed = 0  # Phase-2 counter (FILL phase)

        for check_idx, check_candle in fill_candles.iterrows():
            ck_open  = check_candle['open']
            ck_high  = check_candle['high']
            ck_low   = check_candle['low']

            ck_close = check_candle['close']

            if direction == "BUY":
                if ck_open < entry_price:
                    # Price on wrong side — WAIT phase (range_percent) or gap-fill (close)
                    # SL invalidation respects sl_type:
                    #   price_based → wick hits SL → trade invalid immediately
                    #   close_based → only close below SL invalidates (wick alone is OK)
                    sl_invalid = (ck_low <= stop_loss) if sl_type == "price_based" else (ck_close <= stop_loss)
                    if sl_invalid:
                        break  # SL hit while waiting → MISSED

                    if entry_mode == "close":
                        # "close" mode: market fill at open
                        order_filled = True
                        fill_candle_iloc = df.index.get_loc(check_idx)
                        actual_fill_price = ck_open
                        break
                    else:
                        # "range_percent": WAIT — each candle counts against expire
                        candles_waited += 1
                        if expire > 0 and candles_waited >= expire:
                            break  # WAIT expired → MISSED
                        continue
                else:
                    # Open >= entry — LIMIT placed (or already was), FILL phase
                    if not limit_placed:
                        limit_placed = True
                        candles_since_limit_placed = 0  # reset for FILL phase

                    candles_since_limit_placed += 1
                    if expire > 0 and candles_since_limit_placed > expire:
                        break  # FILL expired → MISSED

                    if ck_low <= entry_price:
                        order_filled = True
                        fill_candle_iloc = df.index.get_loc(check_idx)
                        actual_fill_price = entry_price
                        break

            else:  # SELL
                if ck_open > entry_price:
                    # Price on wrong side — WAIT phase (range_percent) or gap-fill (close)
                    sl_invalid = (ck_high >= stop_loss) if sl_type == "price_based" else (ck_close >= stop_loss)
                    if sl_invalid:
                        break  # SL hit while waiting → MISSED

                    if entry_mode == "close":
                        # "close" mode: market fill at open
                        order_filled = True
                        fill_candle_iloc = df.index.get_loc(check_idx)
                        actual_fill_price = ck_open
                        break
                    else:
                        # "range_percent": WAIT — each candle counts against expire
                        candles_waited += 1
                        if expire > 0 and candles_waited >= expire:
                            break  # WAIT expired → MISSED
                        continue
                else:
                    # Open <= entry — LIMIT placed (or already was), FILL phase
                    if not limit_placed:
                        limit_placed = True
                        candles_since_limit_placed = 0

                    candles_since_limit_placed += 1
                    if expire > 0 and candles_since_limit_placed > expire:
                        break  # FILL expired → MISSED

                    if ck_high >= entry_price:
                        order_filled = True
                        fill_candle_iloc = df.index.get_loc(check_idx)
                        actual_fill_price = entry_price
                        break

        if not order_filled:
            if expire > 0:
                miss_reason = f"LIMIT not filled after {expire} candles"
            else:
                miss_reason = "LIMIT not filled (price hit SL before entry)" if len(fill_candles) > 0 else "LIMIT never filled (end of data)"
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
            continue

        # Recalculate SL/TP if market fill at different price ("close" mode gap fill)
        if actual_fill_price != entry_price:
            if direction == "BUY":
                risk = actual_fill_price - stop_loss
                take_profit = actual_fill_price + (risk * rr_ratio)
                candle_sl_pips = risk / pip_value
            else:
                risk = stop_loss - actual_fill_price
                take_profit = actual_fill_price - (risk * rr_ratio)
                candle_sl_pips = risk / pip_value

        # ── PHASE 2: EXIT MONITORING ──────────────────────────────────────────
        # Start monitoring from the candle AFTER the fill candle.
        # Mirrors bot_runner: LIMIT fill confirmed → next loop iteration monitors.

        exit_candles_start = fill_candle_iloc + 1

        if max_candles > 0:
            next_candles = df.iloc[exit_candles_start: exit_candles_start + max_candles]
        else:
            next_candles = df.iloc[exit_candles_start:]

        exit_type = None
        exit_price = None
        exit_time = None
        candles_held = 0
        sl_moved_to_breakeven = False
        current_sl = stop_loss

        for candle_idx, candle_row in next_candles.iterrows():
            candles_held += 1
            candle = {
                "high":  candle_row['high'],
                "low":   candle_row['low'],
                "close": candle_row['close']
            }

            # Breakeven SL move — mirrors bot_runner test-mode logic exactly
            if move_sl_to_breakeven and not sl_moved_to_breakeven:
                be_target = c if breakeven_target == "close" else actual_fill_price
                if direction == "BUY":
                    tp_distance = take_profit - actual_fill_price
                    trigger_price = actual_fill_price + (tp_distance * breakeven_trigger_percent / 100)
                    if candle['high'] >= trigger_price:
                        current_sl = be_target
                        sl_moved_to_breakeven = True
                else:  # SELL
                    tp_distance = actual_fill_price - take_profit
                    trigger_price = actual_fill_price - (tp_distance * breakeven_trigger_percent / 100)
                    if candle['low'] <= trigger_price:
                        current_sl = be_target
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

        # Skip if no exit data (end of dataset or max_candles disabled with no hit)
        if not exit_type:
            continue

        # Calculate P&L in pips using actual fill price
        if direction == "BUY":
            pnl_pips = (exit_price - actual_fill_price) / pip_value
        else:
            pnl_pips = (actual_fill_price - exit_price) / pip_value

        # Calculate P&L in USD
        pip_value_per_lot = get_pip_value_per_lot(symbol)
        pnl_usd = lot_size * pnl_pips * pip_value_per_lot

        # Update equity
        current_equity += pnl_usd

        trades.append({
            "date": entry_time.strftime("%Y-%m-%d"),
            "time": entry_time.strftime("%H:%M"),
            "direction": direction,
            "entry": actual_fill_price,
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
