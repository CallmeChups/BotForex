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

    # Parameters
    st.subheader("Backtest Parameters")

    # Strategy selection
    strategy_options = {s['name']: s['id'] for s in enabled_strategies}
    selected_strategy_name = st.selectbox(
        "Select Strategy",
        options=list(strategy_options.keys())
    )
    selected_strategy = strategy_options[selected_strategy_name]

    # Load strategy parameters
    params = get_strategy_parameters(selected_strategy)

    col1, col2, col3 = st.columns(3)

    with col1:
        # Symbol - allow selection from strategy list OR custom input
        strategy_symbols = params.get('symbols', [])

        use_custom_symbol = st.checkbox("Custom symbol", value=False)

        if use_custom_symbol:
            symbol = st.text_input(
                "Symbol",
                value=os.getenv("SYMBOL", "XAUUSD"),
                help="Enter any symbol"
            )
        elif strategy_symbols:
            symbol = st.selectbox(
                "Symbol",
                options=strategy_symbols,
                help="From strategy's supported symbols"
            )
        else:
            symbol = st.text_input(
                "Symbol",
                value=os.getenv("SYMBOL", "XAUUSD"),
                help="Trading symbol"
            )

        # Date range
        default_end = now.date()
        default_start = default_end - timedelta(days=30)

        start_date = st.date_input(
            "Start Date",
            value=default_start,
            max_value=default_end
        )

    with col2:
        end_date = st.date_input(
            "End Date",
            value=default_end,
            max_value=default_end
        )

        # Entry time - allow custom or use strategy default
        entry_time_str = params.get('entry_time', '21:05')

        use_custom_time = st.checkbox("Custom entry time", value=False)

        if use_custom_time:
            # Use text input for better UX (allows backspace/clear)
            custom_time_str = st.text_input(
                "Entry Time",
                value="21:05",
                max_chars=5,
                help="Format: HH:MM (e.g., 21:05)",
                placeholder="HH:MM"
            )
            # Validate and parse time
            try:
                entry_time = datetime.strptime(custom_time_str, "%H:%M").time()
            except ValueError:
                st.error("Invalid time format. Use HH:MM (e.g., 21:05)")
                entry_time = datetime.strptime("21:05", "%H:%M").time()
        else:
            entry_time = st.time_input(
                "Entry Time",
                value=datetime.strptime(entry_time_str, "%H:%M").time(),
                step=300,  # 5 minutes interval
                help=f"From strategy: {entry_time_str}",
                disabled=True
            )
            st.caption(f"Strategy default: {entry_time_str}")

    with col3:
        # Timeframe - allow custom or use strategy default
        strategy_timeframe = params.get('timeframe', 'M5')
        timeframe_options = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]

        use_custom_timeframe = st.checkbox("Custom timeframe", value=False)

        if use_custom_timeframe:
            timeframe = st.selectbox(
                "Timeframe",
                options=timeframe_options,
                index=timeframe_options.index("M5"),
                help="Select timeframe for candles"
            )
        else:
            timeframe = strategy_timeframe
            st.selectbox(
                "Timeframe",
                options=[strategy_timeframe],
                help=f"From strategy: {strategy_timeframe}",
                disabled=True
            )
            st.caption(f"Strategy default: {strategy_timeframe}")

        rr_ratio = st.number_input(
            "RR Ratio",
            value=float(params.get('rr_ratio', 2.0)),
            min_value=0.5,
            max_value=10.0,
            step=0.5,
            help=f"Default: {params.get('rr_ratio', 2.0)}"
        )

        use_max_candles = st.checkbox(
            "Enable Max Candles",
            value=True,
            help="Uncheck to disable time-based exit (only TP/SL)"
        )

        if use_max_candles:
            max_candles = st.number_input(
                "Max Candles",
                value=int(params.get('max_candles', 7)),
                min_value=1,
                max_value=50,
                help=f"Default: {params.get('max_candles', 7)} candles"
            )
        else:
            max_candles = 0  # 0 means no limit
            st.caption("Time exit disabled - trades exit only on TP or SL")

    # Show strategy info
    st.caption(f"Strategy: **{selected_strategy_name}** | Timeframe: {timeframe}")

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

    st.divider()

    # Exit Type Configuration
    st.subheader("Exit Types")

    col1, col2 = st.columns(2)

    with col1:
        tp_type = st.radio(
            "Take Profit (TP) Exit",
            options=["price_based", "close_based"],
            format_func=lambda x: "Price-based (Immediate)" if x == "price_based" else "Close-based (Delayed)",
            horizontal=True,
            help="Price-based: Exit when wick touches TP | Close-based: Exit when candle closes beyond TP"
        )
        if tp_type == "price_based":
            st.caption("TP triggers when High/Low touches TP level (exits at TP price)")
        else:
            st.caption("TP triggers when candle CLOSES beyond TP (exits at close price)")

    with col2:
        sl_type = st.radio(
            "Stop Loss (SL) Exit",
            options=["close_based", "price_based"],
            format_func=lambda x: "Close-based (Delayed)" if x == "close_based" else "Price-based (Immediate)",
            horizontal=True,
            help="Close-based: Exit when candle closes beyond SL | Price-based: Exit when wick touches SL"
        )
        if sl_type == "close_based":
            st.caption("SL triggers when candle CLOSES beyond SL (exits at close price)")
        else:
            st.caption("SL triggers when High/Low touches SL level (exits at SL price)")

    st.divider()

    # Lot Size Configuration
    st.subheader("Lot Size")

    lot_mode = st.radio(
        "Lot Size Mode",
        options=["fixed", "flex"],
        format_func=lambda x: "Fixed" if x == "fixed" else "Flex (Risk-based)",
        horizontal=True,
        help="Fixed: manual lot size | Flex: calculated from risk % and SL distance"
    )

    # Buffer K - used for both modes (SL = candle body + k)
    col1, col2 = st.columns(2)

    with col1:
        buffer_k = st.number_input(
            "Buffer K (pips)",
            value=5.0,
            min_value=0.0,
            max_value=50.0,
            step=1.0,
            help="SL = candle body + k pips"
        )

    st.caption("SL pips = (Close - Low) + k for BUY, (High - Close) + k for SELL")

    if lot_mode == "fixed":
        with col2:
            fixed_lot = st.number_input(
                "Lot Size",
                value=float(params.get('lot_size', 0.01)),
                min_value=0.01,
                max_value=10.0,
                step=0.01,
                format="%.2f"
            )
        # Placeholders for flex params
        risk_percent = 0.5
        risk_amount = 0.0
        risk_mode = "percent"
        starting_equity = 1000.0
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
                    help="Percentage of current equity to risk"
                )
                risk_amount = 0.0
                # Calculate example
                example_r = starting_equity * (risk_percent / 100)
                st.caption(f"Initial: ${starting_equity:.0f} × {risk_percent}% = ${example_r:.2f}/trade")
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

        fixed_lot = 0.01  # Not used in flex mode

    sl_pips = 0  # Not used - always calculated from candle + buffer k

    st.divider()

    # Run backtest button
    if st.button("Run Backtest", type="primary", use_container_width=True):
        with st.spinner("Fetching historical data..."):
            # Convert dates to datetime
            start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=TIMEZONE)
            end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=TIMEZONE)

            # Fetch data
            df, error = fetch_historical_data(symbol, start_dt, end_dt, user_creds, timeframe)

            if error:
                st.error(f"Failed to fetch data: {error}")
                return

            if df is None or df.empty:
                st.warning("No data found for the selected period")
                return

            st.success(f"Fetched {len(df)} candles")

        with st.spinner("Running backtest..."):
            # Run backtest
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
                buffer_k=buffer_k,
                starting_equity=starting_equity,
                tp_type=tp_type,
                sl_type=sl_type,
                entry_mode=entry_mode,
                entry_percent=entry_percent
            )

        # Store results in session state
        st.session_state['backtest_results'] = results
        st.session_state['backtest_symbol'] = symbol
        st.session_state['backtest_strategy'] = selected_strategy_name
        st.session_state['backtest_lot_mode'] = lot_mode
        st.session_state['backtest_timeframe'] = timeframe
        st.session_state['backtest_tp_type'] = tp_type
        st.session_state['backtest_sl_type'] = sl_type

    # Display results if available
    if 'backtest_results' in st.session_state:
        display_results(
            st.session_state['backtest_results'],
            st.session_state.get('backtest_symbol', ''),
            st.session_state.get('backtest_strategy', ''),
            st.session_state.get('backtest_lot_mode', 'fixed'),
            st.session_state.get('backtest_timeframe', 'M5'),
            st.session_state.get('backtest_tp_type', 'price_based'),
            st.session_state.get('backtest_sl_type', 'close_based')
        )


def display_results(results: dict, symbol: str, strategy_name: str = "", lot_mode: str = "fixed", timeframe: str = "M5", tp_type: str = "price_based", sl_type: str = "close_based"):
    """Display backtest results"""

    st.divider()
    st.subheader(f"Results: {strategy_name}" if strategy_name else "Results")

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

    with col3:
        pnl_delta = "profit" if results['total_pnl'] > 0 else "loss" if results['total_pnl'] < 0 else None
        st.metric("Total P&L", f"{results['total_pnl']} pips", delta=pnl_delta)
        if lot_mode == "flex":
            st.metric("Total P&L (USD)", f"${results.get('total_pnl_usd', 0):.2f}")
        else:
            st.metric("Avg P&L", f"{results['avg_pnl']} pips")

    with col4:
        st.metric("Best Trade", f"{results['best_trade']} pips")
        st.metric("Worst Trade", f"{results['worst_trade']} pips")
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

    # Equity curve
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
            show_trade_table(trades, lot_mode, strategy_name, symbol)
        else:
            show_interactive_chart(trades, ohlc_data, symbol)


def show_trade_table(trades: list, lot_mode: str, strategy_name: str, symbol: str):
    """Show trades as a table"""
    trades_df = pd.DataFrame(trades)

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

    # Drop exit_time column if exists
    if 'exit_time' in trades_df.columns:
        trades_df = trades_df.drop(columns=['exit_time'])

    # Select columns based on lot mode
    if lot_mode == "fixed":
        # Hide flex-specific columns
        cols_to_drop = ['SL Pips', 'Lot', 'P&L (USD)']
        for col in cols_to_drop:
            if col in trades_df.columns:
                trades_df = trades_df.drop(columns=[col])

    # Color P&L
    def color_pnl(val):
        if val > 0:
            return 'color: green'
        elif val < 0:
            return 'color: red'
        return ''

    styled_df = trades_df.style.map(color_pnl, subset=['P&L (pips)'])
    st.dataframe(styled_df, width='stretch', hide_index=True)

    # Download button
    csv = trades_df.to_csv(index=False)
    filename_parts = [strategy_name.replace(' ', '_')] if strategy_name else []
    filename_parts.extend([symbol, datetime.now().strftime('%Y%m%d')])
    st.download_button(
        label="Download CSV",
        data=csv,
        file_name=f"backtest_{'_'.join(filename_parts)}.csv",
        mime="text/csv"
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
    end_idx = min(len(ohlc_data), entry_idx + trade['candles'] + 15)
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

    # Exit marker
    exit_candle_idx = entry_idx + trade['candles']
    if exit_candle_idx < len(ohlc_data):
        exit_time = ohlc_data.iloc[exit_candle_idx]['time']
    else:
        exit_time = chart_data['time'].iloc[-1]

    exit_price = trade['exit_price']
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
        st.metric("Exit Price", f"{trade['exit_price']:.2f}")
    with col4:
        pnl_color = "green" if trade['pnl_pips'] > 0 else "red"
        st.metric("P&L", f"{trade['pnl_pips']:+.1f} pips")
        st.metric("Candles Held", trade['candles'])


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


if __name__ == "__main__":
    main()
