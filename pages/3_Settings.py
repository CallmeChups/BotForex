"""
Settings Page - Configure bot settings
"""

import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv, set_key
import os

load_dotenv()

st.set_page_config(
    page_icon="⚙️",
    page_title="Settings",
    layout="wide",
)

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
ENV_FILE = ".env"


def main():
    st.title("⚙️ Settings")

    now = datetime.now(TIMEZONE)
    st.markdown(f"**Current Time:** {now.strftime('%H:%M:%S %d/%m/%Y')} (HCM)")

    st.divider()

    # MT5 Settings
    st.subheader("🔗 MT5 Configuration")

    col1, col2 = st.columns(2)

    with col1:
        mt5_login = st.text_input(
            "MT5 Login",
            value=os.getenv("MT5_LOGIN", ""),
            type="default"
        )
        mt5_server = st.text_input(
            "MT5 Server",
            value=os.getenv("MT5_SERVER", ""),
        )

    with col2:
        mt5_password = st.text_input(
            "MT5 Password",
            value=os.getenv("MT5_PASSWORD", ""),
            type="password"
        )
        symbol = st.text_input(
            "Trading Symbol",
            value=os.getenv("SYMBOL", "ETHUSDm"),
            help="Use ETHUSDm for Standard account, ETHUSD for Pro/Raw"
        )

    st.divider()

    # Telegram Settings
    st.subheader("📱 Telegram Configuration")

    col1, col2 = st.columns(2)

    with col1:
        telegram_token = st.text_input(
            "Bot Token",
            value=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            type="password"
        )
        telegram_chat_id = st.text_input(
            "Main Chat ID",
            value=os.getenv("TELEGRAM_CHAT_ID", ""),
            help="Main group for trade signals"
        )

    with col2:
        telegram_error_chat_id = st.text_input(
            "Error Chat ID",
            value=os.getenv("TELEGRAM_ERROR_CHAT_ID", ""),
            help="Group for error notifications"
        )
        telegram_test_chat_id = st.text_input(
            "Test Chat ID",
            value=os.getenv("TELEGRAM_TEST_CHAT_ID", ""),
            help="Group for testing"
        )

    st.divider()

    # Test connections
    st.subheader("🔬 Test Connections")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔗 Test MT5 Connection", use_container_width=True):
            try:
                import MetaTrader5 as mt5

                if not mt5.initialize():
                    st.error("MT5 initialization failed")
                else:
                    login = int(os.getenv("MT5_LOGIN"))
                    password = os.getenv("MT5_PASSWORD")
                    server = os.getenv("MT5_SERVER")

                    if mt5.login(login=login, password=password, server=server):
                        account = mt5.account_info()._asdict()
                        st.success(f"Connected! Balance: {account['balance']}")
                        mt5.shutdown()
                    else:
                        st.error(f"Login failed: {mt5.last_error()}")
                        mt5.shutdown()
            except Exception as e:
                st.error(f"Error: {e}")

    with col2:
        if st.button("📱 Test Telegram", use_container_width=True):
            try:
                import requests

                token = os.getenv("TELEGRAM_BOT_TOKEN")
                chat_id = os.getenv("TELEGRAM_TEST_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")

                url = f"https://api.telegram.org/bot{token}/sendMessage"
                payload = {
                    "chat_id": chat_id,
                    "text": "🔔 Test from BotForex Settings",
                    "parse_mode": "HTML"
                }
                response = requests.post(url, json=payload)

                if response.ok:
                    st.success("Message sent!")
                else:
                    st.error(f"Failed: {response.text}")
            except Exception as e:
                st.error(f"Error: {e}")

    st.divider()

    # Current .env display (read-only)
    st.subheader("📄 Current Configuration")

    with st.expander("View .env (masked)"):
        st.code(f"""
# MT5 Configuration
MT5_LOGIN={os.getenv('MT5_LOGIN', '')}
MT5_PASSWORD=********
MT5_SERVER={os.getenv('MT5_SERVER', '')}

# Trading
SYMBOL={os.getenv('SYMBOL', '')}

# Telegram
TELEGRAM_BOT_TOKEN=********
TELEGRAM_CHAT_ID={os.getenv('TELEGRAM_CHAT_ID', '')}
TELEGRAM_ERROR_CHAT_ID={os.getenv('TELEGRAM_ERROR_CHAT_ID', '')}
TELEGRAM_TEST_CHAT_ID={os.getenv('TELEGRAM_TEST_CHAT_ID', '')}
        """)

    st.divider()

    # Info
    st.subheader("ℹ️ Information")

    st.markdown("""
    **Note:** To change settings permanently, edit the `.env` file directly.

    **File locations:**
    - `.env` - Environment variables
    - `data/signals.csv` - Signal history
    - `.streamlit/config.toml` - Streamlit theme

    **Account Types:**
    - Standard account: Use symbols with `m` suffix (ETHUSDm, BTCUSDm)
    - Pro/Raw account: Use symbols without suffix (ETHUSD, BTCUSD)
    """)

    # App info
    st.divider()
    col1, col2, col3 = st.columns(3)

    with col1:
        st.caption("**Version:** 0.1.0")

    with col2:
        st.caption("**Strategy:** Master Candle")

    with col3:
        st.caption("**Timeframe:** M5")


if __name__ == "__main__":
    main()
