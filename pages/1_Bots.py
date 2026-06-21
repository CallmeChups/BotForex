"""
Bots Page - Manage trading bot processes
"""

import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import os

load_dotenv()

st.set_page_config(
    page_icon="🤖",
    page_title="Bots",
    layout="wide",
)

# Auth check
from src.auth import require_auth, has_mt5_credentials
username, name = require_auth()

from src.bot_manager import (
    start_bot,
    stop_bot,
    stop_all_bots,
    list_bots,
    restart_bot,
    get_bot_stats
)
from src.strategy_manager import list_strategies, get_strategy_parameters

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def main():
    st.title("Bot Management")

    now = datetime.now(TIMEZONE)
    st.markdown(f"**Current Time:** {now.strftime('%H:%M:%S %d/%m/%Y')} (HCM)")

    st.divider()

    # Check MT5 credentials
    if not has_mt5_credentials(username):
        st.warning("MT5 account not configured. Please go to Settings first.")
        st.page_link("pages/8_Settings.py", label="Go to Settings", icon="⚙️")

    # Stats overview
    stats = get_bot_stats()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Running Bots", stats['total'])
    with col2:
        st.metric("Test Mode", stats['test_mode'])
    with col3:
        st.metric("Live Mode", stats['live_mode'])
    with col4:
        st.metric("Strategies", len(stats['strategies']))

    st.divider()

    # Tabs
    tab1, tab2 = st.tabs(["Running Bots", "Create Bot"])

    with tab1:
        show_running_bots()

    with tab2:
        show_create_bot()


def show_running_bots():
    """Show list of running bots"""
    st.subheader("Running Bots")

    # Refresh button
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("Refresh", type="primary", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("Stop All My Bots", type="secondary", use_container_width=True):
            stopped, msg = stop_all_bots(user=username)
            st.success(msg)
            st.rerun()

    # List bots
    bots = list_bots(refresh=True)

    if not bots:
        st.info("No bots running. Create one in the 'Create Bot' tab.")
        return

    # Filter options
    with st.expander("Filters"):
        col1, col2 = st.columns(2)
        with col1:
            filter_user = st.checkbox("Only my bots", value=True)
        with col2:
            filter_test = st.selectbox("Mode", ["All", "Test Only", "Live Only"])

    # Apply filters
    if filter_user:
        bots = [b for b in bots if b['user'] == username]

    if filter_test == "Test Only":
        bots = [b for b in bots if b.get('test', True)]
    elif filter_test == "Live Only":
        bots = [b for b in bots if not b.get('test', True)]

    if not bots:
        st.info("No bots match the filters")
        return

    st.success(f"Found {len(bots)} bot(s)")

    # Display bots
    for bot in bots:
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

            with col1:
                mode_badge = "🧪 TEST" if bot.get('test', True) else "🔴 LIVE"
                st.markdown(f"**{bot['strategy']}** | {bot['symbol']} | {mode_badge}")
                st.caption(f"PID: {bot['pid']} | User: {bot['user']} | Started: {bot.get('started_at', 'N/A')}")

                # Parameters
                params = []
                if bot.get('lot_size'):
                    params.append(f"Lot: {bot['lot_size']}")
                if bot.get('sl_pips'):
                    params.append(f"SL: {bot['sl_pips']} pips")
                if bot.get('rr_ratio'):
                    params.append(f"RR: {bot['rr_ratio']}")
                if params:
                    st.caption(" | ".join(params))

            with col2:
                # Only allow control if user owns the bot
                if bot['user'] == username:
                    if st.button("Stop", key=f"stop_{bot['pid']}", type="secondary"):
                        success, msg = stop_bot(bot['pid'])
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
                        st.rerun()
                else:
                    st.button("Stop", key=f"stop_{bot['pid']}", disabled=True)

            with col3:
                if bot['user'] == username:
                    if st.button("Restart", key=f"restart_{bot['pid']}", type="secondary"):
                        success, msg, _ = restart_bot(bot['pid'])
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
                        st.rerun()
                else:
                    st.button("Restart", key=f"restart_{bot['pid']}", disabled=True)

            with col4:
                status_color = "green" if bot.get('status') == 'running' else "red"
                st.markdown(f":{status_color}[● {bot.get('status', 'unknown').upper()}]")

            st.divider()


def show_create_bot():
    """Show form to create new bot"""
    st.subheader("Create New Bot")

    # Get available strategies
    strategies = list_strategies()
    enabled_strategies = [s for s in strategies if s.get('enabled', True)]

    if not enabled_strategies:
        st.warning("No strategies available. Create one in the Strategies page.")
        st.page_link("pages/4_Strategies.py", label="Go to Strategies", icon="📖")
        return

    with st.form("create_bot"):
        col1, col2 = st.columns(2)

        with col1:
            # Strategy selection
            strategy_options = {s['name']: s['id'] for s in enabled_strategies}
            selected_strategy_name = st.selectbox(
                "Strategy*",
                options=list(strategy_options.keys())
            )
            selected_strategy = strategy_options[selected_strategy_name]

            # Load strategy parameters as defaults
            params = get_strategy_parameters(selected_strategy)
            is_pattern = params.get('entry_type', 'time') == 'pattern'

            symbol = st.text_input(
                "Symbol*",
                value=params.get('symbols', ['XAUUSD'])[0] if params.get('symbols') else os.getenv("SYMBOL", "XAUUSD")
            )

            test_mode = st.checkbox("Test Mode", value=True, help="No real trades, only simulation")

        with col2:
            lot_size = st.number_input(
                "Lot Size",
                value=float(params.get('lot_size', 0.01)),
                min_value=0.01,
                step=0.01,
                format="%.2f"
            )

            sl_pips = st.number_input(
                "SL (pips)",
                value=int(params.get('sl_pips', 30)),
                min_value=1,
                max_value=200
            )

            rr_ratio = st.number_input(
                "RR Ratio",
                value=float(params.get('rr_ratio', 2.0)),
                min_value=0.5,
                max_value=10.0,
                step=0.5
            )

        col1, col2 = st.columns(2)

        with col1:
            max_candles = st.number_input(
                "Max Candles",
                value=int(params.get('max_candles', 7)),
                min_value=1,
                max_value=50
            )

        with col2:
            interval = st.number_input(
                "Check Interval (seconds)",
                value=60,
                min_value=10,
                max_value=300,
                help="How often to check for signals"
            )

        if is_pattern:
            st.markdown("**EMA Filter (FEG)**")
            ec1, ec2, ec3 = st.columns(3)
            with ec1:
                ema_period = st.number_input("EMA Period", value=int(params.get('ema_period', 21)), min_value=2, max_value=200)
            with ec2:
                ema_distance_enabled = st.checkbox("Xét khoảng cách EMA21", value=bool(params.get('ema_distance_enabled', False)))
            with ec3:
                ema_distance_pips = st.number_input("Khoảng cách (pips)", value=float(params.get('ema_distance_pips', 0) or 0), min_value=0.0, step=1.0, disabled=not ema_distance_enabled)
        else:
            ema_period = None
            ema_distance_enabled = False
            ema_distance_pips = 0.0

        # Show strategy info
        st.markdown("---")
        st.markdown(f"**Strategy:** {selected_strategy_name}")
        if is_pattern:
            st.caption(f"Pattern: {params.get('pattern', 'feg')} | EMA{params.get('ema_period', 21)} ({params.get('timeframe', 'M5')})")
        else:
            st.caption(f"Entry: {params.get('entry_time', 'N/A')} ({params.get('timeframe', 'N/A')})")

        submitted = st.form_submit_button("Start Bot", type="primary", use_container_width=True)

        if submitted:
            if not symbol:
                st.error("Symbol is required")
            else:
                success, msg, bot_info = start_bot(
                    strategy=selected_strategy,
                    symbol=symbol,
                    user=username,
                    test=test_mode,
                    lot_size=lot_size,
                    sl_pips=sl_pips,
                    rr_ratio=rr_ratio,
                    max_candles=max_candles,
                    interval=interval,
                    ema_period=ema_period,
                    ema_distance_enabled=ema_distance_enabled,
                    ema_distance_pips=ema_distance_pips,
                )

                if success:
                    st.success(f"Bot started! {msg}")
                    st.balloons()
                    st.rerun()
                else:
                    st.error(msg)

    # Quick start buttons
    st.markdown("---")
    st.markdown("**Quick Start (Test Mode)**")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("XAUUSD", use_container_width=True):
            success, msg, _ = start_bot(
                strategy=enabled_strategies[0]['id'],
                symbol="XAUUSD",
                user=username,
                test=True
            )
            if success:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    with col2:
        if st.button("BTCUSD", use_container_width=True):
            success, msg, _ = start_bot(
                strategy=enabled_strategies[0]['id'],
                symbol="BTCUSD",
                user=username,
                test=True
            )
            if success:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    with col3:
        if st.button("ETHUSD", use_container_width=True):
            success, msg, _ = start_bot(
                strategy=enabled_strategies[0]['id'],
                symbol="ETHUSD",
                user=username,
                test=True
            )
            if success:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)


if __name__ == "__main__":
    main()
