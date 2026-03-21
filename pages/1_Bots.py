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

from src.i18n import t, lang_toggle_button
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
from src.log_manager import read_log_tail, read_log_errors, get_log_files

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


# ── Cached data loaders (avoid re-reading files on every widget change) ──
@st.cache_data(ttl=10)
def _cached_bot_stats():
    return get_bot_stats()

@st.cache_data(ttl=30)
def _cached_list_bots(_refresh=True, _cleanup=False):
    return list_bots(refresh=_refresh, cleanup=_cleanup)

@st.cache_data(ttl=60)
def _cached_strategies():
    return list_strategies()

@st.cache_data(ttl=60)
def _cached_strategy_params(strategy_id):
    return get_strategy_parameters(strategy_id)

@st.cache_data(ttl=60)
def _cached_config_history(user):
    return get_config_history(username=user)

@st.cache_data(ttl=60)
def _build_preset_options(user):
    """Build preset options dict once — avoid rebuilding on every widget change"""
    from datetime import datetime
    history = get_config_history(username=user)
    all_bots = list_bots(refresh=False, cleanup=False)
    running_bots = [b for b in all_bots if b['user'] == user]

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
    return preset_options


def _apply_preset_to_session(config: dict):
    """Write config values to st.session_state['preset_*'] keys for form pre-fill"""
    mapping = {
        'strategy': 'preset_strategy',
        'symbol': 'preset_symbol',
        'timeframe': 'preset_timeframe',
        'entry_time': 'preset_entry_time',
        'entry_mode': 'preset_entry_mode',
        'entry_percent': 'preset_entry_percent',
        'pending_order_max_candles': 'preset_pending_order_max_candles',
        'pending_order_expire_candles': 'preset_pending_order_expire_candles',
        'rr_ratio': 'preset_rr_ratio',
        'buffer_k': 'preset_buffer_k',
        'tp_type': 'preset_tp_type',
        'sl_type': 'preset_sl_type',
        'max_candles': 'preset_max_candles',
        'move_sl_to_breakeven': 'preset_move_sl_to_breakeven',
        'breakeven_trigger_percent': 'preset_breakeven_trigger_percent',
        'breakeven_target': 'preset_breakeven_target',
        'lot_mode': 'preset_lot_mode',
        'lot_size': 'preset_lot_size',
        'starting_equity': 'preset_starting_equity',
        'risk_mode': 'preset_risk_mode',
        'risk_percent': 'preset_risk_percent',
        'risk_amount': 'preset_risk_amount',
        'risk_compounding': 'preset_risk_compounding',
        'window_start': 'preset_window_start',
        'window_end': 'preset_window_end',
        'priority_direction': 'preset_priority_direction',
    }
    for cfg_key, ss_key in mapping.items():
        if cfg_key in config and config[cfg_key] is not None:
            st.session_state[ss_key] = config[cfg_key]


def main():
    lang_toggle_button(st.sidebar)
    st.title(t("page_bots"))

    now = datetime.now(TIMEZONE)
    st.markdown(f"**{t('current_time')}:** {now.strftime('%H:%M:%S %d/%m/%Y')} (HCM)")

    st.divider()

    # Check MT5 credentials
    if not has_mt5_credentials(username):
        st.warning(t("no_credentials"))
        st.page_link("pages/8_Settings.py", label=t("go_settings"), icon="⚙️")

    # Stats overview (cached — refreshes every 10s)
    stats = _cached_bot_stats()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(t("running_bots"), stats['total'])
    with col2:
        st.metric(t("test_mode"), stats['test_mode'])
    with col3:
        st.metric(t("live_mode"), stats['live_mode'])
    with col4:
        st.metric(t("strategies_count"), len(stats['strategies']))

    st.divider()

    # Tabs
    tab1, tab2, tab3 = st.tabs([t("running_bots"), t("create_bot"), t("bot_history")])

    with tab1:
        show_running_bots()

    with tab2:
        show_create_bot()

    with tab3:
        show_bot_history()


@st.fragment
def show_running_bots():
    """Show list of running bots"""
    st.subheader(t("running_bots"))

    # Refresh button
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.button(t("refresh"), type="primary", width='stretch'):
            # Clear caches so next call fetches fresh data
            _cached_bot_stats.clear()
            _cached_list_bots.clear()
            st.rerun(scope="app")

    with col2:
        if st.button(t("stop_all"), type="secondary", width='stretch'):
            stopped, msg = stop_all_bots(user=username)
            _cached_bot_stats.clear()
            _cached_list_bots.clear()
            st.success(msg)
            st.rerun(scope="app")

    # List bots (cached — no OS calls on every widget change)
    bots = _cached_list_bots(_refresh=True, _cleanup=False)

    if not bots:
        st.info(t("no_bots_running"))
        return

    # Filter options
    with st.expander("Filters"):
        col1, col2 = st.columns(2)
        with col1:
            filter_user = st.checkbox(t("only_my_bots"), value=True)
        with col2:
            filter_test = st.selectbox(t("mode"), [t("all"), t("test_only"), t("live_only")])

    # Apply filters
    if filter_user:
        bots = [b for b in bots if b['user'] == username]

    if filter_test == t("test_only"):
        bots = [b for b in bots if b.get('test', True)]
    elif filter_test == t("live_only"):
        bots = [b for b in bots if not b.get('test', True)]

    if not bots:
        st.info(t("no_bots_match"))
        return

    st.success(t("found_bots", n=len(bots)))

    # Deduplicate by PID (in case running_bots.json has stale entries)
    seen_pids = set()
    unique_bots = []
    for bot in bots:
        pid = bot['pid']
        if pid not in seen_pids:
            seen_pids.add(pid)
            unique_bots.append(bot)
    bots = unique_bots

    # Display bots
    for idx, bot in enumerate(bots):
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

            with col1:
                mode_badge = "TEST" if bot.get('test', True) else "LIVE"
                tf = bot.get('timeframe', 'M5')
                if bot.get('window_start'):
                    entry = f"{bot['window_start']}→{bot['window_end']} ({bot.get('priority_direction', 'auto')})"
                else:
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
                    if st.button(t("stop_bot"), key=f"stop_{bot['pid']}_{idx}", type="secondary"):
                        success, msg = stop_bot(bot['pid'])
                        _cached_bot_stats.clear()
                        _cached_list_bots.clear()
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
                        st.rerun(scope="app")
                else:
                    st.button(t("stop_bot"), key=f"stop_{bot['pid']}_{idx}", disabled=True)

            with col3:
                if bot['user'] == username:
                    if st.button(t("restart_bot"), key=f"restart_{bot['pid']}_{idx}", type="secondary"):
                        success, msg, _ = restart_bot(bot['pid'])
                        _cached_bot_stats.clear()
                        _cached_list_bots.clear()
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
                        st.rerun(scope="app")
                else:
                    st.button(t("restart_bot"), key=f"restart_{bot['pid']}_{idx}", disabled=True)

            with col4:
                status_color = "green" if bot.get('status') == 'running' else "red"
                st.markdown(f":{status_color}[{bot.get('status', 'unknown').upper()}]")

            # Config details expander
            with st.expander(t("config_details"), expanded=False):
                _show_bot_config_details(bot)
                if bot['user'] == username:
                    if st.button(t("load_config"), key=f"load_running_{bot['pid']}_{idx}"):
                        _apply_preset_to_session(bot)
                        st.success(t("config_loaded"))
                        st.rerun(scope="app")

                # ── View Log ──
                log_path = bot.get("log_file", "")
                if log_path and os.path.isfile(log_path):
                    if st.button(t("view_log"), key=f"viewlog_{bot['pid']}_{idx}"):
                        st.session_state[f"show_log_{bot['pid']}"] = True

                    if st.session_state.get(f"show_log_{bot['pid']}"):
                        tail = read_log_tail(log_path, 100)
                        st.code(tail or "(empty log)", language="log")
                        with open(log_path, "r", encoding="utf-8", errors="replace") as _lf:
                            st.download_button(
                                t("download_log"),
                                data=_lf.read(),
                                file_name=os.path.basename(log_path),
                                mime="text/plain",
                                key=f"dl_log_{bot['pid']}_{idx}",
                            )

            st.divider()


def _show_bot_config_details(bot: dict):
    """Display full config details for a bot in a compact layout"""
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"**Strategy:** {bot.get('strategy', 'N/A')}")
        st.markdown(f"**Symbol:** {bot.get('symbol', 'N/A')}")
        st.markdown(f"**Timeframe:** {bot.get('timeframe', 'N/A')}")
        if bot.get('window_start'):
            st.markdown(f"**Window:** {bot.get('window_start')} → {bot.get('window_end')}")
            st.markdown(f"**Priority:** {bot.get('priority_direction', 'auto')}")
        else:
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


@st.fragment
def show_create_bot():
    """Show config widgets to create new bot — no st.form, no dynamic computation"""
    st.subheader("Create New Bot")

    # ── SIMPLE / ADVANCED MODE TOGGLE ──────────────────────────────────────
    mode_col, _ = st.columns([1, 3])
    with mode_col:
        ui_mode = st.radio(
            t("ui_mode_label"),
            options=[t("ui_mode_simple"), t("ui_mode_advanced")],
            horizontal=True,
            key="create_bot_ui_mode",
            help="Simple: chỉ hiện các cài đặt cốt lõi | Advanced: tất cả tùy chọn"
        )
    is_advanced = ui_mode == t("ui_mode_advanced")
    if not is_advanced:
        st.caption(f"💡 {t('simple_mode_hint')}")
    st.divider()

    # ── PRESET LOADER (data built once and cached, not rebuilt on every widget change) ──
    with st.expander(t("load_from_past")):
        preset_options = _build_preset_options(username)

        if preset_options:
            selected_preset = st.selectbox(t("select_config"), options=["-- Select --"] + list(preset_options.keys()), key="preset_selector")
            if selected_preset != "-- Select --":
                if st.button(t("load_selected")):
                    _apply_preset_to_session(preset_options[selected_preset])
                    st.success(t("config_loaded"))
                    st.rerun(scope="app")
        else:
            st.caption(t("no_saved_configs"))

    # Pre-load strategy data (cached)
    strategies = _cached_strategies()
    enabled_strategies = [s for s in strategies if s.get('enabled', True)]
    if not enabled_strategies:
        st.warning(t("no_strategies"))
        st.page_link("pages/4_Strategies.py", label=t("go_strategies"), icon="📖")
        return

    strategy_options = {s['name']: s['id'] for s in enabled_strategies}
    strategy_ids = {s['id']: s['name'] for s in enabled_strategies}

    preset_strategy = st.session_state.get('preset_strategy')
    default_strategy_idx = 0
    if preset_strategy and preset_strategy in strategy_ids:
        strategy_names = list(strategy_options.keys())
        pname = strategy_ids[preset_strategy]
        if pname in strategy_names:
            default_strategy_idx = strategy_names.index(pname)

    selected_strategy_name = st.selectbox("Strategy*", list(strategy_options.keys()), index=default_strategy_idx)
    selected_strategy = strategy_options[selected_strategy_name]
    params = _cached_strategy_params(selected_strategy)
    is_multi_strategy = params.get('window_start') is not None
    # Initialize variables -- filled by respective branch below
    entry_time = None
    entry_times = None
    window_start = window_end = priority_direction = None

    st.divider()

    # ═══════════════════════════════════════════════════════
    # SECTION 1: Market
    # ═══════════════════════════════════════════════════════
    st.markdown(f"**{t('section_market')}**")

    symbol_help = (
        "Pip info per symbol:\n"
        "XAUUSD: pip=0.01, $10/pip/lot | BTCUSDm: pip=1, $1/pip/lot\n"
        "ETHUSD: pip=0.01, $0.01/pip/lot | EURUSD: pip=0.0001, $10/pip/lot\n"
        "USDJPY: pip=0.01, ~$6.67/pip/lot | AUDUSD: pip=0.0001, $10/pip/lot"
    )

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        preset_symbol = st.session_state.get('preset_symbol')
        strategy_symbols = params.get('symbols', [])
        if strategy_symbols:
            sym_idx = 0
            if preset_symbol and preset_symbol in strategy_symbols:
                sym_idx = strategy_symbols.index(preset_symbol)
            symbol = st.selectbox("Symbol*", options=strategy_symbols, index=sym_idx, help=symbol_help)
        else:
            symbol = st.text_input("Symbol*", value=preset_symbol or "XAUUSD", help=symbol_help)

    with col2:
        preset_tf = st.session_state.get('preset_timeframe', params.get('timeframe', 'M5'))
        tf_options = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
        tf_idx = tf_options.index(preset_tf) if preset_tf in tf_options else 1
        timeframe = st.selectbox(t("timeframe"), options=tf_options, index=tf_idx)

    with col3:
        if is_multi_strategy:
            preset_ws = st.session_state.get('preset_window_start', params.get('window_start', '21:00'))
            window_start = st.text_input("Window Start", value=preset_ws, max_chars=5, help="HH:MM format")
        else:
            preset_et = st.session_state.get('preset_entry_time', params.get('entry_time', '21:05'))
            entry_time = st.text_input(t("entry_time"), value=preset_et, max_chars=5, help="HH:MM format")
            entry_times = [entry_time]

    if is_multi_strategy:
        col_we, col_pd = st.columns(2)
        with col_we:
            preset_we = st.session_state.get('preset_window_end', params.get('window_end', '23:00'))
            window_end = st.text_input("Window End", value=preset_we, max_chars=5, help="HH:MM format")
        with col_pd:
            preset_pd = st.session_state.get('preset_priority_direction', params.get('priority_direction', 'auto'))
            pd_options = ["auto", "BUY", "SELL"]
            pd_idx = pd_options.index(preset_pd) if preset_pd in pd_options else 0
            priority_direction = st.selectbox("Priority Direction", options=pd_options, index=pd_idx)
        entry_times = None
    else:
        # Batch entry times
        with st.expander(t("batch_entry_times")):
            batch_str = st.text_input(t("batch_comma_times"), value="21:05, 22:00, 23:00", help="Creates one bot per time")
            use_batch = st.checkbox(t("batch_enable"))
            if use_batch:
                entry_times = [_t.strip() for _t in batch_str.split(',') if _t.strip()]
                if not entry_times:
                    entry_times = [entry_time]

    st.divider()

    # ═══════════════════════════════════════════════════════
    # SECTION 2: Trade Setup
    # ═══════════════════════════════════════════════════════
    st.markdown(f"**{t('section_trade_setup')}**")

    col1, col2, col3 = st.columns(3)
    with col1:
        preset_em = st.session_state.get('preset_entry_mode', 'close')
        em_options = ["close", "range_percent"]
        em_idx = em_options.index(preset_em) if preset_em in em_options else 0
        entry_mode = st.radio(t("entry_mode"), em_options, index=em_idx,
                              format_func=lambda x: t("entry_mode_close") if x == "close" else t("entry_mode_range"),
                              horizontal=True, help=t("tip_entry_mode"))
    with col2:
        preset_rr = st.session_state.get('preset_rr_ratio')
        rr_default = float(preset_rr) if preset_rr is not None else float(params.get('rr_ratio', 2.0))
        rr_ratio = st.number_input(t("rr_ratio"), value=rr_default, min_value=0.5, max_value=10.0, step=0.5,
                                   help=t("tip_rr_ratio"))
    with col3:
        preset_buf = st.session_state.get('preset_buffer_k')
        buf_default = float(preset_buf) if preset_buf is not None else float(params.get('buffer_k', 5.0))
        buffer_k = st.number_input(t("buffer_k"), value=buf_default, min_value=0.0, max_value=1000.0, step=1.0,
                                   help=t("tip_buffer_k"))

    # Range percent fields — hidden in Simple mode unless range_percent selected
    if is_advanced or entry_mode == "range_percent":
        col1, col2, col3 = st.columns(3)
        with col1:
            preset_ep = st.session_state.get('preset_entry_percent')
            ep_default = float(preset_ep) if preset_ep is not None else 30.0
            entry_percent = st.number_input(t("entry_percent"), value=ep_default,
                                            min_value=0.0, max_value=100.0, step=5.0,
                                            help=t("tip_entry_percent"))
        with col2:
            preset_pomc = st.session_state.get('preset_pending_order_max_candles')
            pomc_default = int(preset_pomc) if preset_pomc is not None else 3
            pending_order_max_candles = st.number_input(t("retry_candles"), value=pomc_default,
                                                        min_value=1, max_value=10, step=1,
                                                        help=t("tip_retry_candles"))
        with col3:
            preset_poec = st.session_state.get('preset_pending_order_expire_candles')
            poec_default = int(preset_poec) if preset_poec is not None else 0
            pending_order_expire_candles = st.number_input(t("expire_candles"), value=poec_default,
                                                            min_value=0, max_value=50, step=1,
                                                            help=t("tip_expire_candles"))
    else:
        # Simple mode + close entry: use defaults silently
        preset_ep = st.session_state.get('preset_entry_percent')
        entry_percent = float(preset_ep) if preset_ep is not None else 30.0
        preset_pomc = st.session_state.get('preset_pending_order_max_candles')
        pending_order_max_candles = int(preset_pomc) if preset_pomc is not None else 3
        preset_poec = st.session_state.get('preset_pending_order_expire_candles')
        pending_order_expire_candles = int(preset_poec) if preset_poec is not None else 0

    # ═══════════════════════════════════════════════════════
    # SECTION 3: Exit Rules (collapsible; hidden in Simple mode)
    # ═══════════════════════════════════════════════════════
    if is_advanced:
        with st.expander(t("section_exit_rules"), expanded=False):
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                preset_tp = st.session_state.get('preset_tp_type', 'price_based')
                tp_options = ["price_based", "close_based"]
                tp_idx = tp_options.index(preset_tp) if preset_tp in tp_options else 0
                tp_type = st.radio(t("tp_type"), tp_options, index=tp_idx,
                                   format_func=lambda x: t("tp_price") if x == "price_based" else t("tp_close"),
                                   help=t("tip_tp_price") if tp_idx == 0 else t("tip_tp_close"))

            with col2:
                preset_sl = st.session_state.get('preset_sl_type', 'price_based')
                sl_options = ["price_based", "close_based"]
                sl_idx = sl_options.index(preset_sl) if preset_sl in sl_options else 0
                sl_type = st.radio(t("sl_type"), sl_options, index=sl_idx,
                                   format_func=lambda x: t("sl_close") if x == "close_based" else t("sl_price"),
                                   help=t("tip_sl_close") if sl_idx == 1 else t("tip_sl_price"))

            with col3:
                preset_mc = st.session_state.get('preset_max_candles')
                mc_val = int(preset_mc) if preset_mc is not None and int(preset_mc) > 0 else int(params.get('max_candles', 7))
                use_max_candles = st.checkbox(t("max_candles"), value=True if preset_mc is None else bool(preset_mc and int(preset_mc) > 0))
                max_candles = st.number_input(t("max_candles_limit"), value=mc_val, min_value=1, max_value=50,
                                              help=t("tip_max_candles"))
                if not use_max_candles:
                    max_candles = 0

            with col4:
                preset_be = st.session_state.get('preset_move_sl_to_breakeven', False)
                move_sl_to_breakeven = st.checkbox(t("breakeven"), value=bool(preset_be), help=t("tip_breakeven"))
                preset_be_pct = st.session_state.get('preset_breakeven_trigger_percent')
                be_default = float(preset_be_pct) if preset_be_pct is not None else 50.0
                breakeven_trigger_percent = st.number_input(t("breakeven_trigger"), value=be_default,
                                                             min_value=10.0, max_value=90.0, step=5.0,
                                                             help=t("tip_breakeven"))
                preset_bt = st.session_state.get('preset_breakeven_target', 'entry')
                bt_options = ["entry", "close"]
                bt_idx = bt_options.index(preset_bt) if preset_bt in bt_options else 0
                breakeven_target = st.radio(t("breakeven_sl_target"), bt_options, index=bt_idx,
                                            format_func=lambda x: t("breakeven_entry") if x == "entry" else t("breakeven_close"),
                                        horizontal=True,
                                        help=t("tip_breakeven"))
    else:
        # Simple mode: use safe defaults for exit rules
        preset_tp = st.session_state.get('preset_tp_type', 'price_based')
        tp_type = preset_tp if preset_tp in ["price_based", "close_based"] else 'price_based'
        preset_sl = st.session_state.get('preset_sl_type', 'price_based')
        sl_type = preset_sl if preset_sl in ["price_based", "close_based"] else 'price_based'
        preset_mc = st.session_state.get('preset_max_candles')
        max_candles = int(preset_mc) if preset_mc is not None and int(preset_mc) > 0 else int(params.get('max_candles', 7))
        move_sl_to_breakeven = bool(st.session_state.get('preset_move_sl_to_breakeven', False))
        preset_be_pct = st.session_state.get('preset_breakeven_trigger_percent')
        breakeven_trigger_percent = float(preset_be_pct) if preset_be_pct is not None else 50.0
        preset_bt = st.session_state.get('preset_breakeven_target', 'entry')
        breakeven_target = preset_bt if preset_bt in ["entry", "close"] else 'entry'
        # Show compact summary of active exit rules
        tp_lbl = t("tp_price") if tp_type == "price_based" else t("tp_close")
        sl_lbl = t("sl_close") if sl_type == "close_based" else t("sl_price")
        st.caption(f"📤 {t('section_exit_rules')}: TP={tp_lbl} | SL={sl_lbl} | Max {max_candles} candles — [switch to ⚙️ Advanced to change]")

    # ═══════════════════════════════════════════════════════
    # SECTION 4: Position Sizing (collapsible)
    # ═══════════════════════════════════════════════════════
    with st.expander(t("section_position"), expanded=False):
        preset_lm = st.session_state.get('preset_lot_mode', 'fixed')
        lm_options = ["fixed", "flex"]
        lm_idx = lm_options.index(preset_lm) if preset_lm in lm_options else 0
        lot_mode = st.radio(t("lot_mode"), lm_options, index=lm_idx,
                            format_func=lambda x: t("lot_fixed") if x == "fixed" else t("lot_flex"),
                            horizontal=True,
                            help=t("tip_lot_fixed") if lm_idx == 0 else t("tip_lot_flex"))

        # Fixed mode
        preset_ls = st.session_state.get('preset_lot_size')
        ls_default = float(preset_ls) if preset_ls is not None else float(params.get('lot_size', 0.01))
        lot_size = st.number_input(t("lot_size"), value=ls_default,
                                    min_value=0.01, max_value=10.0, step=0.01, format="%.2f",
                                    help=t("tip_lot_fixed"))

        # Flex mode fields (always shown)
        col1, col2, col3 = st.columns(3)
        with col1:
            preset_se = st.session_state.get('preset_starting_equity')
            se_default = float(preset_se) if preset_se is not None else 1000.0
            starting_equity = st.number_input(t("starting_equity"), value=se_default,
                                               min_value=100.0, max_value=1000000.0, step=100.0,
                                               help=t("tip_starting_equity"))
        with col2:
            preset_rm = st.session_state.get('preset_risk_mode', 'percent')
            rm_options = ["percent", "fixed_amount"]
            rm_idx = rm_options.index(preset_rm) if preset_rm in rm_options else 0
            risk_mode = st.radio(t("risk_mode"), rm_options, index=rm_idx,
                                 format_func=lambda x: t("risk_pct_label") if x == "percent" else t("risk_fixed_label"),
                                 horizontal=True, help=t("tip_lot_flex"))
        with col3:
            preset_rp = st.session_state.get('preset_risk_percent')
            rp_default = float(preset_rp) if preset_rp is not None else 0.5
            risk_percent = st.number_input(t("risk_per_trade_pct"), value=rp_default,
                                           min_value=0.1, max_value=5.0, step=0.1, format="%.1f",
                                           help=t("tip_risk_percent"))
            preset_ra = st.session_state.get('preset_risk_amount')
            ra_default = float(preset_ra) if preset_ra is not None else 5.0
            risk_amount = st.number_input(t("risk_per_trade_usd"), value=ra_default,
                                          min_value=1.0, max_value=1000.0, step=1.0, format="%.2f",
                                          help=t("tip_risk_amount"))

        preset_rc = st.session_state.get('preset_risk_compounding')
        rc_default = bool(preset_rc) if preset_rc is not None else True
        risk_compounding = st.checkbox(t("compounding"), value=rc_default,
                                       help=t("tip_compounding"))

    # ═══════════════════════════════════════════════════════
    # CONFIG SUMMARY CARD — preview before start
    # ═══════════════════════════════════════════════════════
    st.divider()
    with st.container(border=True):
        st.markdown(f"**{t('config_preview')}**")
        st.caption(t("confirm_start"))
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"**{t('preview_symbol')}:** `{symbol}`")
            st.markdown(f"**{t('strategy')}:** {selected_strategy_name}")
            _et_label = entry_times[0] if entry_times else (window_start or "?")
            st.markdown(f"**{t('entry_time')}:** {_et_label}")
        with c2:
            _em_lbl = t("entry_mode_close") if entry_mode == "close" else f"{t('entry_mode_range')} {entry_percent:.0f}%"
            st.markdown(f"**{t('entry_mode')}:** {_em_lbl}")
            st.markdown(f"**{t('rr_ratio')}:** {rr_ratio}:1")
            st.markdown(f"**{t('buffer_k')}:** {buffer_k:.0f} pts")
        with c3:
            _tp_lbl = t("tp_price") if tp_type == "price_based" else t("tp_close")
            _sl_lbl = t("sl_close") if sl_type == "close_based" else t("sl_price")
            st.markdown(f"**TP:** {_tp_lbl}  |  **SL:** {_sl_lbl}")
            if lot_mode == "fixed":
                st.markdown(f"**{t('lot_size')}:** {lot_size:.2f} lot")
            else:
                _risk_lbl = f"{risk_percent:.1f}% of ${starting_equity:,.0f}" if risk_mode == "percent" else f"${risk_amount:.2f} fixed"
                st.markdown(f"**Risk:** {_risk_lbl}")
            st.markdown(f"**Max Candles:** {max_candles if max_candles > 0 else '∞'}")

    # ═══════════════════════════════════════════════════════
    # ACTION BUTTONS
    # ═══════════════════════════════════════════════════════
    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if st.button(t("validate_config"), use_container_width=True):
            from src.symbol_validator import validate_symbol_and_params
            from src.auth import get_user_mt5_credentials
            from src.utils import get_pip_value

            credentials = get_user_mt5_credentials(username)
            symbol_upper = symbol.upper()
            if "XAU" in symbol_upper: sample_entry = 2400.0
            elif "BTC" in symbol_upper: sample_entry = 95000.0
            elif "ETH" in symbol_upper: sample_entry = 3500.0
            elif "JPY" in symbol_upper: sample_entry = 150.0
            elif symbol_upper in ("USDCHF", "USDCAD"): sample_entry = 1.0
            else: sample_entry = 1.1

            pip_value = get_pip_value(symbol)
            # Use realistic sample SL distance per symbol (matches typical candle range)
            if "XAU" in symbol_upper:
                sample_sl_pips = 800.0   # Gold: ~$8 SL (800 × $0.01)
            elif "BTC" in symbol_upper:
                sample_sl_pips = 500.0   # BTC: ~$500 SL
            elif "ETH" in symbol_upper:
                sample_sl_pips = 300.0   # ETH: ~$3 SL
            else:
                sample_sl_pips = 50.0    # Forex: ~50 pips
            sample_sl = sample_entry - (sample_sl_pips * pip_value)
            sample_tp = sample_entry + (sample_sl_pips * pip_value * rr_ratio)
            sample_lot = lot_size if lot_mode == "fixed" else 0.01

            if lot_mode == "flex":
                from src.backtest import calculate_flex_lot_size
                from src.utils import get_pip_value_per_lot
                pvl = get_pip_value_per_lot(symbol)
                if risk_mode == "fixed_amount":
                    raw_risk = risk_amount
                    sample_lot = calculate_flex_lot_size(equity=starting_equity, risk_percent=0, sl_pips=sample_sl_pips, symbol=symbol, risk_amount=risk_amount)
                else:
                    raw_risk = starting_equity * (risk_percent / 100)
                    sample_lot = calculate_flex_lot_size(equity=starting_equity, risk_percent=risk_percent, sl_pips=sample_sl_pips, symbol=symbol)
                # Warn if actual risk deviates from target due to min_lot constraint
                actual_risk = sample_lot * sample_sl_pips * pvl
                if actual_risk > raw_risk * 1.1:
                    st.warning(
                        f"⚠️ **Min lot constraint**: With ${starting_equity:,.0f} equity and {sample_sl_pips:.0f} pip SL, "
                        f"calculated lot ({sample_lot:.3f}) = min broker lot. "
                        f"Actual risk ≈ **${actual_risk:.2f}** ({actual_risk/starting_equity*100:.2f}%) vs target ${raw_risk:.2f} ({risk_percent if risk_mode!='fixed_amount' else ''}%). "
                        f"Increase equity or reduce risk % to fit within min lot.")

            is_valid, messages = validate_symbol_and_params(
                symbol=symbol, lot_size=sample_lot,
                entry_price=sample_entry, sl_price=sample_sl,
                tp_price=sample_tp, credentials=credentials
            )
            for msg in messages:
                if "[ERROR]" in msg: st.error(msg)
                elif "[WARN]" in msg: st.warning(msg)
                else: st.info(msg)
            if is_valid: st.success(t("config_valid"))
            else: st.error(t("fix_errors"))

    with col2:
        button_label = t("start_n_bots", n=len(entry_times)) if entry_times and len(entry_times) > 1 else t("start_bot")
        start_clicked = st.button(button_label, type="primary", use_container_width=True)

    with col3:
        preset_name_input = st.text_input(t("preset_name"), placeholder="e.g. Gold Scalp M5", key="save_preset_name")
        if st.button(t("save_preset"), use_container_width=True):
            preset_config = {
                'strategy': selected_strategy, 'symbol': symbol, 'user': username,
                'timeframe': timeframe,
                'entry_time': entry_times[0] if entry_times else None,
                'window_start': window_start,
                'window_end': window_end,
                'priority_direction': priority_direction,
                'entry_mode': entry_mode, 'entry_percent': entry_percent,
                'pending_order_max_candles': pending_order_max_candles,
                'pending_order_expire_candles': pending_order_expire_candles,
                'rr_ratio': rr_ratio, 'buffer_k': buffer_k,
                'tp_type': tp_type, 'sl_type': sl_type, 'max_candles': max_candles,
                'move_sl_to_breakeven': move_sl_to_breakeven,
                'breakeven_trigger_percent': breakeven_trigger_percent,
                'breakeven_target': breakeven_target,
                'lot_mode': lot_mode,
                'lot_size': lot_size if lot_mode == 'fixed' else None,
                'starting_equity': starting_equity if lot_mode == 'flex' else None,
                'risk_mode': risk_mode if lot_mode == 'flex' else None,
                'risk_percent': risk_percent if lot_mode == 'flex' else None,
                'risk_amount': risk_amount if lot_mode == 'flex' else None,
                'risk_compounding': risk_compounding if lot_mode == 'flex' else None,
            }
            save_config_to_history(preset_config, preset_name=preset_name_input or None)
            _cached_config_history.clear()
            _build_preset_options.clear()
            name_msg = f' as "{preset_name_input}"' if preset_name_input else ''
            st.success(f"Preset saved{name_msg}!")
            st.rerun(scope="app")

    if start_clicked:
        if not symbol:
            st.error("Symbol is required")
        else:
            if is_multi_strategy:
                # Multi strategy: validate window times, start once
                window_valid = True
                for t_val, t_label in [(window_start, "Window Start"), (window_end, "Window End")]:
                    try:
                        datetime.strptime(t_val, "%H:%M")
                    except (ValueError, TypeError):
                        st.error(f"Invalid {t_label} format. Use HH:MM")
                        window_valid = False

                if window_valid:
                    success, msg, bot_info = start_bot(
                        strategy=selected_strategy, symbol=symbol, user=username,
                        test=False, interval=1,
                        lot_size=lot_size if lot_mode == "fixed" else None,
                        sl_pips=None, rr_ratio=rr_ratio,
                        max_candles=max_candles if max_candles > 0 else None,
                        timeframe=timeframe,
                        window_start=window_start, window_end=window_end,
                        priority_direction=priority_direction,
                        entry_mode=entry_mode,
                        entry_percent=entry_percent if entry_mode == "range_percent" else 0.0,
                        buffer_k=buffer_k, lot_mode=lot_mode,
                        starting_equity=starting_equity if lot_mode == "flex" else None,
                        risk_mode=risk_mode if lot_mode == "flex" else None,
                        risk_percent=risk_percent if lot_mode == "flex" else None,
                        risk_amount=risk_amount if lot_mode == "flex" else None,
                        risk_compounding=risk_compounding if lot_mode == "flex" else None,
                        tp_type=tp_type, sl_type=sl_type,
                        move_sl_to_breakeven=move_sl_to_breakeven,
                        breakeven_trigger_percent=breakeven_trigger_percent if move_sl_to_breakeven else None,
                        breakeven_target=breakeven_target if move_sl_to_breakeven else None,
                        pending_order_max_candles=pending_order_max_candles if entry_mode == "range_percent" else None,
                        pending_order_expire_candles=pending_order_expire_candles if entry_mode == "range_percent" and pending_order_expire_candles > 0 else None
                    )
                    if success:
                        st.success(msg)
                        _cached_bot_stats.clear()
                        _cached_list_bots.clear()
                        _cached_config_history.clear()
                        _build_preset_options.clear()
                        st.balloons()
                        st.rerun(scope="app")
                    else:
                        st.error(msg)
            else:
                valid_times = []
                for time_val in entry_times:
                    try:
                        datetime.strptime(time_val, "%H:%M")
                        valid_times.append(time_val)
                    except ValueError:
                        st.error(f"Invalid time format: {time_val}. Use HH:MM")

                if not valid_times:
                    st.error("No valid entry times provided.")
                else:
                    success_count = 0
                    error_count = 0
                    result_msgs = []
                    progress_bar = st.progress(0, text="Starting bots...")

                    for idx, time_str in enumerate(valid_times):
                        progress_bar.progress(idx / len(valid_times), text=f"Starting bot {idx+1}/{len(valid_times)}: {time_str}")
                        if idx > 0:
                            import time
                            time.sleep(0.1)

                        success, msg, bot_info = start_bot(
                            strategy=selected_strategy, symbol=symbol, user=username,
                            test=False, interval=1,
                            lot_size=lot_size if lot_mode == "fixed" else None,
                            sl_pips=None, rr_ratio=rr_ratio,
                            max_candles=max_candles if max_candles > 0 else None,
                            timeframe=timeframe, entry_time=time_str,
                            entry_mode=entry_mode,
                            entry_percent=entry_percent if entry_mode == "range_percent" else 0.0,
                            buffer_k=buffer_k, lot_mode=lot_mode,
                            starting_equity=starting_equity if lot_mode == "flex" else None,
                            risk_mode=risk_mode if lot_mode == "flex" else None,
                            risk_percent=risk_percent if lot_mode == "flex" else None,
                            risk_amount=risk_amount if lot_mode == "flex" else None,
                            risk_compounding=risk_compounding if lot_mode == "flex" else None,
                            tp_type=tp_type, sl_type=sl_type,
                            move_sl_to_breakeven=move_sl_to_breakeven,
                            breakeven_trigger_percent=breakeven_trigger_percent if move_sl_to_breakeven else None,
                            breakeven_target=breakeven_target if move_sl_to_breakeven else None,
                            pending_order_max_candles=pending_order_max_candles if entry_mode == "range_percent" else None,
                            pending_order_expire_candles=pending_order_expire_candles if entry_mode == "range_percent" and pending_order_expire_candles > 0 else None
                        )

                        if success:
                            success_count += 1
                            result_msgs.append(f"[OK] {time_str}: {msg}")
                        else:
                            error_count += 1
                            result_msgs.append(f"[FAIL] {time_str}: {msg}")

                    progress_bar.progress(1.0, text="Done!")

                    if success_count > 0:
                        st.success(f"{success_count} bot(s) started!")
                        if len(valid_times) > 1:
                            for m in result_msgs:
                                if "[OK]" in m: st.caption(m)
                    if error_count > 0:
                        st.error(f"{error_count} bot(s) failed.")
                        for m in result_msgs:
                            if "[FAIL]" in m: st.caption(m)
                    if success_count > 0:
                        _cached_bot_stats.clear()
                        _cached_list_bots.clear()
                        _cached_config_history.clear()
                        _build_preset_options.clear()
                        st.balloons()
                        st.rerun(scope="app")


@st.fragment
def show_bot_history():
    """Show bot config history and performance analysis"""
    import pandas as pd

    st.subheader("Bot History & Performance Analysis")
    st.caption("Analyze past bot configurations and results to optimize your strategy")

    # ── CONFIG HISTORY SECTION ──
    st.markdown("#### Config History")
    config_history = _cached_config_history(username)

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
                        st.rerun(scope="app")
            with c2:
                if st.button("Delete record", key="delete_history_btn", type="secondary"):
                    if delete_config_record(selected_id):
                        _cached_config_history.clear()
                        _build_preset_options.clear()
                        st.success("Deleted.")
                        st.rerun(scope="app")
                    else:
                        st.error("Record not found.")
    else:
        st.info("No config history yet. Start a bot or save a preset to begin.")

    st.divider()

    # ── RECENT LOGS SECTION ──
    st.markdown(f"#### {t('recent_logs')}")

    recent_logs = get_log_files(user=username, max_age_days=7)
    # Only non-empty logs, cap at 50
    recent_logs = [lg for lg in recent_logs if lg["size_bytes"] > 0][:50]

    if recent_logs:
        log_options = {
            f"{lg['filename']}  ({lg['size_bytes'] / 1024:.0f} KB, {lg['modified_dt'].strftime('%m/%d %H:%M')})": lg
            for lg in recent_logs
        }
        selected_log_label = st.selectbox(
            t("select_log_file"), options=list(log_options.keys()), key="history_log_select"
        )
        selected_log = log_options[selected_log_label]

        col_f, col_l = st.columns(2)
        with col_f:
            level_filter = st.selectbox(
                t("filter_level"),
                options=["All", "ERROR", "WARN", "ERROR+WARN"],
                key="log_level_filter",
            )
        with col_l:
            n_lines = st.slider(t("lines_to_show"), 20, 500, 100, key="log_lines_slider")

        log_path = selected_log["path"]

        if level_filter == "All":
            content = read_log_tail(log_path, n_lines)
        else:
            levels = level_filter.split("+")
            lines = read_log_errors(log_path, levels=levels)
            content = "".join(lines[-n_lines:])

        if content.strip():
            st.code(content, language="log")
        else:
            st.info(t("no_matching_lines"))

        with open(log_path, "r", encoding="utf-8", errors="replace") as _lf:
            st.download_button(
                t("download_log"),
                data=_lf.read(),
                file_name=selected_log["filename"],
                mime="text/plain",
                key="dl_history_log",
            )
    else:
        st.info(t("no_recent_logs"))

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
