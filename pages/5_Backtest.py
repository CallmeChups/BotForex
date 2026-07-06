"""
Backtest Page - Test strategy on historical data
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta, time
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
from src.auth import (require_auth, get_user_mt5_credentials, has_mt5_credentials,
                      get_user_mt5_backtest_credentials, set_user_mt5_backtest_credentials)
username, name = require_auth()

from src.backtest import fetch_historical_data, run_backtest
from src.utils import is_mt5_available, get_pip_value, report_page_error
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


def _pip_caption(pips: float, symbol: str) -> str:
    """Hiển thị giá trị thực của N pips theo symbol đang chọn."""
    pv = get_pip_value(symbol)
    return f"{pips} pips = **{pips * pv:.4g}** giá ({symbol})"



def _pf(key, default=None):
    """Get value from backtest_prefill session state, fallback to default."""
    pf = st.session_state.get('backtest_prefill', {})
    return pf.get(key, default)


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

    # Backtest MT5 override — dùng account khác (ví dụ real account stable hơn demo trial)
    _saved_bt = get_user_mt5_backtest_credentials(username)
    with st.expander("🔧 Backtest MT5 Override (fallback account)", expanded=bool(_saved_bt['login'])):
        st.caption("Để trống = dùng MT5 account trong Settings. Điền vào để override khi server demo lỗi.")
        _oc1, _oc2, _oc3 = st.columns(3)
        with _oc1:
            _ov_login = st.text_input("Login", value=_saved_bt['login'], key="bt_ov_login", placeholder="MT5 login number")
        with _oc2:
            _ov_password = st.text_input("Password", value=_saved_bt['password'], key="bt_ov_password", type="password", placeholder="MT5 password")
        with _oc3:
            _ov_server = st.text_input("Server", value=_saved_bt['server'], key="bt_ov_server", placeholder="e.g. Exness-MT5Real8")
        if _ov_login and _ov_password and _ov_server:
            user_creds = {'login': _ov_login, 'password': _ov_password, 'server': _ov_server}
            # Auto-save nếu khác với đã lưu
            if (_ov_login != _saved_bt['login'] or _ov_password != _saved_bt['password']
                    or _ov_server != _saved_bt['server']):
                set_user_mt5_backtest_credentials(username, _ov_login, _ov_password, _ov_server)
            st.success(f"Override active: login={_ov_login} server={_ov_server}")

    # Get available strategies
    strategies = list_strategies()
    enabled_strategies = [s for s in strategies if s.get('enabled', True)]

    if not enabled_strategies:
        st.warning("No strategies available. Create one in the Strategies page.")
        st.page_link("pages/4_Strategies.py", label="Go to Strategies", icon="📖")
        show_demo_results()
        return

    # Layout toggle — default compact
    use_compact = st.toggle("Compact layout", value=st.session_state.get("backtest_compact_layout", True),
                            key="backtest_compact_layout",
                            help="Switch between compact grid and classic expanded layout")

    strategy_options = {s['name']: s['id'] for s in enabled_strategies}
    default_end = now.date()
    default_start = default_end - timedelta(days=30)

    if use_compact:
        # ── COMPACT LAYOUT ────────────────────────────────────────────────────
        # Row 1: Strategy | Symbol | Timeframe
        # Row 2: Date Start | Date End | RR | Max Candles
        # Row 3: Entry/EMA | Window | Entry Mode | Buffer K + Lot Mode
        # Expander: Exit Types + Lot/Risk
        # ─────────────────────────────────────────────────────────────────────

        r1c1, r1c2, r1c3 = st.columns([2, 2, 1])
        with r1c1:
            selected_strategy_name = st.selectbox("Strategy", options=list(strategy_options.keys()))
            selected_strategy = strategy_options[selected_strategy_name]
        params = get_strategy_parameters(selected_strategy)
        entry_type = params.get('entry_type', 'time')
        is_pattern = entry_type == 'pattern'
        strategy_symbols = params.get('symbols', [])
        strategy_timeframe = params.get('timeframe', 'M5')

        with r1c2:
            use_custom_symbol = st.checkbox("Custom symbol", value=False)
            if use_custom_symbol:
                symbol = st.text_input("Symbol", value=os.getenv("SYMBOL", "XAUUSD"))
            elif strategy_symbols:
                symbol = st.selectbox("Symbol", options=strategy_symbols)
            else:
                symbol = st.text_input("Symbol", value=os.getenv("SYMBOL", "XAUUSD"))

        with r1c3:
            timeframe_options = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
            use_custom_timeframe = st.checkbox("Custom TF", value=False)
            if use_custom_timeframe:
                timeframe = st.selectbox("Timeframe", options=timeframe_options,
                                         index=timeframe_options.index(strategy_timeframe))
            else:
                timeframe = strategy_timeframe
                st.selectbox("Timeframe", options=[strategy_timeframe], disabled=True)

        r2c1, r2c2, r2c3, r2c4 = st.columns(4)
        with r2c1:
            start_date = st.date_input("Start Date", value=default_start, max_value=default_end)
        with r2c2:
            end_date = st.date_input("End Date", value=default_end, max_value=default_end)
        with r2c3:
            rr_ratio = st.number_input("RR Ratio", value=float(_pf('rr_ratio', params.get('rr_ratio', 2.0))),
                                       min_value=0.5, max_value=10.0, step=0.5)
        with r2c4:
            use_max_candles = st.checkbox("Max Candles", value=bool(_pf('max_candles', params.get('max_candles', 7))), help="Uncheck = TP/SL only")
            if use_max_candles:
                max_candles = st.number_input("", value=int(_pf('max_candles', params.get('max_candles', 7))),
                                              min_value=1, max_value=50, label_visibility="collapsed")
            else:
                max_candles = 0

        r3c1, r3c2, r3c3, r3c4 = st.columns(4)
        is_feg_stop_order = (selected_strategy == 'feg_stop_order')
        # EMA filter defaults — used below and passed to run_backtest
        ema_filter_enabled = True
        buy_ema_side = "below_ema"
        sell_ema_side = "above_ema"

        with r3c1:
            if is_pattern:
                ema_period = st.number_input("EMA Period", value=int(_pf('ema_period', params.get('ema_period', 21))),
                                             min_value=2, max_value=200)
                h2_exceed_pips = st.number_input(
                    "H2 > H1 + N pips", value=float(_pf('h2_exceed_pips', params.get('h2_exceed_pips', 0.0))),
                    min_value=0.0, step=1.0,
                    help="SELL: H2 phải vượt H1 thêm N pips | BUY: L2 phải thấp hơn L1 thêm N pips")
                st.caption(_pip_caption(h2_exceed_pips, symbol))
                c2_gap_pips = st.number_input(
                    "C2 vượt L1/H1 + N pips", value=float(_pf('c2_gap_pips', params.get('c2_gap_pips', 0.0))),
                    min_value=0.0, step=1.0,
                    help="SELL: C2 phải đóng thấp hơn L1 thêm N pips | BUY: C2 phải đóng cao hơn H1 thêm N pips")
                st.caption(_pip_caption(c2_gap_pips, symbol))
                ema_margin_pips = st.number_input(
                    "L2/H2 cách EMA + N pips", value=float(_pf('ema_margin_pips', params.get('ema_margin_pips', 0.0))),
                    min_value=0.0, step=1.0,
                    help="SELL: L2 phải cách EMA ≥ N pips | BUY: H2 phải cách EMA ≥ N pips")
                st.caption(_pip_caption(ema_margin_pips, symbol))
                if is_pattern:
                    ema_filter_enabled = st.checkbox(
                        "EMA Filter", value=bool(_pf('ema_filter_enabled', params.get('ema_filter_enabled', True))),
                        help="Bật/tắt điều kiện EMA cho tín hiệu entry")
                    if ema_filter_enabled:
                        _ema_side_opts = ["above_ema", "below_ema"]
                        buy_ema_side = st.selectbox(
                            "BUY EMA side",
                            options=_ema_side_opts,
                            index=_ema_side_opts.index(_pf('buy_ema_side', params.get('buy_ema_side', 'below_ema'))),
                            format_func=lambda x: "H2 > EMA (above)" if x == "above_ema" else "H2 < EMA (below)",
                            help="BUY: H2 phải nằm trên hay dưới EMA")
                        sell_ema_side = st.selectbox(
                            "SELL EMA side",
                            options=_ema_side_opts,
                            index=_ema_side_opts.index(_pf('sell_ema_side', params.get('sell_ema_side', 'above_ema'))),
                            format_func=lambda x: "L2 > EMA (above)" if x == "above_ema" else "L2 < EMA (below)",
                            help="SELL: L2 phải nằm trên hay dưới EMA")
                entry_time = datetime.strptime("00:00", "%H:%M").time()
            else:
                ema_period = int(params.get('ema_period', 21))
                h2_exceed_pips = 0.0
                c2_gap_pips = 0.0
                ema_margin_pips = 0.0
                entry_time_str = params.get('entry_time', '21:05')
                use_custom_time = st.checkbox("Custom entry time", value=False)
                if use_custom_time:
                    raw = st.text_input("Entry Time (HH:MM)", value="21:05", max_chars=5)
                    try:
                        entry_time = datetime.strptime(raw, "%H:%M").time()
                    except ValueError:
                        st.error("Use HH:MM format")
                        entry_time = datetime.strptime("21:05", "%H:%M").time()
                else:
                    entry_time = st.time_input("Entry Time", step=300,
                                               value=datetime.strptime(entry_time_str, "%H:%M").time(),
                                               disabled=True, help=f"Strategy default: {entry_time_str}")

        with r3c2:
            _pf_start = _pf('entry_start_time', '00:00')
            _pf_end = _pf('entry_end_time', '23:59')
            entry_start_time = st.time_input("Window Start (HCM)",
                                             value=datetime.strptime(_pf_start, "%H:%M").time() if isinstance(_pf_start, str) else _pf_start,
                                             help="Gate entries from this time. 00:00 = no filter.")
            entry_end_time = st.time_input("Window End (HCM)",
                                           value=datetime.strptime(_pf_end, "%H:%M").time() if isinstance(_pf_end, str) else _pf_end,
                                           help="Gate entries until this time. 23:59 = no filter.")

        with r3c3:
            if is_feg_stop_order:
                # Stop order: entry = H2+buffer / L2-buffer, không có entry_mode/percent
                entry_mode = "close"
                entry_percent = 0.0
                st.caption("Entry: H2+buffer (BUY) / L2-buffer (SELL)")
            else:
                _pf_em = _pf('entry_mode', 'close')
                entry_mode = st.radio("Entry Mode", options=["close", "range_percent"],
                                      index=0 if _pf_em == "close" else 1,
                                      format_func=lambda x: "Close" if x == "close" else "Body %",
                                      help="Close: entry at close price | Body %: limit inside candle body")
                if entry_mode == "range_percent":
                    entry_percent = st.number_input("Entry %", value=float(_pf('entry_percent', 30.0)),
                                                    min_value=0.0, max_value=100.0, step=5.0)
                else:
                    entry_percent = 0.0
            limit_order_candles = st.number_input(
                "Chờ khớp lệnh (nến)", value=int(_pf('limit_order_candles', 1)), min_value=1, max_value=100,
                help="Số nến tối đa chờ stop order khớp. 1 = khớp ngay nến tiếp theo nếu giá chạm entry.")

        with r3c4:
            buffer_k = st.number_input("Buffer K (pips)", value=float(_pf('buffer_k', params.get('buffer_k', 5))),
                                       min_value=0.0, max_value=200.0, step=1.0,
                                       help="SL = candle body edge + K pips")
            _pf_lot = _pf('lot_mode', 'fixed')
            lot_mode = st.radio("Lot Mode", options=["fixed", "flex"],
                                index=0 if _pf_lot == "fixed" else 1,
                                format_func=lambda x: "Fixed" if x == "fixed" else "Flex (Risk)")

        with st.expander("Exit Types & Lot Size", expanded=False):
            ec1, ec2 = st.columns(2)
            with ec1:
                tp_type = st.radio("TP Exit", options=["price_based", "close_based"],
                                   index=0 if _pf('tp_type', 'price_based') == 'price_based' else 1,
                                   format_func=lambda x: "Price-based (wick)" if x == "price_based" else "Close-based",
                                   horizontal=True,
                                   help="Price: wick touches TP | Close: candle closes past TP")
            with ec2:
                sl_type = st.radio("SL Exit", options=["price_based", "close_based"],
                                   index=0 if _pf('sl_type', 'price_based') == 'price_based' else 1,
                                   format_func=lambda x: "Price-based (wick)" if x == "price_based" else "Close-based",
                                   horizontal=True,
                                   help="Price: wick touches SL | Close: candle closes past SL")
            bc1, bc2, bc3 = st.columns(3)
            with bc1:
                be_enabled = st.checkbox("Break-Even (BE)", value=bool(_pf('be_enabled', False)),
                                         help="Dời SL về entry khi lời đủ be_r × SL distance")
            with bc2:
                be_r = st.number_input("BE Trigger (R)", value=float(_pf('be_r', 1.0)), min_value=0.1, max_value=10.0,
                                       step=0.1, format="%.1f",
                                       help="BE kích hoạt khi lời đạt be_r × SL distance",
                                       disabled=not be_enabled)
            with bc3:
                re_entry_after_sl = st.checkbox("Re-Entry After SL", value=bool(_pf('re_entry_after_sl', False)),
                                                help="Trong lúc lệnh đang chạy, vẫn scan signal song song. "
                                                     "Nếu SL hit đúng tại candle2 của signal mới → vào lệnh tiếp ngay.")
            wc1, wc2, wc3 = st.columns(3)
            with wc1:
                c2_wick_filter_enabled = st.checkbox("C2 Wick Filter", value=bool(_pf('c2_wick_filter_enabled', False)),
                                                     help="Râu nến C2 phải nhỏ hơn n% body C2. "
                                                          "SELL: râu dưới (close-low) < body×n%. BUY: râu trên (high-close) < body×n%.")
            with wc2:
                c2_wick_max_percent = st.number_input("Wick Max % of Body", value=float(_pf('c2_wick_max_percent', 30.0)),
                                                      min_value=1.0, max_value=200.0, step=1.0, format="%.0f",
                                                      help="Ngưỡng tối đa của râu so với body C2 (%)",
                                                      disabled=not c2_wick_filter_enabled)
            st.divider()
            if lot_mode == "fixed":
                lc1, _ = st.columns(2)
                with lc1:
                    fixed_lot = st.number_input("Lot Size", value=float(_pf('fixed_lot', params.get('lot_size', 0.01))),
                                                min_value=0.01, max_value=10.0, step=0.01, format="%.2f")
                risk_percent = 0.5
                risk_amount = 0.0
                risk_mode = "percent"
                starting_equity = 1000.0
            else:
                lc1, lc2, lc3 = st.columns(3)
                with lc1:
                    starting_equity = st.number_input("Starting Equity ($)", value=float(_pf('starting_equity', 1000.0)),
                                                      min_value=100.0, step=100.0)
                with lc2:
                    _pf_rm = _pf('risk_mode', 'percent')
                    risk_mode = st.radio("Risk Mode", options=["percent", "fixed_amount"],
                                         index=0 if _pf_rm == "percent" else 1,
                                         format_func=lambda x: "%" if x == "percent" else "Fixed $",
                                         horizontal=True)
                with lc3:
                    if risk_mode == "percent":
                        risk_percent = st.number_input("Risk %", value=float(_pf('risk_percent', 0.5)), min_value=0.1,
                                                       max_value=5.0, step=0.1, format="%.1f")
                        risk_amount = 0.0
                        st.caption(f"${starting_equity:.0f} × {risk_percent}% = ${starting_equity * risk_percent / 100:.2f}/trade")
                    else:
                        risk_amount = st.number_input("Risk $", value=float(_pf('risk_amount', 5.0)), min_value=1.0,
                                                      max_value=1000.0, step=1.0, format="%.2f")
                        risk_percent = 0.0
                fixed_lot = 0.01

        st.caption(f"Strategy: **{selected_strategy_name}** | TF: {timeframe} | Entry: {entry_type}")

    else:
        # ── OLD LAYOUT (multi-section with subheaders) ────────────────────────
        st.subheader("Backtest Parameters")

        selected_strategy_name = st.selectbox("Select Strategy", options=list(strategy_options.keys()))
        selected_strategy = strategy_options[selected_strategy_name]
        params = get_strategy_parameters(selected_strategy)
        entry_type = params.get('entry_type', 'time')
        is_pattern = entry_type == 'pattern'
        strategy_symbols = params.get('symbols', [])
        strategy_timeframe = params.get('timeframe', 'M5')

        col1, col2, col3 = st.columns(3)
        with col1:
            use_custom_symbol = st.checkbox("Custom symbol", value=False)
            if use_custom_symbol:
                symbol = st.text_input("Symbol", value=os.getenv("SYMBOL", "XAUUSD"))
            elif strategy_symbols:
                symbol = st.selectbox("Symbol", options=strategy_symbols)
            else:
                symbol = st.text_input("Symbol", value=os.getenv("SYMBOL", "XAUUSD"))
            start_date = st.date_input("Start Date", value=default_start, max_value=default_end)

        with col2:
            end_date = st.date_input("End Date", value=default_end, max_value=default_end)
            if is_pattern:
                st.markdown("**FEG Filter Margins**")
                ema_period = st.number_input("EMA Period", value=int(params.get('ema_period', 21)),
                                             min_value=2, max_value=200)
                h2_exceed_pips = st.number_input(
                    "H2 > H1 + N pips", value=float(params.get('h2_exceed_pips', 0.0)),
                    min_value=0.0, step=1.0,
                    help="SELL: H2 phải vượt H1 thêm N pips | BUY: L2 phải thấp hơn L1 thêm N pips")
                st.caption(_pip_caption(h2_exceed_pips, symbol))
                c2_gap_pips = st.number_input(
                    "C2 vượt L1/H1 + N pips", value=float(params.get('c2_gap_pips', 0.0)),
                    min_value=0.0, step=1.0,
                    help="SELL: C2 phải đóng thấp hơn L1 thêm N pips | BUY: C2 phải đóng cao hơn H1 thêm N pips")
                st.caption(_pip_caption(c2_gap_pips, symbol))
                ema_margin_pips = st.number_input(
                    "L2/H2 cách EMA + N pips", value=float(params.get('ema_margin_pips', 0.0)),
                    min_value=0.0, step=1.0,
                    help="SELL: L2 phải cách EMA ≥ N pips | BUY: H2 phải cách EMA ≥ N pips")
                st.caption(_pip_caption(ema_margin_pips, symbol))
                entry_time = datetime.strptime("00:00", "%H:%M").time()
            else:
                ema_period = int(params.get('ema_period', 21))
                h2_exceed_pips = 0.0
                c2_gap_pips = 0.0
                ema_margin_pips = 0.0
                entry_time_str = params.get('entry_time', '21:05')
                use_custom_time = st.checkbox("Custom entry time", value=False)
                if use_custom_time:
                    raw = st.text_input("Entry Time", value="21:05", max_chars=5, placeholder="HH:MM")
                    try:
                        entry_time = datetime.strptime(raw, "%H:%M").time()
                    except ValueError:
                        st.error("Invalid time format. Use HH:MM (e.g., 21:05)")
                        entry_time = datetime.strptime("21:05", "%H:%M").time()
                else:
                    entry_time = st.time_input("Entry Time",
                                               value=datetime.strptime(entry_time_str, "%H:%M").time(),
                                               step=300, disabled=True,
                                               help=f"From strategy: {entry_time_str}")
                    st.caption(f"Strategy default: {entry_time_str}")

        with col3:
            timeframe_options = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
            use_custom_timeframe = st.checkbox("Custom timeframe", value=False)
            if use_custom_timeframe:
                timeframe = st.selectbox("Timeframe", options=timeframe_options,
                                         index=timeframe_options.index(strategy_timeframe))
            else:
                timeframe = strategy_timeframe
                st.selectbox("Timeframe", options=[strategy_timeframe], disabled=True)
                st.caption(f"Strategy default: {strategy_timeframe}")
            rr_ratio = st.number_input("RR Ratio", value=float(params.get('rr_ratio', 2.0)),
                                       min_value=0.5, max_value=10.0, step=0.5)
            use_max_candles = st.checkbox("Enable Max Candles", value=True,
                                          help="Uncheck to disable time-based exit (only TP/SL)")
            if use_max_candles:
                max_candles = st.number_input("Max Candles", value=int(params.get('max_candles', 7)),
                                              min_value=1, max_value=50)
            else:
                max_candles = 0
                st.caption("Time exit disabled - trades exit only on TP or SL")

        st.caption(f"Strategy: **{selected_strategy_name}** | Timeframe: {timeframe}")
        st.divider()

        st.subheader("Entry Time Window")
        tw_col1, tw_col2 = st.columns(2)
        with tw_col1:
            entry_start_time = st.time_input("Entry Start Time (HCM)", value=time(0, 0),
                                             help="Only enter new positions at or after this time. Default 00:00 = no filter.")
        with tw_col2:
            entry_end_time = st.time_input("Entry End Time (HCM)", value=time(23, 59),
                                           help="Only enter new positions at or before this time. Default 23:59 = no filter.")
        st.caption("Active trade continues holding if window ends. Window only gates new entries.")
        st.divider()

        st.subheader("Entry")
        col1, col2 = st.columns(2)
        col1, col2, col3 = st.columns(3)
        with col1:
            entry_mode = st.radio("Entry Mode", options=["close", "range_percent"],
                                  format_func=lambda x: "Close Price" if x == "close" else "Body Percent (%)",
                                  horizontal=True,
                                  help="Close: Enter at candle close | Body %: Enter at % of candle body")
        with col2:
            if entry_mode == "range_percent":
                entry_percent = st.number_input("Entry Percent (%)", value=30.0,
                                                min_value=0.0, max_value=100.0, step=5.0)
                st.caption(f"BUY: Close - {entry_percent}%(body) | SELL: Close + {entry_percent}%(body)")
            else:
                entry_percent = 0.0
                st.caption("Entry at candle Close price")
        with col3:
            limit_order_candles = st.number_input(
                "Chờ khớp lệnh (nến)", value=1, min_value=1, max_value=100,
                help="Số nến tối đa chờ limit order khớp. 1 = khớp ngay nến tiếp theo nếu giá chạm entry.")
        st.divider()

        st.subheader("Exit Types")
        col1, col2 = st.columns(2)
        with col1:
            tp_type = st.radio("Take Profit (TP) Exit", options=["price_based", "close_based"],
                               format_func=lambda x: "Price-based (Immediate)" if x == "price_based" else "Close-based (Delayed)",
                               horizontal=True,
                               help="Price-based: Exit when wick touches TP | Close-based: Exit when candle closes beyond TP")
            if tp_type == "price_based":
                st.caption("TP triggers when High/Low touches TP level (exits at TP price)")
            else:
                st.caption("TP triggers when candle CLOSES beyond TP (exits at close price)")
        with col2:
            sl_type = st.radio("Stop Loss (SL) Exit", options=["price_based", "close_based"],
                               format_func=lambda x: "Price-based (Immediate)" if x == "price_based" else "Close-based (Delayed)",
                               horizontal=True,
                               help="Price-based: Exit when wick touches SL | Close-based: Exit when candle closes beyond SL")
            if sl_type == "price_based":
                st.caption("SL triggers when High/Low touches SL level (exits at SL price)")
            else:
                st.caption("SL triggers when candle CLOSES beyond SL (exits at close price)")
        bcol1, bcol2, bcol3 = st.columns(3)
        with bcol1:
            be_enabled = st.checkbox("Break-Even (BE)", value=False,
                                     help="Dời SL về entry khi lời đủ be_r × SL distance")
        with bcol2:
            be_r = st.number_input("BE Trigger (R)", value=1.0, min_value=0.1, max_value=10.0,
                                   step=0.1, format="%.1f",
                                   help="BE kích hoạt khi lời đạt be_r × SL distance",
                                   disabled=not be_enabled)
        with bcol3:
            re_entry_after_sl = st.checkbox("Re-Entry After SL", value=False,
                                            help="Trong lúc lệnh đang chạy, vẫn scan signal song song. "
                                                 "Nếu SL hit đúng tại candle2 của signal mới → vào lệnh tiếp ngay.")
        wkcol1, wkcol2, wkcol3 = st.columns(3)
        with wkcol1:
            c2_wick_filter_enabled = st.checkbox("C2 Wick Filter", value=False,
                                                 help="Râu nến C2 phải nhỏ hơn n% body C2. "
                                                      "SELL: râu dưới (close-low) < body×n%. BUY: râu trên (high-close) < body×n%.")
        with wkcol2:
            c2_wick_max_percent = st.number_input("Wick Max % of Body", value=30.0,
                                                  min_value=1.0, max_value=200.0, step=1.0, format="%.0f",
                                                  help="Ngưỡng tối đa của râu so với body C2 (%)",
                                                  disabled=not c2_wick_filter_enabled)
        st.divider()

        st.subheader("Lot Size")
        lot_mode = st.radio("Lot Size Mode", options=["fixed", "flex"],
                            format_func=lambda x: "Fixed" if x == "fixed" else "Flex (Risk-based)",
                            horizontal=True,
                            help="Fixed: manual lot size | Flex: calculated from risk % and SL distance")
        col1, col2 = st.columns(2)
        with col1:
            buffer_k = st.number_input("Buffer K (pips)", value=float(params.get('buffer_k', 5)),
                                       min_value=0.0, max_value=200.0, step=1.0,
                                       help="SL = candle body + k pips")
        st.caption("SL pips = (Close - Low) + k for BUY, (High - Close) + k for SELL")
        if lot_mode == "fixed":
            with col2:
                fixed_lot = st.number_input("Lot Size", value=float(params.get('lot_size', 0.01)),
                                            min_value=0.01, max_value=10.0, step=0.01, format="%.2f")
            risk_percent = 0.5
            risk_amount = 0.0
            risk_mode = "percent"
            starting_equity = 1000.0
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                starting_equity = st.number_input("Starting Equity (USD)", value=1000.0,
                                                  min_value=100.0, max_value=1000000.0, step=100.0)
            with col2:
                risk_mode = st.radio("Risk Mode", options=["percent", "fixed_amount"],
                                     format_func=lambda x: "Percentage (%)" if x == "percent" else "Fixed Amount ($)",
                                     horizontal=True)
            with col3:
                if risk_mode == "percent":
                    risk_percent = st.number_input("Risk per Trade (%)", value=0.5, min_value=0.1,
                                                   max_value=5.0, step=0.1, format="%.1f")
                    risk_amount = 0.0
                    example_r = starting_equity * (risk_percent / 100)
                    st.caption(f"Initial: ${starting_equity:.0f} × {risk_percent}% = ${example_r:.2f}/trade")
                else:
                    risk_amount = st.number_input("Risk per Trade ($)", value=5.0, min_value=1.0,
                                                  max_value=1000.0, step=1.0, format="%.2f")
                    risk_percent = 0.0
                    st.caption(f"Constant ${risk_amount:.2f} risk per trade")
            fixed_lot = 0.01
        st.divider()

    sl_pips = 0  # always calculated from candle + buffer_k

    # Run backtest button
    if st.button("Run Backtest", type="primary", use_container_width=True):
        try:
            with st.spinner("Fetching historical data..."):
                # Convert dates to datetime
                start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=TIMEZONE)
                end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=TIMEZONE)

                # Fetch data
                df, error = fetch_historical_data(symbol, start_dt, end_dt, user_creds, timeframe)

                if error:
                    st.error(f"Failed to fetch data: {error}")
                    st.stop()

                if df is None or df.empty:
                    st.warning("No data found for the selected period")
                    st.stop()

                st.success(f"Fetched {len(df)} candles")

            with st.spinner("Running backtest..."):
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
                    entry_percent=entry_percent,
                    entry_type=entry_type,
                    ema_period=ema_period,
                    h2_exceed_pips=h2_exceed_pips,
                    c2_gap_pips=c2_gap_pips,
                    ema_margin_pips=ema_margin_pips,
                    entry_start_time=entry_start_time,
                    entry_end_time=entry_end_time,
                    limit_order_candles=int(limit_order_candles),
                    be_enabled=be_enabled,
                    be_r=be_r,
                    strategy=selected_strategy,
                    ema_filter_enabled=ema_filter_enabled,
                    buy_ema_side=buy_ema_side,
                    sell_ema_side=sell_ema_side,
                    re_entry_after_sl=re_entry_after_sl,
                    c2_wick_filter_enabled=c2_wick_filter_enabled,
                    c2_wick_max_percent=c2_wick_max_percent,
                )

            # Build config dict for export/history
            backtest_config = {
                'timeframe': timeframe,
                'start_date': str(start_date),
                'end_date': str(end_date),
                'entry_time': entry_time.strftime('%H:%M'),
                'entry_start_time': entry_start_time.strftime('%H:%M'),
                'entry_end_time': entry_end_time.strftime('%H:%M'),
                'entry_mode': entry_mode,
                'entry_percent': entry_percent,
                'rr_ratio': rr_ratio,
                'max_candles': max_candles,
                'buffer_k': buffer_k,
                'lot_mode': lot_mode,
                'tp_type': tp_type,
                'sl_type': sl_type,
                'entry_type': entry_type,
                'ema_period': ema_period,
                'h2_exceed_pips': h2_exceed_pips,
                'c2_gap_pips': c2_gap_pips,
                'ema_margin_pips': ema_margin_pips,
                'limit_order_candles': int(limit_order_candles),
                'be_enabled': be_enabled,
                'be_r': be_r,
                're_entry_after_sl': re_entry_after_sl,
                'c2_wick_filter_enabled': c2_wick_filter_enabled,
                'c2_wick_max_percent': c2_wick_max_percent,
            }

            if lot_mode == 'fixed':
                backtest_config['fixed_lot'] = fixed_lot
            else:
                backtest_config['starting_equity'] = starting_equity
                backtest_config['risk_mode'] = risk_mode
                backtest_config['risk_percent'] = risk_percent
                backtest_config['risk_amount'] = risk_amount

            # Store results in session state
            st.session_state['backtest_results'] = results
            st.session_state['backtest_symbol'] = symbol
            st.session_state['backtest_strategy'] = selected_strategy_name
            st.session_state['backtest_lot_mode'] = lot_mode
            st.session_state['backtest_timeframe'] = timeframe
            st.session_state['backtest_tp_type'] = tp_type
            st.session_state['backtest_sl_type'] = sl_type
            st.session_state['backtest_config'] = backtest_config

            # Auto-save to history
            if results.get('total_trades', 0) > 0:
                save_backtest_result(
                    config=backtest_config,
                    results=results,
                    strategy_name=selected_strategy_name,
                    symbol=symbol
                )

        except Exception as e:
            report_page_error(e, f"Backtest / {selected_strategy} / {symbol}")
            st.error(f"Lỗi khi chạy backtest: {type(e).__name__}: {e}")

    # Display results if available
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
    try:
        show_history_section()
    except Exception as e:
        report_page_error(e, "Backtest / show_history_section")
        st.error(f"Lỗi hiển thị history: {type(e).__name__}: {e}")


def display_results(results: dict, symbol: str, strategy_name: str = "", lot_mode: str = "fixed", timeframe: str = "M5", tp_type: str = "price_based", sl_type: str = "close_based", config: dict = None):
    """Display backtest results"""
    config = config or {}

    st.divider()
    run_id = results.get("run_id", "")
    header_col, id_col = st.columns([3, 2])
    with header_col:
        st.subheader(f"Results: {strategy_name}" if strategy_name else "Results")
    with id_col:
        if run_id:
            st.markdown(f"**Backtest ID**")
            st.code(run_id, language=None)

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
            show_trade_table(trades, lot_mode, strategy_name, symbol, config, results)
        else:
            show_interactive_chart(trades, ohlc_data, symbol)


def show_trade_table(trades: list, lot_mode: str, strategy_name: str, symbol: str, config: dict = None, results: dict = None):
    """Show trades as a table"""
    config = config or {}
    results = results or {}
    trades_df = pd.DataFrame(trades)

    # Drop internal debug columns (underscore-prefixed) before display/export
    trades_df = trades_df[[c for c in trades_df.columns if not c.startswith("_")]]

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

    # Download buttons
    filename_parts = [strategy_name.replace(' ', '_')] if strategy_name else []
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

    # Indicator toggles
    ema_cols = [c for c in ohlc_data.columns if c.startswith("ema")]
    show_ema = {}
    if ema_cols:
        with st.expander("Indicators", expanded=False):
            cols = st.columns(min(len(ema_cols), 4))
            for i, col_name in enumerate(ema_cols):
                period = col_name.replace("ema", "")
                show_ema[col_name] = cols[i % 4].checkbox(f"EMA{period}", value=True, key=f"ind_{col_name}")

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

    # EMA overlays
    ema_colors = {"ema21": "#FF6B00", "ema9": "#9B59B6", "ema50": "#3498DB", "ema200": "#E74C3C"}
    for col_name, enabled in show_ema.items():
        if enabled and col_name in chart_data.columns:
            period = col_name.replace("ema", "")
            color = ema_colors.get(col_name, "#888888")
            fig.add_trace(go.Scatter(
                x=chart_data['time'],
                y=chart_data[col_name],
                mode='lines',
                line=dict(color=color, width=1.5),
                name=f"EMA{period}",
                legendgroup=col_name
            ))

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


def show_history_section():
    """Show backtest history for comparison"""

    st.divider()
    st.subheader("Backtest History")

    history = get_history()

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
            options=['Date', 'Win %', 'Total USD', 'Trades'],
            index=0,
            key="history_sort"
        )

    # Optional columns selector
    with st.expander("Customize Columns"):
        st.caption("Select additional columns to display")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Config Columns**")
            selected_config = st.multiselect(
                "Config",
                options=HISTORY_COLUMNS['config'],
                default=HISTORY_COLUMNS['default_optional'],
                key="history_config_cols",
                label_visibility="collapsed"
            )

        with col2:
            st.markdown("**Summary Columns**")
            selected_summary = st.multiselect(
                "Summary",
                options=HISTORY_COLUMNS['summary'],
                default=[],
                key="history_summary_cols",
                label_visibility="collapsed"
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

    # Build display columns: core + selected optional
    display_cols = HISTORY_COLUMNS['core'].copy()

    # Insert config columns after Symbol
    for col in selected_config:
        if col not in display_cols:
            display_cols.append(col)

    # Add summary columns at the end
    for col in selected_summary:
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
    if 'Win %' in display_df.columns:
        style_subsets.append(('Win %', color_win_rate))
    if 'Total Pips' in display_df.columns:
        style_subsets.append(('Total Pips', color_pips))
    if 'Total USD' in display_df.columns:
        style_subsets.append(('Total USD', color_pips))
    if 'Avg Pips' in display_df.columns:
        style_subsets.append(('Avg Pips', color_pips))

    # Format số thập phân tại tầng display
    fmt = {}
    for col in ['Win %', 'Total USD', 'RR', 'Entry %', 'K', 'Risk %']:
        if col in display_df.columns:
            fmt[col] = '{:.1f}'
    for col in ['Fixed Lot']:
        if col in display_df.columns:
            fmt[col] = '{:.2f}'

    styled_history = display_df.style.format(fmt, na_rep='')
    for col, func in style_subsets:
        styled_history = styled_history.map(func, subset=[col])

    st.dataframe(styled_history, use_container_width=True, hide_index=True)

    st.caption(f"Showing {len(filtered_df)} of {len(history_df)} records | {len(display_cols)} columns")

    # Reuse / Manage History
    st.markdown("---")

    with st.expander("Reuse Config"):
        reuse_options = {
            f"{r['ID']} | {r.get('Date', '')} | {r.get('Strategy', '')} | {r.get('Symbol', '')} | Win {r['Win %']}%": r['ID']
            for _, r in filtered_df.iterrows()
        }
        if reuse_options:
            selected_reuse = st.selectbox("Chọn backtest để load config", options=list(reuse_options.keys()),
                                          key="reuse_record_select")
            record_id = reuse_options[selected_reuse]
            from src.backtest_history import get_history_record
            record = get_history_record(record_id)

            col_load, col_dl = st.columns([1, 1])
            with col_load:
                if st.button("Load Config", type="primary", key="btn_reuse_config"):
                    if record:
                        cfg = dict(record['config'])
                        # migrate legacy keys
                        if 'ema_dist_pips' in cfg and 'ema_margin_pips' not in cfg:
                            cfg['ema_margin_pips'] = cfg.pop('ema_dist_pips')
                        cfg.pop('ema_dist_enabled', None)
                        st.session_state['backtest_prefill'] = cfg
                        st.success(f"Đã load config từ {record_id} — scroll lên để xem params.")
                        st.rerun()
            with col_dl:
                if record:
                    import json as _json
                    st.download_button(
                        label="Download JSON",
                        data=_json.dumps(record, indent=2, ensure_ascii=False),
                        file_name=f"record_{record_id}.json",
                        mime="application/json",
                        key="btn_download_config",
                    )
        else:
            st.info("Không có record nào để reuse.")

    with st.expander("Manage History"):
        st.warning("Delete records from history")

        # Select record to delete
        record_options = {
            f"{r['Date']} - {r['Strategy']} - {r['Symbol']} ({r['Win %']}% WR)": r['ID']
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
