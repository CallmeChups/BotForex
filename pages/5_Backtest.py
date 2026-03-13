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
from src.backtest_multi import run_backtest_multi
from src.utils import is_mt5_available
from src.strategy_manager import list_strategies, get_strategy_parameters
from src.i18n import t, lang_toggle_button
from src.backtest_history import (
    save_backtest_result,
    get_history,
    delete_history_record,
    history_to_dataframe,
    create_excel_export,
    HISTORY_COLUMNS
)

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


# ── Cached data loaders ──
@st.cache_data(ttl=30)
def _cached_strategies():
    return list_strategies()

@st.cache_data(ttl=30)
def _cached_strategy_params(strategy_id):
    return get_strategy_parameters(strategy_id)


def main():
    lang_toggle_button(st.sidebar)
    st.title(t("page_title"))

    now = datetime.now(TIMEZONE)
    st.markdown(f"**{t('current_time')}:** {now.strftime('%H:%M:%S %d/%m/%Y')} (HCM)")

    st.divider()

    # Check MT5 availability
    if not is_mt5_available():
        st.error(t("no_mt5"))
        show_demo_results()
        return

    # Check if user has MT5 credentials
    if not has_mt5_credentials(username):
        st.warning(t("no_credentials"))
        st.page_link("pages/8_Settings.py", label=t("go_settings"), icon="⚙️")
        show_demo_results()
        return

    # Get user credentials
    user_creds = get_user_mt5_credentials(username)

    # Get available strategies (cached)
    strategies = _cached_strategies()
    enabled_strategies = [s for s in strategies if s.get('enabled', True)]

    if not enabled_strategies:
        st.warning(t("no_strategies"))
        st.page_link("pages/4_Strategies.py", label=t("go_strategies"), icon="📖")
        show_demo_results()
        return

    # Strategy selection
    strategy_options = {s['name']: s['id'] for s in enabled_strategies}
    selected_strategy_name = st.selectbox(
        t("strategy"),
        options=list(strategy_options.keys())
    )
    selected_strategy = strategy_options[selected_strategy_name]
    params = _cached_strategy_params(selected_strategy)
    is_multi_strategy = params.get('window_start') is not None

    st.divider()

    # Config fragment (isolated reruns)
    show_backtest_config(params, selected_strategy_name, user_creds, now, is_multi_strategy)

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


def _apply_bt_preset(config: dict):
    """Queue a preset to be applied on next rerun (before widgets render).

    Cannot write to widget keys after widgets are instantiated in the same
    script run. Instead, store the config as 'pending' and st.rerun().
    The show_backtest_config fragment picks it up before creating widgets.
    """
    st.session_state['bt_preset_pending'] = config


def _flush_pending_preset():
    """Apply pending preset into widget keys. Call BEFORE any widget is created.

    Streamlit allows writing to session_state keys before the widget with that
    key is instantiated — so this must run at the top of the fragment.
    """
    config = st.session_state.pop('bt_preset_pending', None)
    if config is None:
        return

    # Also store raw config for any non-widget reads (first-render defaults)
    st.session_state['bt_preset'] = config

    widget_map = {
        'timeframe':                    'bt_w_timeframe',
        'entry_time':                   'bt_w_entry_time',
        'window_start':                 'bt_w_window_start',
        'window_end':                   'bt_w_window_end',
        'priority_direction':           'bt_w_priority_dir',
        'entry_mode':                   'bt_w_entry_mode',
        'rr_ratio':                     'bt_w_rr_ratio',
        'buffer_k':                     'bt_w_buffer_k',
        'entry_percent':                'bt_w_entry_pct',
        'pending_order_expire_candles': 'bt_w_expire_candles',
        'tp_type':                      'bt_w_tp_type',
        'sl_type':                      'bt_w_sl_type',
        'max_candles':                  'bt_w_max_candles_val',
        'move_sl_to_breakeven':         'bt_be',
        'breakeven_trigger_percent':    'bt_w_be_trigger',
        'breakeven_target':             'bt_be_target',
        'lot_mode':                     'bt_w_lot_mode',
        'fixed_lot':                    'bt_w_fixed_lot',
        'starting_equity':              'bt_w_equity',
        'risk_mode':                    'bt_w_risk_mode',
        'risk_percent':                 'bt_w_risk_pct',
        'risk_amount':                  'bt_w_risk_amt',
        'risk_compounding':             'bt_w_compounding',
    }

    for cfg_key, widget_key in widget_map.items():
        if cfg_key in config and config[cfg_key] is not None:
            st.session_state[widget_key] = config[cfg_key]

    # Special handling: max_candles checkbox
    mc = config.get('max_candles')
    if mc is not None:
        st.session_state['bt_max_c'] = (mc > 0)
        if mc > 0:
            st.session_state['bt_w_max_candles_val'] = int(mc)


@st.fragment
def show_backtest_config(params, selected_strategy_name, user_creds, now, is_multi_strategy=False):
    """Backtest config widgets — no dynamic computation, stable widget tree"""

    # Flush any pending preset into widget keys BEFORE widgets are created
    _flush_pending_preset()

    symbol_help = (
        "Pip info per symbol:\n"
        "XAUUSD: pip=0.01, $10/pip/lot | BTCUSDm: pip=1, $1/pip/lot\n"
        "ETHUSD: pip=0.01, $0.01/pip/lot | EURUSD: pip=0.0001, $10/pip/lot\n"
        "USDJPY: pip=0.01, ~$6.67/pip/lot | AUDUSD: pip=0.0001, $10/pip/lot"
    )
    buffer_help = (
        "Extra points beyond candle wick for SL.\n"
        "XAUUSD: 1pt=0.01 (5pts=$0.05) | BTCUSD: 1pt=1 (50pts=$50)\n"
        "EURUSD: 1pt=0.00001 (50pts=$0.0005)"
    )

    # Read preset (if any was loaded from history)
    preset = st.session_state.get('bt_preset', {})

    # ── SECTION 1: Market ──
    st.markdown(f"**{t('section_market')}**")
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        strategy_symbols = params.get('symbols', [])
        if strategy_symbols:
            symbol = st.selectbox(t("symbol") + "*", options=strategy_symbols, help=symbol_help)
        else:
            symbol = st.text_input(t("symbol") + "*", value="XAUUSD", help=symbol_help)

    with col2:
        strategy_timeframe = params.get('timeframe', 'M5')
        tf_options = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
        preset_tf = preset.get('timeframe', strategy_timeframe)
        tf_idx = tf_options.index(preset_tf) if preset_tf in tf_options else (tf_options.index(strategy_timeframe) if strategy_timeframe in tf_options else 1)
        timeframe = st.selectbox(t("timeframe"), options=tf_options, index=tf_idx, key="bt_w_timeframe")

    with col3:
        if is_multi_strategy:
            ws_str = preset.get('window_start', params.get('window_start', '09:00'))
            window_start_input = st.text_input("Window Start", value=ws_str, max_chars=5, help="HH:MM - scan window start", key="bt_w_window_start")
            try:
                ws_time = datetime.strptime(window_start_input, "%H:%M").time()
            except ValueError:
                ws_time = datetime.strptime("09:00", "%H:%M").time()
            entry_times = []  # not used for multi strategy
        else:
            entry_time_str = preset.get('entry_time', params.get('entry_time', '21:05'))
            entry_time_input = st.text_input(t("entry_time"), value=entry_time_str, max_chars=5, help="HH:MM format", key="bt_w_entry_time")
            try:
                entry_times = [datetime.strptime(entry_time_input, "%H:%M").time()]
            except ValueError:
                entry_times = [datetime.strptime("21:05", "%H:%M").time()]

    # Date range
    col1, col2 = st.columns(2)
    default_end = now.date()
    default_start = default_end - timedelta(days=30)

    with col1:
        start_date = st.date_input(t("start_date"), value=default_start, max_value=default_end)
    with col2:
        end_date = st.date_input(t("end_date"), value=default_end, max_value=default_end)

    if is_multi_strategy:
        # Window end + priority direction fields
        col1, col2 = st.columns(2)
        with col1:
            we_str = preset.get('window_end', params.get('window_end', '11:00'))
            window_end_input = st.text_input("Window End", value=we_str, max_chars=5, help="HH:MM - scan window end", key="bt_w_window_end")
            try:
                we_time = datetime.strptime(window_end_input, "%H:%M").time()
            except ValueError:
                we_time = datetime.strptime("11:00", "%H:%M").time()
        with col2:
            pd_options = ["auto", "BUY", "SELL"]
            pd_default = preset.get('priority_direction', params.get('priority_direction', 'auto'))
            pd_idx = pd_options.index(pd_default) if pd_default in pd_options else 0
            priority_direction = st.selectbox("Priority Direction", options=pd_options, index=pd_idx,
                                              help="Force BUY/SELL or auto-detect from master candle", key="bt_w_priority_dir")
    else:
        # Batch entry times
        with st.expander(t("batch_entry_times")):
            batch_str = st.text_input(t("batch_comma_times"), value="21:05, 22:00, 23:00",
                                      help="Creates one backtest per time")
            use_batch = st.checkbox(t("batch_enable"), value=False, key="bt_batch")
            if use_batch:
                entry_times = []
                for _t in batch_str.split(','):
                    _t = _t.strip()
                    try:
                        entry_times.append(datetime.strptime(_t, "%H:%M").time())
                    except ValueError:
                        pass
                if not entry_times:
                    entry_times = [datetime.strptime("21:05", "%H:%M").time()]

    st.divider()

    # ── SECTION 2: Trade Setup ──
    st.markdown(f"**{t('section_trade_setup')}**")
    col1, col2, col3 = st.columns(3)

    with col1:
        entry_mode_options = ["close", "range_percent"]
        preset_entry_mode = preset.get('entry_mode', 'close')
        entry_mode_idx = entry_mode_options.index(preset_entry_mode) if preset_entry_mode in entry_mode_options else 0
        entry_mode = st.radio(
            t("entry_mode"), options=entry_mode_options,
            format_func=lambda x: t("entry_mode_close") if x == "close" else t("entry_mode_range"),
            horizontal=True,
            index=entry_mode_idx,
            help="Close: enter at candle close | Range %: LIMIT at % retracement",
            key="bt_w_entry_mode"
        )
    with col2:
        rr_ratio = st.number_input(
            t("rr_ratio"), value=float(preset.get('rr_ratio', params.get('rr_ratio', 2.0))),
            min_value=0.5, max_value=10.0, step=0.5, key="bt_w_rr_ratio"
        )
    with col3:
        buffer_k = st.number_input(
            t("buffer_k"), value=float(preset.get('buffer_k', 5.0)),
            min_value=0.0, max_value=1000.0, step=1.0, help=buffer_help, key="bt_w_buffer_k"
        )

    # Range percent fields (always shown — ignored when entry_mode is "close")
    col1, col2 = st.columns(2)
    with col1:
        entry_percent = st.number_input(
            t("entry_percent"), value=float(preset.get('entry_percent', 30.0)),
            min_value=0.0, max_value=100.0, step=5.0,
            help="Range Percent only. BUY: Close - X%(body) | SELL: Close + X%(body)",
            key="bt_w_entry_pct"
        )
    with col2:
        pending_order_expire_candles = st.number_input(
            t("expire_candles"), value=int(preset.get('pending_order_expire_candles', 0)),
            min_value=0, max_value=50, step=1,
            help="Range Percent only. Cancel LIMIT if not filled after N candles (0=wait forever)",
            key="bt_w_expire_candles"
        )

    # ── SECTION 3: Exit Rules ──
    with st.expander(t("section_exit_rules"), expanded=True):
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            tp_type_options = ["price_based", "close_based"]
            preset_tp = preset.get('tp_type', 'price_based')
            tp_type_idx = tp_type_options.index(preset_tp) if preset_tp in tp_type_options else 0
            tp_type = st.radio(
                t("tp_type"), options=tp_type_options,
                format_func=lambda x: t("tp_price") if x == "price_based" else t("tp_close"),
                index=tp_type_idx,
                help="Price: exit when wick touches TP | Close: exit when candle closes beyond TP",
                key="bt_w_tp_type"
            )

        with col2:
            sl_type_options = ["close_based", "price_based"]
            preset_sl = preset.get('sl_type', 'close_based')
            sl_type_idx = sl_type_options.index(preset_sl) if preset_sl in sl_type_options else 0
            sl_type = st.radio(
                t("sl_type"), options=sl_type_options,
                format_func=lambda x: t("sl_close") if x == "close_based" else t("sl_price"),
                index=sl_type_idx,
                help="Close: exit when candle closes beyond SL | Price: exit when wick touches SL",
                key="bt_w_sl_type"
            )

        with col3:
            preset_max_c = preset.get('max_candles', None)
            use_max_candles = st.checkbox(t("max_candles"), value=True if preset_max_c is None or preset_max_c > 0 else False, key="bt_max_c")
            max_candles = st.number_input(
                t("max_candles_limit"), value=int(preset_max_c) if preset_max_c and preset_max_c > 0 else int(params.get('max_candles', 7)),
                min_value=1, max_value=50,
                help="Force close after N candles. Ignored if unchecked.",
                key="bt_w_max_candles_val"
            )
            if not use_max_candles:
                max_candles = 0

        with col4:
            preset_be = preset.get('move_sl_to_breakeven', False)
            move_sl_to_breakeven = st.checkbox(t("breakeven"), value=bool(preset_be), key="bt_be",
                                               help="Move SL when TP partially reached")
            breakeven_trigger_percent = st.number_input(
                t("breakeven_trigger"), value=float(preset.get('breakeven_trigger_percent') or 50.0),
                min_value=10.0, max_value=90.0, step=5.0,
                help="Move SL at this % of TP. Only if Breakeven ON.",
                key="bt_w_be_trigger"
            )
            be_target_options = ["entry", "close"]
            preset_be_target = preset.get('breakeven_target', 'entry') or 'entry'
            be_target_idx = be_target_options.index(preset_be_target) if preset_be_target in be_target_options else 0
            breakeven_target = st.radio(
                t("breakeven_sl_target"), options=be_target_options,
                format_func=lambda x: t("breakeven_entry") if x == "entry" else t("breakeven_close"),
                horizontal=True, key="bt_be_target", index=be_target_idx,
                help="'Candle Close' useful for Range % mode. Only if Breakeven ON."
            )

    # ── SECTION 4: Position Sizing ──
    with st.expander(t("section_position"), expanded=True):
        lot_mode_options = ["fixed", "flex"]
        preset_lot_mode = preset.get('lot_mode', 'fixed')
        lot_mode_idx = lot_mode_options.index(preset_lot_mode) if preset_lot_mode in lot_mode_options else 0
        lot_mode = st.radio(
            t("lot_mode"), options=lot_mode_options,
            format_func=lambda x: t("lot_fixed") if x == "fixed" else t("lot_flex"),
            horizontal=True, index=lot_mode_idx, key="bt_w_lot_mode"
        )

        # Fixed mode
        fixed_lot = st.number_input(
            t("lot_size"), value=float(preset.get('fixed_lot') or params.get('lot_size', 0.01)),
            min_value=0.01, max_value=10.0, step=0.01, format="%.2f",
            help="Fixed mode only.", key="bt_w_fixed_lot"
        )

        # Flex mode fields (always shown)
        col1, col2, col3 = st.columns(3)
        with col1:
            starting_equity = st.number_input(
                t("starting_equity"), value=float(preset.get('starting_equity') or 1000.0),
                min_value=100.0, max_value=1000000.0, step=100.0,
                help="Flex mode only.", key="bt_w_equity"
            )
        with col2:
            risk_mode_options = ["percent", "fixed_amount"]
            preset_risk_mode = preset.get('risk_mode', 'percent') or 'percent'
            risk_mode_idx = risk_mode_options.index(preset_risk_mode) if preset_risk_mode in risk_mode_options else 0
            risk_mode = st.radio(
                t("risk_mode"), options=risk_mode_options,
                format_func=lambda x: t("risk_percent_label") if x == "percent" else t("risk_fixed_label"),
                horizontal=True, help="Flex mode only.", index=risk_mode_idx, key="bt_w_risk_mode"
            )
        with col3:
            risk_percent = st.number_input(
                t("risk_per_trade_pct"), value=float(preset.get('risk_percent') or 0.5),
                min_value=0.1, max_value=5.0, step=0.1, format="%.1f",
                help="Flex + % mode.", key="bt_w_risk_pct"
            )
            risk_amount = st.number_input(
                t("risk_per_trade_usd"), value=float(preset.get('risk_amount') or 5.0),
                min_value=1.0, max_value=1000.0, step=1.0, format="%.2f",
                help="Flex + Fixed $ mode.", key="bt_w_risk_amt"
            )

        risk_compounding = st.checkbox(t("compounding"), value=bool(preset.get('risk_compounding', True)),
                                       help="Flex only. ON: risk % of current equity | OFF: of starting equity",
                                       key="bt_w_compounding")

    sl_pips = 0

    # ── RUN BACKTEST ──
    st.divider()
    is_batch = len(entry_times) > 1
    button_label = t("run_batch", n=len(entry_times)) if is_batch else t("run_backtest")

    if st.button(button_label, type="primary", use_container_width=True):
        # Convert dates to datetime
        start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=TIMEZONE)
        end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=TIMEZONE)

        # Fetch data once (same timeframe for all entry times)
        with st.spinner(t("fetching_data")):
            df, error = fetch_historical_data(symbol, start_dt, end_dt, user_creds, timeframe)

            if error:
                st.error(t("failed_fetch", err=error))
                st.stop()

            if df is None or df.empty:
                st.warning(t("no_data"))
                st.stop()

            st.success(t("fetched_candles", n=len(df)))

        batch_results = []
        progress_bar = st.progress(0, text=t("starting_backtest"))

        if is_multi_strategy:
            progress_bar.progress(0.5, text="Running Multi Master Candle backtest...")
            results = run_backtest_multi(
                df=df,
                symbol=symbol,
                window_start_hour=ws_time.hour,
                window_start_minute=ws_time.minute,
                window_end_hour=we_time.hour,
                window_end_minute=we_time.minute,
                priority_direction=priority_direction,
                rr_ratio=rr_ratio,
                max_candles=max_candles,
                lot_mode=lot_mode,
                fixed_lot=fixed_lot if lot_mode == "fixed" else 0.01,
                risk_percent=risk_percent if lot_mode == "flex" else 0.5,
                risk_amount=risk_amount if lot_mode == "flex" else 0.0,
                risk_mode=risk_mode if lot_mode == "flex" else "percent",
                risk_compounding=risk_compounding if lot_mode == "flex" else True,
                buffer_k=buffer_k,
                starting_equity=starting_equity if lot_mode == "flex" else 1000.0,
                tp_type=tp_type,
                sl_type=sl_type,
                entry_mode=entry_mode,
                entry_percent=entry_percent if entry_mode == "range_percent" else 0.0,
                move_sl_to_breakeven=move_sl_to_breakeven,
                breakeven_trigger_percent=breakeven_trigger_percent if move_sl_to_breakeven else 50.0,
                breakeven_target=breakeven_target if move_sl_to_breakeven else "entry",
                pending_order_expire_candles=pending_order_expire_candles if entry_mode == "range_percent" else 0,
            )
            time_label = f"{window_start_input}-{window_end_input}"
            backtest_config = {
                'timeframe': timeframe,
                'start_date': str(start_date),
                'end_date': str(end_date),
                'window_start': window_start_input,
                'window_end': window_end_input,
                'priority_direction': priority_direction,
                'entry_mode': entry_mode,
                'entry_percent': entry_percent if entry_mode == "range_percent" else 0.0,
                'rr_ratio': rr_ratio,
                'max_candles': max_candles,
                'buffer_k': buffer_k,
                'lot_mode': lot_mode,
                'tp_type': tp_type,
                'sl_type': sl_type,
                'move_sl_to_breakeven': move_sl_to_breakeven,
                'breakeven_trigger_percent': breakeven_trigger_percent if move_sl_to_breakeven else None,
                'breakeven_target': breakeven_target if move_sl_to_breakeven else None,
                'pending_order_expire_candles': pending_order_expire_candles if entry_mode == "range_percent" else 0,
                'fixed_lot': fixed_lot if lot_mode == 'fixed' else None,
                'starting_equity': starting_equity if lot_mode == 'flex' else None,
                'risk_mode': risk_mode if lot_mode == 'flex' else None,
                'risk_percent': risk_percent if lot_mode == 'flex' else None,
                'risk_amount': risk_amount if lot_mode == 'flex' else None,
                'risk_compounding': risk_compounding if lot_mode == 'flex' else None,
            }
            if results.get('total_trades', 0) > 0:
                save_backtest_result(
                    config=backtest_config,
                    results=results,
                    strategy_name=selected_strategy_name,
                    symbol=symbol,
                    username=username,
                )
            batch_results.append({
                'entry_time': time_label,
                'results': results,
                'config': backtest_config,
            })

        for idx, entry_time in enumerate(entry_times):
            time_str = entry_time.strftime('%H:%M')
            progress_text = t("running_time", t=time_str, i=idx + 1, n=len(entry_times))
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
                fixed_lot=fixed_lot if lot_mode == "fixed" else 0.01,
                risk_percent=risk_percent if lot_mode == "flex" else 0.5,
                risk_amount=risk_amount if lot_mode == "flex" else 0.0,
                risk_mode=risk_mode if lot_mode == "flex" else "percent",
                risk_compounding=risk_compounding if lot_mode == "flex" else True,
                buffer_k=buffer_k,
                starting_equity=starting_equity if lot_mode == "flex" else 1000.0,
                tp_type=tp_type,
                sl_type=sl_type,
                entry_mode=entry_mode,
                entry_percent=entry_percent if entry_mode == "range_percent" else 0.0,
                move_sl_to_breakeven=move_sl_to_breakeven,
                breakeven_trigger_percent=breakeven_trigger_percent if move_sl_to_breakeven else 50.0,
                breakeven_target=breakeven_target if move_sl_to_breakeven else "entry",
                pending_order_expire_candles=pending_order_expire_candles if entry_mode == "range_percent" else 0
            )

            # Build config dict for export/history
            backtest_config = {
                'timeframe': timeframe,
                'start_date': str(start_date),
                'end_date': str(end_date),
                'entry_time': time_str,
                'entry_mode': entry_mode,
                'entry_percent': entry_percent if entry_mode == "range_percent" else 0.0,
                'rr_ratio': rr_ratio,
                'max_candles': max_candles,
                'buffer_k': buffer_k,
                'lot_mode': lot_mode,
                'tp_type': tp_type,
                'sl_type': sl_type,
                'move_sl_to_breakeven': move_sl_to_breakeven,
                'breakeven_trigger_percent': breakeven_trigger_percent if move_sl_to_breakeven else None,
                'breakeven_target': breakeven_target if move_sl_to_breakeven else None,
                'pending_order_expire_candles': pending_order_expire_candles if entry_mode == "range_percent" else 0,
                'fixed_lot': fixed_lot if lot_mode == 'fixed' else None,
                'starting_equity': starting_equity if lot_mode == 'flex' else None,
                'risk_mode': risk_mode if lot_mode == 'flex' else None,
                'risk_percent': risk_percent if lot_mode == 'flex' else None,
                'risk_amount': risk_amount if lot_mode == 'flex' else None,
                'risk_compounding': risk_compounding if lot_mode == 'flex' else None,
            }

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

        progress_bar.progress(1.0, text=t("complete"))

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
                st.success(t("batch_done", n=len(batch_results)))
            st.rerun(scope="app")


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
        if config.get('entry_mode') == 'range_percent' and config.get('pending_order_expire_candles', 0) > 0:
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
        'pnl_usd': 'P&L (USD)',
        'priority': 'Priority',
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

    # ── Load Config from History ──
    st.markdown("---")

    with st.expander(t("load_from_history"), expanded=False):
        st.caption(t("load_from_history_caption"))

        # Build ID → config lookup from raw history
        id_to_config = {r['id']: r['config'] for r in history}

        # Build display options from filtered records
        load_options = {
            f"{r['Date']} - {r['Strategy']} - {r['Symbol']} ({r['Win Rate %']}% WR | {r.get('Entry Mode', '')} {r.get('Entry %', '')}%)": r['ID']
            for _, r in filtered_df.iterrows()
        }

        if load_options:
            selected_load = st.selectbox(
                t("select_history_record"),
                options=list(load_options.keys()),
                key="load_config_select"
            )

            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button(t("load_config_btn"), type="primary"):
                    record_id = load_options[selected_load]
                    config_to_load = id_to_config.get(record_id)
                    if config_to_load:
                        _apply_bt_preset(config_to_load)
                        st.success(t("config_loaded"))
                        st.rerun()
                    else:
                        st.error(t("config_load_failed"))

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
