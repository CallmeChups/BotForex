"""
BotForex - Multi-Strategy MT5 Trading Dashboard
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import os

load_dotenv()

# Page config - MUST be first Streamlit command
st.set_page_config(
    page_icon="📈",
    page_title="BotForex Dashboard",
    layout="wide",
)

# Import auth after page config
from src.auth import get_authenticator, check_auth, get_user_role, is_admin

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
SYMBOL = os.getenv("SYMBOL", "XAUUSD")


def show_login_page():
    """Show login page"""
    st.title("📈 BotForex")
    st.subheader("Login to Dashboard")

    authenticator, config = get_authenticator()

    # Login form
    authenticator.login(location='main')

    auth_status = st.session_state.get('authentication_status')

    if auth_status == False:
        st.error("Username/password is incorrect")
    elif auth_status == None:
        st.info("Please enter your username and password")

        # Show default credentials for testing
        with st.expander("Demo Credentials"):
            st.code("""
Admin:
  Username: admin
  Password: admin123

User:
  Username: user
  Password: user123
            """)


def show_dashboard():
    """Show main dashboard after login"""
    authenticator, config = get_authenticator()

    # Sidebar with user info and logout
    with st.sidebar:
        st.markdown(f"### Welcome, {st.session_state['name']}!")

        username = st.session_state['username']
        role = get_user_role(username)
        st.caption(f"Role: {role.upper()}")

        st.divider()

        authenticator.logout("Logout", "sidebar")

        # Version ID (git commit hash)
        try:
            import subprocess
            _hash = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL, text=True
            ).strip()
        except Exception:
            _hash = "unknown"
        st.sidebar.markdown(f"<div style='position:fixed;bottom:12px;left:12px;font-size:11px;color:#888;'>v {_hash}</div>", unsafe_allow_html=True)

    # Main content
    st.title("📈 BotForex Dashboard")
    st.caption(f"Multi-Strategy Trading | {SYMBOL}")

    # Current time
    now = datetime.now(TIMEZONE)
    st.markdown(f"**Current Time:** {now.strftime('%H:%M:%S %d/%m/%Y')} (HCM)")

    st.divider()

    # Status metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Bot Status",
            value="WAITING",
            delta="Next: 21:05",
        )

    with col2:
        st.metric(
            label="Symbol",
            value=SYMBOL,
        )

    with col3:
        st.metric(
            label="Today's Signals",
            value="0",
            delta="0 wins",
        )

    with col4:
        st.metric(
            label="Total P&L",
            value="0.00",
            delta="0 pips",
        )

    st.divider()

    # Strategy summary
    st.subheader("📋 Active Strategies")

    with st.expander("Master Candle Strategy", expanded=False):
        st.markdown("""
        **Entry Time:** 21:05 HCM (M5 candle close)

        **Entry Rules:**
        - Bullish candle (Close > Open) → **BUY**
        - Bearish candle (Close < Open) → **SELL**

        **Risk Management:**
        - **SL:** Candle Low/High ± buffer pips
        - **TP:** Risk × RR ratio (default 2.0)
        - **Lot:** Fixed or flex (risk-based)

        **Exit Rules:**
        - TP: Price-based or Close-based
        - SL: Close-based or Price-based
        - Time: Max N candles (configurable)
        """)

    with st.expander("FEG EMA21 Strategy", expanded=False):
        st.markdown("""
        **Entry Trigger:** 2-candle FEG pattern (continuous scan, M5)

        **SELL Pattern:** H2>H1, C2<L1, L2>EMA21
        **BUY Pattern:** L2<L1, C2>H1, H2<EMA21

        **Risk Management:**
        - **SL:** Candle2 High/Low ± buffer pips
        - **TP:** Risk × RR ratio (default 2.0)
        - 1 trade at a time (no stacking)

        **Exit Rules:**
        - Same engine as Master Candle
        - Magic number: 212100
        """)

    st.divider()

    # Recent signals placeholder
    st.subheader("📊 Recent Signals")

    signals_data = {
        "Time": ["--"],
        "Direction": ["--"],
        "Entry": ["--"],
        "SL": ["--"],
        "TP": ["--"],
        "Result": ["--"],
        "P&L": ["--"],
    }

    signals_df = pd.DataFrame(signals_data)
    st.dataframe(signals_df, width='stretch', hide_index=True)

    st.caption("No signals yet. Bot will trigger at 21:05 HCM.")

    st.divider()

    # Quick actions
    st.subheader("⚡ Quick Actions")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔄 Refresh Data", width='stretch'):
            st.rerun()

    with col2:
        if st.button("📤 Test Telegram", width='stretch'):
            try:
                import requests
                token = os.getenv("TELEGRAM_BOT_TOKEN")
                chat_id = os.getenv("TELEGRAM_TEST_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")

                if not token or not chat_id:
                    st.error("Telegram not configured. Check Settings.")
                else:
                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    payload = {"chat_id": chat_id, "text": "🔔 Test from BotForex Dashboard"}
                    response = requests.post(url, json=payload)
                    if response.ok:
                        st.success("Message sent!")
                    else:
                        st.error("Failed to send message")
            except Exception as e:
                st.error(f"Error: {e}")

    with col3:
        if st.button("📊 Run Simulation", width='stretch'):
            st.info("Go to Strategy page to run simulation")

    # Footer
    st.divider()
    st.caption("BotForex v0.2.0 | Master Candle + FEG EMA21")


def main():
    """Main entry point"""
    auth_status, username, name = check_auth()

    if auth_status:
        show_dashboard()
    else:
        show_login_page()


if __name__ == "__main__":
    main()
