"""
Bots Page - Manage trading bot processes
"""

import streamlit as st
from datetime import datetime, time
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
from src.utils import get_pip_value

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def _pip_caption(pips: float, symbol: str) -> str:
    """Hiển thị giá trị thực của N pips theo symbol đang chọn."""
    pv = get_pip_value(symbol)
    return f"{pips} pips = **{pips * pv:.4g}** giá ({symbol})"


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

    # Layout toggle — persisted in session state, default compact
    use_compact = st.toggle("Compact layout", value=st.session_state.get("bots_compact_layout", True),
                            key="bots_compact_layout",
                            help="Switch between compact grid and classic expanded layout")

    # Get available strategies
    strategies = list_strategies()
    enabled_strategies = [s for s in strategies if s.get('enabled', True)]

    if not enabled_strategies:
        st.warning("No strategies available. Create one in the Strategies page.")
        st.page_link("pages/4_Strategies.py", label="Go to Strategies", icon="📖")
        return

    # Strategy selection (always outside layout block — drives param reload)
    strategy_options = {s['name']: s['id'] for s in enabled_strategies}
    selected_strategy_name = st.selectbox("Strategy*", options=list(strategy_options.keys()))
    selected_strategy = strategy_options[selected_strategy_name]

    params = get_strategy_parameters(selected_strategy)
    is_pattern = params.get('entry_type', 'time') == 'pattern'
    sk = selected_strategy  # key prefix — forces widget reinit when strategy changes

    if use_compact:
        # ── COMPACT LAYOUT ────────────────────────────────────────────────────
        # Row 1: Symbol | Test Mode | RR | Max Candles | Interval
        r1c1, r1c2, r1c3, r1c4, r1c5 = st.columns([2, 1, 1, 1, 1])

        strategy_symbols = params.get('symbols', [])
        with r1c1:
            use_custom_symbol = st.checkbox("Custom symbol", value=False, key=f"{sk}_custom_sym")
            if use_custom_symbol:
                symbol = st.text_input("Symbol*", value=os.getenv("SYMBOL", "XAUUSD"), key=f"{sk}_symbol")
            elif strategy_symbols:
                symbol = st.selectbox("Symbol*", options=strategy_symbols, key=f"{sk}_symbol")
            else:
                symbol = st.text_input("Symbol*", value=os.getenv("SYMBOL", "XAUUSD"), key=f"{sk}_symbol")

        with r1c2:
            test_mode = st.checkbox("Test Mode", value=True, key=f"{sk}_test",
                                    help="No real trades, simulation only")

        with r1c3:
            rr_ratio = st.number_input("RR Ratio", value=float(params.get('rr_ratio', 2.0)),
                                       min_value=0.5, max_value=10.0, step=0.5, key=f"{sk}_rr")

        with r1c4:
            use_max_candles = st.checkbox("Max Candles", value=True, key=f"{sk}_use_mc",
                                          help="Uncheck = exit on TP/SL only")
            if use_max_candles:
                max_candles = st.number_input("", value=int(params.get('max_candles', 7)),
                                              min_value=1, max_value=50, key=f"{sk}_mc",
                                              label_visibility="collapsed")
            else:
                max_candles = 0

        with r1c5:
            interval = st.number_input("Interval (s)", value=60, min_value=10, max_value=300,
                                       key=f"{sk}_iv", help="Signal check interval in seconds")
            st.caption(f"TF: **{params.get('timeframe', 'M5')}**")

        # Row 2: Entry config | Window | Entry Mode | Buffer K | Lot Mode
        r2c1, r2c2, r2c3, r2c4 = st.columns(4)

        with r2c1:
            if is_pattern:
                ema_period = st.number_input("EMA Period", value=int(params.get('ema_period', 21)),
                                             min_value=2, max_value=200, key=f"{sk}_ema")
                h2_exceed_pips = st.number_input(
                    "H2 > H1 + N pips", value=float(params.get('h2_exceed_pips', 0.0)),
                    min_value=0.0, step=1.0, key=f"{sk}_h2x",
                    help="SELL: H2 phải vượt H1 thêm N pips | BUY: L2 phải thấp hơn L1 thêm N pips")
                st.caption(_pip_caption(h2_exceed_pips, symbol))
                c2_gap_pips = st.number_input(
                    "C2 vượt L1/H1 + N pips", value=float(params.get('c2_gap_pips', 0.0)),
                    min_value=0.0, step=1.0, key=f"{sk}_c2g",
                    help="SELL: C2 phải đóng thấp hơn L1 thêm N pips | BUY: C2 phải đóng cao hơn H1 thêm N pips")
                st.caption(_pip_caption(c2_gap_pips, symbol))
                ema_margin_pips = st.number_input(
                    "L2/H2 cách EMA + N pips", value=float(params.get('ema_margin_pips', 0.0)),
                    min_value=0.0, step=1.0, key=f"{sk}_emam",
                    help="SELL: L2 phải cách EMA ≥ N pips | BUY: H2 phải cách EMA ≥ N pips")
                st.caption(_pip_caption(ema_margin_pips, symbol))
            else:
                ema_period = None
                h2_exceed_pips = 0.0
                c2_gap_pips = 0.0
                ema_margin_pips = 0.0
                st.caption(f"Entry: **{params.get('entry_time', 'N/A')}** (from strategy)")

        with r2c2:
            entry_start_time = st.time_input("Window Start (HCM)", value=time(0, 0),
                                             key=f"{sk}_tw_start",
                                             help="Gate entries from this time. 00:00 = no filter.")
            entry_end_time = st.time_input("Window End (HCM)", value=time(23, 59),
                                           key=f"{sk}_tw_end",
                                           help="Gate entries until this time. 23:59 = no filter.")

        with r2c3:
            entry_mode = st.radio("Entry Mode", options=["close", "range_percent"],
                                  index=0 if params.get('entry_mode', 'close') == 'close' else 1,
                                  format_func=lambda x: "Close" if x == "close" else "Body %",
                                  key=f"{sk}_entry_mode")
            if entry_mode == "range_percent":
                entry_percent = st.number_input("Entry %",
                                                value=float(params.get('entry_percent', 10.0) or 10.0),
                                                min_value=0.0, max_value=100.0, step=5.0,
                                                key=f"{sk}_entry_pct")
            else:
                entry_percent = 0.0

        with r2c4:
            buffer_k = st.number_input("Buffer K (pips)", value=float(params.get('buffer_k', 5)),
                                       min_value=0.0, max_value=200.0, step=1.0,
                                       key=f"{sk}_buffer_k", help="SL = candle extreme + K pips")
            lot_mode = st.radio("Lot Mode", options=["fixed", "flex"],
                                format_func=lambda x: "Fixed" if x == "fixed" else "Flex (Risk)",
                                key=f"{sk}_lot_mode")

        # Expander: Exit Types + Lot detail
        with st.expander("Exit Types & Lot Size", expanded=False):
            xc1, xc2 = st.columns(2)
            with xc1:
                tp_type = st.radio("TP Exit", options=["price_based", "close_based"],
                                   index=0 if params.get('tp_type', 'price_based') == 'price_based' else 1,
                                   format_func=lambda x: "Price-based (wick)" if x == "price_based" else "Close-based",
                                   horizontal=True, key=f"{sk}_tp_type")
            with xc2:
                sl_type = st.radio("SL Exit", options=["price_based", "close_based"],
                                   index=0 if params.get('sl_type', 'price_based') == 'price_based' else 1,
                                   format_func=lambda x: "Price-based (wick)" if x == "price_based" else "Close-based",
                                   horizontal=True, key=f"{sk}_sl_type")
            st.divider()
            if lot_mode == "fixed":
                fc1, _ = st.columns(2)
                with fc1:
                    lot_size = st.number_input("Lot Size", value=float(params.get('lot_size', 0.01)),
                                               min_value=0.01, max_value=10.0, step=0.01, format="%.2f",
                                               key=f"{sk}_lot")
                risk_mode = "percent"
                risk_percent = 0.5
                risk_amount = 0.0
            else:
                fc1, fc2, fc3 = st.columns(3)
                with fc1:
                    risk_mode = st.radio("Risk Mode", options=["percent", "fixed_amount"],
                                         format_func=lambda x: "%" if x == "percent" else "Fixed $",
                                         horizontal=True, key=f"{sk}_risk_mode")
                with fc2:
                    if risk_mode == "percent":
                        risk_percent = st.number_input("Risk %", value=0.5, min_value=0.1,
                                                       max_value=5.0, step=0.1, format="%.1f",
                                                       key=f"{sk}_risk_pct")
                        risk_amount = 0.0
                        st.caption(f"Lot tự động = equity MT5 × {risk_percent}%")
                    else:
                        risk_amount = st.number_input("Risk $", value=5.0, min_value=1.0,
                                                      max_value=1000.0, step=1.0, format="%.2f",
                                                      key=f"{sk}_risk_amt")
                        risk_percent = 0.0
                lot_size = 0.01

        st.caption(f"Strategy: **{selected_strategy_name}** | TF: {params.get('timeframe','M5')} | Entry: {params.get('entry_type','time')}")

    else:
        # ── OLD LAYOUT (verbose, multi-section) ───────────────────────────────
        # Strategy info preview
        if is_pattern:
            st.caption(f"Pattern: {params.get('pattern', 'feg')} | EMA{params.get('ema_period', 21)} | TF: {params.get('timeframe', 'M5')} | buffer_k: {params.get('buffer_k', 5)}")
        else:
            st.caption(f"Entry: {params.get('entry_time', 'N/A')} | TF: {params.get('timeframe', 'M5')} | SL: {params.get('sl_pips', 30)} pips")

        strategy_symbols = params.get('symbols', [])
        use_custom_symbol = st.checkbox("Custom symbol", value=False, key=f"{sk}_custom_sym")
        if use_custom_symbol:
            symbol = st.text_input("Symbol*", value=os.getenv("SYMBOL", "XAUUSD"), key=f"{sk}_symbol")
        elif strategy_symbols:
            symbol = st.selectbox("Symbol*", options=strategy_symbols, key=f"{sk}_symbol")
        else:
            symbol = st.text_input("Symbol*", value=os.getenv("SYMBOL", "XAUUSD"), key=f"{sk}_symbol")

        col1, col2, col3 = st.columns(3)
        with col1:
            test_mode = st.checkbox("Test Mode", value=True, help="No real trades, only simulation", key=f"{sk}_test")
            rr_ratio = st.number_input("RR Ratio", value=float(params.get('rr_ratio', 2.0)),
                                       min_value=0.5, max_value=10.0, step=0.5, key=f"{sk}_rr")
        with col2:
            use_max_candles = st.checkbox("Enable Max Candles", value=True, key=f"{sk}_use_mc")
            if use_max_candles:
                max_candles = st.number_input("Max Candles", value=int(params.get('max_candles', 7)),
                                              min_value=1, max_value=50, key=f"{sk}_mc")
            else:
                max_candles = 0
                st.caption("Không giới hạn thời gian — chỉ thoát TP/SL")
        with col3:
            interval = st.number_input("Check Interval (seconds)", value=60, min_value=10,
                                       max_value=300, key=f"{sk}_iv")
            st.caption(f"Timeframe: **{params.get('timeframe', 'M5')}** (from strategy)")

        if is_pattern:
            st.markdown("**FEG Filter Margins**")
            ec1, ec2, ec3, ec4 = st.columns(4)
            with ec1:
                ema_period = st.number_input("EMA Period", value=int(params.get('ema_period', 21)),
                                             min_value=2, max_value=200, key=f"{sk}_ema")
            with ec2:
                h2_exceed_pips = st.number_input(
                    "H2 > H1 + N pips", value=float(params.get('h2_exceed_pips', 0.0)),
                    min_value=0.0, step=1.0, key=f"{sk}_h2x",
                    help="SELL: H2 phải vượt H1 thêm N pips | BUY: L2 phải thấp hơn L1 thêm N pips")
                st.caption(_pip_caption(h2_exceed_pips, symbol))
            with ec3:
                c2_gap_pips = st.number_input(
                    "C2 vượt L1/H1 + N pips", value=float(params.get('c2_gap_pips', 0.0)),
                    min_value=0.0, step=1.0, key=f"{sk}_c2g",
                    help="SELL: C2 phải đóng thấp hơn L1 thêm N pips | BUY: C2 phải đóng cao hơn H1 thêm N pips")
                st.caption(_pip_caption(c2_gap_pips, symbol))
            with ec4:
                ema_margin_pips = st.number_input(
                    "L2/H2 cách EMA + N pips", value=float(params.get('ema_margin_pips', 0.0)),
                    min_value=0.0, step=1.0, key=f"{sk}_emam",
                    help="SELL: L2 phải cách EMA ≥ N pips | BUY: H2 phải cách EMA ≥ N pips")
                st.caption(_pip_caption(ema_margin_pips, symbol))
        else:
            ema_period = None
            h2_exceed_pips = 0.0
            c2_gap_pips = 0.0
            ema_margin_pips = 0.0

        st.divider()
        st.subheader("Entry Time Window")
        tw1, tw2 = st.columns(2)
        with tw1:
            entry_start_time = st.time_input("Entry Start Time (HCM)", value=time(0, 0),
                                             key=f"{sk}_tw_start")
        with tw2:
            entry_end_time = st.time_input("Entry End Time (HCM)", value=time(23, 59),
                                           key=f"{sk}_tw_end")
        st.caption("Active trade continues if time window ends. Window only gates new entries.")

        st.divider()
        st.subheader("Entry")
        ecol1, ecol2 = st.columns(2)
        with ecol1:
            entry_mode = st.radio("Entry Mode", options=["close", "range_percent"],
                                  index=0 if params.get('entry_mode', 'close') == 'close' else 1,
                                  format_func=lambda x: "Close Price" if x == "close" else "Body Percent (%)",
                                  horizontal=True, key=f"{sk}_entry_mode")
        with ecol2:
            if entry_mode == "range_percent":
                entry_percent = st.number_input("Entry Percent (%)",
                                                value=float(params.get('entry_percent', 10.0) or 10.0),
                                                min_value=0.0, max_value=100.0, step=5.0,
                                                key=f"{sk}_entry_pct")
            else:
                entry_percent = 0.0

        st.divider()
        st.subheader("Exit Types")
        xcol1, xcol2 = st.columns(2)
        with xcol1:
            tp_type = st.radio("Take Profit (TP) Exit", options=["price_based", "close_based"],
                               index=0 if params.get('tp_type', 'price_based') == 'price_based' else 1,
                               format_func=lambda x: "Price-based (Immediate)" if x == "price_based" else "Close-based (Delayed)",
                               horizontal=True, key=f"{sk}_tp_type")
        with xcol2:
            sl_type = st.radio("Stop Loss (SL) Exit", options=["price_based", "close_based"],
                               index=0 if params.get('sl_type', 'price_based') == 'price_based' else 1,
                               format_func=lambda x: "Price-based (Immediate)" if x == "price_based" else "Close-based (Delayed)",
                               horizontal=True, key=f"{sk}_sl_type")

        st.divider()
        st.subheader("Lot Size")
        lot_mode = st.radio("Lot Size Mode", options=["fixed", "flex"],
                            format_func=lambda x: "Fixed" if x == "fixed" else "Flex (Risk-based)",
                            horizontal=True, key=f"{sk}_lot_mode")
        lc1, lc2 = st.columns(2)
        with lc1:
            buffer_k = st.number_input("Buffer K (pips)", value=float(params.get('buffer_k', 5)),
                                       min_value=0.0, max_value=200.0, step=1.0, key=f"{sk}_buffer_k")
        if lot_mode == "fixed":
            with lc2:
                lot_size = st.number_input("Lot Size", value=float(params.get('lot_size', 0.01)),
                                           min_value=0.01, max_value=10.0, step=0.01, format="%.2f",
                                           key=f"{sk}_lot")
            risk_mode = "percent"
            risk_percent = 0.5
            risk_amount = 0.0
        else:
            lc1b, lc2b, _ = st.columns(3)
            with lc1b:
                risk_mode = st.radio("Risk Mode", options=["percent", "fixed_amount"],
                                     format_func=lambda x: "Percentage (%)" if x == "percent" else "Fixed Amount ($)",
                                     horizontal=True, key=f"{sk}_risk_mode")
            with lc2b:
                if risk_mode == "percent":
                    risk_percent = st.number_input("Risk per Trade (%)", value=0.5,
                                                   min_value=0.1, max_value=5.0, step=0.1, format="%.1f",
                                                   key=f"{sk}_risk_pct")
                    risk_amount = 0.0
                else:
                    risk_amount = st.number_input("Risk per Trade ($)", value=5.0,
                                                  min_value=1.0, max_value=1000.0, step=1.0, format="%.2f",
                                                  key=f"{sk}_risk_amt")
                    risk_percent = 0.0
            lot_size = 0.01

        st.divider()

    # sl_pips not used for pattern strategies (SL from candle + buffer_k)
    sl_pips = None if is_pattern else int(params.get('sl_pips', 30))

    if st.button("Start Bot", type="primary", use_container_width=True):
        if not symbol:
            st.error("Symbol is required")
        else:
            success, msg, bot_info = start_bot(
                strategy=selected_strategy,
                symbol=symbol,
                user=username,
                test=test_mode,
                lot_size=lot_size if lot_mode == "fixed" else None,
                sl_pips=sl_pips,
                rr_ratio=rr_ratio,
                max_candles=max_candles,
                interval=interval,
                ema_period=ema_period,
                h2_exceed_pips=h2_exceed_pips,
                c2_gap_pips=c2_gap_pips,
                ema_margin_pips=ema_margin_pips,
                entry_mode=entry_mode,
                entry_percent=entry_percent if entry_mode == "range_percent" else None,
                tp_type=tp_type,
                sl_type=sl_type,
                buffer_k=buffer_k,
                lot_mode=lot_mode,
                risk_mode=risk_mode if lot_mode == "flex" else None,
                risk_percent=risk_percent if lot_mode == "flex" else None,
                risk_amount=risk_amount if lot_mode == "flex" else None,
                entry_start_time=entry_start_time.strftime('%H:%M'),
                entry_end_time=entry_end_time.strftime('%H:%M'),
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
