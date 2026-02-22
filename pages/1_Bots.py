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
from src.bot_config_history import (
    save_bot_config as save_config_to_history,
    get_config_history,
    delete_config_record
)

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def _apply_preset_to_session(config: dict):
    """Write config values to st.session_state['preset_*'] keys for form pre-fill"""
    mapping = {
        'strategy': 'preset_strategy',
        'symbol': 'preset_symbol',
        'test': 'preset_test',
        'timeframe': 'preset_timeframe',
        'entry_time': 'preset_entry_time',
        'entry_mode': 'preset_entry_mode',
        'entry_percent': 'preset_entry_percent',
        'pending_order_max_candles': 'preset_pending_order_max_candles',
        'rr_ratio': 'preset_rr_ratio',
        'buffer_k': 'preset_buffer_k',
        'tp_type': 'preset_tp_type',
        'sl_type': 'preset_sl_type',
        'max_candles': 'preset_max_candles',
        'move_sl_to_breakeven': 'preset_move_sl_to_breakeven',
        'breakeven_trigger_percent': 'preset_breakeven_trigger_percent',
        'lot_mode': 'preset_lot_mode',
        'lot_size': 'preset_lot_size',
        'starting_equity': 'preset_starting_equity',
        'risk_mode': 'preset_risk_mode',
        'risk_percent': 'preset_risk_percent',
        'risk_amount': 'preset_risk_amount',
        'risk_compounding': 'preset_risk_compounding',
        'interval': 'preset_interval',
    }
    for cfg_key, ss_key in mapping.items():
        if cfg_key in config and config[cfg_key] is not None:
            st.session_state[ss_key] = config[cfg_key]


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
    tab1, tab2, tab3 = st.tabs(["Running Bots", "Create Bot", "Bot History & Analysis"])

    with tab1:
        show_running_bots()

    with tab2:
        show_create_bot()

    with tab3:
        show_bot_history()


def show_running_bots():
    """Show list of running bots"""
    st.subheader("Running Bots")

    # Refresh button
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        refresh_clicked = st.button("Refresh", type="primary", width='stretch')

    with col2:
        if st.button("Stop All My Bots", type="secondary", width='stretch'):
            stopped, msg = stop_all_bots(user=username)
            st.success(msg)
            st.rerun()

    # List bots
    # Only cleanup dead bots when user clicks "Refresh" button
    # Don't cleanup on normal page refresh to prevent accidental bot removal
    bots = list_bots(refresh=True, cleanup=refresh_clicked)

    # Rerun after cleanup if refresh was clicked
    if refresh_clicked:
        st.rerun()

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
                mode_badge = "TEST" if bot.get('test', True) else "LIVE"
                tf = bot.get('timeframe', 'M5')
                entry = bot.get('entry_time', 'N/A')
                st.markdown(f"**{bot['strategy']}** | {bot['symbol']} | {tf} | {mode_badge}")
                log_file = bot.get('log_file', 'N/A')
                st.caption(f"PID: {bot['pid']} | User: {bot['user']} | Entry: {entry} | Started: {bot.get('started_at', 'N/A')}")
                if log_file != 'N/A':
                    st.caption(f"Log: {log_file}")

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
                st.markdown(f":{status_color}[{bot.get('status', 'unknown').upper()}]")

            # Config details expander
            with st.expander("Config Details", expanded=False):
                _show_bot_config_details(bot)
                if bot['user'] == username:
                    if st.button("Load this config", key=f"load_running_{bot['pid']}"):
                        _apply_preset_to_session(bot)
                        st.success("Config loaded! Switch to Create Bot tab.")
                        st.rerun()

            st.divider()


def _show_bot_config_details(bot: dict):
    """Display full config details for a bot in a compact layout"""
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"**Strategy:** {bot.get('strategy', 'N/A')}")
        st.markdown(f"**Symbol:** {bot.get('symbol', 'N/A')}")
        st.markdown(f"**Timeframe:** {bot.get('timeframe', 'N/A')}")
        st.markdown(f"**Entry Time:** {bot.get('entry_time', 'N/A')}")
    with col2:
        entry_mode = bot.get('entry_mode', 'close')
        st.markdown(f"**Entry Mode:** {entry_mode}")
        if entry_mode == 'range_percent':
            st.markdown(f"**Entry %:** {bot.get('entry_percent', 0)}%")
            st.markdown(f"**Pending Max:** {bot.get('pending_order_max_candles', 0)}c")
        st.markdown(f"**RR Ratio:** 1:{bot.get('rr_ratio', 'N/A')}")
        st.markdown(f"**Buffer K:** {bot.get('buffer_k', 0)} pts")
    with col3:
        st.markdown(f"**TP Type:** {bot.get('tp_type', 'N/A')}")
        st.markdown(f"**SL Type:** {bot.get('sl_type', 'N/A')}")
        st.markdown(f"**Max Candles:** {bot.get('max_candles', 0) or 'Off'}")
        if bot.get('move_sl_to_breakeven'):
            st.markdown(f"**Breakeven:** {bot.get('breakeven_trigger_percent', 50)}%")
    with col4:
        lot_mode = bot.get('lot_mode', 'fixed')
        st.markdown(f"**Lot Mode:** {lot_mode}")
        if lot_mode == 'fixed':
            st.markdown(f"**Lot Size:** {bot.get('lot_size', 0.01)}")
        else:
            st.markdown(f"**Equity:** ${bot.get('starting_equity', 0)}")
            risk_mode = bot.get('risk_mode', 'percent')
            if risk_mode == 'percent':
                st.markdown(f"**Risk:** {bot.get('risk_percent', 0)}%")
                st.markdown(f"**Compound:** {'Yes' if bot.get('risk_compounding', True) else 'No'}")
            else:
                st.markdown(f"**Risk:** ${bot.get('risk_amount', 0)}")


def show_create_bot():
    """Show form to create new bot"""
    st.subheader("Create New Bot")

    # ── PRESET LOADER ──
    with st.expander("Load from past config"):
        history = get_config_history(username=username)
        running_bots = list_bots(user=username, refresh=False)

        # Build options list from history + running bots
        preset_options = {}

        for bot in running_bots:
            label = f"[Running] {bot.get('symbol', '?')} | {bot.get('strategy', '?')} | {bot.get('timeframe', '?')} | {bot.get('entry_time', '?')}"
            preset_options[label] = bot

        for rec in history:
            cfg = rec.get('config', {})
            ts = datetime.fromisoformat(rec['timestamp']).strftime('%m/%d %H:%M')
            preset_label = f" ({rec['preset_name']})" if rec.get('preset_name') else ""
            label = f"[{ts}] {rec.get('symbol', '?')} | {rec.get('strategy', '?')} | {cfg.get('timeframe', '?')} | {cfg.get('entry_time', '?')}{preset_label}"
            preset_options[label] = cfg

        if preset_options:
            selected_preset = st.selectbox(
                "Select config",
                options=["-- Select --"] + list(preset_options.keys()),
                key="preset_selector"
            )
            if selected_preset != "-- Select --":
                if st.button("Load selected config"):
                    _apply_preset_to_session(preset_options[selected_preset])
                    st.success("Config loaded! Form updated.")
                    st.rerun()
        else:
            st.caption("No saved configs yet. Start a bot or save a preset to build history.")

    # Get available strategies
    strategies = list_strategies()
    enabled_strategies = [s for s in strategies if s.get('enabled', True)]

    if not enabled_strategies:
        st.warning("No strategies available. Create one in the Strategies page.")
        st.page_link("pages/4_Strategies.py", label="Go to Strategies", icon="📖")
        return

    # Strategy selection — use preset if available
    strategy_options = {s['name']: s['id'] for s in enabled_strategies}
    strategy_ids = {s['id']: s['name'] for s in enabled_strategies}

    preset_strategy = st.session_state.get('preset_strategy')
    default_strategy_idx = 0
    if preset_strategy and preset_strategy in strategy_ids:
        strategy_names = list(strategy_options.keys())
        preset_name = strategy_ids[preset_strategy]
        if preset_name in strategy_names:
            default_strategy_idx = strategy_names.index(preset_name)

    selected_strategy_name = st.selectbox(
        "Strategy*",
        options=list(strategy_options.keys()),
        index=default_strategy_idx
    )
    selected_strategy = strategy_options[selected_strategy_name]

    # Load strategy parameters as defaults
    params = get_strategy_parameters(selected_strategy)

    st.divider()

    # ── SECTION 1: Market ──
    st.subheader("Market")
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

    with col1:
        # Symbol
        strategy_symbols = params.get('symbols', [])
        preset_symbol = st.session_state.get('preset_symbol')

        # Force custom symbol mode if preset has a symbol not in strategy list
        force_custom = preset_symbol and strategy_symbols and preset_symbol not in strategy_symbols
        use_custom_symbol = st.checkbox("Custom symbol", value=bool(force_custom), key="bot_custom_symbol")

        if use_custom_symbol:
            symbol = st.text_input(
                "Symbol*",
                value=preset_symbol or os.getenv("SYMBOL", "XAUUSD"),
                help="Enter any symbol supported by your broker"
            )
        elif strategy_symbols:
            sym_index = 0
            if preset_symbol and preset_symbol in strategy_symbols:
                sym_index = strategy_symbols.index(preset_symbol)
            symbol = st.selectbox(
                "Symbol*",
                options=strategy_symbols,
                index=sym_index,
                help="From strategy's supported symbols"
            )
        else:
            symbol = st.text_input("Symbol*", value=preset_symbol or os.getenv("SYMBOL", "XAUUSD"))

        # Show symbol info inline
        from src.utils import get_pip_value, get_pip_value_per_lot, get_contract_size
        pv = get_pip_value(symbol)
        pvl = get_pip_value_per_lot(symbol)
        cs = get_contract_size(symbol)
        st.caption(f"pip={pv} | $/pip/lot=${pvl:.2f} | contract={cs:,.0f}")

    with col2:
        # Timeframe
        strategy_timeframe = st.session_state.get('preset_timeframe', params.get('timeframe', 'M5'))
        timeframe_options = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
        tf_index = timeframe_options.index(strategy_timeframe) if strategy_timeframe in timeframe_options else 1
        timeframe = st.selectbox("Timeframe", options=timeframe_options, index=tf_index)

    with col3:
        # Entry time
        entry_time_str = st.session_state.get('preset_entry_time', params.get('entry_time', '21:05'))

        use_custom_time = st.checkbox("Custom time", value=False)
        if use_custom_time:
            entry_time = st.text_input("Entry Time", value=entry_time_str, max_chars=5, help="HH:MM")
            entry_times = [entry_time]
        else:
            entry_time = entry_time_str
            st.text_input("Entry Time", value=entry_time_str, disabled=True)
            entry_times = [entry_time]

    with col4:
        preset_test = st.session_state.get('preset_test')
        test_default = preset_test if preset_test is not None else False
        test_mode = st.checkbox("Test Mode", value=test_default, help="Simulate only, no real orders")
        if not test_mode:
            st.warning("LIVE MODE")

        preset_interval = st.session_state.get('preset_interval', 1)
        interval = st.number_input("Interval (s)", value=int(preset_interval), min_value=1, max_value=300, help="Check interval")

    # Batch entry times (expandable)
    with st.expander("Batch Entry Times (create multiple bots)"):
        custom_times_str = st.text_input(
            "Entry Times",
            value="21:05, 22:00, 23:00",
            help="Comma-separated HH:MM. Creates one bot per time.",
            placeholder="HH:MM, HH:MM, ..."
        )
        use_batch = st.checkbox("Enable batch mode", value=False)
        if use_batch:
            entry_times = [t.strip() for t in custom_times_str.split(',') if t.strip()]
            if not entry_times:
                st.error("No valid times.")
                entry_times = ["21:05"]
            st.caption(f"Will create {len(entry_times)} bot(s): {', '.join(entry_times)}")

    st.divider()

    # ── SECTION 2: Trade Setup ──
    st.subheader("Trade Setup")
    col1, col2, col3 = st.columns(3)

    with col1:
        preset_entry_mode = st.session_state.get('preset_entry_mode', 'close')
        entry_mode_options = ["close", "range_percent"]
        entry_mode_idx = entry_mode_options.index(preset_entry_mode) if preset_entry_mode in entry_mode_options else 0
        entry_mode = st.radio(
            "Entry Mode",
            options=entry_mode_options,
            index=entry_mode_idx,
            format_func=lambda x: "Close Price" if x == "close" else "Range Percent",
            horizontal=True,
            help="Close: MARKET order at candle close | Range %: LIMIT order at % retracement"
        )

    with col2:
        preset_rr = st.session_state.get('preset_rr_ratio')
        rr_default = float(preset_rr) if preset_rr is not None else float(params.get('rr_ratio', 2.0))
        rr_ratio = st.number_input(
            "RR Ratio",
            value=rr_default,
            min_value=0.5, max_value=10.0, step=0.5
        )

    with col3:
        preset_buf = st.session_state.get('preset_buffer_k')
        buf_default = float(preset_buf) if preset_buf is not None else float(params.get('buffer_k', 5.0))
        buffer_k = st.number_input(
            "Buffer K (points)",
            value=buf_default,
            min_value=0.0, max_value=1000.0, step=1.0,
            help="Extra points added to SL beyond candle wick"
        )
        from src.utils import get_point_value
        pt = get_point_value(symbol)
        buffer_usd = buffer_k * pt
        st.caption(f"{symbol}: {buffer_k:.0f} pts = ${buffer_usd:.2f} SL buffer")

    if entry_mode == "range_percent":
        col1, col2 = st.columns(2)
        with col1:
            preset_ep = st.session_state.get('preset_entry_percent')
            ep_default = float(preset_ep) if preset_ep is not None else 30.0
            entry_percent = st.number_input(
                "Entry Percent (%)", value=ep_default,
                min_value=0.0, max_value=100.0, step=5.0,
                help="BUY: Close - X%(body) | SELL: Close + X%(body)"
            )
        with col2:
            preset_pomc = st.session_state.get('preset_pending_order_max_candles')
            pomc_default = int(preset_pomc) if preset_pomc is not None else 3
            pending_order_max_candles = st.number_input(
                "Max Wait (candles)", value=pomc_default,
                min_value=1, max_value=10, step=1,
                help="Cancel LIMIT order if not filled after N candles"
            )
    else:
        entry_percent = 0.0
        pending_order_max_candles = 0

    # ── SECTION 3: Exit Rules (collapsible) ──
    with st.expander("Exit Rules", expanded=False):
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            preset_tp = st.session_state.get('preset_tp_type', 'price_based')
            tp_options = ["price_based", "close_based"]
            tp_idx = tp_options.index(preset_tp) if preset_tp in tp_options else 0
            tp_type = st.radio(
                "TP Type",
                options=tp_options,
                index=tp_idx,
                format_func=lambda x: "Price (wick)" if x == "price_based" else "Close (candle)",
                help="Price: exit when wick touches TP | Close: exit when candle closes beyond TP"
            )

        with col2:
            preset_sl = st.session_state.get('preset_sl_type', 'price_based')
            sl_options = ["price_based", "close_based"]
            sl_idx = sl_options.index(preset_sl) if preset_sl in sl_options else 0
            sl_type = st.radio(
                "SL Type",
                options=sl_options,
                index=sl_idx,
                format_func=lambda x: "Close (candle)" if x == "close_based" else "Price (wick)",
                help="Close: exit when candle closes beyond SL | Price: exit when wick touches SL"
            )

        with col3:
            preset_mc = st.session_state.get('preset_max_candles')
            mc_has_value = preset_mc is not None and int(preset_mc) > 0
            use_max_candles = st.checkbox("Max Candles", value=mc_has_value if preset_mc is not None else True)
            if use_max_candles:
                mc_default = int(preset_mc) if mc_has_value else int(params.get('max_candles', 7))
                max_candles = st.number_input(
                    "Limit", value=mc_default,
                    min_value=1, max_value=50,
                    help="Force close after N candles"
                )
            else:
                max_candles = 0

        with col4:
            preset_be = st.session_state.get('preset_move_sl_to_breakeven', False)
            move_sl_to_breakeven = st.checkbox("Breakeven", value=bool(preset_be), help="Move SL to entry when TP partially reached")
            if move_sl_to_breakeven:
                preset_be_pct = st.session_state.get('preset_breakeven_trigger_percent')
                be_default = float(preset_be_pct) if preset_be_pct is not None else 50.0
                breakeven_trigger_percent = st.number_input(
                    "Trigger (%)", value=be_default,
                    min_value=10.0, max_value=90.0, step=5.0,
                    help="Move SL to entry when price reaches this % of TP"
                )
            else:
                breakeven_trigger_percent = 50.0

    # ── SECTION 4: Position Sizing (collapsible) ──
    with st.expander("Position Sizing", expanded=False):
        preset_lm = st.session_state.get('preset_lot_mode', 'fixed')
        lm_options = ["fixed", "flex"]
        lm_idx = lm_options.index(preset_lm) if preset_lm in lm_options else 0
        lot_mode = st.radio(
            "Mode",
            options=lm_options,
            index=lm_idx,
            format_func=lambda x: "Fixed Lot" if x == "fixed" else "Flex (Risk-based)",
            horizontal=True
        )

        if lot_mode == "fixed":
            preset_ls = st.session_state.get('preset_lot_size')
            ls_default = float(preset_ls) if preset_ls is not None else float(params.get('lot_size', 0.01))
            lot_size = st.number_input(
                "Lot Size",
                value=ls_default,
                min_value=0.01, max_value=10.0, step=0.01, format="%.2f"
            )
            starting_equity = 1000.0
            risk_mode = "percent"
            risk_percent = 1.0
            risk_amount = 10.0
            risk_compounding = True
        else:
            col1, col2, col3 = st.columns(3)

            with col1:
                preset_se = st.session_state.get('preset_starting_equity')
                se_default = float(preset_se) if preset_se is not None else 1000.0
                starting_equity = st.number_input(
                    "Starting Equity ($)", value=se_default,
                    min_value=100.0, max_value=1000000.0, step=100.0
                )

            with col2:
                preset_rm = st.session_state.get('preset_risk_mode', 'percent')
                rm_options = ["percent", "fixed_amount"]
                rm_idx = rm_options.index(preset_rm) if preset_rm in rm_options else 0
                risk_mode = st.radio(
                    "Risk Mode",
                    options=rm_options,
                    index=rm_idx,
                    format_func=lambda x: "Percentage (%)" if x == "percent" else "Fixed Amount ($)",
                    horizontal=True
                )

            with col3:
                if risk_mode == "percent":
                    preset_rp = st.session_state.get('preset_risk_percent')
                    rp_default = float(preset_rp) if preset_rp is not None else 0.5
                    risk_percent = st.number_input(
                        "Risk/Trade (%)", value=rp_default,
                        min_value=0.1, max_value=5.0, step=0.1, format="%.1f"
                    )
                    risk_amount = 0.0
                else:
                    preset_ra = st.session_state.get('preset_risk_amount')
                    ra_default = float(preset_ra) if preset_ra is not None else 5.0
                    risk_amount = st.number_input(
                        "Risk/Trade ($)", value=ra_default,
                        min_value=1.0, max_value=1000.0, step=1.0, format="%.2f"
                    )
                    risk_percent = 0.0

            if risk_mode == "percent":
                preset_rc = st.session_state.get('preset_risk_compounding')
                rc_default = bool(preset_rc) if preset_rc is not None else True
                risk_compounding = st.checkbox(
                    "Compounding", value=rc_default,
                    help="ON: risk % based on current equity | OFF: based on starting equity"
                )
            else:
                risk_compounding = True

            lot_size = 0.01

    # ── SUMMARY & ACTIONS ──
    is_batch = len(entry_times) > 1
    times_display = ', '.join(entry_times)
    mode_label = "TEST" if test_mode else "LIVE"
    entry_label = f"Range {entry_percent}%" if entry_mode == "range_percent" else "Close"
    lot_label = f"{lot_size} lot" if lot_mode == "fixed" else f"Flex {risk_percent}%" if risk_mode == "percent" else f"Flex ${risk_amount}"
    tp_label = "Price" if tp_type == "price_based" else "Close"
    sl_label = "Close" if sl_type == "close_based" else "Price"

    with st.container(border=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Symbol", symbol)
        with col2:
            st.metric("Timeframe", timeframe)
        with col3:
            if is_batch:
                st.metric("Entry Times", f"{len(entry_times)} times")
            else:
                st.metric("Entry Time", times_display)
        with col4:
            st.metric("Mode", mode_label)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("RR Ratio", f"1:{rr_ratio}")
        with col2:
            st.metric("Entry Mode", entry_label)
        with col3:
            st.metric("TP / SL", f"{tp_label} / {sl_label}")
        with col4:
            if lot_mode == "fixed":
                pip_cost = lot_size * pvl
                st.metric("Lot / Risk per Pip", f"{lot_size} / ${pip_cost:.2f}")
            else:
                if risk_mode == "percent":
                    max_loss = starting_equity * risk_percent / 100
                    st.metric("Max Loss / Trade", f"${max_loss:.2f}")
                else:
                    st.metric("Max Loss / Trade", f"${risk_amount:.2f}")

    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if st.button("Validate Config", width='stretch'):
            from src.symbol_validator import validate_symbol_and_params
            from src.auth import get_user_mt5_credentials

            credentials = get_user_mt5_credentials(username)

            # Realistic sample price per symbol type
            symbol_upper = symbol.upper()
            if "XAU" in symbol_upper:
                sample_entry = 2400.0
            elif "BTC" in symbol_upper:
                sample_entry = 95000.0
            elif "ETH" in symbol_upper:
                sample_entry = 3500.0
            elif "JPY" in symbol_upper:
                sample_entry = 150.0
            elif symbol_upper in ("USDCHF", "USDCAD"):
                sample_entry = 1.0
            else:
                sample_entry = 1.1

            pip_value = get_pip_value(symbol)
            sample_sl = sample_entry - (10 * pip_value)
            sample_tp = sample_entry + (10 * pip_value * rr_ratio)
            sample_lot = lot_size if lot_mode == "fixed" else 0.01

            if lot_mode == "flex":
                from src.backtest import calculate_flex_lot_size
                sample_sl_pips = 10.0
                if risk_mode == "fixed_amount":
                    sample_lot = calculate_flex_lot_size(
                        equity=starting_equity, risk_percent=0,
                        sl_pips=sample_sl_pips, symbol=symbol, risk_amount=risk_amount
                    )
                else:
                    sample_lot = calculate_flex_lot_size(
                        equity=starting_equity, risk_percent=risk_percent,
                        sl_pips=sample_sl_pips, symbol=symbol
                    )

            is_valid, messages = validate_symbol_and_params(
                symbol=symbol, lot_size=sample_lot,
                entry_price=sample_entry, sl_price=sample_sl,
                tp_price=sample_tp, credentials=credentials
            )

            for msg in messages:
                if "[ERROR]" in msg:
                    st.error(msg)
                elif "[WARN]" in msg:
                    st.warning(msg)
                else:
                    st.info(msg)

            if is_valid:
                st.success("Configuration is valid!")
            else:
                st.error("Fix errors above before starting.")

    with col2:
        button_label = f"Start {len(entry_times)} Bots" if is_batch else "Start Bot"
        start_clicked = st.button(button_label, type="primary", width='stretch')

    with col3:
        # Save Preset (without starting a bot)
        preset_name_input = st.text_input("Preset name", placeholder="e.g. Gold Scalp M5", key="save_preset_name")
        if st.button("Save Preset", width='stretch'):
            preset_config = {
                'strategy': selected_strategy,
                'symbol': symbol,
                'user': username,
                'test': test_mode,
                'timeframe': timeframe,
                'entry_time': entry_times[0] if entry_times else '21:05',
                'entry_mode': entry_mode,
                'entry_percent': entry_percent,
                'pending_order_max_candles': pending_order_max_candles,
                'rr_ratio': rr_ratio,
                'buffer_k': buffer_k,
                'tp_type': tp_type,
                'sl_type': sl_type,
                'max_candles': max_candles,
                'move_sl_to_breakeven': move_sl_to_breakeven,
                'breakeven_trigger_percent': breakeven_trigger_percent,
                'lot_mode': lot_mode,
                'lot_size': lot_size if lot_mode == 'fixed' else None,
                'starting_equity': starting_equity if lot_mode == 'flex' else None,
                'risk_mode': risk_mode if lot_mode == 'flex' else None,
                'risk_percent': risk_percent if lot_mode == 'flex' else None,
                'risk_amount': risk_amount if lot_mode == 'flex' else None,
                'risk_compounding': risk_compounding if lot_mode == 'flex' else None,
                'interval': interval,
            }
            save_config_to_history(preset_config, preset_name=preset_name_input or None)
            name_msg = f' as "{preset_name_input}"' if preset_name_input else ''
            st.success(f"Preset saved{name_msg}!")
            st.rerun()

    if start_clicked:
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

                    # Small delay to prevent file race condition in batch creation
                    if idx > 0:
                        import time
                        time.sleep(0.1)  # 100ms delay between bots

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
                        sl_type=sl_type,
                        move_sl_to_breakeven=move_sl_to_breakeven,
                        breakeven_trigger_percent=breakeven_trigger_percent if move_sl_to_breakeven else None,
                        pending_order_max_candles=pending_order_max_candles if entry_mode == "range_percent" else None
                    )

                    if success:
                        success_count += 1
                        messages.append(f"[OK] {time_str}: {msg}")
                    else:
                        error_count += 1
                        messages.append(f"[FAIL] {time_str}: {msg}")

                progress_bar.progress(1.0, text="Done!")

                # Show results
                if success_count > 0:
                    st.success(f"{success_count} bot(s) started successfully!")
                    if is_batch:
                        for m in messages:
                            if "[OK]" in m:
                                st.caption(m)

                if error_count > 0:
                    st.error(f"{error_count} bot(s) failed to start.")
                    for m in messages:
                        if "[FAIL]" in m:
                            st.caption(m)

                if success_count > 0:
                    st.balloons()
                    st.rerun()

    # Quick start buttons
    st.markdown("---")
    st.markdown("**Quick Start (Test Mode - uses strategy defaults)**")

    # Get default params from first strategy
    default_params = get_strategy_parameters(enabled_strategies[0]['id'])

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

    # Define all supported symbols
    quick_symbols = [
        # Row 1: Metals & Crypto
        ["XAUUSD", "BTCUSD", "ETHUSD"],
        # Row 2: Major USD pairs
        ["EURUSD", "GBPUSD", "AUDUSD"],
        # Row 3: USD base & JPY pairs
        ["USDJPY", "USDCHF", "USDCAD", "AUDJPY"],
    ]

    def start_quick_bot(symbol):
        success, msg, _ = start_bot(
            strategy=enabled_strategies[0]['id'],
            symbol=symbol,
            user=username,
            **quick_start_config
        )
        if success:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)

    # Row 1: Metals & Crypto
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("XAUUSD", width='stretch', help="Gold"):
            start_quick_bot("XAUUSD")
    with col2:
        if st.button("BTCUSD", width='stretch', help="Bitcoin"):
            start_quick_bot("BTCUSD")
    with col3:
        if st.button("ETHUSD", width='stretch', help="Ethereum"):
            start_quick_bot("ETHUSD")

    # Row 2: Major USD quote pairs
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("EURUSD", width='stretch', help="Euro"):
            start_quick_bot("EURUSD")
    with col2:
        if st.button("GBPUSD", width='stretch', help="British Pound"):
            start_quick_bot("GBPUSD")
    with col3:
        if st.button("AUDUSD", width='stretch', help="Australian Dollar"):
            start_quick_bot("AUDUSD")

    # Row 3: USD base & JPY pairs
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("USDJPY", width='stretch', help="Yen"):
            start_quick_bot("USDJPY")
    with col2:
        if st.button("USDCHF", width='stretch', help="Swiss Franc"):
            start_quick_bot("USDCHF")
    with col3:
        if st.button("USDCAD", width='stretch', help="Canadian Dollar"):
            start_quick_bot("USDCAD")
    with col4:
        if st.button("AUDJPY", width='stretch', help="AUD/JPY Cross"):
            start_quick_bot("AUDJPY")


def show_bot_history():
    """Show bot config history and performance analysis"""
    import pandas as pd

    st.subheader("Bot History & Performance Analysis")
    st.caption("Analyze past bot configurations and results to optimize your strategy")

    # ── CONFIG HISTORY SECTION ──
    st.markdown("#### Config History")
    config_history = get_config_history(username=username)

    if config_history:
        # Build dataframe for display
        rows = []
        for rec in config_history:
            cfg = rec.get('config', {})
            ts = datetime.fromisoformat(rec['timestamp']).strftime('%m/%d %H:%M')
            entry_mode = cfg.get('entry_mode', 'close')
            lot_mode = cfg.get('lot_mode', 'fixed')

            if lot_mode == 'fixed':
                lot_display = f"{cfg.get('lot_size', 0.01)} lot"
            else:
                rm = cfg.get('risk_mode', 'percent')
                if rm == 'percent':
                    lot_display = f"Flex {cfg.get('risk_percent', 0)}%"
                else:
                    lot_display = f"Flex ${cfg.get('risk_amount', 0)}"

            row = {
                'ID': rec['id'],
                'Date': ts,
                'Preset': rec.get('preset_name') or '-',
                'Symbol': rec.get('symbol', '?'),
                'Strategy': rec.get('strategy', '?'),
                'TF': cfg.get('timeframe', '?'),
                'Entry': cfg.get('entry_time', '?'),
                'Mode': 'Close' if entry_mode == 'close' else f"Range {cfg.get('entry_percent', 0)}%",
                'RR': cfg.get('rr_ratio', '?'),
                'Lot': lot_display,
                'MaxC': cfg.get('max_candles', 0) or '-',
                'TP': cfg.get('tp_type', '?')[:5] if cfg.get('tp_type') else '-',
                'SL': cfg.get('sl_type', '?')[:5] if cfg.get('sl_type') else '-',
            }
            rows.append(row)

        history_df = pd.DataFrame(rows)
        display_cols = [c for c in history_df.columns if c != 'ID']
        st.dataframe(history_df[display_cols], hide_index=True, use_container_width=True)

        # Actions
        col1, col2 = st.columns(2)
        with col1:
            selected_id = st.selectbox(
                "Select record",
                options=[r['id'] for r in config_history],
                format_func=lambda x: next(
                    (f"{r.get('symbol', '?')} | {r.get('strategy', '?')} | {datetime.fromisoformat(r['timestamp']).strftime('%m/%d %H:%M')}"
                     + (f" ({r['preset_name']})" if r.get('preset_name') else ""))
                    for r in config_history if r['id'] == x
                ),
                key="history_select"
            )
        with col2:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Load into Create Bot", key="load_history_btn"):
                    rec = next((r for r in config_history if r['id'] == selected_id), None)
                    if rec:
                        _apply_preset_to_session(rec.get('config', {}))
                        st.success("Config loaded! Switch to Create Bot tab.")
                        st.rerun()
            with c2:
                if st.button("Delete record", key="delete_history_btn", type="secondary"):
                    if delete_config_record(selected_id):
                        st.success("Deleted.")
                        st.rerun()
                    else:
                        st.error("Record not found.")
    else:
        st.info("No config history yet. Start a bot or save a preset to begin.")

    st.divider()

    # ── PERFORMANCE ANALYSIS SECTION (existing) ──
    st.markdown("#### Performance Analysis")

    # Load orders data
    orders_file = "data/orders.csv"
    if not os.path.exists(orders_file):
        st.info("No trade history found. Run some bots first!")
        return

    try:
        orders_df = pd.read_csv(orders_file)
    except Exception as e:
        st.error(f"Error loading orders: {e}")
        return

    if len(orders_df) == 0:
        st.info("No trades recorded yet.")
        return

    # Filter by user (if column exists)
    if 'user' in orders_df.columns:
        user_orders = orders_df[orders_df['user'] == username].copy()
    else:
        # No user column - show all trades
        user_orders = orders_df.copy()
        st.warning("User column not found in orders data - showing all trades")

    if len(user_orders) == 0:
        st.info("No trades found.")
        return

    st.success(f"Found {len(user_orders)} trades")

    # Determine which P&L column to use (support both old and new CSV format)
    # New format: has 'pnl_pips', 'pnl_usd', 'symbol', etc.
    # Old format: only has 'profit' (USD from MT5)
    has_pips = 'pnl_pips' in user_orders.columns
    has_symbol = 'symbol' in user_orders.columns
    pnl_col = 'pnl_pips' if has_pips else 'profit'

    if not has_pips and 'profit' not in user_orders.columns:
        st.error("No P&L data found in orders.")
        return

    # Ensure numeric
    user_orders[pnl_col] = pd.to_numeric(user_orders[pnl_col], errors='coerce').fillna(0)

    # Group by bot configuration
    st.subheader("Performance by Configuration")

    # Create config identifier
    if has_symbol and 'strategy' in user_orders.columns:
        user_orders['config'] = user_orders['symbol'].astype(str) + " | " + user_orders['strategy'].astype(str)
    elif has_symbol:
        user_orders['config'] = user_orders['symbol'].astype(str)
    elif 'exit_type' in user_orders.columns:
        user_orders['config'] = "All Trades"
    else:
        user_orders['config'] = "All Trades"

    # Group and aggregate
    agg_dict = {
        pnl_col: ['count', 'sum', 'mean', 'min', 'max'],
    }
    if has_symbol:
        agg_dict['symbol'] = 'first'
    if 'pnl_usd' in user_orders.columns:
        agg_dict['pnl_usd'] = ['sum', 'mean']
    if 'strategy' in user_orders.columns:
        agg_dict['strategy'] = 'first'

    config_stats = user_orders.groupby('config').agg(agg_dict).reset_index()

    # Flatten columns
    config_stats.columns = ['_'.join(col).strip('_') if col[1] else col[0] for col in config_stats.columns.values]

    # Calculate win rate
    def calc_win_rate(config):
        config_trades = user_orders[user_orders['config'] == config]
        wins = len(config_trades[config_trades[pnl_col] > 0])
        total = len(config_trades)
        return round((wins / total * 100), 1) if total > 0 else 0

    config_stats['win_rate'] = config_stats['config'].apply(calc_win_rate)

    # Rename columns based on available data
    pnl_label = 'Total P&L (pips)' if has_pips else 'Total P&L ($)'
    rename_map = {
        f'{pnl_col}_count': 'Trades',
        f'{pnl_col}_sum': pnl_label,
        f'{pnl_col}_mean': 'Avg P&L',
        f'{pnl_col}_min': 'Worst',
        f'{pnl_col}_max': 'Best',
        'win_rate': 'Win %'
    }
    if has_symbol:
        rename_map['symbol_first'] = 'Symbol'
    if 'pnl_usd_sum' in config_stats.columns:
        rename_map['pnl_usd_sum'] = 'P&L ($)'
    if 'strategy_first' in config_stats.columns:
        rename_map['strategy_first'] = 'Strategy'

    config_stats = config_stats.rename(columns=rename_map)

    # Build display columns
    base_cols = []
    if 'Symbol' in config_stats.columns:
        base_cols.append('Symbol')
    if 'Strategy' in config_stats.columns:
        base_cols.append('Strategy')
    base_cols.extend(['Trades', 'Win %', pnl_label, 'Avg P&L', 'Best', 'Worst'])
    if 'P&L ($)' in config_stats.columns and has_pips:
        base_cols.append('P&L ($)')

    display_cols = [col for col in base_cols if col in config_stats.columns]
    config_stats = config_stats[display_cols].sort_values(pnl_label, ascending=False)

    # Style dataframe
    def highlight_pnl(row):
        if row[pnl_label] > 0:
            return ['background-color: #d4edda'] * len(row)
        elif row[pnl_label] < 0:
            return ['background-color: #f8d7da'] * len(row)
        return [''] * len(row)

    styled_df = config_stats.style.apply(highlight_pnl, axis=1)
    st.dataframe(styled_df, hide_index=True, use_container_width=True)

    # Export
    csv = config_stats.to_csv(index=False)
    st.download_button(
        "Download Analysis",
        csv,
        f"bot_analysis_{username}_{datetime.now().strftime('%Y%m%d')}.csv",
        "text/csv"
    )


if __name__ == "__main__":
    main()
