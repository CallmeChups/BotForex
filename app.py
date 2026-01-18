"""
BotForex - MT5 Master Candle Trading Bot Dashboard
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import os

load_dotenv()

# Page config
st.set_page_config(
    page_icon="📈",
    page_title="BotForex Dashboard",
    layout="wide",
)

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
SYMBOL = os.getenv("SYMBOL", "ETHUSDm")


def get_status_color(status: str) -> str:
    """Return color based on status"""
    colors = {
        "RUNNING": "🟢",
        "STOPPED": "🔴",
        "WAITING": "🟡",
    }
    return colors.get(status, "⚪")


def main():
    # Header
    st.title("📈 BotForex Dashboard")
    st.caption(f"Master Candle Strategy | {SYMBOL} | M5")

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
    st.subheader("📋 Strategy Rules")

    with st.expander("Master Candle Strategy", expanded=True):
        st.markdown("""
        **Entry Time:** 21:05 HCM (M5 candle close)

        **Entry Rules:**
        - Bullish candle (Close > Open) → **BUY**
        - Bearish candle (Close < Open) → **SELL**

        **Risk Management:**
        - **SL:** Low - 30 pips (BUY) / High + 30 pips (SELL)
        - **TP:** Risk × 2 (RR 1:2)
        - **Lot Size:** 0.01

        **Exit Rules:**
        - TP: Price-based (immediate)
        - SL: Close-based (candle must CLOSE beyond)
        - Time: Max 7 candles (~35 min)
        """)

    st.divider()

    # Recent signals placeholder
    st.subheader("📊 Recent Signals")

    # Placeholder data - will be replaced with real data later
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
    st.dataframe(signals_df, use_container_width=True, hide_index=True)

    st.caption("No signals yet. Bot will trigger at 21:05 HCM.")

    st.divider()

    # Quick actions
    st.subheader("⚡ Quick Actions")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.rerun()

    with col2:
        if st.button("📤 Test Telegram", use_container_width=True):
            from src.strategy import send_telegram
            if send_telegram("🔔 Test message from BotForex Dashboard"):
                st.success("Message sent!")
            else:
                st.error("Failed to send message")

    with col3:
        if st.button("📊 Run Simulation", use_container_width=True):
            st.info("Go to Strategy page to run simulation")

    # Footer
    st.divider()
    st.caption("BotForex v0.1.0 | Master Candle Strategy")


if __name__ == "__main__":
    main()
