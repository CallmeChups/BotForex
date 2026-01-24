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
                tf = bot.get('timeframe', 'M5')
                entry = bot.get('entry_time', 'N/A')
                st.markdown(f"**{bot['strategy']}** | {bot['symbol']} | {tf} | {mode_badge}")
                st.caption(f"PID: {bot['pid']} | User: {bot['user']} | Entry: {entry} | Started: {bot.get('started_at', 'N/A')}")

                # Parameters
                params = []
                lot_mode = bot.get('lot_mode', 'fixed')
                if lot_mode == 'fixed' and bot.get('lot_size'):
                    params.append(f"Lot: {bot['lot_size']}")
                elif lot_mode == 'flex':
                    risk_pct = bot.get('risk_percent', 1)
                    compound_indicator = "C" if bot.get('risk_compounding', True) else "F"
                    params.append(f"Flex: {risk_pct}% ({compound_indicator})")
                if bot.get('rr_ratio'):
                    params.append(f"RR: {bot['rr_ratio']}")
                if bot.get('max_candles'):
                    params.append(f"Max: {bot['max_candles']}c")
                if bot.get('tp_type'):
                    params.append(f"TP: {bot['tp_type'][:5]}")
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

    # Strategy selection (outside form for dynamic updates)
    strategy_options = {s['name']: s['id'] for s in enabled_strategies}
    selected_strategy_name = st.selectbox(
        "Strategy*",
        options=list(strategy_options.keys())
    )
    selected_strategy = strategy_options[selected_strategy_name]

    # Load strategy parameters as defaults
    params = get_strategy_parameters(selected_strategy)

    st.divider()

    # Basic Settings
    st.subheader("Basic Settings")
    col1, col2, col3 = st.columns(3)

    with col1:
        symbol = st.text_input(
            "Symbol*",
            value=params.get('symbols', ['XAUUSD'])[0] if params.get('symbols') else os.getenv("SYMBOL", "XAUUSD")
        )

        test_mode = st.checkbox(
            "Test Mode",
            value=True,
            help="ON: Bot simulates trades (logs only, NO real orders) | OFF: Bot places REAL orders on your account"
        )
        if not test_mode:
            st.warning("⚠️ LIVE MODE: Real trades will be placed!")

    with col2:
        # Timeframe
        strategy_timeframe = params.get('timeframe', 'M5')
        timeframe_options = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]

        use_custom_timeframe = st.checkbox("Custom timeframe", value=False)
        if use_custom_timeframe:
            timeframe = st.selectbox(
                "Timeframe",
                options=timeframe_options,
                index=timeframe_options.index(strategy_timeframe) if strategy_timeframe in timeframe_options else 1
            )
        else:
            timeframe = strategy_timeframe
            st.text_input("Timeframe", value=strategy_timeframe, disabled=True)

    with col3:
        # Entry time
        entry_time_str = params.get('entry_time', '21:05')

        use_custom_time = st.checkbox("Custom entry time", value=False)
        if use_custom_time:
            batch_times = st.checkbox("Batch (multiple times)", value=False)

            if batch_times:
                custom_times_str = st.text_input(
                    "Entry Times",
                    value="21:05, 22:00, 23:00",
                    help="Comma-separated times (e.g., 21:05, 22:00). Creates one bot per time.",
                    placeholder="HH:MM, HH:MM, ..."
                )
                # Parse multiple times
                entry_times = []
                for t in custom_times_str.split(','):
                    t = t.strip()
                    try:
                        entry_times.append(t)
                    except ValueError:
                        pass
                if not entry_times:
                    st.error("No valid times. Use HH:MM format separated by commas.")
                    entry_times = ["21:05"]
            else:
                entry_time = st.text_input(
                    "Entry Time",
                    value=entry_time_str,
                    max_chars=5,
                    help="Format: HH:MM"
                )
                entry_times = [entry_time]
        else:
            entry_time = entry_time_str
            st.text_input("Entry Time", value=entry_time_str, disabled=True)
            entry_times = [entry_time]

        interval = st.number_input(
            "Check Interval (sec)",
            value=60,
            min_value=1,
            max_value=300,
            help="How often bot checks for new candles. Fast forex: 1-5s | M1: 10-30s | M5+: 60s"
        )
        if interval < 10:
            st.warning(f"⚠️ {interval}s interval: Very frequent checks may strain broker connection")

    st.divider()

    # Entry Configuration
    st.subheader("Entry")

    col1, col2 = st.columns(2)

    with col1:
        entry_mode = st.radio(
            "Entry Mode",
            options=["close", "range_percent"],
            format_func=lambda x: "Close Price" if x == "close" else "Body Percent (%)",
            horizontal=True,
            help="Close: Enter at candle close | Body %: Enter at % of candle body (Close-Open)"
        )

    with col2:
        if entry_mode == "range_percent":
            entry_percent = st.number_input(
                "Entry Percent (%)",
                value=30.0,
                min_value=0.0,
                max_value=100.0,
                step=5.0,
                help="BUY: Close - X%(C-O) | SELL: Close + X%(O-C)"
            )
            st.caption(f"BUY: Close - {entry_percent}%(body) | SELL: Close + {entry_percent}%(body)")
        else:
            entry_percent = 0.0
            st.caption("Entry at candle Close price")

    col1, col2 = st.columns(2)

    with col1:
        rr_ratio = st.number_input(
            "RR Ratio",
            value=float(params.get('rr_ratio', 2.0)),
            min_value=0.5,
            max_value=10.0,
            step=0.5
        )

    st.divider()

    # Exit Configuration
    st.subheader("Exit Types")
    col1, col2 = st.columns(2)

    with col1:
        tp_type = st.radio(
            "TP Type",
            options=["price_based", "close_based"],
            format_func=lambda x: "Price-based (hit exact price)" if x == "price_based" else "Close-based (candle close)",
            horizontal=True
        )

    with col2:
        sl_type = st.radio(
            "SL Type",
            options=["price_based", "close_based", ],
            format_func=lambda x: "Close-based (candle close)" if x == "close_based" else "Price-based (hit exact price)",
            horizontal=True
        )

    col1, col2 = st.columns(2)

    with col1:
        use_max_candles = st.checkbox("Enable Max Candles", value=True)
        if use_max_candles:
            max_candles = st.number_input(
                "Max Candles",
                value=int(params.get('max_candles', 7)),
                min_value=1,
                max_value=50
            )
        else:
            max_candles = 0

    st.divider()

    # Lot Size Configuration
    st.subheader("Lot Size")

    lot_mode = st.radio(
        "Mode",
        options=["fixed", "flex"],
        format_func=lambda x: "Fixed Lot" if x == "fixed" else "Flex (Risk-based)",
        horizontal=True
    )

    # Buffer K - used for both modes (SL = candle body + k)
    col1, col2 = st.columns(2)

    with col1:
        buffer_k = st.number_input(
            "Buffer K (pips)",
            value=float(params.get('buffer_k', 5.0)),
            min_value=0.0,
            max_value=200.0,
            step=1.0,
            help="SL = candle body + k pips"
        )

    st.caption("SL pips = (Close - Low) + k for BUY, (High - Close) + k for SELL")

    if lot_mode == "fixed":
        with col2:
            lot_size = st.number_input(
                "Lot Size",
                value=float(params.get('lot_size', 0.01)),
                min_value=0.01,
                max_value=10.0,
                step=0.01,
                format="%.2f"
            )
        # Set defaults for flex params
        starting_equity = 1000.0
        risk_mode = "percent"
        risk_percent = 1.0
        risk_amount = 10.0
        risk_compounding = True
    else:
        col1, col2, col3 = st.columns(3)

        with col1:
            starting_equity = st.number_input(
                "Starting Equity (USD)",
                value=1000.0,
                min_value=100.0,
                max_value=1000000.0,
                step=100.0,
                help="Initial account equity"
            )

        with col2:
            risk_mode = st.radio(
                "Risk Mode",
                options=["percent", "fixed_amount"],
                format_func=lambda x: "Percentage (%)" if x == "percent" else "Fixed Amount ($)",
                horizontal=True,
                help="Percent: risk changes with equity | Fixed: constant risk per trade"
            )

        with col3:
            if risk_mode == "percent":
                risk_percent = st.number_input(
                    "Risk per Trade (%)",
                    value=0.5,
                    min_value=0.1,
                    max_value=5.0,
                    step=0.1,
                    format="%.1f",
                    help="Percentage of equity to risk per trade"
                )
                risk_amount = 0.0
            else:
                risk_amount = st.number_input(
                    "Risk per Trade ($)",
                    value=5.0,
                    min_value=1.0,
                    max_value=1000.0,
                    step=1.0,
                    format="%.2f",
                    help="Fixed dollar amount to risk per trade"
                )
                risk_percent = 0.0
                st.caption(f"Constant ${risk_amount:.2f} risk per trade")

        # Risk compounding option (only for percent mode)
        if risk_mode == "percent":
            risk_compounding = st.checkbox(
                "Compounding Risk",
                value=True,
                help="ON: Risk % based on current equity (grows/shrinks) | OFF: Risk % based on starting equity (fixed)"
            )
            if risk_compounding:
                st.caption(f"Risk will compound with equity changes")
            else:
                example_r = starting_equity * (risk_percent / 100)
                st.caption(f"Risk fixed at {risk_percent}% of ${starting_equity:.0f} = ${example_r:.2f}/trade")
        else:
            risk_compounding = True  # Not applicable for fixed_amount mode

        lot_size = 0.01  # Will be calculated dynamically

    st.divider()

    # Summary
    is_batch = len(entry_times) > 1
    times_display = ', '.join(entry_times)
    st.caption(f"**Strategy:** {selected_strategy_name} | **Symbol:** {symbol} | **Timeframe:** {timeframe} | **Entry:** {times_display}")

    # Start button
    button_label = f"Start {len(entry_times)} Bots" if is_batch else "Start Bot"
    if st.button(button_label, type="primary", use_container_width=True):
        if not symbol:
            st.error("Symbol is required")
        else:
            # Validate all entry times first
            valid_times = []
            for t in entry_times:
                try:
                    datetime.strptime(t, "%H:%M")
                    valid_times.append(t)
                except ValueError:
                    st.error(f"Invalid time format: {t}. Use HH:MM (e.g., 21:05)")

            if not valid_times:
                st.error("No valid entry times provided.")
            else:
                success_count = 0
                error_count = 0
                messages = []

                progress_bar = st.progress(0, text="Starting bots...")

                for idx, time_str in enumerate(valid_times):
                    progress_bar.progress((idx) / len(valid_times), text=f"Starting bot {idx+1}/{len(valid_times)}: {time_str}")

                    success, msg, bot_info = start_bot(
                        strategy=selected_strategy,
                        symbol=symbol,
                        user=username,
                        test=test_mode,
                        lot_size=lot_size if lot_mode == "fixed" else None,
                        sl_pips=None,  # Calculated from candle
                        rr_ratio=rr_ratio,
                        max_candles=max_candles if max_candles > 0 else None,
                        interval=interval,
                        timeframe=timeframe,
                        entry_time=time_str,
                        entry_mode=entry_mode,
                        entry_percent=entry_percent,
                        buffer_k=buffer_k,
                        lot_mode=lot_mode,
                        starting_equity=starting_equity if lot_mode == "flex" else None,
                        risk_mode=risk_mode if lot_mode == "flex" else None,
                        risk_percent=risk_percent if lot_mode == "flex" else None,
                        risk_amount=risk_amount if lot_mode == "flex" else None,
                        risk_compounding=risk_compounding if lot_mode == "flex" else None,
                        tp_type=tp_type,
                        sl_type=sl_type
                    )

                    if success:
                        success_count += 1
                        messages.append(f"✓ {time_str}: {msg}")
                    else:
                        error_count += 1
                        messages.append(f"✗ {time_str}: {msg}")

                progress_bar.progress(1.0, text="Done!")

                # Show results
                if success_count > 0:
                    st.success(f"{success_count} bot(s) started successfully!")
                    if is_batch:
                        for m in messages:
                            if "✓" in m:
                                st.caption(m)

                if error_count > 0:
                    st.error(f"{error_count} bot(s) failed to start.")
                    for m in messages:
                        if "✗" in m:
                            st.caption(m)

                if success_count > 0:
                    st.balloons()
                    st.rerun()

    # Quick start buttons
    st.markdown("---")
    st.markdown("**Quick Start (Test Mode - uses strategy defaults)**")

    # Get default params from first strategy
    default_params = get_strategy_parameters(enabled_strategies[0]['id'])

    col1, col2, col3 = st.columns(3)

    quick_start_config = {
        'test': True,
        'timeframe': default_params.get('timeframe', 'M5'),
        'entry_time': default_params.get('entry_time', '21:05'),
        'entry_mode': 'signal',
        'rr_ratio': default_params.get('rr_ratio', 2.0),
        'max_candles': default_params.get('max_candles', 7),
        'lot_mode': 'fixed',
        'lot_size': 0.01,
        'tp_type': 'price_based',
        'sl_type': 'close_based'
    }

    with col1:
        if st.button("XAUUSD", use_container_width=True):
            success, msg, _ = start_bot(
                strategy=enabled_strategies[0]['id'],
                symbol="XAUUSD",
                user=username,
                **quick_start_config
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
                **quick_start_config
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
                **quick_start_config
            )
            if success:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)


if __name__ == "__main__":
    main()
