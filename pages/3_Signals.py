"""
Signals Page - View signal history and statistics
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import os

load_dotenv()

st.set_page_config(
    page_icon="📊",
    page_title="Signals",
    layout="wide",
)

# Auth check
from src.auth import require_auth
username, name = require_auth()

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
SIGNALS_FILE = "data/signals.csv"


def load_signals() -> pd.DataFrame:
    """Load signals from CSV file"""
    if os.path.exists(SIGNALS_FILE):
        return pd.read_csv(SIGNALS_FILE)
    else:
        # Return empty dataframe with correct columns
        return pd.DataFrame(columns=[
            "Date", "Time", "Symbol", "Direction", "Entry", "SL", "TP",
            "Exit_Type", "Exit_Price", "PnL_Pips", "Candles"
        ])


def save_signals(df: pd.DataFrame):
    """Save signals to CSV file"""
    os.makedirs("data", exist_ok=True)
    df.to_csv(SIGNALS_FILE, index=False)


def calculate_stats(df: pd.DataFrame) -> dict:
    """Calculate trading statistics"""
    if df.empty:
        return {
            "total": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": "0%",
            "total_pnl": 0,
            "avg_pnl": 0,
            "best": 0,
            "worst": 0,
        }

    total = len(df)
    wins = len(df[df["PnL_Pips"] > 0])
    losses = len(df[df["PnL_Pips"] < 0])
    win_rate = f"{(wins / total * 100):.1f}%" if total > 0 else "0%"
    total_pnl = df["PnL_Pips"].sum()
    avg_pnl = df["PnL_Pips"].mean()
    best = df["PnL_Pips"].max()
    worst = df["PnL_Pips"].min()

    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "avg_pnl": avg_pnl,
        "best": best,
        "worst": worst,
    }


def main():
    st.title("📊 Signal History")

    now = datetime.now(TIMEZONE)
    st.markdown(f"**Current Time:** {now.strftime('%H:%M:%S %d/%m/%Y')} (HCM)")

    st.divider()

    # Load signals
    signals_df = load_signals()
    stats = calculate_stats(signals_df)

    # Statistics
    st.subheader("📈 Statistics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Trades", stats["total"])
        st.metric("Wins", stats["wins"])

    with col2:
        st.metric("Win Rate", stats["win_rate"])
        st.metric("Losses", stats["losses"])

    with col3:
        pnl_delta = "profit" if stats["total_pnl"] > 0 else "loss" if stats["total_pnl"] < 0 else None
        st.metric("Total P&L", f"{stats['total_pnl']:.1f} pips", delta=pnl_delta)
        st.metric("Avg P&L", f"{stats['avg_pnl']:.1f} pips")

    with col4:
        st.metric("Best Trade", f"{stats['best']:.1f} pips")
        st.metric("Worst Trade", f"{stats['worst']:.1f} pips")

    st.divider()

    # Filters
    st.subheader("🔍 Filter Signals")

    col1, col2, col3 = st.columns(3)

    with col1:
        direction_filter = st.multiselect(
            "Direction",
            options=["BUY", "SELL"],
            default=[]
        )

    with col2:
        result_filter = st.multiselect(
            "Result",
            options=["TP", "SL", "TIME"],
            default=[]
        )

    with col3:
        date_range = st.date_input(
            "Date Range",
            value=[],
            help="Filter by date range"
        )

    # Apply filters
    filtered_df = signals_df.copy()

    if direction_filter:
        filtered_df = filtered_df[filtered_df["Direction"].isin(direction_filter)]

    if result_filter:
        filtered_df = filtered_df[filtered_df["Exit_Type"].isin(result_filter)]

    st.divider()

    # Signal table
    st.subheader("📋 Signal List")

    if filtered_df.empty:
        st.info("No signals recorded yet. Run the bot to generate signals.")
    else:
        # Add color to P&L
        def color_pnl(val):
            if val > 0:
                return 'color: green'
            elif val < 0:
                return 'color: red'
            return ''

        styled_df = filtered_df.style.map(color_pnl, subset=['PnL_Pips'])
        st.dataframe(styled_df, width='stretch', hide_index=True)

    st.divider()

    # Manual entry (for testing)
    with st.expander("➕ Add Manual Signal (Testing)"):
        st.caption("Use this to manually add signals for testing purposes")

        col1, col2 = st.columns(2)

        with col1:
            signal_date = st.date_input("Date", value=datetime.now(TIMEZONE).date())
            signal_time = st.time_input("Time", value=datetime.now(TIMEZONE).time())
            signal_symbol = st.text_input("Symbol", value=os.getenv("SYMBOL", "XAUUSD"))
            signal_direction = st.selectbox("Direction", ["BUY", "SELL"])
            signal_entry = st.number_input("Entry", value=3300.0, format="%.2f")

        with col2:
            signal_sl = st.number_input("SL", value=3295.0, format="%.2f")
            signal_tp = st.number_input("TP", value=3310.0, format="%.2f")
            signal_exit_type = st.selectbox("Exit Type", ["TP", "SL", "TIME"])
            signal_exit_price = st.number_input("Exit Price", value=3310.0, format="%.2f")
            signal_candles = st.number_input("Candles", value=3, min_value=1, max_value=7)

        # Calculate P&L
        if signal_direction == "BUY":
            signal_pnl = (signal_exit_price - signal_entry) / 0.1  # ETH pip
        else:
            signal_pnl = (signal_entry - signal_exit_price) / 0.1

        st.metric("Calculated P&L", f"{signal_pnl:.1f} pips")

        if st.button("Add Signal", type="primary"):
            new_signal = pd.DataFrame([{
                "Date": signal_date.strftime("%Y-%m-%d"),
                "Time": signal_time.strftime("%H:%M"),
                "Symbol": signal_symbol,
                "Direction": signal_direction,
                "Entry": signal_entry,
                "SL": signal_sl,
                "TP": signal_tp,
                "Exit_Type": signal_exit_type,
                "Exit_Price": signal_exit_price,
                "PnL_Pips": signal_pnl,
                "Candles": signal_candles
            }])

            signals_df = pd.concat([signals_df, new_signal], ignore_index=True)
            save_signals(signals_df)
            st.success("Signal added!")
            st.rerun()

    # Clear signals
    st.divider()
    col1, col2, col3 = st.columns([2, 1, 2])

    with col2:
        if st.button("🗑️ Clear All Signals", type="secondary"):
            if os.path.exists(SIGNALS_FILE):
                os.remove(SIGNALS_FILE)
                st.success("All signals cleared!")
                st.rerun()


if __name__ == "__main__":
    main()
