"""
Orders Page - View and manage open positions
"""

import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import os
import time

load_dotenv()

st.set_page_config(
    page_icon="📋",
    page_title="Orders",
    layout="wide",
)

# Auth check
from src.auth import require_auth, get_user_mt5_credentials, has_mt5_credentials
username, name = require_auth()

from src.orders import (
    fetch_open_positions,
    close_position,
    close_all_positions,
    get_account_info,
    get_order_history,
    place_order,
    get_symbol_info
)
from src.utils import get_pip_value, is_mt5_available, report_page_error

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def main():
    st.title("Orders Management")

    now = datetime.now(TIMEZONE)
    st.markdown(f"**Current Time:** {now.strftime('%H:%M:%S %d/%m/%Y')} (HCM)")

    st.divider()

    # Check MT5 availability
    if not is_mt5_available():
        st.warning("MT5 not available (Windows only). Showing demo mode.")
        show_demo_mode()
        return

    # Check if user has MT5 credentials configured
    if not has_mt5_credentials(username):
        st.warning("MT5 account not configured. Please go to Settings to add your MT5 credentials.")
        st.page_link("pages/8_Settings.py", label="Go to Settings", icon="⚙️")
        show_demo_mode()
        return

    # Get user's MT5 credentials
    user_creds = get_user_mt5_credentials(username)

    # Account Info
    st.subheader("Account Info")

    account, error = get_account_info(user_creds)

    if error:
        st.error(f"Failed to get account info: {error}")
    else:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Balance", f"${account['balance']:,.2f}")

        with col2:
            st.metric("Equity", f"${account['equity']:,.2f}")

        with col3:
            profit_delta = "profit" if account['profit'] > 0 else "loss" if account['profit'] < 0 else None
            st.metric("Floating P&L", f"${account['profit']:,.2f}", delta=profit_delta)

        with col4:
            st.metric("Free Margin", f"${account['free_margin']:,.2f}")

    st.divider()

    # Tabs for different sections
    tab1, tab2 = st.tabs(["Open Positions", "Place Order"])

    with tab1:
        show_open_positions(user_creds)

    with tab2:
        show_place_order(user_creds)

    st.divider()

    # Order close history
    st.subheader("Manual Close History")

    history_df = get_order_history()

    if history_df.empty:
        st.info("No manual closes recorded yet")
    else:
        st.dataframe(history_df, width='stretch', hide_index=True)


def show_open_positions(user_creds: dict):
    """Show open positions section"""

    # Open Positions
    st.subheader("Open Positions")

    # Controls
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.button("Refresh Positions", width='stretch', type="primary"):
            st.rerun()

    with col2:
        auto_refresh = st.checkbox("Auto-refresh", value=False)

    with col3:
        if auto_refresh:
            refresh_interval = st.select_slider(
                "Interval",
                options=[5, 10, 15, 30, 60],
                value=10,
                format_func=lambda x: f"{x}s"
            )

    # Fetch positions
    positions, error = fetch_open_positions(user_creds)

    if error:
        st.error(f"Failed to fetch positions: {error}")
    elif not positions:
        st.info("No open positions")
    else:
        st.success(f"Found {len(positions)} open position(s)")

        # Position table
        for pos in positions:
            with st.container():
                col1, col2, col3, col4, col5, col6 = st.columns([2, 1, 1, 1, 1, 0.8])

                with col1:
                    direction_color = "green" if pos['type'] == "BUY" else "red"
                    st.markdown(f"**{pos['symbol']}** - :{direction_color}[{pos['type']}]")
                    st.caption(f"Ticket: {pos['ticket']} | Vol: {pos['volume']} | Open: {pos['open_time']}")

                with col2:
                    st.metric("Entry", f"{pos['open_price']:.2f}")
                    # Show SL/TP below entry
                    sl_display = f"{pos['sl']:.2f}" if pos['sl'] > 0 else "-"
                    tp_display = f"{pos['tp']:.2f}" if pos['tp'] > 0 else "-"
                    st.caption(f"SL: {sl_display} | TP: {tp_display}")

                with col3:
                    st.metric("Current", f"{pos['current_price']:.2f}")

                with col4:
                    pnl_color = "green" if pos['profit'] > 0 else "red" if pos['profit'] < 0 else "gray"
                    st.markdown(f"**P&L**")
                    st.markdown(f":{pnl_color}[${pos['profit']:.2f}]")
                    st.caption(f"{pos['pnl_pips']:+.1f} pips")

                with col5:
                    # Show distance to SL/TP
                    if pos['sl'] > 0 or pos['tp'] > 0:
                        if pos['type'] == "BUY":
                            sl_dist = pos['current_price'] - pos['sl'] if pos['sl'] > 0 else 0
                            tp_dist = pos['tp'] - pos['current_price'] if pos['tp'] > 0 else 0
                        else:
                            sl_dist = pos['sl'] - pos['current_price'] if pos['sl'] > 0 else 0
                            tp_dist = pos['current_price'] - pos['tp'] if pos['tp'] > 0 else 0
                        st.markdown("**Distance**")
                        if pos['sl'] > 0:
                            st.caption(f"SL: {sl_dist:.2f}")
                        if pos['tp'] > 0:
                            st.caption(f"TP: {tp_dist:.2f}")

                with col6:
                    if st.button("Close", key=f"close_{pos['ticket']}", type="secondary"):
                        try:
                            success, msg = close_position(pos['ticket'], credentials=user_creds)
                            if success:
                                st.success(msg)
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(msg)
                        except Exception as e:
                            report_page_error(e, f"Orders / close_position / ticket={pos['ticket']}")
                            st.error(f"Lỗi: {type(e).__name__}: {e}")

                st.divider()

        # Close all button
        st.markdown("")
        col1, col2, col3 = st.columns([2, 1, 2])

        with col2:
            if st.button("Close All Positions", type="secondary", width='stretch'):
                try:
                    closed, error = close_all_positions(credentials=user_creds)
                    if error:
                        st.warning(error)
                    else:
                        st.success(f"Closed {closed} position(s)")
                        time.sleep(1)
                        st.rerun()
                except Exception as e:
                    report_page_error(e, "Orders / close_all_positions")
                    st.error(f"Lỗi: {type(e).__name__}: {e}")

    # Auto-refresh logic
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()


def show_place_order(user_creds: dict):
    """Show place order form"""

    st.subheader("Place Manual Order")

    # Common symbols
    common_symbols = ["XAUUSD", "BTCUSD", "ETHUSD", "EURUSD", "GBPUSD"]

    col1, col2 = st.columns(2)

    with col1:
        # Symbol input with suggestions
        use_custom_symbol = st.checkbox("Custom symbol", value=False, key="order_custom_symbol")

        if use_custom_symbol:
            symbol = st.text_input("Symbol", value="XAUUSD", key="order_symbol")
        else:
            symbol = st.selectbox("Symbol", options=common_symbols, key="order_symbol_select")

        direction = st.radio(
            "Direction",
            options=["BUY", "SELL"],
            horizontal=True,
            key="order_direction"
        )

        volume = st.number_input(
            "Volume (Lot)",
            value=0.01,
            min_value=0.01,
            max_value=10.0,
            step=0.01,
            format="%.2f",
            key="order_volume"
        )

    with col2:
        # Get current price for reference
        if symbol:
            symbol_info, error = get_symbol_info(symbol, user_creds)
            if symbol_info and not error:
                pip_value = get_pip_value(symbol)

                st.markdown("**Current Price**")
                col_bid, col_ask = st.columns(2)
                with col_bid:
                    st.metric("Bid", f"{symbol_info['bid']:.5f}")
                with col_ask:
                    st.metric("Ask", f"{symbol_info['ask']:.5f}")

                st.caption(f"Spread: {symbol_info['spread']} | Min Vol: {symbol_info['volume_min']}")

                # Reference price for SL/TP
                ref_price = symbol_info['ask'] if direction == "BUY" else symbol_info['bid']
            else:
                st.warning(f"Could not fetch symbol info: {error}")
                ref_price = 0
                pip_value = 0.0001

        # SL/TP inputs
        use_sl_tp = st.checkbox("Set SL/TP", value=False, key="order_use_sl_tp")

        if use_sl_tp:
            sl_col, tp_col = st.columns(2)

            with sl_col:
                sl_pips = st.number_input(
                    "SL (pips)",
                    value=30,
                    min_value=0,
                    max_value=500,
                    key="order_sl_pips"
                )

            with tp_col:
                tp_pips = st.number_input(
                    "TP (pips)",
                    value=60,
                    min_value=0,
                    max_value=1000,
                    key="order_tp_pips"
                )

            # Calculate actual SL/TP prices
            if ref_price > 0 and pip_value > 0:
                if direction == "BUY":
                    sl_price = ref_price - (sl_pips * pip_value) if sl_pips > 0 else 0
                    tp_price = ref_price + (tp_pips * pip_value) if tp_pips > 0 else 0
                else:
                    sl_price = ref_price + (sl_pips * pip_value) if sl_pips > 0 else 0
                    tp_price = ref_price - (tp_pips * pip_value) if tp_pips > 0 else 0

                if sl_pips > 0:
                    st.caption(f"SL Price: {sl_price:.5f}")
                if tp_pips > 0:
                    st.caption(f"TP Price: {tp_price:.5f}")
            else:
                sl_price = 0
                tp_price = 0
        else:
            sl_price = 0
            tp_price = 0

    st.divider()

    # Order summary
    st.markdown("**Order Summary**")
    direction_color = "green" if direction == "BUY" else "red"
    st.markdown(f":{direction_color}[**{direction}**] {volume} lot of **{symbol}**")

    if use_sl_tp and (sl_pips > 0 or tp_pips > 0):
        summary_parts = []
        if sl_pips > 0:
            summary_parts.append(f"SL: {sl_pips} pips")
        if tp_pips > 0:
            summary_parts.append(f"TP: {tp_pips} pips")
        st.caption(" | ".join(summary_parts))

    # Place order button
    st.markdown("")

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        if st.button(
            f"Place {direction} Order",
            type="primary",
            use_container_width=True,
            key="place_order_btn"
        ):
            try:
                with st.spinner("Placing order..."):
                    success, msg, ticket = place_order(
                        symbol=symbol,
                        direction=direction,
                        volume=volume,
                        sl=sl_price if use_sl_tp and sl_pips > 0 else None,
                        tp=tp_price if use_sl_tp and tp_pips > 0 else None,
                        credentials=user_creds
                    )

                if success:
                    st.success(f"Order placed! {msg}")
                    if ticket:
                        st.info(f"Ticket: {ticket}")
                    st.balloons()
                else:
                    st.error(f"Order failed: {msg}")
            except Exception as e:
                report_page_error(e, f"Orders / place_order / {symbol} {direction}")
                st.error(f"Lỗi khi đặt lệnh: {type(e).__name__}: {e}")


def show_demo_mode():
    """Show demo data when MT5 is not available"""

    st.subheader("Account Info (Demo)")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Balance", "$10,000.00")

    with col2:
        st.metric("Equity", "$10,150.00")

    with col3:
        st.metric("Floating P&L", "$150.00", delta="profit")

    with col4:
        st.metric("Free Margin", "$9,500.00")

    st.divider()

    st.subheader("Open Positions (Demo)")

    demo_positions = [
        {
            "ticket": 12345678,
            "symbol": "XAUUSD",
            "type": "BUY",
            "volume": 0.01,
            "open_price": 2650.00,
            "current_price": 2665.00,
            "profit": 15.00,
            "pnl_pips": 150.0,
            "open_time": "21:05 15/01"
        },
        {
            "ticket": 12345679,
            "symbol": "BTCUSD",
            "type": "SELL",
            "volume": 0.01,
            "open_price": 98500.00,
            "current_price": 98350.00,
            "profit": 15.00,
            "pnl_pips": 150.0,
            "open_time": "21:05 15/01"
        }
    ]

    for pos in demo_positions:
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])

            with col1:
                direction_color = "green" if pos['type'] == "BUY" else "red"
                st.markdown(f"**{pos['symbol']}** - :{direction_color}[{pos['type']}]")
                st.caption(f"Ticket: {pos['ticket']} | Vol: {pos['volume']} | Open: {pos['open_time']}")

            with col2:
                st.metric("Entry", f"{pos['open_price']:.2f}")

            with col3:
                st.metric("Current", f"{pos['current_price']:.2f}")

            with col4:
                st.markdown(f"**P&L**")
                st.markdown(f":green[${pos['profit']:.2f}]")
                st.caption(f"{pos['pnl_pips']:+.1f} pips")

            with col5:
                st.button("Close", key=f"demo_close_{pos['ticket']}", type="secondary", disabled=True)

            st.divider()

    st.info("Connect to MT5 on Windows to manage real positions")


if __name__ == "__main__":
    main()
