"""
Backtest Module for Multiple Master Candle Strategy

Extends backtest.py to handle multiple master candles within a time window.
Instead of one specific entry time, scans ALL candles between window_start
and window_end each day, spawning an independent trade per qualifying candle.

Fill/exit logic is identical to backtest.py (mirrors bot_runner.py exactly).
"""

from zoneinfo import ZoneInfo
import pandas as pd

from src.utils import get_pip_value, get_point_value, get_pip_value_per_lot, check_exit
from src.backtest import calculate_flex_lot_size, calculate_stats

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


# -- Helpers (copied from backtest.py -- private there, duplicated here) ------

def _check_limit_fill(direction: str, candle: dict, entry_price: float) -> tuple:
    """
    Check if a LIMIT order fills on this candle. Copied from backtest.py.

    BUY LIMIT: open >= entry AND low <= entry -> fill at entry_price
    SELL LIMIT: open <= entry AND high >= entry -> fill at entry_price

    Returns:
        (filled: bool, fill_price: float or None)
    """
    ck_open = candle["open"]
    ck_high = candle["high"]
    ck_low  = candle["low"]

    if direction == "BUY":
        if ck_open >= entry_price and ck_low <= entry_price:
            return True, entry_price
    else:
        if ck_open <= entry_price and ck_high >= entry_price:
            return True, entry_price

    return False, None


def _price_past_sl(direction: str, candle: dict, stop_loss: float) -> bool:
    """
    Check if price passed SL before fill. Copied from backtest.py.
    """
    if direction == "BUY":
        return candle["low"] <= stop_loss
    else:
        return candle["high"] >= stop_loss


# -- Internal helpers ----------------------------------------------------------

def _make_missed(po: dict, reason: str, rr_ratio: float) -> dict:
    """Build a MISSED trade record from a pending order dict."""
    mt = po["master_time"]
    return {
        "date":                  mt.strftime("%Y-%m-%d"),
        "time":                  mt.strftime("%H:%M"),
        "direction":             po["direction"],
        "entry":                 po["entry_price"],
        "sl":                    po["stop_loss"],
        "tp":                    po["take_profit"],
        "sl_pips":               round(po["candle_sl_pips"], 1),
        "tp_pips":               round(po["candle_sl_pips"] * rr_ratio, 1),
        "exit_type":             "MISSED",
        "exit_price":            None,
        "pnl_pips":              0,
        "pnl_usd":               0,
        "lot":                   0,
        "candles":               0,
        "sl_moved_to_breakeven": False,
        "final_sl":              po["stop_loss"],
        "status":                "MISSED",
        "miss_reason":           reason,
        "priority":              po["priority"],
    }


def _finalize_trade(
    ot: dict,
    exit_type: str,
    exit_price: float,
    exit_time,
    pip_value: float,
    symbol: str,
    completed_trades: list,
    equity_curve_pips: list,
    equity_curve_usd: list,
) -> None:
    """
    Record a completed trade and append to equity curves in-place.

    Uses equity_curve_usd[-1] as current equity so multiple exits on the same
    candle stack correctly (second exit accounts for first exit P&L).
    """
    direction  = ot["direction"]
    fill_price = ot["fill_price"]
    lot_size   = ot["lot_size"]
    mt         = ot["master_time"]

    if direction == "BUY":
        pnl_pips = (exit_price - fill_price) / pip_value
    else:
        pnl_pips = (fill_price - exit_price) / pip_value

    pnl_usd    = lot_size * pnl_pips * get_pip_value_per_lot(symbol)
    new_equity = equity_curve_usd[-1] + pnl_usd

    completed_trades.append({
        "date":                  mt.strftime("%Y-%m-%d"),
        "time":                  mt.strftime("%H:%M"),
        "direction":             direction,
        "entry":                 fill_price,
        "sl":                    ot["stop_loss"],
        "tp":                    ot["take_profit"],
        "sl_pips":               round(ot["sl_pips"], 1),
        "lot":                   lot_size,
        "exit_type":             exit_type,
        "exit_price":            exit_price,
        "exit_time":             exit_time.strftime("%H:%M") if exit_time else "",
        "candles":               ot["candles_held"],
        "pnl_pips":              round(pnl_pips, 1),
        "pnl_usd":               round(pnl_usd, 2),
        "sl_moved_to_breakeven": ot["sl_moved_to_breakeven"],
        "final_sl":              ot["current_sl"],
        "priority":              ot["priority"],
    })

    equity_curve_pips.append(equity_curve_pips[-1] + pnl_pips)
    equity_curve_usd.append(new_equity)


# -- Main backtest function ----------------------------------------------------

def run_backtest_multi(
    df: pd.DataFrame,
    symbol: str,
    window_start_hour: int = 9,
    window_start_minute: int = 0,
    window_end_hour: int = 11,
    window_end_minute: int = 0,
    priority_direction: str = "auto",
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
    pending_order_expire_candles: int = 0,
) -> dict:
    """
    Run backtest for Multiple Master Candle Strategy.

    Scans all candles whose open time falls in [window_start, window_end] each
    day. Each qualifying candle (direction matches priority_direction) spawns
    an independent trade using identical fill/exit logic to run_backtest().

    Multiple trades can be active simultaneously. Equity is shared: each trade
    uses current_equity at fill time for flex lot calculation.

    Args:
        df: DataFrame with OHLC data (time column must be timezone-aware).
        symbol: Trading symbol.
        window_start_hour / window_start_minute: Start of scan window (inclusive).
        window_end_hour   / window_end_minute:   End of scan window (inclusive).
        priority_direction:
            "BUY"  -- only BUY master candles (Close > Open).
            "SELL" -- only SELL master candles (Close < Open).
            "auto" -- first master candle each day locks direction for that day.
        rr_ratio: Risk:Reward ratio.
        max_candles: Max monitoring candles after fill (0 = no limit, no time exit).
        lot_mode: "fixed" or "flex".
        fixed_lot: Lot size for fixed mode.
        risk_percent: Risk % per trade for flex/percent mode (e.g. 0.5 = 0.5%).
        risk_amount: Fixed risk in USD for flex/fixed_amount mode.
        risk_mode: "percent" or "fixed_amount" (also accepts legacy "amount").
        risk_compounding: If True, pct risk based on current equity; else starting equity.
        buffer_k: Buffer points added beyond master candle wick for SL.
        starting_equity: Starting equity in USD.
        tp_type: "price_based" (wick touch) or "close_based" (candle close).
        sl_type: "close_based" (candle close) or "price_based" (wick touch).
        entry_mode: "close" (LIMIT at close) or "range_percent" (LIMIT at pct of body).
        entry_percent: For range_percent -- distance from close as pct of candle body.
        move_sl_to_breakeven: If True, move SL to breakeven when trigger is hit.
        breakeven_trigger_percent: pct of TP distance that triggers SL move (default 50).
        breakeven_target: "entry" (fill price) or "close" (master candle close).
        pending_order_max_candles: Kept for API parity with run_backtest -- not used.
        pending_order_expire_candles: Cancel LIMIT if not filled within N candles
            (0 = unlimited).

    Returns:
        Same dict format as run_backtest():
            trades           -- list of trade dicts; each has a "priority" field.
            equity_curve     -- cumulative P&L in pips (list, starting at 0).
            equity_curve_usd -- equity in USD after each completed trade.
            total_trades, wins, losses, win_rate, total_pnl, total_pnl_usd, ...
            lot_mode, final_equity, starting_equity, ohlc_data.
    """
    # Normalize risk_mode for backward compatibility
    if risk_mode == "amount":
        risk_mode = "fixed_amount"

    pip_value   = get_pip_value(symbol)
    point_value = get_point_value(symbol)

    window_start_mins = window_start_hour * 60 + window_start_minute
    window_end_mins   = window_end_hour   * 60 + window_end_minute

    # -- State -----------------------------------------------------------------
    current_equity          = float(starting_equity)
    priority_locked_per_day = {}  # date -> locked direction (for "auto" mode)

    # pending_orders entries:
    #   {master_iloc, master_time, master_close, direction, entry_price,
    #    stop_loss, take_profit, candle_sl_pips, priority, candles_waited}
    pending_orders: list = []

    # open_trades entries:
    #   {master_time, master_close, direction, fill_price, stop_loss,
    #    take_profit, sl_pips, lot_size, fill_iloc, fill_time,
    #    candles_held, current_sl, sl_moved_to_breakeven, priority}
    open_trades: list = []

    completed_trades:  list = []
    equity_curve_pips: list = [0.0]
    equity_curve_usd:  list = [float(starting_equity)]

    n = len(df)
    for iloc in range(n):
        row      = df.iloc[iloc]
        row_time = row["time"]
        row_date = row_time.date()
        row_mins = row_time.hour * 60 + row_time.minute

        ck = {
            "open":  float(row["open"]),
            "high":  float(row["high"]),
            "low":   float(row["low"]),
            "close": float(row["close"]),
        }

        # -- STEP 1: Identify master candles in the window --------------------
        if window_start_mins <= row_mins <= window_end_mins:
            o, h, l, c = ck["open"], ck["high"], ck["low"], ck["close"]
            direction = "BUY" if c > o else "SELL"

            # Resolve effective priority for this day
            if priority_direction == "auto":
                if row_date not in priority_locked_per_day:
                    priority_locked_per_day[row_date] = direction
                effective_priority = priority_locked_per_day[row_date]
            else:
                effective_priority = priority_direction

            if direction == effective_priority:
                buffer_offset = buffer_k * point_value
                candle_body   = abs(c - o)

                if direction == "BUY":
                    entry_price = (
                        c - (entry_percent / 100.0) * candle_body
                        if entry_mode == "range_percent" else c
                    )
                    stop_loss   = l - buffer_offset
                    sl_pips_mc  = (entry_price - stop_loss) / pip_value
                    risk_dist   = entry_price - stop_loss
                    take_profit = entry_price + (risk_dist * rr_ratio)
                else:  # SELL
                    entry_price = (
                        c + (entry_percent / 100.0) * candle_body
                        if entry_mode == "range_percent" else c
                    )
                    stop_loss   = h + buffer_offset
                    sl_pips_mc  = (stop_loss - entry_price) / pip_value
                    risk_dist   = stop_loss - entry_price
                    take_profit = entry_price - (risk_dist * rr_ratio)

                pending_orders.append({
                    "master_iloc":    iloc,
                    "master_time":    row_time,
                    "master_close":   c,
                    "direction":      direction,
                    "entry_price":    entry_price,
                    "stop_loss":      stop_loss,
                    "take_profit":    take_profit,
                    "candle_sl_pips": sl_pips_mc,
                    "priority":       effective_priority,
                    "candles_waited": 0,
                })

        # -- STEP 2: Check pending orders for fill ----------------------------
        still_pending = []
        for po in pending_orders:
            if po["master_iloc"] >= iloc:
                # Created on this candle -- defer fill check to next candle
                still_pending.append(po)
                continue

            direction   = po["direction"]
            entry_price = po["entry_price"]
            stop_loss   = po["stop_loss"]
            ck_open     = ck["open"]
            ck_high     = ck["high"]
            ck_low      = ck["low"]

            # Increment wait counter
            po["candles_waited"] += 1

            # Fill logic -- mirrors run_backtest fill loop exactly.
            #
            # "close" mode (bot_runner market fallback):
            #   a. Open past entry AND past SL         -> MISSED
            #   b. Open past entry but NOT past SL     -> MARKET fill at open
            #   c. Open on correct side, wick touches  -> LIMIT fill at entry_price
            #
            # "range_percent" mode (bot_runner WAIT state):
            #   a. Open on wrong side AND wick hits SL -> MISSED
            #   b. Open on wrong side, no SL           -> WAIT (continue)
            #   c. Open on correct side, wick touches  -> LIMIT fill at entry_price
            filled            = False
            actual_fill_price = entry_price

            if direction == "BUY":
                if ck_open < entry_price:
                    # Open below entry
                    if ck_low <= stop_loss:
                        completed_trades.append(
                            _make_missed(po, "SL hit before fill", rr_ratio)
                        )
                        continue
                    if entry_mode == "close":
                        # Market fallback: fill at open price
                        filled            = True
                        actual_fill_price = ck_open
                    # range_percent: keep waiting (fall through to expire check)
                else:
                    # Open >= entry -- LIMIT can be placed, check wick fill
                    if ck_low <= entry_price:
                        filled            = True
                        actual_fill_price = entry_price

            else:  # SELL
                if ck_open > entry_price:
                    # Open above entry
                    if ck_high >= stop_loss:
                        completed_trades.append(
                            _make_missed(po, "SL hit before fill", rr_ratio)
                        )
                        continue
                    if entry_mode == "close":
                        filled            = True
                        actual_fill_price = ck_open
                else:
                    # Open <= entry -- LIMIT can be placed, check wick fill
                    if ck_high >= entry_price:
                        filled            = True
                        actual_fill_price = entry_price

            if not filled:
                # Check expire AFTER the fill attempt.
                # expire=N means we check N candles total before giving up.
                # candles_waited reaches N on the Nth candle; expire if no fill.
                if (pending_order_expire_candles > 0
                        and po["candles_waited"] >= pending_order_expire_candles):
                    completed_trades.append(
                        _make_missed(
                            po,
                            f"LIMIT not filled after {pending_order_expire_candles} candles",
                            rr_ratio,
                        )
                    )
                else:
                    still_pending.append(po)
                continue

            # -- Order filled -------------------------------------------------
            # Recalculate TP / SL distance if market fill (gap fill changes risk)
            take_profit_final = po["take_profit"]
            sl_pips_final     = po["candle_sl_pips"]

            if actual_fill_price != entry_price:
                if direction == "BUY":
                    r                 = actual_fill_price - stop_loss
                    take_profit_final = actual_fill_price + (r * rr_ratio)
                    sl_pips_final     = r / pip_value
                else:
                    r                 = stop_loss - actual_fill_price
                    take_profit_final = actual_fill_price - (r * rr_ratio)
                    sl_pips_final     = r / pip_value

            # Lot size computed at fill time using current_equity
            if lot_mode == "flex":
                if risk_mode == "fixed_amount":
                    lot_size = calculate_flex_lot_size(
                        equity=current_equity,
                        risk_percent=0,
                        sl_pips=sl_pips_final,
                        symbol=symbol,
                        risk_amount=risk_amount,
                    )
                else:
                    equity_for_risk = (
                        starting_equity if not risk_compounding else current_equity
                    )
                    lot_size = calculate_flex_lot_size(
                        equity=equity_for_risk,
                        risk_percent=risk_percent,
                        sl_pips=sl_pips_final,
                        symbol=symbol,
                    )
            else:
                lot_size = fixed_lot

            open_trades.append({
                "master_time":           po["master_time"],
                "master_close":          po["master_close"],
                "direction":             direction,
                "fill_price":            actual_fill_price,
                "stop_loss":             stop_loss,
                "take_profit":           take_profit_final,
                "sl_pips":               sl_pips_final,
                "lot_size":              lot_size,
                "fill_iloc":             iloc,
                "fill_time":             row_time,
                "candles_held":          0,
                "current_sl":            stop_loss,
                "sl_moved_to_breakeven": False,
                "priority":              po["priority"],
            })

        pending_orders = still_pending

        # -- STEP 3: Monitor open trades for exit -----------------------------
        still_open = []
        for ot in open_trades:
            if ot["fill_iloc"] >= iloc:
                # Filled on this candle -- start monitoring from next candle
                still_open.append(ot)
                continue

            ot["candles_held"] += 1

            # Breakeven SL move -- mirrors bot_runner test-mode logic exactly
            if move_sl_to_breakeven and not ot["sl_moved_to_breakeven"]:
                be_target = (
                    ot["master_close"]
                    if breakeven_target == "close"
                    else ot["fill_price"]
                )
                if ot["direction"] == "BUY":
                    tp_dist = ot["take_profit"] - ot["fill_price"]
                    trigger = ot["fill_price"] + (tp_dist * breakeven_trigger_percent / 100.0)
                    if ck["high"] >= trigger:
                        ot["current_sl"]            = be_target
                        ot["sl_moved_to_breakeven"] = True
                else:
                    tp_dist = ot["fill_price"] - ot["take_profit"]
                    trigger = ot["fill_price"] - (tp_dist * breakeven_trigger_percent / 100.0)
                    if ck["low"] <= trigger:
                        ot["current_sl"]            = be_target
                        ot["sl_moved_to_breakeven"] = True

            exit_type, exit_price = check_exit(
                ot["direction"], ck,
                ot["take_profit"], ot["current_sl"],
                tp_type, sl_type,
            )

            # Time exit -- only when max_candles is enabled (> 0)
            if not exit_type and max_candles > 0 and ot["candles_held"] >= max_candles:
                exit_type  = "TIME"
                exit_price = ck["close"]

            if exit_type:
                _finalize_trade(
                    ot, exit_type, exit_price, row_time,
                    pip_value, symbol,
                    completed_trades, equity_curve_pips, equity_curve_usd,
                )
                continue  # Trade closed -- do not add to still_open

            still_open.append(ot)

        open_trades = still_open

        # Update current_equity after all exits on this candle are processed.
        # Ensures the next candle fill checks use up-to-date equity.
        current_equity = equity_curve_usd[-1]

    # -- End of data: flush remaining pending orders --------------------------
    for po in pending_orders:
        completed_trades.append(
            _make_missed(po, "LIMIT never filled (end of data)", rr_ratio)
        )

    # Open trades with no exit at end of data are silently dropped.
    # (same behavior as run_backtest -- incomplete trades excluded from stats)

    # -- Build output (same format as run_backtest) ---------------------------
    stats                     = calculate_stats(completed_trades, lot_mode)
    stats["equity_curve"]     = equity_curve_pips
    stats["equity_curve_usd"] = equity_curve_usd
    stats["trades"]           = completed_trades
    stats["lot_mode"]         = lot_mode
    stats["final_equity"]     = current_equity
    stats["starting_equity"]  = starting_equity
    stats["ohlc_data"]        = df

    return stats
