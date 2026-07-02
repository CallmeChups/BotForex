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


def log_order_close(ticket: int, exit_type: str, exit_price: float, profit: float):
    """Log order close to CSV"""
    os.makedirs("data", exist_ok=True)

    log_entry = {
        "timestamp": datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S'),
        "ticket": ticket,
        "exit_type": exit_type,
        "exit_price": exit_price,
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
    return pd.DataFrame(columns=["timestamp", "ticket", "exit_type", "exit_price", "profit"])


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
    test: bool = False,
    magic: int = 123456,
    comment: str = "Order",
) -> tuple:
    """
    Place a market order

    Args:
        symbol: Trading symbol
        direction: "BUY" or "SELL"
        volume: Lot size
        sl: Stop loss price (optional)
        tp: Take profit price (optional)
        credentials: MT5 credentials dict
        test: If True, simulate without touching MT5
        magic: Magic number for the order
        comment: Comment for the order

    Returns:
        (success, message, ticket)
    """
    if test:
        return True, f"[TEST] {direction} {symbol} vol={volume} sl={sl} tp={tp} simulated", None

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

        # Determine order type and price
        if direction.upper() == "BUY":
            order_type = mt5_module.ORDER_TYPE_BUY
            price = tick.ask
        else:
            order_type = mt5_module.ORDER_TYPE_SELL
            price = tick.bid

        # Prepare order request
        request = {
            "action": mt5_module.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": magic,
            "comment": comment,
            "type_time": mt5_module.ORDER_TIME_GTC,
            "type_filling": mt5_module.ORDER_FILLING_IOC,
        }

        # Add SL/TP if provided
        if sl is not None and sl > 0:
            request["sl"] = sl
        if tp is not None and tp > 0:
            request["tp"] = tp

        # Send order
        result = mt5.order_send(request)
        mt5.shutdown()

        if result is None:
            return False, "Order failed: No response from MT5", None

        if result.retcode != mt5_module.TRADE_RETCODE_DONE:
            return False, f"Order failed: {result.comment} (code: {result.retcode})", None

        return True, f"Order placed at {price:.5f}", result.order

    except Exception as e:
        mt5.shutdown()
        return False, str(e), None


def place_limit_order(
    symbol: str,
    direction: str,
    volume: float,
    price: float,
    sl: float = None,
    tp: float = None,
    credentials: dict = None,
    test: bool = False,
    magic: int = 123456,
    comment: str = "LimitOrder",
) -> tuple:
    """
    Place a pending limit order (SELL_LIMIT or BUY_LIMIT).

    Returns (success, message, ticket).
    """
    if test:
        return True, f"[TEST] {direction}_LIMIT {symbol} vol={volume} price={price} sl={sl} tp={tp} simulated", None

    mt5, error = get_mt5_connection(credentials)
    if error:
        return False, error, None

    try:
        import MetaTrader5 as mt5_module

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            mt5.shutdown()
            return False, f"Symbol {symbol} not found", None

        if not symbol_info.visible:
            if not mt5.symbol_select(symbol, True):
                mt5.shutdown()
                return False, f"Failed to select {symbol}", None

        if direction.upper() == "BUY":
            order_type = mt5_module.ORDER_TYPE_BUY_LIMIT
        else:
            order_type = mt5_module.ORDER_TYPE_SELL_LIMIT

        request = {
            "action": mt5_module.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": magic,
            "comment": comment,
            "type_time": mt5_module.ORDER_TIME_GTC,
            "type_filling": mt5_module.ORDER_FILLING_RETURN,
        }

        if sl is not None and sl > 0:
            request["sl"] = sl
        if tp is not None and tp > 0:
            request["tp"] = tp

        result = mt5.order_send(request)
        mt5.shutdown()

        if result is None:
            return False, "Limit order failed: No response from MT5", None

        if result.retcode != mt5_module.TRADE_RETCODE_DONE:
            return False, f"Limit order failed: {result.comment} (code: {result.retcode})", None

        return True, f"Limit order placed at {price:.5f}", result.order

    except Exception as e:
        mt5.shutdown()
        return False, str(e), None


def cancel_pending_order(
    ticket: int,
    credentials: dict = None,
) -> tuple:
    """
    Cancel a pending order by ticket.

    Returns (success, message).
    """
    mt5, error = get_mt5_connection(credentials)
    if error:
        return False, error

    try:
        import MetaTrader5 as mt5_module

        request = {
            "action": mt5_module.TRADE_ACTION_REMOVE,
            "order": ticket,
        }

        result = mt5.order_send(request)
        mt5.shutdown()

        if result is None:
            return False, "Cancel failed: No response from MT5"

        if result.retcode != mt5_module.TRADE_RETCODE_DONE:
            return False, f"Cancel failed: {result.comment} (code: {result.retcode})"

        return True, f"Pending order {ticket} cancelled"

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
