"""
Strategy Page - Run simulations and monitor strategy
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
    page_title="Strategy",
    layout="wide",
)

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
SYMBOL = os.getenv("SYMBOL", "ETHUSDm")
SL_PIPS = 30
MAX_CANDLES = 7


def get_pip_value(symbol: str) -> float:
    if "BTC" in symbol:
        return 1.0
    elif "ETH" in symbol:
        return 0.1
    elif "XAU" in symbol:
        return 0.1
    elif "JPY" in symbol:
        return 0.01
    return 0.0001


def run_simulation():
    """Run strategy simulation with MT5 data"""
    try:
        import MetaTrader5 as mt5

        account = int(os.getenv("MT5_LOGIN"))
        password = os.getenv("MT5_PASSWORD")
        server = os.getenv("MT5_SERVER")

        if not mt5.initialize():
            return None, "MT5 initialization failed"

        if not mt5.login(login=account, password=password, server=server):
            return None, f"MT5 login failed: {mt5.last_error()}"

        # Get candles
        data = pd.DataFrame(mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, 15))

        if data.empty or len(data) < 10:
            mt5.shutdown()
            return None, f"No data for {SYMBOL}"

        # Convert time
        data['time_hcm'] = pd.to_datetime(data['time'], unit='s').dt.tz_localize('UTC').dt.tz_convert(TIMEZONE)

        # Use candle at index -9 as master candle
        master_idx = len(data) - 9
        master = data.iloc[master_idx]
        master_time = master['time_hcm']

        o, h, l, c = master["open"], master["high"], master["low"], master["close"]
        pip = get_pip_value(SYMBOL)
        sl_dist = SL_PIPS * pip

        # Determine direction and calculate levels (RR 1:2)
        if c > o:  # Bullish
            direction = "BUY"
            entry = c
            sl = l - sl_dist
            risk = entry - sl
            reward = risk * 2
            tp = entry + reward
        else:  # Bearish
            direction = "SELL"
            entry = c
            sl = h + sl_dist
            risk = sl - entry
            reward = risk * 2
            tp = entry - reward

        # Simulate following candles
        exit_type = None
        exit_price = None
        exit_candle = None
        candle_results = []

        for i in range(1, MAX_CANDLES + 1):
            candle_idx = master_idx + i
            if candle_idx >= len(data):
                break

            candle = data.iloc[candle_idx]
            candle_time = candle['time_hcm'].strftime('%H:%M')
            ch, cl, cc = candle["high"], candle["low"], candle["close"]

            # Check exit
            if direction == "BUY":
                if ch >= tp:
                    exit_type, exit_price = "TP", tp
                elif cc <= sl:
                    exit_type, exit_price = "SL", cc
            else:
                if cl <= tp:
                    exit_type, exit_price = "TP", tp
                elif cc >= sl:
                    exit_type, exit_price = "SL", cc

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
            last_candle = data.iloc[master_idx + MAX_CANDLES] if master_idx + MAX_CANDLES < len(data) else data.iloc[-1]
            exit_price = last_candle["close"]
            exit_candle = MAX_CANDLES

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
    st.title("🎯 Strategy Simulation")
    st.caption(f"Master Candle Strategy | {SYMBOL}")

    now = datetime.now(TIMEZONE)
    st.markdown(f"**Current Time:** {now.strftime('%H:%M:%S %d/%m/%Y')} (HCM)")

    st.divider()

    # Strategy parameters
    st.subheader("📊 Strategy Parameters")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Symbol", SYMBOL)
    with col2:
        st.metric("SL Pips", SL_PIPS)
    with col3:
        st.metric("RR Ratio", "1:2")
    with col4:
        st.metric("Max Candles", MAX_CANDLES)

    st.divider()

    # Run simulation
    st.subheader("🔬 Run Simulation")

    if st.button("▶️ Run Simulation", use_container_width=True, type="primary"):
        with st.spinner("Connecting to MT5 and running simulation..."):
            result, error = run_simulation()

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
                direction_color = "🟢" if result['direction'] == "BUY" else "🔴"
                st.markdown(f"**Signal:** {direction_color} {result['direction']}")
                st.code(f"Entry: {result['entry']:.2f}\nSL:    {result['sl']:.2f}\nTP:    {result['tp']:.2f}")

            st.divider()

            # Candle tracking
            st.markdown("### Candle Tracking")

            candles_df = pd.DataFrame(result['candles'])
            candles_df.columns = ["#", "Time", "High", "Low", "Close", "Exit"]
            st.dataframe(candles_df, use_container_width=True, hide_index=True)

            # Result
            st.divider()
            exit_emoji = "✅" if result['exit_type'] == "TP" else "❌" if result['exit_type'] == "SL" else "⏰"
            pnl_color = "green" if result['pnl'] > 0 else "red" if result['pnl'] < 0 else "gray"

            st.markdown(f"### {exit_emoji} Result: {result['exit_type']}")
            st.markdown(f"**Exit Price:** {result['exit_price']:.2f} (Candle #{result['exit_candle']})")
            st.markdown(f"**P&L:** :{pnl_color}[{result['pnl']:+.1f} pips]")

    st.divider()

    # Exit rules explanation
    with st.expander("📖 Exit Rules Explained"):
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
        - After 7 M5 candles (~35 min), force close
        - Prevents holding positions too long
        """)


if __name__ == "__main__":
    main()
