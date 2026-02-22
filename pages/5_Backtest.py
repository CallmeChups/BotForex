"""
Backtest Page - Test strategy on historical data
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import os

load_dotenv()

st.set_page_config(
    page_icon="🔬",
    page_title="Backtest",
    layout="wide",
)

# Auth check
from src.auth import require_auth, get_user_mt5_credentials, has_mt5_credentials
username, name = require_auth()

from src.backtest import fetch_historical_data, run_backtest
from src.utils import is_mt5_available
from src.strategy_manager import list_strategies, get_strategy_parameters
from src.backtest_history import (
    save_backtest_result,
    get_history,
    delete_history_record,
    history_to_dataframe,
    create_excel_export,
    HISTORY_COLUMNS
)

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def main():
    st.title("Backtest Strategy")

    now = datetime.now(TIMEZONE)
    st.markdown(f"**Current Time:** {now.strftime('%H:%M:%S %d/%m/%Y')} (HCM)")

    st.divider()

    # Check MT5 availability
    if not is_mt5_available():
        st.error("MT5 not available (Windows only). Backtest requires MT5 for historical data.")
        show_demo_results()
        return

    # Check if user has MT5 credentials
    if not has_mt5_credentials(username):
        st.warning("MT5 account not configured. Please go to Settings to add your MT5 credentials.")
        st.page_link("pages/8_Settings.py", label="Go to Settings", icon="⚙️")
        show_demo_results()
        return

    # Get user credentials
    user_creds = get_user_mt5_credentials(username)

    # Get available strategies
    strategies = list_strategies()
    enabled_strategies = [s for s in strategies if s.get('enabled', True)]

    if not enabled_strategies:
        st.warning("No strategies available. Create one in the Strategies page.")
        st.page_link("pages/4_Strategies.py", label="Go to Strategies", icon="📖")
        show_demo_results()
        return

    # Strategy selection
    strategy_options = {s['name']: s['id'] for s in enabled_strategies}
    selected_strategy_name = st.selectbox(
        "Strategy",
        options=list(strategy_options.keys())
    )
    selected_strategy = strategy_options[selected_strategy_name]
    params = get_strategy_parameters(selected_strategy)

    st.divider()

    # ── SECTION 1: Market ──
    st.subheader("Market")
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        # Symbol
        strategy_symbols = params.get('symbols', [])
        use_custom_symbol = st.checkbox("Custom symbol", value=False, key="bt_custom_symbol")

        if use_custom_symbol:
            symbol = st.text_input("Symbol", value=os.getenv("SYMBOL", "XAUUSD"), help="Enter any symbol")
        elif strategy_symbols:
            symbol = st.selectbox("Symbol", options=strategy_symbols)
        else:
            symbol = st.text_input("Symbol", value=os.getenv("SYMBOL", "XAUUSD"))

        # Show symbol info inline
        from src.utils import get_pip_value, get_pip_value_per_lot, get_contract_size
        pv = get_pip_value(symbol)
        pvl = get_pip_value_per_lot(symbol)
        cs = get_contract_size(symbol)
        st.caption(f"pip={pv} | $/pip/lot=${pvl:.2f} | contract={cs:,.0f}")

    with col2:
        # Timeframe
        strategy_timeframe = params.get('timeframe', 'M5')
        timeframe_options = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
        tf_index = timeframe_options.index(strategy_timeframe) if strategy_timeframe in timeframe_options else 1
        timeframe = st.selectbox("Timeframe", options=timeframe_options, index=tf_index)

    with col3:
        # Entry time
        entry_time_str = params.get('entry_time', '21:05')
        use_custom_time = st.checkbox("Custom time", value=False, key="bt_custom_time")

        if use_custom_time:
            custom_time_str = st.text_input("Entry Time", value="21:05", max_chars=5, placeholder="HH:MM")
            try:
                entry_times = [datetime.strptime(custom_time_str, "%H:%M").time()]
            except ValueError:
                st.error("Invalid format. Use HH:MM")
                entry_times = [datetime.strptime("21:05", "%H:%M").time()]
        else:
            entry_times = [datetime.strptime(entry_time_str, "%H:%M").time()]
            st.text_input("Entry Time", value=entry_time_str, disabled=True)

    # Date range
    col1, col2 = st.columns(2)
    default_end = now.date()
    default_start = default_end - timedelta(days=30)

    with col1:
        start_date = st.date_input("Start Date", value=default_start, max_value=default_end)
    with col2:
        end_date = st.date_input("End Date", value=default_end, max_value=default_end)

    # Batch entry times (expandable)
    with st.expander("Batch Entry Times"):
        custom_times_str = st.text_input(
            "Entry Times", value="21:05, 22:00, 23:00",
            help="Comma-separated HH:MM", placeholder="HH:MM, HH:MM, ..."
        )
        use_batch = st.checkbox("Enable batch mode", value=False, key="bt_batch")
        if use_batch:
            entry_times = []
            for t in custom_times_str.split(','):
                t = t.strip()
                try:
                    entry_times.append(datetime.strptime(t, "%H:%M").time())
                except ValueError:
                    pass
            if not entry_times:
                st.error("No valid times.")
                entry_times = [datetime.strptime("21:05", "%H:%M").time()]
            st.caption(f"Will backtest {len(entry_times)} entry time(s)")

    st.divider()

    # ── SECTION 2: Trade Setup ──
    st.subheader("Trade Setup")
    col1, col2, col3 = st.columns(3)

    with col1:
        entry_mode = st.radio(
            "Entry Mode",
            options=["close", "range_percent"],
            format_func=lambda x: "Close Price" if x == "close" else "Range Percent",
            horizontal=True,
            help="Close: enter at candle close | Range %: enter at % retracement"
        )

    with col2:
        rr_ratio = st.number_input(
            "RR Ratio", value=float(params.get('rr_ratio', 2.0)),
            min_value=0.5, max_value=10.0, step=0.5
        )

    with col3:
        buffer_k = st.number_input(
            "Buffer K (points)", value=5.0,
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
            entry_percent = st.number_input(
                "Entry Percent (%)", value=30.0,
                min_value=0.0, max_value=100.0, step=5.0,
                help="BUY: Close - X%(body) | SELL: Close + X%(body)"
            )
        with col2:
            pending_order_max_candles = st.number_input(
                "Max Wait (candles)", value=3,
                min_value=1, max_value=10, step=1,
                help="MISSED if not filled after N candles"
            )
    else:
        entry_percent = 0.0
        pending_order_max_candles = 0

    # ── SECTION 3: Exit Rules (collapsible) ──
    with st.expander("Exit Rules", expanded=False):
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            tp_type = st.radio(
                "TP Type",
                options=["price_based", "close_based"],
                format_func=lambda x: "Price (wick)" if x == "price_based" else "Close (candle)",
                help="Price: exit when wick touches TP | Close: exit when candle closes beyond TP"
            )

        with col2:
            sl_type = st.radio(
                "SL Type",
                options=["close_based", "price_based"],
                format_func=lambda x: "Close (candle)" if x == "close_based" else "Price (wick)",
                help="Close: exit when candle closes beyond SL | Price: exit when wick touches SL"
            )

        with col3:
            use_max_candles = st.checkbox("Max Candles", value=True, key="bt_max_c")
            if use_max_candles:
                max_candles = st.number_input(
                    "Limit", value=int(params.get('max_candles', 7)),
                    min_value=1, max_value=50,
                    help="Force close after N candles"
                )
            else:
                max_candles = 0

        with col4:
            move_sl_to_breakeven = st.checkbox("Breakeven", value=False, key="bt_be",
                                               help="Move SL to entry when TP partially reached")
            if move_sl_to_breakeven:
                breakeven_trigger_percent = st.number_input(
                    "Trigger (%)", value=50.0,
                    min_value=10.0, max_value=90.0, step=5.0,
                    help="Move SL to entry at this % of TP"
                )
            else:
                breakeven_trigger_percent = 50.0

    # ── SECTION 4: Position Sizing (collapsible) ──
    with st.expander("Position Sizing", expanded=False):
        lot_mode = st.radio(
            "Mode",
            options=["fixed", "flex"],
            format_func=lambda x: "Fixed Lot" if x == "fixed" else "Flex (Risk-based)",
            horizontal=True
        )

        if lot_mode == "fixed":
            fixed_lot = st.number_input(
                "Lot Size", value=float(params.get('lot_size', 0.01)),
                min_value=0.01, max_value=10.0, step=0.01, format="%.2f"
            )
            risk_percent = 0.5
            risk_amount = 0.0
            risk_mode = "percent"
            risk_compounding = True
            starting_equity = 1000.0
        else:
            col1, col2, col3 = st.columns(3)

            with col1:
                starting_equity = st.number_input(
                    "Starting Equity ($)", value=1000.0,
                    min_value=100.0, max_value=1000000.0, step=100.0
                )

            with col2:
                risk_mode = st.radio(
                    "Risk Mode",
                    options=["percent", "fixed_amount"],
                    format_func=lambda x: "Percentage (%)" if x == "percent" else "Fixed Amount ($)",
                    horizontal=True
                )

            with col3:
                if risk_mode == "percent":
                    risk_percent = st.number_input(
                        "Risk/Trade (%)", value=0.5,
                        min_value=0.1, max_value=5.0, step=0.1, format="%.1f"
                    )
                    risk_amount = 0.0
                else:
                    risk_amount = st.number_input(
                        "Risk/Trade ($)", value=5.0,
                        min_value=1.0, max_value=1000.0, step=1.0, format="%.2f"
                    )
                    risk_percent = 0.0

            if risk_mode == "percent":
                risk_compounding = st.checkbox("Compounding", value=True,
                                               help="ON: risk % based on current equity | OFF: based on starting equity")
            else:
                risk_compounding = True

            fixed_lot = 0.01

    sl_pips = 0

    # ── SUMMARY ──
    is_batch = len(entry_times) > 1
    entry_label = f"Range {entry_percent}%" if entry_mode == "range_percent" else "Close"
    lot_label = f"{fixed_lot} lot" if lot_mode == "fixed" else f"Flex {risk_percent}%" if risk_mode == "percent" else f"Flex ${risk_amount}"
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
                st.metric("Entry Time", entry_times[0].strftime('%H:%M'))
        with col4:
            st.metric("RR Ratio", f"1:{rr_ratio}")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Entry Mode", entry_label)
        with col2:
            st.metric("TP / SL", f"{tp_label} / {sl_label}")
        with col3:
            st.metric("Date Range", f"{start_date} ~ {end_date}")
        with col4:
            if lot_mode == "fixed":
                pip_cost = fixed_lot * pvl
                st.metric("Lot / Risk per Pip", f"{fixed_lot} / ${pip_cost:.2f}")
            else:
                if risk_mode == "percent":
                    max_loss = starting_equity * risk_percent / 100
                    st.metric("Max Loss / Trade", f"${max_loss:.2f}")
                else:
                    st.metric("Max Loss / Trade", f"${risk_amount:.2f}")

    # Run backtest button
    button_label = f"Run Batch Backtest ({len(entry_times)} entry times)" if is_batch else "Run Backtest"

    if st.button(button_label, type="primary", width='stretch'):
        # Convert dates to datetime
        start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=TIMEZONE)
        end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=TIMEZONE)

        # Fetch data once (same timeframe for all entry times)
        with st.spinner("Fetching historical data..."):
            df, error = fetch_historical_data(symbol, start_dt, end_dt, user_creds, timeframe)

            if error:
                st.error(f"Failed to fetch data: {error}")
                st.stop()

            if df is None or df.empty:
                st.warning("No data found for the selected period")
                st.stop()

            st.success(f"Fetched {len(df)} candles")

        batch_results = []
        progress_bar = st.progress(0, text="Starting backtest...")

        for idx, entry_time in enumerate(entry_times):
            time_str = entry_time.strftime('%H:%M')
            progress_text = f"Running {time_str}... ({idx + 1}/{len(entry_times)})"
            progress_bar.progress((idx) / len(entry_times), text=progress_text)

            # Run backtest for this entry time
            results = run_backtest(
                df=df,
                symbol=symbol,
                entry_hour=entry_time.hour,
                entry_minute=entry_time.minute,
                sl_pips=sl_pips,
                rr_ratio=rr_ratio,
                max_candles=max_candles,
                lot_mode=lot_mode,
                fixed_lot=fixed_lot,
                risk_percent=risk_percent,
                risk_amount=risk_amount,
                risk_mode=risk_mode,
                risk_compounding=risk_compounding,
                buffer_k=buffer_k,
                starting_equity=starting_equity,
                tp_type=tp_type,
                sl_type=sl_type,
                entry_mode=entry_mode,
                entry_percent=entry_percent,
                move_sl_to_breakeven=move_sl_to_breakeven,
                breakeven_trigger_percent=breakeven_trigger_percent,
                pending_order_max_candles=pending_order_max_candles if entry_mode == "range_percent" else 0
            )

            # Build config dict for export/history
            backtest_config = {
                'timeframe': timeframe,
                'start_date': str(start_date),
                'end_date': str(end_date),
                'entry_time': time_str,
                'entry_mode': entry_mode,
                'entry_percent': entry_percent,
                'rr_ratio': rr_ratio,
                'max_candles': max_candles,
                'buffer_k': buffer_k,
                'lot_mode': lot_mode,
                'tp_type': tp_type,
                'sl_type': sl_type,
                'move_sl_to_breakeven': move_sl_to_breakeven,
                'breakeven_trigger_percent': breakeven_trigger_percent,
                'pending_order_max_candles': pending_order_max_candles if entry_mode == "range_percent" else 0,
            }

            if lot_mode == 'fixed':
                backtest_config['fixed_lot'] = fixed_lot
            else:
                backtest_config['starting_equity'] = starting_equity
                backtest_config['risk_mode'] = risk_mode
                backtest_config['risk_percent'] = risk_percent
                backtest_config['risk_amount'] = risk_amount
                backtest_config['risk_compounding'] = risk_compounding

            # Auto-save to history
            if results.get('total_trades', 0) > 0:
                save_backtest_result(
                    config=backtest_config,
                    results=results,
                    strategy_name=selected_strategy_name,
                    symbol=symbol,
                    username=username
                )

            batch_results.append({
                'entry_time': time_str,
                'results': results,
                'config': backtest_config
            })

        progress_bar.progress(1.0, text="Complete!")

        # Store results in session state
        if batch_results:
            # Use the last result for detailed display
            last_result = batch_results[-1]
            st.session_state['backtest_results'] = last_result['results']
            st.session_state['backtest_symbol'] = symbol
            st.session_state['backtest_strategy'] = selected_strategy_name
            st.session_state['backtest_lot_mode'] = lot_mode
            st.session_state['backtest_timeframe'] = timeframe
            st.session_state['backtest_entry_time'] = last_result['entry_time']
            st.session_state['backtest_tp_type'] = tp_type
            st.session_state['backtest_sl_type'] = sl_type
            st.session_state['backtest_config'] = last_result['config']
            st.session_state['backtest_batch_results'] = batch_results

            if is_batch:
                st.success(f"Completed {len(batch_results)} backtests. Results saved to history.")

    # Display batch summary if multiple entry times were run
    if 'backtest_batch_results' in st.session_state and len(st.session_state['backtest_batch_results']) > 1:
        show_batch_summary(
            st.session_state['backtest_batch_results'],
            st.session_state.get('backtest_strategy', ''),
            st.session_state.get('backtest_symbol', ''),
            st.session_state.get('backtest_lot_mode', 'fixed')
        )

    # Display detailed results for selected timeframe
    if 'backtest_results' in st.session_state:
        display_results(
            st.session_state['backtest_results'],
            st.session_state.get('backtest_symbol', ''),
            st.session_state.get('backtest_strategy', ''),
            st.session_state.get('backtest_lot_mode', 'fixed'),
            st.session_state.get('backtest_timeframe', 'M5'),
            st.session_state.get('backtest_tp_type', 'price_based'),
            st.session_state.get('backtest_sl_type', 'close_based'),
            st.session_state.get('backtest_config', {})
        )

    # Show history section
    show_history_section(username)


def show_batch_summary(batch_results: list, strategy_name: str, symbol: str, lot_mode: str):
    """Show summary comparison of batch backtest results"""

    st.divider()
    st.subheader(f"Batch Results: {strategy_name}" if strategy_name else "Batch Results")
    st.caption(f"Comparing {len(batch_results)} entry times for {symbol}")

    # Build comparison table
    rows = []
    for br in batch_results:
        et = br['entry_time']
        r = br['results']
        rows.append({
            'Entry Time': et,
            'Trades': r.get('total_trades', 0),
            'Wins': r.get('wins', 0),
            'Losses': r.get('losses', 0),
            'Win Rate %': r.get('win_rate', 0),
            'P/F': r.get('profit_factor', 0),
            'Total Pips': r.get('total_pnl', 0),
            'Avg Pips': r.get('avg_pnl', 0),
            'Best': r.get('best_trade', 0),
            'Worst': r.get('worst_trade', 0),
        })

        if lot_mode == 'flex':
            rows[-1]['Total USD'] = r.get('total_pnl_usd', 0)
            rows[-1]['Final Equity'] = r.get('final_equity', 0)

    batch_df = pd.DataFrame(rows)

    # Color functions
    def color_positive(val):
        if isinstance(val, (int, float)):
            if val > 0:
                return 'color: green'
            elif val < 0:
                return 'color: red'
        return ''

    def color_win_rate(val):
        if isinstance(val, (int, float)):
            if val >= 60:
                return 'color: green; font-weight: bold'
            elif val < 50:
                return 'color: red'
        return ''

    styled_batch = batch_df.style
    styled_batch = styled_batch.map(color_win_rate, subset=['Win Rate %'])
    styled_batch = styled_batch.map(color_positive, subset=['Total Pips', 'Avg Pips'])
    if 'Total USD' in batch_df.columns:
        styled_batch = styled_batch.map(color_positive, subset=['Total USD'])

    st.dataframe(styled_batch, width='stretch', hide_index=True)

    # Find best performer
    if not batch_df.empty:
        best_idx = batch_df['Win Rate %'].idxmax()
        best_et = batch_df.loc[best_idx, 'Entry Time']
        best_wr = batch_df.loc[best_idx, 'Win Rate %']
        best_pips = batch_df.loc[best_idx, 'Total Pips']
        st.info(f"Best performer: **{best_et}** with {best_wr}% win rate and {best_pips} pips")

    # Selector for detailed view
    st.markdown("---")
    selected_et = st.selectbox(
        "View detailed results for:",
        options=[br['entry_time'] for br in batch_results],
        key="batch_detail_select"
    )

    # Update session state with selected entry time's results
    for br in batch_results:
        if br['entry_time'] == selected_et:
            st.session_state['backtest_results'] = br['results']
            st.session_state['backtest_entry_time'] = br['entry_time']
            st.session_state['backtest_config'] = br['config']
            break


def display_results(results: dict, symbol: str, strategy_name: str = "", lot_mode: str = "fixed", timeframe: str = "M5", tp_type: str = "price_based", sl_type: str = "close_based", config: dict = None):
    """Display backtest results"""
    config = config or {}

    st.divider()
    st.subheader(f"Results: {strategy_name} ({timeframe})" if strategy_name else f"Results ({timeframe})")

    if results['total_trades'] == 0:
        st.warning("No trades found in the selected period")
        return

    # Show config summary
    mode_label = "Fixed Lot" if lot_mode == "fixed" else "Flex (Risk-based)"
    tp_label = "Price-based" if tp_type == "price_based" else "Close-based"
    sl_label = "Close-based" if sl_type == "close_based" else "Price-based"
    st.caption(f"Lot: **{mode_label}** | TP: **{tp_label}** | SL: **{sl_label}**")

    # Summary stats
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Trades", results['total_trades'])
        st.metric("Wins", results['wins'])
        st.metric("Losses", results['losses'])

    with col2:
        st.metric("Win Rate", f"{results['win_rate']}%")
        st.metric("Profit Factor", results['profit_factor'])
        # Show SL Moved count if feature was enabled
        if config.get('move_sl_to_breakeven', False):
            sl_moved_count = sum(1 for t in results.get('trades', []) if t.get('sl_moved_to_breakeven', False))
            st.metric("SL Moved to BE", f"{sl_moved_count}/{results['total_trades']}")

        # Show MISSED trades count if pending order mode
        if config.get('entry_mode') == 'range_percent' and config.get('pending_order_max_candles', 0) > 0:
            missed_count = sum(1 for t in results.get('trades', []) if t.get('status') == 'MISSED')
            total_signals = len(results.get('trades', []))
            filled_count = total_signals - missed_count
            st.metric("Trades Filled", f"{filled_count}/{total_signals}")
            if missed_count > 0:
                st.caption(f"⚠️ {missed_count} trades MISSED (pending order not filled)")

    with col3:
        pnl_delta = "profit" if results['total_pnl'] > 0 else "loss" if results['total_pnl'] < 0 else None
        st.metric("Total P&L", f"{results['total_pnl']} pips", delta=pnl_delta)
        usd_delta = "profit" if results.get('total_pnl_usd', 0) > 0 else "loss" if results.get('total_pnl_usd', 0) < 0 else None
        st.metric("Total P&L (USD)", f"${results.get('total_pnl_usd', 0):.2f}", delta=usd_delta)

    with col4:
        st.metric("Best Trade", f"{results['best_trade']} pips")
        st.metric("Worst Trade", f"{results['worst_trade']} pips")
        st.metric("Avg P&L", f"{results['avg_pnl']} pips")
        if lot_mode == "flex":
            final_eq = results.get('final_equity', 0)
            start_eq = results.get('starting_equity', 1000)
            roi = ((final_eq - start_eq) / start_eq * 100) if start_eq > 0 else 0
            st.metric("Final Equity", f"${final_eq:.2f}", delta=f"{roi:+.1f}%")

    st.divider()

    # Additional stats
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Consecutive Streaks**")
        st.caption(f"Max Wins: {results['max_consecutive_wins']}")
        st.caption(f"Max Losses: {results['max_consecutive_losses']}")

    with col2:
        st.markdown("**Exit Types**")
        st.caption(f"TP: {results['tp_exits']}")
        st.caption(f"SL: {results['sl_exits']}")
        st.caption(f"TIME: {results['time_exits']}")

    with col3:
        st.markdown("**Details**")
        st.caption(f"Symbol: {symbol}")
        st.caption(f"Timeframe: {timeframe}")
        if strategy_name:
            st.caption(f"Strategy: {strategy_name}")

    st.divider()

    # Equity curve (optional, default hidden)
    show_equity_curve = st.checkbox("Show Equity Curve", value=False, key="show_equity_curve")

    if show_equity_curve:
        st.subheader("Equity Curve")

        if lot_mode == "flex":
            # Show USD equity curve for flex mode
            equity_data = results.get('equity_curve_usd', [])
            if equity_data:
                chart_df = pd.DataFrame({
                    'Trade': range(len(equity_data)),
                    'Equity (USD)': equity_data
                })

                st.line_chart(
                    chart_df,
                    x='Trade',
                    y='Equity (USD)',
                    width='stretch'
                )
        else:
            # Show pips curve for fixed mode
            equity_data = results.get('equity_curve', [])
            if equity_data:
                chart_df = pd.DataFrame({
                    'Trade': range(len(equity_data)),
                    'Cumulative P&L (pips)': equity_data
                })

                st.line_chart(
                    chart_df,
                    x='Trade',
                    y='Cumulative P&L (pips)',
                    width='stretch'
                )

    st.divider()

    # Trade list with view toggle
    st.subheader("Trade Analysis")

    trades = results.get('trades', [])
    ohlc_data = results.get('ohlc_data', None)

    if trades:
        # View toggle
        view_mode = st.radio(
            "View Mode",
            options=["Table", "Interactive Chart"],
            horizontal=True,
            key="trade_view_mode"
        )

        if view_mode == "Table":
            show_trade_table(trades, lot_mode, strategy_name, symbol, config, results)
        else:
            show_interactive_chart(trades, ohlc_data, symbol)


def show_trade_table(trades: list, lot_mode: str, strategy_name: str, symbol: str, config: dict = None, results: dict = None):
    """Show trades as a table"""
    config = config or {}
    results = results or {}
    trades_df = pd.DataFrame(trades)

    # Add SL Moved indicator column
    if 'sl_moved_to_breakeven' in trades_df.columns:
        trades_df['SL Moved'] = trades_df['sl_moved_to_breakeven'].apply(lambda x: '✓ BE' if x else '')

    # Add Status indicator column for missed trades
    if 'status' in trades_df.columns:
        trades_df['Status'] = trades_df.apply(
            lambda row: f"⚠️ MISSED ({row.get('miss_reason', 'N/A')})" if row.get('status') == 'MISSED' else '',
            axis=1
        )

    # Rename columns for display
    rename_cols = {
        'date': 'Date',
        'time': 'Time',
        'direction': 'Direction',
        'entry': 'Entry',
        'sl': 'SL',
        'tp': 'TP',
        'sl_pips': 'SL Pips',
        'lot': 'Lot',
        'exit_type': 'Exit',
        'exit_price': 'Exit Price',
        'candles': 'Candles',
        'pnl_pips': 'P&L (pips)',
        'pnl_usd': 'P&L (USD)'
    }
    trades_df = trades_df.rename(columns=rename_cols)

    # Drop internal columns
    internal_cols = ['exit_time', 'sl_moved_to_breakeven', 'final_sl', 'status', 'miss_reason']
    for col in internal_cols:
        if col in trades_df.columns:
            trades_df = trades_df.drop(columns=[col])

    # Select columns based on lot mode
    if lot_mode == "fixed":
        # Hide flex-specific columns (keep P&L USD for all modes)
        cols_to_drop = ['SL Pips', 'Lot']
        for col in cols_to_drop:
            if col in trades_df.columns:
                trades_df = trades_df.drop(columns=[col])

    # Color P&L columns
    def color_pnl(val):
        if val > 0:
            return 'color: green'
        elif val < 0:
            return 'color: red'
        return ''

    pnl_cols = ['P&L (pips)']
    if 'P&L (USD)' in trades_df.columns:
        pnl_cols.append('P&L (USD)')
    styled_df = trades_df.style.map(color_pnl, subset=pnl_cols)
    st.dataframe(styled_df, width='stretch', hide_index=True)

    # Download buttons (include username to avoid conflicts)
    filename_parts = [username, strategy_name.replace(' ', '_')] if strategy_name else [username]
    filename_parts.extend([symbol, datetime.now().strftime('%Y%m%d')])
    base_filename = f"backtest_{'_'.join(filename_parts)}"

    col1, col2 = st.columns(2)

    with col1:
        # CSV download (trades only)
        csv = trades_df.to_csv(index=False)
        st.download_button(
            label="Download CSV (Trades)",
            data=csv,
            file_name=f"{base_filename}.csv",
            mime="text/csv"
        )

    with col2:
        # Excel download (Config + Summary + Trades)
        excel_buffer = create_excel_export(
            config=config,
            results=results,
            trades_df=trades_df,
            strategy_name=strategy_name,
            symbol=symbol
        )
        st.download_button(
            label="Download Excel (Full Report)",
            data=excel_buffer,
            file_name=f"{base_filename}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


def show_interactive_chart(trades: list, ohlc_data: pd.DataFrame, symbol: str):
    """Show interactive candlestick chart with trade markers"""

    if ohlc_data is None or ohlc_data.empty:
        st.warning("No OHLC data available for chart")
        return

    # Trade selector
    trade_options = [f"Trade {i+1}: {t['date']} {t['time']} - {t['direction']} ({t['exit_type']})" for i, t in enumerate(trades)]
    selected_idx = st.selectbox(
        "Select Trade to View",
        options=range(len(trades)),
        format_func=lambda x: trade_options[x]
    )

    trade = trades[selected_idx]

    # Parse trade datetime
    trade_datetime_str = f"{trade['date']} {trade['time']}"
    trade_dt = datetime.strptime(trade_datetime_str, "%Y-%m-%d %H:%M")

    # Filter OHLC data around the trade (30 candles before and after)
    ohlc_data['time_naive'] = ohlc_data['time'].dt.tz_localize(None) if ohlc_data['time'].dt.tz is not None else ohlc_data['time']

    # Find the entry candle index
    entry_mask = ohlc_data['time_naive'] == trade_dt
    if not entry_mask.any():
        # Try to find closest candle
        time_diffs = abs(ohlc_data['time_naive'] - trade_dt)
        entry_idx = time_diffs.idxmin()
    else:
        entry_idx = ohlc_data[entry_mask].index[0]

    # Get data range (30 candles before, candles + 10 after)
    start_idx = max(0, entry_idx - 30)
    candles_count = trade.get('candles', 10)  # Default 10 candles for missed trades
    end_idx = min(len(ohlc_data), entry_idx + candles_count + 15)
    chart_data = ohlc_data.iloc[start_idx:end_idx].copy()

    # Create candlestick chart
    fig = make_subplots(rows=1, cols=1)

    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=chart_data['time'],
            open=chart_data['open'],
            high=chart_data['high'],
            low=chart_data['low'],
            close=chart_data['close'],
            name='Price',
            increasing_line_color='green',
            decreasing_line_color='red'
        )
    )

    # Get time range for horizontal lines
    x_min = chart_data['time'].iloc[0]
    x_max = chart_data['time'].iloc[-1]

    # Entry marker
    entry_time = ohlc_data.iloc[entry_idx]['time']
    entry_price = trade['entry']

    fig.add_trace(
        go.Scatter(
            x=[entry_time],
            y=[entry_price],
            mode='markers',
            marker=dict(
                symbol='triangle-up' if trade['direction'] == 'BUY' else 'triangle-down',
                size=15,
                color='blue',
                line=dict(width=2, color='darkblue')
            ),
            name=f"Entry ({trade['direction']})",
            legendgroup="entry"
        )
    )

    # Entry price line (toggleable)
    fig.add_trace(
        go.Scatter(
            x=[x_min, x_max],
            y=[entry_price, entry_price],
            mode='lines',
            line=dict(color='blue', width=1, dash='dot'),
            name=f"Entry Line ({entry_price:.2f})",
            legendgroup="entry_line"
        )
    )

    # SL line (toggleable)
    sl_price = trade['sl']
    fig.add_trace(
        go.Scatter(
            x=[x_min, x_max],
            y=[sl_price, sl_price],
            mode='lines',
            line=dict(color='red', width=2, dash='dash'),
            name=f"SL ({sl_price:.2f})",
            legendgroup="sl"
        )
    )

    # TP line (toggleable)
    tp_price = trade['tp']
    fig.add_trace(
        go.Scatter(
            x=[x_min, x_max],
            y=[tp_price, tp_price],
            mode='lines',
            line=dict(color='green', width=2, dash='dash'),
            name=f"TP ({tp_price:.2f})",
            legendgroup="tp"
        )
    )

    # Exit marker (skip for MISSED trades with no exit_price)
    exit_price = trade.get('exit_price')
    if exit_price is not None:
        exit_candle_idx = entry_idx + candles_count
        if exit_candle_idx < len(ohlc_data):
            exit_time = ohlc_data.iloc[exit_candle_idx]['time']
        else:
            exit_time = chart_data['time'].iloc[-1]

        exit_color = 'green' if trade['exit_type'] == 'TP' else 'red' if trade['exit_type'] == 'SL' else 'orange'

        fig.add_trace(
            go.Scatter(
                x=[exit_time],
                y=[exit_price],
                mode='markers',
                marker=dict(
                    symbol='x',
                    size=15,
                    color=exit_color,
                    line=dict(width=2, color='black')
                ),
                name=f"Exit ({trade['exit_type']})",
                legendgroup="exit"
            )
        )

    # Layout
    fig.update_layout(
        title=f"Trade {selected_idx + 1}: {trade['direction']} {symbol} - {trade['exit_type']} ({trade['pnl_pips']:+.1f} pips)",
        xaxis_title="Time",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        height=600,
        showlegend=True,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01
        )
    )

    st.plotly_chart(fig, use_container_width=True)

    # Download button for interactive chart
    chart_html = fig.to_html(include_plotlyjs='cdn', full_html=True)
    chart_filename = f"trade_{selected_idx + 1}_{trade['date']}_{symbol}_{trade['direction']}.html"
    st.download_button(
        label="Download Interactive Chart (HTML)",
        data=chart_html,
        file_name=chart_filename,
        mime="text/html",
        help="Download as HTML file - opens in browser with full interactivity"
    )

    # Trade details
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Direction", trade['direction'])
        st.metric("Entry", f"{trade['entry']:.2f}")
    with col2:
        st.metric("SL", f"{trade['sl']:.2f}")
        st.metric("TP", f"{trade['tp']:.2f}")
    with col3:
        st.metric("Exit Type", trade['exit_type'])
        exit_price_display = f"{trade['exit_price']:.2f}" if trade.get('exit_price') else "N/A"
        st.metric("Exit Price", exit_price_display)
    with col4:
        pnl_color = "green" if trade['pnl_pips'] > 0 else "red"
        st.metric("P&L", f"{trade['pnl_pips']:+.1f} pips")
        st.metric("Candles Held", trade.get('candles', 'N/A'))


def show_demo_results():
    """Show demo results when MT5 not available"""

    st.divider()
    st.subheader("Demo Results")

    st.info("This is demo data. Connect to MT5 on Windows to run real backtest.")

    # Demo stats
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Trades", 20)
        st.metric("Wins", 12)
        st.metric("Losses", 8)

    with col2:
        st.metric("Win Rate", "60%")
        st.metric("Profit Factor", 1.85)

    with col3:
        st.metric("Total P&L", "185.5 pips", delta="profit")
        st.metric("Avg P&L", "9.3 pips")

    with col4:
        st.metric("Best Trade", "62.0 pips")
        st.metric("Worst Trade", "-31.5 pips")

    st.divider()

    # Demo equity curve
    st.subheader("Equity Curve (Demo)")

    demo_equity = [0, 15, 30, 18, 45, 60, 48, 75, 90, 78, 95, 110, 125, 108, 135, 150, 165, 148, 175, 185]
    chart_df = pd.DataFrame({
        'Trade': range(len(demo_equity)),
        'Cumulative P&L (pips)': demo_equity
    })

    st.line_chart(
        chart_df,
        x='Trade',
        y='Cumulative P&L (pips)',
        width='stretch'
    )


def show_history_section(username: str):
    """Show backtest history for comparison"""

    st.divider()
    st.subheader("Backtest History")

    # User filter toggle
    col1, col2 = st.columns([3, 1])

    with col1:
        st.caption(f"Viewing backtest history for: **{username}**")

    with col2:
        show_all_users = st.checkbox("Show all users", value=False, key="show_all_users_history")

    # Get history (filtered by user or all)
    history = get_history(username=None if show_all_users else username)

    if not history:
        st.info("No backtest history yet. Run a backtest to start building your comparison history.")
        return

    # Convert to DataFrame for display
    history_df = history_to_dataframe(history)

    # Filter and column options
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        strategies = ['All'] + list(history_df['Strategy'].unique())
        filter_strategy = st.selectbox(
            "Filter by Strategy",
            options=strategies,
            key="history_filter_strategy"
        )

    with col2:
        symbols = ['All'] + list(history_df['Symbol'].unique())
        filter_symbol = st.selectbox(
            "Filter by Symbol",
            options=symbols,
            key="history_filter_symbol"
        )

    with col3:
        sort_by = st.selectbox(
            "Sort by",
            options=['Date', 'Win Rate %', 'Total Pips', 'P/F', 'Trades'],
            index=0,
            key="history_sort"
        )

    # Optional columns selector
    with st.expander("Customize Columns"):
        st.caption("Select columns to display (in order)")

        # All available optional columns
        all_optional = HISTORY_COLUMNS['config'] + HISTORY_COLUMNS['summary']

        selected_optional = st.multiselect(
            "Optional Columns",
            options=all_optional,
            default=HISTORY_COLUMNS['default_optional'],
            key="history_optional_cols"
        )

    # Apply filters
    filtered_df = history_df.copy()
    if filter_strategy != 'All':
        filtered_df = filtered_df[filtered_df['Strategy'] == filter_strategy]
    if filter_symbol != 'All':
        filtered_df = filtered_df[filtered_df['Symbol'] == filter_symbol]

    # Sort
    if sort_by == 'Date':
        filtered_df = filtered_df.sort_values('Date', ascending=False)
    else:
        filtered_df = filtered_df.sort_values(sort_by, ascending=False)

    # Build display columns: core + selected optional (in order)
    display_cols = HISTORY_COLUMNS['core'].copy()

    # Add optional columns in the order they were selected
    for col in selected_optional:
        if col not in display_cols:
            display_cols.append(col)

    # Filter to only existing columns
    display_df = filtered_df[[c for c in display_cols if c in filtered_df.columns]]

    # Color functions
    def color_win_rate(val):
        if isinstance(val, (int, float)):
            if val >= 60:
                return 'color: green'
            elif val < 50:
                return 'color: red'
        return ''

    def color_pips(val):
        if isinstance(val, (int, float)):
            if val > 0:
                return 'color: green'
            elif val < 0:
                return 'color: red'
        return ''

    # Apply styling
    style_subsets = []
    if 'Win Rate %' in display_df.columns:
        style_subsets.append(('Win Rate %', color_win_rate))
    if 'Total Pips' in display_df.columns:
        style_subsets.append(('Total Pips', color_pips))
    if 'Total USD' in display_df.columns:
        style_subsets.append(('Total USD', color_pips))
    if 'Avg Pips' in display_df.columns:
        style_subsets.append(('Avg Pips', color_pips))

    styled_history = display_df.style
    for col, func in style_subsets:
        styled_history = styled_history.map(func, subset=[col])

    st.dataframe(styled_history, width='stretch', hide_index=True)

    st.caption(f"Showing {len(filtered_df)} of {len(history_df)} records | {len(display_cols)} columns")

    # Delete functionality
    st.markdown("---")

    with st.expander("Manage History"):
        st.warning("Delete records from history")

        # Select record to delete
        record_options = {
            f"{r['Date']} - {r['Strategy']} - {r['Symbol']} ({r['Win Rate %']}% WR)": r['ID']
            for _, r in filtered_df.iterrows()
        }

        if record_options:
            selected_record = st.selectbox(
                "Select record to delete",
                options=list(record_options.keys()),
                key="delete_record_select"
            )

            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("Delete Selected", type="secondary"):
                    record_id = record_options[selected_record]
                    if delete_history_record(record_id):
                        st.success("Record deleted!")
                        st.rerun()
                    else:
                        st.error("Failed to delete record")


if __name__ == "__main__":
    main()
