"""
Backtest Module for Master Candle Strategy

Fetches historical M5 data from MT5 and simulates trades.
"""

from datetime import datetime, timedelta, time as _time
from zoneinfo import ZoneInfo
import uuid
import pandas as pd

from src.utils import get_pip_value, check_exit, compute_trade_levels, _in_time_window
from src.feg_strategy import detect_feg_signal

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def get_pip_value_per_lot(symbol: str) -> float:
    """
    Get dollar value per pip per 1 standard lot.

    For XAUUSD: 1 lot = 100 oz, 1 pip = $0.1 → $10 per pip per lot
    For BTCUSD: 1 lot = 1 BTC, 1 pip = $1 → $1 per pip per lot
    For ETHUSD: 1 lot = 1 ETH, 1 pip = $0.1 → $0.1 per pip per lot
    For Forex: 1 lot = 100,000 units, 1 pip = 0.0001 → $10 per pip per lot
    """
    symbol_upper = symbol.upper()
    if "XAU" in symbol_upper:
        return 10.0  # 100 oz × $0.1 pip
    elif "BTC" in symbol_upper:
        return 1.0   # 1 BTC × $1 pip
    elif "ETH" in symbol_upper:
        return 0.1   # 1 ETH × $0.1 pip
    elif "JPY" in symbol_upper:
        return 10.0  # 100,000 × 0.01 pip / 100
    return 10.0  # Standard forex: 100,000 × 0.0001 = $10


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


def _compute_lot_size(lot_mode, current_equity, risk_mode, risk_percent, risk_amount, sl_pips, symbol, fixed_lot):
    """Tính lot theo mode fixed/flex (dùng chung cho mọi entry_type)."""
    if lot_mode == "flex":
        if risk_mode == "fixed_amount":
            return calculate_flex_lot_size(
                equity=current_equity, risk_percent=0, sl_pips=sl_pips,
                symbol=symbol, risk_amount=risk_amount,
            )
        return calculate_flex_lot_size(
            equity=current_equity, risk_percent=risk_percent, sl_pips=sl_pips, symbol=symbol,
        )
    return fixed_lot


def _simulate_exit(df, entry_pos, direction, tp, sl, max_candles, tp_type, sl_type,
                   be_enabled: bool = False, be_r: float = 1.0, entry_price: float = None):
    """
    Mô phỏng exit từ vị trí entry_pos (integer position). Trả:
        (exit_type, exit_price, exit_time, candles_held, exit_pos)
    exit_type None khi hết data mà không có TP/SL và max_candles=0.

    BE (Break-Even): khi giá đạt entry ± be_r * SL_distance, dời SL về entry.
    """
    if max_candles > 0:
        next_candles = df.iloc[entry_pos + 1: entry_pos + 1 + max_candles]
    else:
        next_candles = df.iloc[entry_pos + 1:]

    exit_type = exit_price = exit_time = None
    candles_held = 0
    exit_pos = entry_pos

    # BE: tính ngưỡng trigger và SL động
    current_sl = sl
    be_triggered = False
    if be_enabled and entry_price is not None:
        sl_distance = abs(entry_price - sl)
        be_trigger_price = (entry_price + be_r * sl_distance) if direction == "BUY" else (entry_price - be_r * sl_distance)
    else:
        be_trigger_price = None
        sl_distance = 0

    for offset, (_, row) in enumerate(next_candles.iterrows(), start=1):
        candles_held += 1
        exit_pos = entry_pos + offset

        # Check BE trigger trước khi check exit
        if be_enabled and not be_triggered and be_trigger_price is not None:
            if direction == "BUY" and row["high"] >= be_trigger_price:
                current_sl = entry_price
                be_triggered = True
            elif direction == "SELL" and row["low"] <= be_trigger_price:
                current_sl = entry_price
                be_triggered = True

        candle = {"high": row["high"], "low": row["low"], "close": row["close"]}
        exit_type, exit_price = check_exit(direction, candle, tp, current_sl, tp_type, sl_type)
        if exit_type:
            exit_time = row["time"]
            break

    if not exit_type and len(next_candles) > 0 and max_candles > 0:
        exit_type = "TIME"
        last = next_candles.iloc[-1]
        exit_price = last["close"]
        exit_time = last["time"]
        candles_held = len(next_candles)
        exit_pos = entry_pos + len(next_candles)

    return exit_type, exit_price, exit_time, candles_held, exit_pos


def _make_trade(entry_time, direction, levels, lot, exit_type, exit_price, exit_time, candles_held, symbol, exit_pos=None):
    """Dựng dict trade + tính pnl pips/usd."""
    pip_value = get_pip_value(symbol)
    entry = levels["entry_price"]
    if direction == "BUY":
        pnl_pips = (exit_price - entry) / pip_value
    else:
        pnl_pips = (entry - exit_price) / pip_value
    pnl_usd = lot * pnl_pips * get_pip_value_per_lot(symbol)
    trade = {
        "date": entry_time.strftime("%Y-%m-%d"),
        "time": entry_time.strftime("%H:%M"),
        "direction": direction,
        "entry": entry,
        "sl": levels["stop_loss"],
        "tp": levels["take_profit"],
        "sl_pips": round(levels["sl_pips"], 1),
        "lot": lot,
        "exit_type": exit_type,
        "exit_price": exit_price,
        "exit_time": exit_time.strftime("%H:%M") if exit_time else "",
        "candles": candles_held,
        "pnl_pips": round(pnl_pips, 1),
        "pnl_usd": round(pnl_usd, 2),
        "_exit_pos": exit_pos,
    }
    return trade, pnl_pips, pnl_usd


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
    buffer_k: float = 5.0,
    starting_equity: float = 1000.0,
    tp_type: str = "price_based",
    sl_type: str = "close_based",
    entry_mode: str = "close",
    entry_percent: float = 0.0,
    entry_type: str = "time",
    ema_period: int = 21,
    h2_exceed_pips: float = 0.0,
    c2_gap_pips: float = 0.0,
    ema_margin_pips: float = 0.0,
    entry_start_time: _time = _time(0, 0),
    entry_end_time: _time = _time(23, 59),
    limit_order_candles: int = 1,
    be_enabled: bool = False,
    be_r: float = 1.0,
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
        risk_mode: "percent" (risk changes with equity) or "fixed_amount" (constant risk)
        buffer_k: Buffer pips added to candle body for SL (both modes)
        starting_equity: Starting equity in USD for flex mode
        tp_type: "price_based" (immediate on wick) or "close_based" (delayed on close)
        sl_type: "close_based" (delayed on close) or "price_based" (immediate on wick)
        entry_mode: "close" (enter at close) or "range_percent" (enter at % of H-L range)
        entry_percent: For range_percent mode - BUY: High - X%(H-L), SELL: Low + X%(H-L)

    SL Calculation (both modes):
        BUY: SL pips = (Close - Low) / pip_value + buffer_k
        SELL: SL pips = (High - Close) / pip_value + buffer_k

    Returns:
        dict with results
    """
    run_id = f"BT-{datetime.now().strftime('%y%m%d-%H%M%S')}-{symbol}-{uuid.uuid4().hex[:4].upper()}"

    if entry_type == "pattern":
        result = _run_feg_backtest(
            df=df, symbol=symbol, rr_ratio=rr_ratio, max_candles=max_candles,
            lot_mode=lot_mode, fixed_lot=fixed_lot, risk_percent=risk_percent,
            risk_amount=risk_amount, risk_mode=risk_mode, buffer_k=buffer_k,
            starting_equity=starting_equity, tp_type=tp_type, sl_type=sl_type,
            entry_mode=entry_mode, entry_percent=entry_percent, ema_period=ema_period,
            h2_exceed_pips=h2_exceed_pips, c2_gap_pips=c2_gap_pips, ema_margin_pips=ema_margin_pips,
            entry_start_time=entry_start_time, entry_end_time=entry_end_time,
            limit_order_candles=limit_order_candles,
            be_enabled=be_enabled, be_r=be_r,
        )
        result["run_id"] = run_id
        return result

    pip_value = get_pip_value(symbol)

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
        if not _in_time_window(entry_time, entry_start_time, entry_end_time):
            continue
        o, h, l, c = entry_row['open'], entry_row['high'], entry_row['low'], entry_row['close']

        candle = {"open": o, "high": h, "low": l, "close": c}
        if c > o:
            direction = "BUY"
        elif c < o:
            direction = "SELL"
        else:
            continue  # Doji

        levels = compute_trade_levels(direction, candle, entry_mode, entry_percent, buffer_k, rr_ratio, pip_value)

        lot_size = _compute_lot_size(
            lot_mode, current_equity, risk_mode, risk_percent, risk_amount,
            levels["sl_pips"], symbol, fixed_lot,
        )

        entry_pos = df.index.get_loc(idx)
        exit_type, exit_price, exit_time, candles_held, _ = _simulate_exit(
            df, entry_pos, direction, levels["take_profit"], levels["stop_loss"],
            max_candles, tp_type, sl_type,
            be_enabled=be_enabled, be_r=be_r, entry_price=levels["entry_price"],
        )
        if not exit_type:
            continue

        trade, pnl_pips, pnl_usd = _make_trade(
            entry_time, direction, levels, lot_size, exit_type, exit_price,
            exit_time, candles_held, symbol,
        )
        current_equity += pnl_usd
        trades.append(trade)
        trade["_candle"] = {"open": o, "high": h, "low": l, "close": c}  # trace-only
        equity_curve_pips.append(equity_curve_pips[-1] + pnl_pips)
        equity_curve_usd.append(current_equity)

    # Calculate statistics
    stats = calculate_stats(trades, lot_mode)
    stats["run_id"] = run_id
    stats["equity_curve"] = equity_curve_pips
    stats["equity_curve_usd"] = equity_curve_usd
    stats["trades"] = trades
    stats["lot_mode"] = lot_mode
    stats["final_equity"] = current_equity
    stats["starting_equity"] = starting_equity
    stats["ohlc_data"] = df  # Include OHLC data for interactive charts

    return stats


def _run_feg_backtest(
    df, symbol, rr_ratio, max_candles, lot_mode, fixed_lot, risk_percent,
    risk_amount, risk_mode, buffer_k, starting_equity, tp_type, sl_type,
    entry_mode, entry_percent, ema_period,
    h2_exceed_pips: float = 0.0, c2_gap_pips: float = 0.0, ema_margin_pips: float = 0.0,
    entry_start_time: _time = _time(0, 0),
    entry_end_time: _time = _time(23, 59),
    limit_order_candles: int = 1,
    be_enabled: bool = False,
    be_r: float = 1.0,
):
    """Backtest FEG: quét tuần tự, 1 lệnh tại 1 thời điểm."""
    pip_value = get_pip_value(symbol)
    df = df.reset_index(drop=True)
    ema = df["close"].ewm(span=ema_period, adjust=False).mean()
    df[f"ema{ema_period}"] = ema
    ema = ema.tolist()

    trades = []
    equity_curve_pips = [0]
    equity_curve_usd = [starting_equity]
    current_equity = starting_equity

    n = len(df)
    i = max(1, ema_period)  # warmup: bỏ vùng EMA chưa ổn định
    while i < n:
        candle_time = df.at[i, "time"]
        if not _in_time_window(candle_time, entry_start_time, entry_end_time):
            i += 1
            continue

        c1 = {"open": df.at[i - 1, "open"], "high": df.at[i - 1, "high"],
              "low": df.at[i - 1, "low"], "close": df.at[i - 1, "close"]}
        c2 = {"open": df.at[i, "open"], "high": df.at[i, "high"],
              "low": df.at[i, "low"], "close": df.at[i, "close"]}
        direction = detect_feg_signal(
            c1, c2, ema[i], pip_value, h2_exceed_pips, c2_gap_pips, ema_margin_pips,
        )
        if direction:
            levels = compute_trade_levels(
                direction, c2, entry_mode, entry_percent, buffer_k, rr_ratio, pip_value,
            )
            lot_size = _compute_lot_size(
                lot_mode, current_equity, risk_mode, risk_percent, risk_amount,
                levels["sl_pips"], symbol, fixed_lot,
            )

            # Tìm nến khớp lệnh trong limit_order_candles nến tiếp theo
            entry_price = levels["entry_price"]
            filled_at = None
            for j in range(i + 1, min(i + 1 + limit_order_candles, n)):
                if df.at[j, "low"] <= entry_price <= df.at[j, "high"]:
                    filled_at = j
                    break

            if filled_at is not None:
                exit_type, exit_price, exit_time, candles_held, exit_pos = _simulate_exit(
                    df, filled_at, direction, levels["take_profit"], levels["stop_loss"],
                    max_candles, tp_type, sl_type,
                    be_enabled=be_enabled, be_r=be_r, entry_price=entry_price,
                )
                if not exit_type:
                    break  # hết data

                trade, pnl_pips, pnl_usd = _make_trade(
                    df.at[filled_at, "time"], direction, levels, lot_size, exit_type,
                    exit_price, exit_time, candles_held, symbol, exit_pos=exit_pos,
                )
                current_equity += pnl_usd
                trade["_c1"] = {**c1, "time": df.at[i - 1, "time"]}
                trade["_c2"] = {**c2, "time": df.at[i, "time"]}
                trade["_ema"] = ema[i]
                trades.append(trade)
                equity_curve_pips.append(equity_curve_pips[-1] + pnl_pips)
                equity_curve_usd.append(current_equity)

                i = exit_pos + 1  # 1 lệnh/lúc: quét tiếp sau nến exit
                continue

        i += 1

    stats = calculate_stats(trades, lot_mode)
    stats["equity_curve"] = equity_curve_pips
    stats["equity_curve_usd"] = equity_curve_usd
    stats["trades"] = trades
    stats["lot_mode"] = lot_mode
    stats["final_equity"] = current_equity
    stats["starting_equity"] = starting_equity
    stats["ohlc_data"] = df
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
