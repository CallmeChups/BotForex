"""
Order Management Module
- Fetch open positions from MT5
- Close positions manually
- Track order history
"""

from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import os
import pandas as pd

from src.utils import is_mt5_available, get_pip_value

load_dotenv()

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
ORDERS_FILE = "data/orders.csv"


def get_mt5_connection(credentials: dict = None):
    """
    Initialize and login to MT5

    Args:
        credentials: dict with 'login', 'password', 'server' keys.
                    If None, uses environment variables as fallback.
    """
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return None, "MT5 not available (Windows only)"

    # Use provided credentials or fall back to env vars
    if credentials:
        account = int(credentials.get('login') or 0)
        password = credentials.get('password', '')
        server = credentials.get('server', '')
    else:
        account = int(os.getenv("MT5_LOGIN") or 0)
        password = os.getenv("MT5_PASSWORD")
        server = os.getenv("MT5_SERVER")

    if not account or not password or not server:
        return None, "MT5 credentials not configured"

    if not mt5.initialize():
        return None, "MT5 initialization failed"

    if not mt5.login(login=account, password=password, server=server):
        error = mt5.last_error()
        mt5.shutdown()
        return None, f"MT5 login failed: {error}"

    return mt5, None


def fetch_open_positions(credentials: dict = None) -> tuple:
    """
    Fetch all open positions from MT5

    Args:
        credentials: dict with 'login', 'password', 'server' keys

    Returns:
        (positions_list, error_message)
    """
    mt5, error = get_mt5_connection(credentials)
    if error:
        return [], error

    try:
        positions = mt5.positions_get()

        if positions is None or len(positions) == 0:
            mt5.shutdown()
            return [], None  # No positions, not an error

        positions_list = []
        for pos in positions:
            pos_dict = pos._asdict()

            # Calculate P&L in pips
            symbol = pos_dict['symbol']
            pip_value = get_pip_value(symbol)

            if pos_dict['type'] == 0:  # BUY
                pnl_pips = (pos_dict['price_current'] - pos_dict['price_open']) / pip_value
            else:  # SELL
                pnl_pips = (pos_dict['price_open'] - pos_dict['price_current']) / pip_value

            positions_list.append({
                "ticket": pos_dict['ticket'],
                "symbol": symbol,
                "type": "BUY" if pos_dict['type'] == 0 else "SELL",
                "volume": pos_dict['volume'],
                "open_price": pos_dict['price_open'],
                "current_price": pos_dict['price_current'],
                "sl": pos_dict['sl'],
                "tp": pos_dict['tp'],
                "profit": pos_dict['profit'],
                "pnl_pips": round(pnl_pips, 1),
                "open_time": datetime.fromtimestamp(pos_dict['time'], tz=TIMEZONE).strftime('%H:%M %d/%m'),
                "comment": pos_dict['comment'],
                "magic": pos_dict['magic']
            })

        mt5.shutdown()
        return positions_list, None

    except Exception as e:
        mt5.shutdown()
        return [], str(e)


def close_position(ticket: int, volume: float = None, credentials: dict = None) -> tuple:
    """
    Close a position by ticket number

    Args:
        ticket: Position ticket
        volume: Volume to close (None = close all)
        credentials: dict with 'login', 'password', 'server' keys

    Returns:
        (success, message)
    """
    mt5, error = get_mt5_connection(credentials)
    if error:
        return False, error

    try:
        # Get position info
        position = mt5.positions_get(ticket=ticket)
        if not position:
            mt5.shutdown()
            return False, f"Position {ticket} not found"

        position = position[0]
        symbol = position.symbol
        pos_type = position.type
        close_volume = volume or position.volume

        # Get current price
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            mt5.shutdown()
            return False, f"Failed to get price for {symbol}"

        # Determine close type and price
        if pos_type == 0:  # BUY -> close with SELL
            close_type = mt5.ORDER_TYPE_SELL
            price = tick.bid
        else:  # SELL -> close with BUY
            close_type = mt5.ORDER_TYPE_BUY
            price = tick.ask

        # Prepare close request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": close_volume,
            "type": close_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": 210500,
            "comment": "Manual_Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        # Send order
        result = mt5.order_send(request)

        mt5.shutdown()

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return False, f"Close failed: {result.comment} (code: {result.retcode})"

        # Log the manual close
        log_order_close(ticket, "MANUAL", price, position.profit)

        return True, f"Position {ticket} closed at {price:.2f}"

    except Exception as e:
        mt5.shutdown()
        return False, str(e)


def close_all_positions(symbol: str = None, credentials: dict = None) -> tuple:
    """
    Close all positions (optionally filtered by symbol)

    Args:
        symbol: Filter by symbol (optional)
        credentials: dict with 'login', 'password', 'server' keys

    Returns:
        (closed_count, error_message)
    """
    positions, error = fetch_open_positions(credentials)
    if error:
        return 0, error

    if not positions:
        return 0, "No positions to close"

    closed = 0
    errors = []

    for pos in positions:
        if symbol and pos['symbol'] != symbol:
            continue

        success, msg = close_position(pos['ticket'], credentials=credentials)
        if success:
            closed += 1
        else:
            errors.append(f"Ticket {pos['ticket']}: {msg}")

    if errors:
        return closed, f"Closed {closed}, Errors: {'; '.join(errors)}"

    return closed, None


def log_order_close(ticket: int, exit_type: str, exit_price: float, profit: float,
                    symbol: str = "", direction: str = "", entry_price: float = 0.0,
                    pnl_pips: float = 0.0, pnl_usd: float = 0.0, lot: float = 0.0,
                    strategy: str = "", user: str = ""):
    """Log order close to CSV with full trade details"""
    os.makedirs("data", exist_ok=True)

    log_entry = {
        "timestamp": datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S'),
        "ticket": ticket,
        "symbol": symbol,
        "direction": direction,
        "strategy": strategy,
        "user": user,
        "entry_price": entry_price,
        "exit_type": exit_type,
        "exit_price": exit_price,
        "lot": lot,
        "pnl_pips": round(pnl_pips, 1),
        "pnl_usd": round(pnl_usd, 2),
        "profit": profit
    }

    if os.path.exists(ORDERS_FILE):
        df = pd.read_csv(ORDERS_FILE)
        df = pd.concat([df, pd.DataFrame([log_entry])], ignore_index=True)
    else:
        df = pd.DataFrame([log_entry])

    df.to_csv(ORDERS_FILE, index=False)


def get_order_history() -> pd.DataFrame:
    """Get order close history"""
    if os.path.exists(ORDERS_FILE):
        return pd.read_csv(ORDERS_FILE)
    return pd.DataFrame(columns=["timestamp", "ticket", "symbol", "direction", "strategy",
                                     "user", "entry_price", "exit_type", "exit_price",
                                     "lot", "pnl_pips", "pnl_usd", "profit"])


def get_account_info(credentials: dict = None) -> tuple:
    """
    Get MT5 account info

    Args:
        credentials: dict with 'login', 'password', 'server' keys

    Returns:
        (account_dict, error)
    """
    mt5, error = get_mt5_connection(credentials)
    if error:
        return None, error

    try:
        account = mt5.account_info()
        if account is None:
            mt5.shutdown()
            return None, "Failed to get account info"

        info = {
            "balance": account.balance,
            "equity": account.equity,
            "margin": account.margin,
            "free_margin": account.margin_free,
            "profit": account.profit,
            "leverage": account.leverage,
            "name": account.name,
            "server": account.server,
            "currency": account.currency
        }

        mt5.shutdown()
        return info, None

    except Exception as e:
        mt5.shutdown()
        return None, str(e)


def place_order(
    symbol: str,
    direction: str,
    volume: float,
    sl: float = None,
    tp: float = None,
    credentials: dict = None,
    theoretical_entry: float = None
) -> tuple:
    """
    Place a market order with signal SL/TP (structural levels).

    SL/TP are NOT recalculated on slippage because they are anchored to
    candle structure (e.g. Low - buffer for BUY SL). Shifting them would
    move them away from the structural level they are meant to protect.

    Args:
        symbol: Trading symbol
        direction: "BUY" or "SELL"
        volume: Lot size
        sl: Stop loss price (optional) - used as-is (structural level)
        tp: Take profit price (optional) - used as-is (structural level)
        credentials: MT5 credentials dict
        theoretical_entry: (unused, kept for backward compatibility)

    Returns:
        (success, message, ticket)
    """
    mt5, error = get_mt5_connection(credentials)
    if error:
        return False, error, None

    try:
        import MetaTrader5 as mt5_module

        # Check symbol
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            mt5.shutdown()
            return False, f"Symbol {symbol} not found", None

        if not symbol_info.visible:
            if not mt5.symbol_select(symbol, True):
                mt5.shutdown()
                return False, f"Failed to select {symbol}", None

        # Get current price
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            mt5.shutdown()
            return False, f"Failed to get price for {symbol}", None

        # Get broker's stop level (minimum distance for SL/TP in points)
        # stops_level might be 0 for some brokers, use a reasonable default
        stops_level = getattr(symbol_info, 'trade_stops_level', 0)
        if stops_level == 0:
            stops_level = 10  # Default minimum of 10 points
        point = symbol_info.point
        min_stop_distance = stops_level * point

        # Determine order type and actual execution price
        if direction.upper() == "BUY":
            order_type = mt5_module.ORDER_TYPE_BUY
            actual_entry = tick.ask
        else:
            order_type = mt5_module.ORDER_TYPE_SELL
            actual_entry = tick.bid

        # Validate SL is on correct side of entry (reject if price moved past SL)
        final_sl = sl
        final_tp = tp

        if final_sl and final_sl > 0:
            if direction.upper() == "BUY" and final_sl >= actual_entry:
                mt5.shutdown()
                return False, f"Trade invalidated: SL ({final_sl:.5f}) >= Entry ({actual_entry:.5f}) for BUY", None
            elif direction.upper() == "SELL" and final_sl <= actual_entry:
                mt5.shutdown()
                return False, f"Trade invalidated: SL ({final_sl:.5f}) <= Entry ({actual_entry:.5f}) for SELL", None

        # Enforce minimum stop distance required by broker (add 1 point margin)
        margin = point  # Extra point to avoid "exactly at minimum" rejection

        if final_sl and final_sl > 0:
            if direction.upper() == "BUY":
                if (actual_entry - final_sl) < min_stop_distance:
                    final_sl = actual_entry - min_stop_distance - margin
            else:
                if (final_sl - actual_entry) < min_stop_distance:
                    final_sl = actual_entry + min_stop_distance + margin

        if final_tp and final_tp > 0:
            if direction.upper() == "BUY":
                if (final_tp - actual_entry) < min_stop_distance:
                    final_tp = actual_entry + min_stop_distance + margin
            else:
                if (actual_entry - final_tp) < min_stop_distance:
                    final_tp = actual_entry - min_stop_distance - margin

        # Get filling mode from symbol
        filling_mode = symbol_info.filling_mode

        # Determine the best filling type
        filling_type = None
        if filling_mode & 1:  # FOK supported
            filling_type = mt5_module.ORDER_FILLING_FOK
        elif filling_mode & 2:  # IOC supported
            filling_type = mt5_module.ORDER_FILLING_IOC
        else:  # RETURN (default)
            filling_type = mt5_module.ORDER_FILLING_RETURN

        # Prepare order request
        request = {
            "action": mt5_module.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": actual_entry,
            "deviation": 20,
            "magic": 123456,
            "comment": "BotForex",
            "type_time": mt5_module.ORDER_TIME_GTC,
            "type_filling": filling_type,
        }

        # Add SL/TP if provided
        if final_sl is not None and final_sl > 0:
            request["sl"] = round(final_sl, symbol_info.digits)
        if final_tp is not None and final_tp > 0:
            request["tp"] = round(final_tp, symbol_info.digits)

        # Send order
        result = mt5.order_send(request)

        if result is None:
            mt5.shutdown()
            return False, "Order failed: No response from MT5", None

        if result.retcode != mt5_module.TRADE_RETCODE_DONE:
            error_msg = f"Order failed: {result.comment} (retcode: {result.retcode})"

            # Add helpful error messages for common issues
            if result.retcode == 10004:
                error_msg += " | Requote - price changed, try again"
            elif result.retcode == 10006:
                error_msg += " | Request rejected - check AutoTrading is enabled"
            elif result.retcode == 10013:
                error_msg += " | Invalid request - check order parameters"
            elif result.retcode == 10014:
                error_msg += " | Invalid volume - check lot size"
            elif result.retcode == 10015:
                error_msg += " | Invalid price - check price levels"
            elif result.retcode == 10016:
                error_msg += f" | Invalid stops - SL/TP too close (min: {min_stop_distance:.5f})"
                error_msg += f" | Requested SL={final_sl if final_sl else 'None'}, TP={final_tp if final_tp else 'None'}, Entry={actual_entry:.5f}"
            elif result.retcode == 10019:
                error_msg += " | No money - insufficient funds"
            elif result.retcode == 10027:
                error_msg += " | AutoTrading disabled - enable in MT5 Tools > Options > Expert Advisors"
            elif result.retcode == 10030:
                error_msg += " | Invalid filling mode"

            mt5.shutdown()
            return False, error_msg, None

        mt5.shutdown()
        sl_str = f"{final_sl:.5f}" if final_sl else "None"
        tp_str = f"{final_tp:.5f}" if final_tp else "None"
        return True, f"Order placed at {actual_entry:.5f} (SL={sl_str}, TP={tp_str})", result.order

    except Exception as e:
        mt5.shutdown()
        return False, str(e), None


def place_pending_order(
    symbol: str,
    direction: str,
    volume: float,
    entry_price: float,
    sl: float = None,
    tp: float = None,
    credentials: dict = None
) -> tuple:
    """
    Place a pending order (BUY LIMIT or SELL LIMIT)

    Args:
        symbol: Trading symbol
        direction: "BUY" or "SELL"
        volume: Lot size
        entry_price: Price to enter at
        sl: Stop loss price
        tp: Take profit price
        credentials: MT5 credentials dict

    Returns:
        (success, message, ticket)
    """
    mt5, error = get_mt5_connection(credentials)
    if error:
        return False, error, None

    try:
        # Get symbol info
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            mt5.shutdown()
            return False, f"Symbol {symbol} not found", None

        # Ensure symbol is visible
        if not symbol_info.visible:
            if not mt5.symbol_select(symbol, True):
                mt5.shutdown()
                return False, f"Failed to select symbol {symbol}", None

        # Get current price for validation
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            mt5.shutdown()
            return False, f"Failed to get tick for {symbol}", None

        # Determine order type
        if direction.upper() == "BUY":
            # BUY LIMIT: entry price must be below current ask
            order_type = mt5.ORDER_TYPE_BUY_LIMIT
            if entry_price >= tick.ask:
                mt5.shutdown()
                return False, f"BUY LIMIT price ({entry_price:.5f}) must be below current ask ({tick.ask:.5f})", None
        else:
            # SELL LIMIT: entry price must be above current bid
            order_type = mt5.ORDER_TYPE_SELL_LIMIT
            if entry_price <= tick.bid:
                mt5.shutdown()
                return False, f"SELL LIMIT price ({entry_price:.5f}) must be above current bid ({tick.bid:.5f})", None

        # Enforce minimum stop distance required by broker
        point = symbol_info.point
        stops_level = getattr(symbol_info, 'trade_stops_level', 0)
        if stops_level == 0:
            stops_level = 10
        min_stop_distance = stops_level * point
        margin = point

        final_sl = sl
        final_tp = tp

        if final_sl and final_sl > 0:
            if direction.upper() == "BUY":
                if (entry_price - final_sl) < min_stop_distance:
                    final_sl = entry_price - min_stop_distance - margin
            else:
                if (final_sl - entry_price) < min_stop_distance:
                    final_sl = entry_price + min_stop_distance + margin

        if final_tp and final_tp > 0:
            if direction.upper() == "BUY":
                if (final_tp - entry_price) < min_stop_distance:
                    final_tp = entry_price + min_stop_distance + margin
            else:
                if (entry_price - final_tp) < min_stop_distance:
                    final_tp = entry_price - min_stop_distance - margin

        # Auto-detect filling type from symbol (different symbols support different modes)
        # Build candidate list: try symbol-supported modes first, then RETURN as fallback
        filling_mode = symbol_info.filling_mode
        filling_candidates = []
        if filling_mode & 1:  # FOK supported
            filling_candidates.append(mt5.ORDER_FILLING_FOK)
        if filling_mode & 2:  # IOC supported
            filling_candidates.append(mt5.ORDER_FILLING_IOC)
        filling_candidates.append(mt5.ORDER_FILLING_RETURN)  # Always try RETURN as fallback

        # Create order request
        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": round(entry_price, symbol_info.digits),
            "deviation": 20,
            "magic": 234000,
            "comment": "BotForex_Pending",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_candidates[0],
        }

        # Add SL/TP if provided
        if final_sl is not None and final_sl > 0:
            request["sl"] = round(final_sl, symbol_info.digits)
        if final_tp is not None and final_tp > 0:
            request["tp"] = round(final_tp, symbol_info.digits)

        # Try each filling type with order_check() to find one the broker accepts
        best_filling = None
        for ft in filling_candidates:
            request["type_filling"] = ft
            check = mt5.order_check(request)
            if check and check.retcode == mt5.TRADE_RETCODE_DONE:
                best_filling = ft
                break

        if best_filling is None:
            # No filling type passed order_check — send with first candidate anyway
            # to get a meaningful error from order_send
            request["type_filling"] = filling_candidates[0]
        else:
            request["type_filling"] = best_filling

        # Send order
        result = mt5.order_send(request)

        if result is None:
            mt5.shutdown()
            return False, "order_send() returned None", None

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            error_msg = f"Order failed: {result.comment} (code {result.retcode})"
            if result.retcode == 10006:
                error_msg += f" | Rejected (filling_mode={filling_mode}, tried={[f for f in filling_candidates]})"
            elif result.retcode == 10016:
                error_msg += f" | Stops too close (min={min_stop_distance:.5f})"
            mt5.shutdown()
            return False, error_msg, None

        mt5.shutdown()
        sl_str = f"{final_sl:.5f}" if final_sl else "None"
        tp_str = f"{final_tp:.5f}" if final_tp else "None"
        return True, f"Pending order placed at {entry_price:.5f} (SL={sl_str}, TP={tp_str})", result.order

    except Exception as e:
        mt5.shutdown()
        return False, str(e), None


def check_order_status(ticket: int, credentials: dict = None) -> tuple:
    """
    Check if a pending order has been filled or is still pending

    Args:
        ticket: Order ticket number
        credentials: MT5 credentials dict

    Returns:
        (status, message, position_data) where:
        - status: 'FILLED', 'PENDING', 'CANCELLED', or 'ERROR'
        - message: description string
        - position_data: dict with position details if FILLED, None otherwise
          Keys: price_open, sl, tp, ticket (actual position ticket)
    """
    mt5, error = get_mt5_connection(credentials)
    if error:
        return 'ERROR', error, None

    try:
        # Check if order exists in pending orders
        orders = mt5.orders_get(ticket=ticket)
        if orders and len(orders) > 0:
            mt5.shutdown()
            return 'PENDING', f"Order {ticket} still pending", None

        # Check if position was opened (order filled) - search by ticket
        positions = mt5.positions_get(ticket=ticket)
        if positions and len(positions) > 0:
            pos = positions[0]
            position_data = {
                'price_open': pos.price_open,
                'sl': pos.sl,
                'tp': pos.tp,
                'ticket': pos.ticket,
            }
            mt5.shutdown()
            return 'FILLED', f"Order filled at {pos.price_open:.5f}", position_data

        # Fallback: check history deals (position ticket may differ from order ticket)
        from datetime import datetime, timedelta
        try:
            history_start = datetime.now() - timedelta(hours=1)
            history_end = datetime.now() + timedelta(hours=1)
            deals = mt5.history_deals_get(history_start, history_end)
            if deals:
                for deal in deals:
                    # entry==0 means DEAL_ENTRY_IN (opening deal)
                    if deal.order == ticket and deal.entry == 0:
                        # Found fill deal - try to find position by position_id
                        pos_id = deal.position_id
                        positions = mt5.positions_get(ticket=pos_id)
                        if positions and len(positions) > 0:
                            pos = positions[0]
                            position_data = {
                                'price_open': pos.price_open,
                                'sl': pos.sl,
                                'tp': pos.tp,
                                'ticket': pos.ticket,
                            }
                            mt5.shutdown()
                            return 'FILLED', f"Order filled at {pos.price_open:.5f}", position_data
                        else:
                            # Deal exists but position already closed or not findable
                            mt5.shutdown()
                            return 'FILLED', f"Order filled at {deal.price:.5f}", None
        except Exception:
            pass

        # Order not in pending and not in positions - likely cancelled or rejected
        mt5.shutdown()
        return 'CANCELLED', f"Order {ticket} cancelled or expired", None

    except Exception as e:
        mt5.shutdown()
        return 'ERROR', str(e), None


def cancel_order(ticket: int, credentials: dict = None) -> tuple:
    """
    Cancel a pending order

    Args:
        ticket: Order ticket number
        credentials: MT5 credentials dict

    Returns:
        (success, message)
    """
    mt5, error = get_mt5_connection(credentials)
    if error:
        return False, error

    try:
        # Check if order exists
        orders = mt5.orders_get(ticket=ticket)
        if not orders or len(orders) == 0:
            mt5.shutdown()
            return False, f"Order {ticket} not found"

        order = orders[0]

        # Create cancel request
        request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": ticket,
            "comment": "BotForex_Cancel",
        }

        # Send cancel request
        result = mt5.order_send(request)

        if result is None:
            mt5.shutdown()
            return False, "order_send() returned None"

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            error_msg = f"Cancel failed: {result.comment} (code {result.retcode})"
            mt5.shutdown()
            return False, error_msg

        mt5.shutdown()
        return True, f"Order {ticket} cancelled successfully"

    except Exception as e:
        mt5.shutdown()
        return False, str(e)


def get_symbol_info(symbol: str, credentials: dict = None) -> tuple:
    """
    Get symbol information (for validation and price display)

    Args:
        symbol: Trading symbol
        credentials: MT5 credentials dict

    Returns:
        (info_dict, error)
    """
    mt5, error = get_mt5_connection(credentials)
    if error:
        return None, error

    try:
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            mt5.shutdown()
            return None, f"Symbol {symbol} not found"

        tick = mt5.symbol_info_tick(symbol)

        info = {
            "symbol": symbol,
            "bid": tick.bid if tick else 0,
            "ask": tick.ask if tick else 0,
            "spread": symbol_info.spread,
            "digits": symbol_info.digits,
            "volume_min": symbol_info.volume_min,
            "volume_max": symbol_info.volume_max,
            "volume_step": symbol_info.volume_step,
        }

        mt5.shutdown()
        return info, None

    except Exception as e:
        mt5.shutdown()
        return None, str(e)
