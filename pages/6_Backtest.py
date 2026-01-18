"""
Backtest Page - Test strategy on historical data
"""

import streamlit as st
import pandas as pd
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
from src.orders import is_mt5_available
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
        st.page_link("pages/3_Settings.py", label="Go to Settings", icon="⚙️")
        show_demo_results()
        return

    # Get user credentials
    user_creds = get_user_mt5_credentials(username)

    # Get available strategies
    strategies = list_strategies()
    enabled_strategies = [s for s in strategies if s.get('enabled', True)]

    if not enabled_strategies:
        st.warning("No strategies available. Create one in the Strategies page.")
        st.page_link("pages/7_Strategies.py", label="Go to Strategies", icon="📖")
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
                value=os.getenv("SYMBOL", "ETHUSDm"),
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
                value=os.getenv("SYMBOL", "ETHUSDm"),
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
            entry_time = st.time_input(
                "Entry Time",
                value=datetime.strptime("21:05", "%H:%M").time(),
                step=300,  # 5 minutes interval
                help="Enter custom entry time"
            )
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
        sl_pips = st.number_input(
            "SL (pips)",
            value=int(params.get('sl_pips', 30)),
            min_value=1,
            max_value=200,
            help=f"Default: {params.get('sl_pips', 30)} pips"
        )

        rr_ratio = st.number_input(
            "RR Ratio",
            value=float(params.get('rr_ratio', 2.0)),
            min_value=0.5,
            max_value=10.0,
            step=0.5,
            help=f"Default: {params.get('rr_ratio', 2.0)}"
        )

        max_candles = st.number_input(
            "Max Candles",
            value=int(params.get('max_candles', 7)),
            min_value=1,
            max_value=50,
            help=f"Default: {params.get('max_candles', 7)} candles"
        )

    # Show strategy info
    st.caption(f"Strategy: **{selected_strategy_name}** | Timeframe: {params.get('timeframe', 'M5')} | "
               f"TP: {params.get('tp_type', 'price_based')} | SL: {params.get('sl_type', 'close_based')}")

    st.divider()

    # Run backtest button
    if st.button("Run Backtest", type="primary", use_container_width=True):
        with st.spinner("Fetching historical data..."):
            # Convert dates to datetime
            start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=TIMEZONE)
            end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=TIMEZONE)

            # Fetch data
            df, error = fetch_historical_data(symbol, start_dt, end_dt, user_creds)

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
                max_candles=max_candles
            )

        # Store results in session state
        st.session_state['backtest_results'] = results
        st.session_state['backtest_symbol'] = symbol
        st.session_state['backtest_strategy'] = selected_strategy_name

    # Display results if available
    if 'backtest_results' in st.session_state:
        display_results(
            st.session_state['backtest_results'],
            st.session_state.get('backtest_symbol', ''),
            st.session_state.get('backtest_strategy', '')
        )


def display_results(results: dict, symbol: str, strategy_name: str = ""):
    """Display backtest results"""

    st.divider()
    st.subheader(f"Results: {strategy_name}" if strategy_name else "Results")

    if results['total_trades'] == 0:
        st.warning("No trades found in the selected period")
        return

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
        st.metric("Avg P&L", f"{results['avg_pnl']} pips")

    with col4:
        st.metric("Best Trade", f"{results['best_trade']} pips")
        st.metric("Worst Trade", f"{results['worst_trade']} pips")

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
        if strategy_name:
            st.caption(f"Strategy: {strategy_name}")

    st.divider()

    # Equity curve
    st.subheader("Equity Curve")

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
            use_container_width=True
        )

    st.divider()

    # Trade list
    st.subheader("Trade List")

    trades = results.get('trades', [])
    if trades:
        trades_df = pd.DataFrame(trades)

        # Rename columns for display
        trades_df = trades_df.rename(columns={
            'date': 'Date',
            'time': 'Time',
            'direction': 'Direction',
            'entry': 'Entry',
            'sl': 'SL',
            'tp': 'TP',
            'exit_type': 'Exit',
            'exit_price': 'Exit Price',
            'candles': 'Candles',
            'pnl_pips': 'P&L (pips)'
        })

        # Drop exit_time column if exists
        if 'exit_time' in trades_df.columns:
            trades_df = trades_df.drop(columns=['exit_time'])

        # Color P&L
        def color_pnl(val):
            if val > 0:
                return 'color: green'
            elif val < 0:
                return 'color: red'
            return ''

        styled_df = trades_df.style.applymap(color_pnl, subset=['P&L (pips)'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

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
        use_container_width=True
    )


if __name__ == "__main__":
    main()
