"""
Simulation Page - Run single strategy simulation on live MT5 data
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import os

load_dotenv()

st.set_page_config(
    page_icon="🎯",
    page_title="Simulation",
    layout="wide",
)

# Auth check
from src.auth import require_auth, get_user_mt5_credentials, has_mt5_credentials
username, name = require_auth()

from src.utils import get_pip_value, is_mt5_available, check_exit
from src.strategy_manager import list_strategies, get_strategy_parameters

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def run_simulation(symbol: str, sl_pips: float, rr_ratio: float, max_candles: int, credentials: dict):
    """Run strategy simulation with MT5 data using user's credentials"""
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return None, "MT5 not available (Windows only). Use local machine for live simulation."

    try:
        account = int(credentials.get('login') or 0)
        password = credentials.get('password', '')
        server = credentials.get('server', '')

        if not account or not password or not server:
            return None, "MT5 credentials not configured. Check Settings page."

        if not mt5.initialize():
            return None, "MT5 initialization failed"

        if not mt5.login(login=account, password=password, server=server):
            error = mt5.last_error()
            mt5.shutdown()
            return None, f"MT5 login failed: {error}"

        # Get candles
        data = pd.DataFrame(mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 15))

        if data.empty or len(data) < 10:
            mt5.shutdown()
            return None, f"No data for {symbol}"

        # Convert time
        data['time_hcm'] = pd.to_datetime(data['time'], unit='s').dt.tz_localize('UTC').dt.tz_convert(TIMEZONE)

        # Use candle at index -9 as master candle
        master_idx = len(data) - 9
        master = data.iloc[master_idx]
        master_time = master['time_hcm']

        o, h, l, c = master["open"], master["high"], master["low"], master["close"]
        pip = get_pip_value(symbol)
        sl_dist = sl_pips * pip

        # Determine direction and calculate levels
        if c > o:  # Bullish
            direction = "BUY"
            entry = c
            sl = l - sl_dist
            risk = entry - sl
            reward = risk * rr_ratio
            tp = entry + reward
        elif c < o:  # Bearish
            direction = "SELL"
            entry = c
            sl = h + sl_dist
            risk = sl - entry
            reward = risk * rr_ratio
            tp = entry - reward
        else:  # Doji
            mt5.shutdown()
            return None, "Doji candle detected - no trade signal"

        # Simulate following candles
        exit_type = None
        exit_price = None
        exit_candle = None
        candle_results = []

        for i in range(1, max_candles + 1):
            candle_idx = master_idx + i
            if candle_idx >= len(data):
                break

            candle = data.iloc[candle_idx]
            candle_time = candle['time_hcm'].strftime('%H:%M')
            ch, cl, cc = candle["high"], candle["low"], candle["close"]

            # Check exit using shared function
            candle_dict = {"high": ch, "low": cl, "close": cc}
            exit_type, exit_price = check_exit(direction, candle_dict, tp, sl)

            candle_results.append({
                "num": i,
                "time": candle_time,
                "high": ch,
                "low": cl,
                "close": cc,
                "exit": exit_type
            })

            if exit_type:
                exit_candle = i
                break

        # Time limit if no exit
        if not exit_type:
            exit_type = "TIME"
            last_candle = data.iloc[master_idx + max_candles] if master_idx + max_candles < len(data) else data.iloc[-1]
            exit_price = last_candle["close"]
            exit_candle = max_candles

        # Calculate P&L
        if direction == "BUY":
            pnl = (exit_price - entry) / pip
        else:
            pnl = (entry - exit_price) / pip

        mt5.shutdown()

        result = {
            "master_time": master_time.strftime('%H:%M %d/%m'),
            "direction": direction,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "risk": risk,
            "reward": reward,
            "exit_type": exit_type,
            "exit_price": exit_price,
            "exit_candle": exit_candle,
            "pnl": pnl,
            "candles": candle_results,
            "ohlc": {"o": o, "h": h, "l": l, "c": c}
        }

        return result, None

    except Exception as e:
        return None, str(e)


def main():
    st.title("Strategy Simulation")
    st.caption("Run single simulation on live MT5 data")

    now = datetime.now(TIMEZONE)
    st.markdown(f"**Current Time:** {now.strftime('%H:%M:%S %d/%m/%Y')} (HCM)")

    # MT5 availability check
    mt5_available = is_mt5_available()
    if mt5_available:
        st.success("MT5 available - Live simulation enabled")
    else:
        st.warning("MT5 not available (Windows only) - Demo mode")

    # Check MT5 credentials
    if not has_mt5_credentials(username):
        st.warning("MT5 account not configured. Please go to Settings first.")
        st.page_link("pages/8_Settings.py", label="Go to Settings", icon="⚙️")
        return

    user_creds = get_user_mt5_credentials(username)

    st.divider()

    # Get available strategies
    strategies = list_strategies()
    enabled_strategies = [s for s in strategies if s.get('enabled', True)]

    # Strategy parameters
    st.subheader("Simulation Parameters")

    col1, col2 = st.columns(2)

    with col1:
        if enabled_strategies:
            strategy_options = {s['name']: s['id'] for s in enabled_strategies}
            selected_strategy_name = st.selectbox(
                "Strategy",
                options=list(strategy_options.keys())
            )
            selected_strategy = strategy_options[selected_strategy_name]
            params = get_strategy_parameters(selected_strategy)
        else:
            st.info("No strategies defined. Using default parameters.")
            params = {'symbols': ['XAUUSD'], 'sl_pips': 30, 'rr_ratio': 2.0, 'max_candles': 7}

        # Symbol selection
        strategy_symbols = params.get('symbols', ['XAUUSD'])
        symbol = st.selectbox("Symbol", options=strategy_symbols)

    with col2:
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

        max_candles = st.number_input(
            "Max Candles",
            value=int(params.get('max_candles', 7)),
            min_value=1,
            max_value=50
        )

    st.divider()

    # Run simulation
    if st.button("Run Simulation", width='stretch', type="primary"):
        with st.spinner("Connecting to MT5 and running simulation..."):
            result, error = run_simulation(
                symbol=symbol,
                sl_pips=sl_pips,
                rr_ratio=rr_ratio,
                max_candles=max_candles,
                credentials=user_creds
            )

        if error:
            st.error(f"Error: {error}")
        else:
            # Display results
            st.success("Simulation completed!")

            # Master candle info
            st.markdown(f"### Master Candle: {result['master_time']}")

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**OHLC:**")
                ohlc = result['ohlc']
                st.code(f"Open:  {ohlc['o']:.2f}\nHigh:  {ohlc['h']:.2f}\nLow:   {ohlc['l']:.2f}\nClose: {ohlc['c']:.2f}")

            with col2:
                direction_color = "green" if result['direction'] == "BUY" else "red"
                st.markdown(f"**Signal:** :{direction_color}[{result['direction']}]")
                st.code(f"Entry: {result['entry']:.2f}\nSL:    {result['sl']:.2f}\nTP:    {result['tp']:.2f}")

            st.divider()

            # Candle tracking
            st.markdown("### Candle Tracking")

            candles_df = pd.DataFrame(result['candles'])
            candles_df.columns = ["#", "Time", "High", "Low", "Close", "Exit"]
            st.dataframe(candles_df, width='stretch', hide_index=True)

            # Result
            st.divider()
            exit_emoji = "TP" if result['exit_type'] == "TP" else "SL" if result['exit_type'] == "SL" else "TIME"
            pnl_color = "green" if result['pnl'] > 0 else "red" if result['pnl'] < 0 else "gray"

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Exit Type", exit_emoji)
            with col2:
                st.metric("Exit Price", f"{result['exit_price']:.2f}")
            with col3:
                st.metric("P&L", f"{result['pnl']:+.1f} pips", delta="profit" if result['pnl'] > 0 else "loss" if result['pnl'] < 0 else None)

            st.caption(f"Exited on candle #{result['exit_candle']}")

    st.divider()

    # Exit rules explanation
    with st.expander("Exit Rules Explained"):
        st.markdown("""
        **TP (Take Profit) - Price-based:**
        - Triggers immediately when price touches TP level
        - BUY: High >= TP
        - SELL: Low <= TP

        **SL (Stop Loss) - Close-based:**
        - Triggers only when candle CLOSES beyond SL
        - BUY: Close <= SL
        - SELL: Close >= SL
        - Protects against wicks/fakeouts

        **Time Limit:**
        - After max candles, force close at current price
        - Prevents holding positions too long
        """)


if __name__ == "__main__":
    main()
