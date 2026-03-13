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
from src.i18n import t, lang_toggle_button
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
    lang_toggle_button(st.sidebar)
    st.title(f"📊 {t('page_signals')}")

    now = datetime.now(TIMEZONE)
    st.markdown(f"**{t('current_time')}:** {now.strftime('%H:%M:%S %d/%m/%Y')} (HCM)")

    st.divider()

    # Load signals
    signals_df = load_signals()
    stats = calculate_stats(signals_df)

    # Statistics
    st.subheader(f"📈 {t('statistics')}")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(t("total_trades"), stats["total"])
        st.metric(t("wins"), stats["wins"])

    with col2:
        st.metric(t("win_rate"), stats["win_rate"])
        st.metric(t("losses"), stats["losses"])

    with col3:
        pnl_delta = t("profit") if stats["total_pnl"] > 0 else t("loss") if stats["total_pnl"] < 0 else None
        st.metric(t("total_pnl"), f"{stats['total_pnl']:.1f} pips", delta=pnl_delta)
        st.metric(t("avg_pnl"), f"{stats['avg_pnl']:.1f} pips")

    with col4:
        st.metric(t("best_trade"), f"{stats['best']:.1f} pips")
        st.metric(t("worst_trade"), f"{stats['worst']:.1f} pips")

    st.divider()

    # Filters
    st.subheader(f"🔍 {t('filter_signals')}")

    col1, col2, col3 = st.columns(3)

    with col1:
        direction_filter = st.multiselect(
            t("direction"),
            options=["BUY", "SELL"],
            default=[]
        )

    with col2:
        result_filter = st.multiselect(
            t("result"),
            options=["TP", "SL", "TIME"],
            default=[]
        )

    with col3:
        date_range = st.date_input(
            t("date_range"),
            value=[],
            help=t("date_range")
        )

    # Apply filters
    filtered_df = signals_df.copy()

    if direction_filter:
        filtered_df = filtered_df[filtered_df["Direction"].isin(direction_filter)]

    if result_filter:
        filtered_df = filtered_df[filtered_df["Exit_Type"].isin(result_filter)]

    st.divider()

    # Signal table
    st.subheader(f"📋 {t('signal_list')}")

    if filtered_df.empty:
        st.info(t("no_signals"))
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
    with st.expander(f"➕ {t('add_manual_signal')}"):
        st.caption(t("manual_signal_caption"))

        col1, col2 = st.columns(2)

        with col1:
            signal_date = st.date_input(t("date"), value=datetime.now(TIMEZONE).date())
            signal_time = st.time_input(t("time_col"), value=datetime.now(TIMEZONE).time())
            signal_symbol = st.text_input(t("symbol"), value=os.getenv("SYMBOL", "XAUUSD"))
            signal_direction = st.selectbox(t("direction"), ["BUY", "SELL"])
            signal_entry = st.number_input(t("entry"), value=3300.0, format="%.2f")

        with col2:
            signal_sl = st.number_input(t("sl"), value=3295.0, format="%.2f")
            signal_tp = st.number_input(t("tp"), value=3310.0, format="%.2f")
            signal_exit_type = st.selectbox(t("exit_type"), ["TP", "SL", "TIME"])
            signal_exit_price = st.number_input(t("exit_price"), value=3310.0, format="%.2f")
            signal_candles = st.number_input(t("candles"), value=3, min_value=1, max_value=7)

        # Calculate P&L
        if signal_direction == "BUY":
            signal_pnl = (signal_exit_price - signal_entry) / 0.1
        else:
            signal_pnl = (signal_entry - signal_exit_price) / 0.1

        st.metric("Calculated P&L", f"{signal_pnl:.1f} pips")

        if st.button(t("add_signal"), type="primary"):
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
            st.success(t("signal_added"))
            st.rerun()

    # Clear signals
    st.divider()
    col1, col2, col3 = st.columns([2, 1, 2])

    with col2:
        if st.button(f"🗑️ {t('clear_all_signals')}", type="secondary"):
            if os.path.exists(SIGNALS_FILE):
                os.remove(SIGNALS_FILE)
                st.success(t("signals_cleared"))
                st.rerun()


if __name__ == "__main__":
    main()
