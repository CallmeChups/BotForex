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
    is_mt5_available,
    fetch_open_positions,
    close_position,
    close_all_positions,
    get_account_info,
    get_order_history
)

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
        st.page_link("pages/3_Settings.py", label="Go to Settings", icon="⚙️")
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

    # Open Positions
    st.subheader("Open Positions")

    # Controls
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.button("Refresh Positions", use_container_width=True, type="primary"):
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
                    pnl_color = "green" if pos['profit'] > 0 else "red" if pos['profit'] < 0 else "gray"
                    st.markdown(f"**P&L**")
                    st.markdown(f":{pnl_color}[${pos['profit']:.2f}]")
                    st.caption(f"{pos['pnl_pips']:+.1f} pips")

                with col5:
                    if st.button("Close", key=f"close_{pos['ticket']}", type="secondary"):
                        success, msg = close_position(pos['ticket'], credentials=user_creds)
                        if success:
                            st.success(msg)
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(msg)

                st.divider()

        # Close all button
        st.markdown("")
        col1, col2, col3 = st.columns([2, 1, 2])

        with col2:
            if st.button("Close All Positions", type="secondary", use_container_width=True):
                closed, error = close_all_positions(credentials=user_creds)
                if error:
                    st.warning(error)
                else:
                    st.success(f"Closed {closed} position(s)")
                    time.sleep(1)
                    st.rerun()

    # Auto-refresh logic
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()

    st.divider()

    # Order close history
    st.subheader("Manual Close History")

    history_df = get_order_history()

    if history_df.empty:
        st.info("No manual closes recorded yet")
    else:
        st.dataframe(history_df, use_container_width=True, hide_index=True)


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
            "symbol": "ETHUSDm",
            "type": "BUY",
            "volume": 0.01,
            "open_price": 3300.00,
            "current_price": 3315.00,
            "profit": 15.00,
            "pnl_pips": 150.0,
            "open_time": "21:05 15/01"
        },
        {
            "ticket": 12345679,
            "symbol": "BTCUSDm",
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
