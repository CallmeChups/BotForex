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
from src.auth import require_auth, has_mt5_credentials, is_admin
username, name = require_auth()

from src.bot_manager import (
    start_bot,
    stop_bot,
    stop_all_bots,
    restart_all_bots,
    switch_bot_mode,
    list_bots,
    restart_bot,
    get_bot_stats,
    is_process_running,
)
from src.strategy_manager import list_strategies, get_strategy_parameters
from src.utils import get_pip_value, report_page_error

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def _parse_wick(s: str) -> float | None:
    """Parse wick filter input. Returns None (disabled) if empty or <= 0."""
    s = s.strip()
    if not s:
        return None
    try:
        v = float(s)
        return v if v > 0 else None
    except ValueError:
        return None


def _pip_caption(pips: float, symbol: str) -> str:
    """Hiển thị giá trị thực của N pips theo symbol đang chọn."""
    pv = get_pip_value(symbol)
    return f"{pips} pips = **{pips * pv:.4g}** giá ({symbol})"

def _section_header(icon: str, title: str, color: str) -> None:
    st.markdown(
        f'<div style="background:{color}18;border-left:3px solid {color};'
        f'padding:6px 14px;border-radius:4px;margin:16px 0 8px;'
        f'font-size:11px;font-weight:700;letter-spacing:.06em;color:{color};">'
        f'{icon} {title}</div>',
        unsafe_allow_html=True,
    )


def _vdivider() -> None:
    st.markdown(
        '<div style="border-left:1px solid #e2e8f0;min-height:400px;margin:0 auto;"></div>',
        unsafe_allow_html=True,
    )


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
    tab1, tab2, tab3 = st.tabs(["Running Bots", "Create Bot", "Bot History"])

    with tab1:
        show_running_bots()

    with tab2:
        show_create_bot()

    with tab3:
        show_bot_history()


def _confirm_key(action: str) -> str:
    return f"confirm_pending_{action}"


def _request_confirm(action: str):
    st.session_state[_confirm_key(action)] = True


def _clear_confirm(action: str):
    st.session_state.pop(_confirm_key(action), None)


def _is_confirming(action: str) -> bool:
    return st.session_state.get(_confirm_key(action), False)


def show_running_bots():
    """Show list of running bots"""
    st.subheader("Running Bots")

    admin = is_admin(username)

    # ── Toolbar ───────────────────────────────────────────────────────────────
    col1, col2, col3, col4, col5, col6 = st.columns([1, 1, 1, 1, 1, 2])
    with col1:
        if st.button("Refresh", type="primary", use_container_width=True):
            st.rerun()
    with col2:
        stop_label = "Stop All" if admin else "Stop All Mine"
        if st.button(stop_label, type="secondary", use_container_width=True):
            _request_confirm("stop_all")
    with col3:
        restart_label = "Restart All" if admin else "Restart Mine"
        if st.button(restart_label, type="secondary", use_container_width=True):
            _request_confirm("restart_all")
    with col4:
        if st.button("Tất cả → Live", type="primary", use_container_width=True, key="btn_all_live"):
            _request_confirm("all_live")
    with col5:
        if st.button("Tất cả → Test", type="secondary", use_container_width=True, key="btn_all_test"):
            _request_confirm("all_test")
    with col6:
        filter_mode = st.radio("Mode", ["All", "Live Only", "Test Only"],
                               horizontal=True, key="bot_filter_mode")

    # ── Confirm dialogs for toolbar actions ───────────────────────────────────
    if _is_confirming("stop_all"):
        st.warning(f"⚠️ Bạn có chắc muốn **dừng tất cả bot**?")
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("✅ Xác nhận Stop All", type="primary"):
                try:
                    stopped, msg = stop_all_bots(user=None if admin else username)
                    st.success(msg)
                    _clear_confirm("stop_all")
                    st.rerun()
                except Exception as e:
                    report_page_error(e, "Bots / stop_all_bots")
                    st.error(f"Lỗi: {type(e).__name__}: {e}")
        with cc2:
            if st.button("❌ Hủy"):
                _clear_confirm("stop_all")
                st.rerun()

    if _is_confirming("restart_all"):
        st.warning(f"⚠️ Bạn có chắc muốn **restart tất cả bot**?")
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("✅ Xác nhận Restart All", type="primary"):
                try:
                    restarted, msg = restart_all_bots(user=None if admin else username)
                    st.success(msg)
                    _clear_confirm("restart_all")
                    st.rerun()
                except Exception as e:
                    report_page_error(e, "Bots / restart_all_bots")
                    st.error(f"Lỗi: {type(e).__name__}: {e}")
        with cc2:
            if st.button("❌ Hủy", key="cancel_restart_all"):
                _clear_confirm("restart_all")
                st.rerun()

    if _is_confirming("all_live"):
        st.warning("⚠️ Bạn có chắc muốn chuyển **tất cả bot sang Live**? Bot sẽ đặt lệnh thật!")
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("✅ Xác nhận → Live", type="primary"):
                try:
                    _all_bots = list_bots(refresh=True)
                    if not admin:
                        _all_bots = [b for b in _all_bots if b['user'] == username]
                    _switched, _blocked_msgs = 0, []
                    for _b in _all_bots:
                        if _b.get('test', True):
                            _ok, _msg, _ = switch_bot_mode(_b['pid'], live=True)
                            if _ok:
                                _switched += 1
                            else:
                                _blocked_msgs.append(_msg)
                    if _switched:
                        st.success(f"Đã chuyển {_switched} bot sang Live.")
                    for _m in _blocked_msgs:
                        st.error(_m)
                    _clear_confirm("all_live")
                    st.rerun()
                except Exception as e:
                    report_page_error(e, "Bots / all_bots_to_live")
                    st.error(f"Lỗi: {type(e).__name__}: {e}")
        with cc2:
            if st.button("❌ Hủy", key="cancel_all_live"):
                _clear_confirm("all_live")
                st.rerun()

    if _is_confirming("all_test"):
        st.warning("⚠️ Bạn có chắc muốn chuyển **tất cả bot sang Test**?")
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("✅ Xác nhận → Test", type="primary"):
                try:
                    _all_bots = list_bots(refresh=True)
                    if not admin:
                        _all_bots = [b for b in _all_bots if b['user'] == username]
                    _switched, _blocked_msgs = 0, []
                    for _b in _all_bots:
                        if not _b.get('test', True):
                            _ok, _msg, _ = switch_bot_mode(_b['pid'], live=False)
                            if _ok:
                                _switched += 1
                            else:
                                _blocked_msgs.append(_msg)
                    if _switched:
                        st.success(f"Đã chuyển {_switched} bot sang Test.")
                    for _m in _blocked_msgs:
                        st.warning(_m)
                    _clear_confirm("all_test")
                    st.rerun()
                except Exception as e:
                    report_page_error(e, "Bots / all_bots_to_test")
                    st.error(f"Lỗi: {type(e).__name__}: {e}")
        with cc2:
            if st.button("❌ Hủy", key="cancel_all_test"):
                _clear_confirm("all_test")
                st.rerun()

    # ── Process Scanner — reads bot_state.json, truth independent of running_bots.json ──
    _state_path = os.path.join("data", "bot_state.json")
    if os.path.exists(_state_path):
        try:
            import json as _json
            with open(_state_path, "r", encoding="utf-8") as _f:
                _states = _json.load(_f)
            _live_states = [s for s in _states if is_process_running(s["pid"])]
            if _live_states:
                with st.expander(f"🔍 Process Scanner — {len(_live_states)} bot process(es) detected in bot_state.json", expanded=True):
                    st.caption("Bots được detect trực tiếp qua OS process table, độc lập với running_bots.json")
                    for _s in _live_states:
                        _col1, _col2, _col3 = st.columns([2, 2, 3])
                        with _col1:
                            st.markdown(f"**PID {_s['pid']}** — {_s['symbol']}")
                        with _col2:
                            st.markdown(f"Strategy: `{_s['strategy']}`")
                        with _col3:
                            st.markdown(f"Active trades: `{_s.get('active', '?')}` | Pending: `{_s.get('pending', '?')}`")
        except Exception:
            pass

    # ── Load & scope bots ─────────────────────────────────────────────────────
    bots = list_bots(refresh=True)

    if not bots:
        st.info("No bots running. Create one in the 'Create Bot' tab.")
        return

    if not admin:
        bots = [b for b in bots if b['user'] == username]

    if filter_mode == "Live Only":
        bots = [b for b in bots if not b.get('test', True)]
    elif filter_mode == "Test Only":
        bots = [b for b in bots if b.get('test', True)]

    if not bots:
        st.info("No bots match the filter.")
        return

    st.success(f"Found {len(bots)} bot(s)")

    # ── Per-bot rows ──────────────────────────────────────────────────────────
    for bot in bots:
        pid = bot['pid']
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])

            with col1:
                mode_badge = "🧪 TEST" if bot.get('test', True) else "🔴 LIVE"
                st.markdown(f"**{bot['strategy']}** | {bot['symbol']} | {mode_badge}")
                st.caption(f"PID: {pid} | User: {bot['user']} | Started: {bot.get('started_at', 'N/A')}")
                params = []
                if bot.get('lot_size'):
                    params.append(f"Lot: {bot['lot_size']}")
                if bot.get('sl_pips'):
                    params.append(f"SL: {bot['sl_pips']} pips")
                if bot.get('rr_ratio'):
                    params.append(f"RR: {bot['rr_ratio']}")
                if params:
                    st.caption(" | ".join(params))

            can_control = admin or bot['user'] == username
            is_test = bot.get('test', True)

            with col2:
                if can_control:
                    if st.button("Stop", key=f"stop_{pid}", type="secondary"):
                        _request_confirm(f"stop_{pid}")
                else:
                    st.button("Stop", key=f"stop_{pid}", disabled=True)

            with col3:
                if can_control:
                    if st.button("Restart", key=f"restart_{pid}", type="secondary"):
                        _request_confirm(f"restart_{pid}")
                else:
                    st.button("Restart", key=f"restart_{pid}", disabled=True)

            with col4:
                if can_control:
                    switch_label = "→ Live" if is_test else "→ Test"
                    switch_type = "primary" if is_test else "secondary"
                    if st.button(switch_label, key=f"switch_{pid}", type=switch_type):
                        _request_confirm(f"switch_{pid}")
                else:
                    st.button("→ Live", key=f"switch_{pid}", disabled=True)

            with col5:
                status_color = "green" if bot.get('status') == 'running' else "red"
                st.markdown(f":{status_color}[● {bot.get('status', 'unknown').upper()}]")

            # ── Per-bot confirm dialogs ────────────────────────────────────────
            if _is_confirming(f"stop_{pid}"):
                st.warning(f"⚠️ Dừng bot **{bot['symbol']}** (PID {pid})?")
                dc1, dc2 = st.columns(2)
                with dc1:
                    if st.button("✅ Xác nhận", key=f"confirm_stop_{pid}", type="primary"):
                        try:
                            success, msg = stop_bot(pid)
                            st.success(msg) if success else st.error(msg)
                            _clear_confirm(f"stop_{pid}")
                            st.rerun()
                        except Exception as e:
                            report_page_error(e, f"Bots / stop_bot / pid={pid}")
                            st.error(f"Lỗi: {type(e).__name__}: {e}")
                with dc2:
                    if st.button("❌ Hủy", key=f"cancel_stop_{pid}"):
                        _clear_confirm(f"stop_{pid}")
                        st.rerun()

            if _is_confirming(f"restart_{pid}"):
                st.warning(f"⚠️ Restart bot **{bot['symbol']}** (PID {pid})?")
                dc1, dc2 = st.columns(2)
                with dc1:
                    if st.button("✅ Xác nhận", key=f"confirm_restart_{pid}", type="primary"):
                        try:
                            success, msg, _ = restart_bot(pid)
                            st.success(msg) if success else st.error(msg)
                            _clear_confirm(f"restart_{pid}")
                            st.rerun()
                        except Exception as e:
                            report_page_error(e, f"Bots / restart_bot / pid={pid}")
                            st.error(f"Lỗi: {type(e).__name__}: {e}")
                with dc2:
                    if st.button("❌ Hủy", key=f"cancel_restart_{pid}"):
                        _clear_confirm(f"restart_{pid}")
                        st.rerun()

            if _is_confirming(f"switch_{pid}"):
                target = "Live 🔴" if is_test else "Test 🧪"
                st.warning(f"⚠️ Chuyển bot **{bot['symbol']}** sang **{target}**?")
                dc1, dc2 = st.columns(2)
                with dc1:
                    if st.button("✅ Xác nhận", key=f"confirm_switch_{pid}", type="primary"):
                        try:
                            success, msg, _ = switch_bot_mode(pid, live=is_test)
                            st.success(msg) if success else st.error(msg)
                            _clear_confirm(f"switch_{pid}")
                            st.rerun()
                        except Exception as e:
                            report_page_error(e, f"Bots / switch_bot_mode / pid={pid}")
                            st.error(f"Lỗi: {type(e).__name__}: {e}")
                with dc2:
                    if st.button("❌ Hủy", key=f"cancel_switch_{pid}"):
                        _clear_confirm(f"switch_{pid}")
                        st.rerun()

            # ── Log viewer ────────────────────────────────────────────────────
            log_path = bot.get('log_path')
            if log_path and os.path.exists(log_path):
                with st.expander(f"📋 Log — {os.path.basename(log_path)}"):
                    if st.button("🔄 Refresh log", key=f"refresh_log_{pid}"):
                        st.rerun()
                    try:
                        with open(log_path, 'r', encoding='utf-8', errors='replace') as _lf:
                            _lines = _lf.readlines()
                        _tail = _lines[-100:] if len(_lines) > 100 else _lines
                        st.code("".join(_tail), language=None)
                        with open(log_path, 'rb') as _dl:
                            st.download_button(
                                "⬇ Download log", data=_dl.read(),
                                file_name=os.path.basename(log_path),
                                mime="text/plain", key=f"dl_log_{pid}",
                            )
                    except Exception as _e:
                        st.error(f"Không đọc được log: {_e}")
            elif log_path:
                st.caption(f"Log: {os.path.basename(log_path)} (chưa có nội dung)")

            st.divider()


def show_create_bot():
    """Show form to create new bot"""
    st.subheader("Create New Bot")


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
    is_feg_stop_order = selected_strategy == 'feg_stop_order'
    sk = selected_strategy  # key prefix — forces widget reinit when strategy changes

    # Load from Backtest History
    with st.expander("Load from Backtest History"):
        from src.backtest_history import get_history, get_history_record, history_to_dataframe
        _bh = get_history()
        if _bh:
            _bh_df = history_to_dataframe(_bh)
            _reuse_opts = {
                f"{r['ID']} | {r.get('Date', '')} | {r.get('Strategy', '')} | {r.get('Symbol', '')} | Win {r['Win %']}%": r['ID']
                for _, r in _bh_df.iterrows()
            }
            _sel = st.selectbox("Chọn backtest config", options=list(_reuse_opts.keys()), key="bot_reuse_select")
            if st.button("Load Config vào form", type="primary", key="btn_bot_reuse"):
                _rid = _reuse_opts[_sel]
                _rec = get_history_record(_rid)
                if _rec:
                    _cfg = dict(_rec['config'])
                    # migrate legacy keys
                    if 'ema_dist_pips' in _cfg and 'ema_margin_pips' not in _cfg:
                        _cfg['ema_margin_pips'] = _cfg.pop('ema_dist_pips')
                    _cfg.pop('ema_dist_enabled', None)
                    # Map config → bot widget session state keys (sk prefix)
                    _map = {
                        f"{sk}_rr": float(_cfg.get('rr_ratio', params.get('rr_ratio', 2.0))),
                        f"{sk}_mc": int(_cfg.get('max_candles', params.get('max_candles', 7))),
                        f"{sk}_ema": int(_cfg.get('ema_period', params.get('ema_period', 21))),
                        f"{sk}_h2x": float(_cfg.get('h2_exceed_pips', 0.0)),
                        f"{sk}_c2g": float(_cfg.get('c2_gap_pips', 0.0)),
                        f"{sk}_emm": float(_cfg.get('ema_margin_pips', 0.0)),
                        f"{sk}_loc": int(_cfg.get('limit_order_candles', 1)),
                        f"{sk}_buffer_k": float(_cfg.get('buffer_k', params.get('buffer_k', 5))),
                        f"{sk}_tp_type": _cfg.get('tp_type', 'price_based'),
                        f"{sk}_sl_type": _cfg.get('sl_type', 'price_based'),
                        f"{sk}_be_enabled": bool(_cfg.get('be_enabled', False)),
                        f"{sk}_be_r": float(_cfg.get('be_r', 1.0)),
                        f"{sk}_re_entry_after_sl": bool(_cfg.get('re_entry_after_sl', False)),
                        f"{sk}_c2_buy_upper_wick_max_pct": _cfg.get('c2_buy_upper_wick_max_pct', None),
                        f"{sk}_c2_buy_lower_wick_max_pct": _cfg.get('c2_buy_lower_wick_max_pct', None),
                        f"{sk}_c2_sell_upper_wick_max_pct": _cfg.get('c2_sell_upper_wick_max_pct', None),
                        f"{sk}_c2_sell_lower_wick_max_pct": _cfg.get('c2_sell_lower_wick_max_pct', None),
                        f"{sk}_lot_mode": _cfg.get('lot_mode', 'fixed'),
                    }
                    if _cfg.get('lot_mode') == 'fixed':
                        _map[f"{sk}_lot"] = float(_cfg.get('fixed_lot', params.get('lot_size', 0.01)))
                    else:
                        _map[f"{sk}_risk_mode"] = _cfg.get('risk_mode', 'percent')
                        _map[f"{sk}_risk_pct"] = float(_cfg.get('risk_percent', 0.5))
                        _map[f"{sk}_risk_amt"] = float(_cfg.get('risk_amount', 5.0))
                    for k, v in _map.items():
                        st.session_state[k] = v
                    st.success(f"Đã load config từ {_rid}")
                    st.rerun()
        else:
            st.info("Chưa có backtest history.")

    left, _div, right = st.columns([0.58, 0.02, 0.40])

    with _div:
        _vdivider()

    with left:
        # ── ZONE 1: GENERAL ──────────────────────────────────────────────
        _section_header("⚙", "GENERAL", "#6366f1")
        gc1, gc2, gc3, gc4, gc5, gc6 = st.columns([2, 1, 1, 1, 1, 1])
        strategy_symbols = params.get('symbols', [])
        with gc1:
            use_custom_symbol = st.checkbox("Tùy chọn symbol", value=False, key=f"{sk}_custom_sym")
            if use_custom_symbol:
                symbol = st.text_input("Symbol*", value=os.getenv("SYMBOL", "XAUUSD"), key=f"{sk}_symbol")
            elif strategy_symbols:
                symbol = st.selectbox("Symbol*", options=strategy_symbols, key=f"{sk}_symbol")
            else:
                symbol = st.text_input("Symbol*", value=os.getenv("SYMBOL", "XAUUSD"), key=f"{sk}_symbol")
        with gc2:
            test_mode = st.checkbox("Test Mode", value=st.session_state.get(f"{sk}_test", True), key=f"{sk}_test",
                                    help="Test mode: no real orders placed")
        with gc3:
            rr_ratio = st.number_input("RR Ratio", value=float(st.session_state.get(f"{sk}_rr", params.get('rr_ratio', 2.0))),
                                       min_value=0.1, max_value=20.0, step=0.1, format="%.1f", key=f"{sk}_rr")
        with gc4:
            _use_mc = st.checkbox("Giới hạn số nến", value=st.session_state.get(f"{sk}_use_mc", True), key=f"{sk}_use_mc")
            if _use_mc:
                max_candles = st.number_input("Max Candles", value=int(st.session_state.get(f"{sk}_mc", params.get('max_candles', 7))),
                                              min_value=1, max_value=500, key=f"{sk}_mc")
            else:
                max_candles = 0
                st.caption("No candle limit")
        with gc5:
            interval = st.number_input("Chu kỳ quét (giây)", value=int(st.session_state.get(f"{sk}_iv", 60)),
                                       min_value=5, max_value=3600, step=5, key=f"{sk}_iv",
                                       help="Bot scan interval in seconds")
            strategy_timeframe = params.get('timeframe', 'M1')
            st.caption(f"TF: {strategy_timeframe}")

        # ── ZONE 2: ENTRY ─────────────────────────────────────────────────
        if is_pattern:
            _section_header("📈", "ENTRY", "#10b981")
            e_left, e_right = st.columns(2)
            with e_left:
                # Sub-section: FEG Margins
                st.caption("**FEG Margins**")
                em1, em2, em3, em4 = st.columns(4)
                with em1:
                    ema_period = st.number_input("EMA Period",
                                                 value=int(st.session_state.get(f"{sk}_ema", params.get('ema_period', 21))),
                                                 min_value=2, max_value=200, key=f"{sk}_ema")
                with em2:
                    h2_exceed_pips = st.number_input("H2 vượt H1 (pips)",
                                                     value=float(st.session_state.get(f"{sk}_h2x", params.get('h2_exceed_pips', 0.0))),
                                                     min_value=0.0, step=1.0, key=f"{sk}_h2x",
                                                     help="SELL: H2 phải vượt H1 thêm N pips | BUY: L2 phải thấp hơn L1 thêm N pips")
                    st.caption(_pip_caption(h2_exceed_pips, symbol))
                with em3:
                    c2_gap_pips = st.number_input("C2 vượt L1/H1 + N pips",
                                                  value=float(st.session_state.get(f"{sk}_c2g", params.get('c2_gap_pips', 0.0))),
                                                  min_value=0.0, step=1.0, key=f"{sk}_c2g",
                                                  help="SELL: C2 phải đóng thấp hơn L1 thêm N pips | BUY: C2 phải đóng cao hơn H1 thêm N pips")
                    st.caption(_pip_caption(c2_gap_pips, symbol))
                with em4:
                    ema_margin_pips = st.number_input("L2/H2 cách EMA + N pips",
                                                      value=float(st.session_state.get(f"{sk}_emam", params.get('ema_margin_pips', 0.0))),
                                                      min_value=0.0, step=1.0, key=f"{sk}_emam",
                                                      help="SELL: L2 phải cách EMA ≥ N pips | BUY: H2 phải cách EMA ≥ N pips")
                    st.caption(_pip_caption(ema_margin_pips, symbol))
                # Wick Filter
                st.caption("**Wick Filter** — để trống = tắt")
                _nw_wk1 = st.columns(2)
                with _nw_wk1[0]:
                    _raw_nw_bu = st.session_state.get(f"{sk}_c2_buy_upper_wick_max_pct")
                    _nw_wk_bu_str = st.text_input("BUY — Râu trên tối đa % body",
                                                   value="" if _raw_nw_bu is None else str(_raw_nw_bu),
                                                   key=f"{sk}_c2_buy_upper_wick_max_pct_str",
                                                   placeholder="VD: 30  (để trống = tắt)",
                                                   help="BUY: (high-close) < body × n%.")
                    c2_buy_upper_wick_max_pct = _parse_wick(_nw_wk_bu_str)
                with _nw_wk1[1]:
                    _raw_nw_bl = st.session_state.get(f"{sk}_c2_buy_lower_wick_max_pct")
                    _nw_wk_bl_str = st.text_input("BUY — Râu dưới tối đa % body",
                                                   value="" if _raw_nw_bl is None else str(_raw_nw_bl),
                                                   key=f"{sk}_c2_buy_lower_wick_max_pct_str",
                                                   placeholder="VD: 30  (để trống = tắt)",
                                                   help="BUY: (close-low) < body × n%.")
                    c2_buy_lower_wick_max_pct = _parse_wick(_nw_wk_bl_str)
                _nw_wk2 = st.columns(2)
                with _nw_wk2[0]:
                    _raw_nw_su = st.session_state.get(f"{sk}_c2_sell_upper_wick_max_pct")
                    _nw_wk_su_str = st.text_input("SELL — Râu trên tối đa % body",
                                                   value="" if _raw_nw_su is None else str(_raw_nw_su),
                                                   key=f"{sk}_c2_sell_upper_wick_max_pct_str",
                                                   placeholder="VD: 30  (để trống = tắt)",
                                                   help="SELL: (high-close) < body × n%.")
                    c2_sell_upper_wick_max_pct = _parse_wick(_nw_wk_su_str)
                with _nw_wk2[1]:
                    _raw_nw_sl = st.session_state.get(f"{sk}_c2_sell_lower_wick_max_pct")
                    _nw_wk_sl_str = st.text_input("SELL — Râu dưới tối đa % body",
                                                   value="" if _raw_nw_sl is None else str(_raw_nw_sl),
                                                   key=f"{sk}_c2_sell_lower_wick_max_pct_str",
                                                   placeholder="VD: 30  (để trống = tắt)",
                                                   help="SELL: (close-low) < body × n%.")
                    c2_sell_lower_wick_max_pct = _parse_wick(_nw_wk_sl_str)
            with e_right:
                # Sub-section: EMA Direction
                st.caption("**Bộ lọc EMA**")
                ed1, ed2, ed3 = st.columns(3)
                with ed1:
                    ema_filter_enabled = st.checkbox("Bộ lọc EMA",
                                                     value=bool(st.session_state.get(f"{sk}_ema_filter", params.get('ema_filter_enabled', True))),
                                                     key=f"{sk}_ema_filter",
                                                     help="Bật/tắt điều kiện EMA cho tín hiệu entry")
                with ed2:
                    _ema_side_opts = ["above_ema", "below_ema"]
                    buy_ema_side = st.selectbox("BUY — Phía EMA", options=_ema_side_opts,
                                                index=_ema_side_opts.index(st.session_state.get(f"{sk}_buy_ema_side", params.get('buy_ema_side', 'below_ema'))),
                                                format_func=lambda x: "H2 > EMA (above)" if x == "above_ema" else "H2 < EMA (below)",
                                                key=f"{sk}_buy_ema_side",
                                                disabled=not ema_filter_enabled)
                with ed3:
                    sell_ema_side = st.selectbox("SELL — Phía EMA", options=_ema_side_opts,
                                                 index=_ema_side_opts.index(st.session_state.get(f"{sk}_sell_ema_side", params.get('sell_ema_side', 'above_ema'))),
                                                 format_func=lambda x: "L2 > EMA (above)" if x == "above_ema" else "L2 < EMA (below)",
                                                 key=f"{sk}_sell_ema_side",
                                                 disabled=not ema_filter_enabled)
                st.divider()
                # Sub-section: Time Window
                st.caption("**Khung giờ & Kiểu vào lệnh**")
                tw1, tw2 = st.columns(2)
                with tw1:
                    entry_start_time = st.time_input("Giờ vào lệnh — Từ (HCM)", value=time(0, 0),
                                                     key=f"{sk}_tw_start",
                                                     help="Gate entries from this time. 00:00 = no filter.")
                with tw2:
                    entry_end_time = st.time_input("Giờ vào lệnh — Đến (HCM)", value=time(23, 59),
                                                   key=f"{sk}_tw_end",
                                                   help="Gate entries until this time. 23:59 = no filter.")
                # Sub-section: Entry Mode
                st.caption("**Entry Mode**")
                if not is_feg_stop_order:
                    enm1, enm2 = st.columns(2)
                    with enm1:
                        _em_opts = ["close", "range_percent"]
                        _em_default = st.session_state.get(f"{sk}_entry_mode", params.get('entry_mode', 'close'))
                        entry_mode = st.radio("Entry Mode", options=_em_opts,
                                              index=_em_opts.index(_em_default),
                                              format_func=lambda x: "Market (close)" if x == "close" else "Limit (body%)",
                                              horizontal=True, key=f"{sk}_entry_mode")
                    with enm2:
                        if entry_mode == "range_percent":
                            entry_percent = st.number_input("Entry %",
                                                            value=float(st.session_state.get(f"{sk}_entry_pct", params.get('entry_percent', 10.0))),
                                                            min_value=0.0, max_value=100.0, step=1.0, format="%.0f",
                                                            key=f"{sk}_entry_pct")
                        else:
                            entry_percent = 0.0
                    limit_order_candles = 1
                else:
                    entry_mode = "close"
                    entry_percent = 0.0
                    limit_order_candles = st.number_input("Limit Order Candles",
                                                          value=int(st.session_state.get(f"{sk}_loc", 1)),
                                                          min_value=1, max_value=50, key=f"{sk}_loc",
                                                          help="Số nến tối đa để chờ stop order fill")
        else:
            # Master Candle — no Entry zone, set defaults
            ema_period = None
            h2_exceed_pips = 0.0
            c2_gap_pips = 0.0
            ema_margin_pips = 0.0
            c2_buy_upper_wick_max_pct = None
            c2_buy_lower_wick_max_pct = None
            c2_sell_upper_wick_max_pct = None
            c2_sell_lower_wick_max_pct = None
            ema_filter_enabled = True
            buy_ema_side = "below_ema"
            sell_ema_side = "above_ema"
            entry_start_time = time(0, 0)
            entry_end_time = time(23, 59)
            entry_mode = "close"
            entry_percent = 0.0
            limit_order_candles = 1

    with right:
        # ── ZONE 3+4: ORDER SETTINGS & RISK ──────────────────────────────
        _section_header("📊", "ORDER SETTINGS & RISK", "#f59e0b")
        _or_col1, _or_col2, _or_col3 = st.columns(3)
        with _or_col1:
            buffer_k = st.number_input("Buffer K (pips)",
                                       value=float(st.session_state.get(f"{sk}_buffer_k", params.get('buffer_k', 5))),
                                       min_value=0.0, max_value=200.0, step=1.0, key=f"{sk}_buffer_k",
                                       help="SL = candle body + k pips")
        with _or_col2:
            re_entry_after_sl = st.checkbox("Entry tiếp tục sau SL",
                                            value=bool(st.session_state.get(f"{sk}_re_entry_after_sl", False)),
                                            key=f"{sk}_re_entry_after_sl",
                                            help="Trong lúc lệnh đang chạy, bot vẫn scan signal. "
                                                 "Nếu SL hit đúng tại candle2 của signal mới → vào lệnh tiếp ngay.")
        lot_mode = st.radio("Lot Mode", options=["fixed", "flex"],
                            format_func=lambda x: "Fixed" if x == "fixed" else "Flex (Risk-based)",
                            horizontal=True, key=f"{sk}_lot_mode")
        if lot_mode == "fixed":
            with _or_col3:
                lot_size = st.number_input("Lot Size",
                                           value=float(st.session_state.get(f"{sk}_lot", params.get('lot_size', 0.01))),
                                           min_value=0.01, max_value=10.0, step=0.01, format="%.2f",
                                           key=f"{sk}_lot")
            risk_mode = "percent"
            risk_percent = 0.5
            risk_amount = 0.0
        else:
            _rs1, _rs2, _rs3 = st.columns(3)
            with _rs1:
                _rm_opts = ["percent", "fixed_amount"]
                _rm_default = st.session_state.get(f"{sk}_risk_mode", "percent")
                risk_mode = st.radio("Risk Mode", options=_rm_opts,
                                     index=_rm_opts.index(_rm_default),
                                     format_func=lambda x: "%" if x == "percent" else "Fixed $",
                                     horizontal=True, key=f"{sk}_risk_mode")
            with _rs2:
                if risk_mode == "percent":
                    risk_percent = st.number_input("Risk mỗi lệnh (%)",
                                                   value=float(st.session_state.get(f"{sk}_risk_pct", 0.5)),
                                                   min_value=0.1, max_value=5.0, step=0.1, format="%.1f",
                                                   key=f"{sk}_risk_pct")
                    risk_amount = 0.0
                else:
                    risk_amount = st.number_input("Risk mỗi lệnh ($)",
                                                  value=float(st.session_state.get(f"{sk}_risk_amt", 5.0)),
                                                  min_value=1.0, max_value=1000.0, step=1.0, format="%.2f",
                                                  key=f"{sk}_risk_amt")
                    risk_percent = 0.0
            lot_size = 0.01

        # ── ZONE 5: EXIT ──────────────────────────────────────────────────
        _section_header("🚪", "EXIT", "#ef4444")
        ex1, ex2, ex3, ex4 = st.columns(4)
        with ex1:
            _tp_opts = ["price_based", "close_based"]
            tp_type = st.radio("TP Exit", options=_tp_opts,
                               index=_tp_opts.index(st.session_state.get(f"{sk}_tp_type", params.get('tp_type', 'price_based'))),
                               format_func=lambda x: "Price-based (wick)" if x == "price_based" else "Close-based",
                               horizontal=True, key=f"{sk}_tp_type")
        with ex2:
            _sl_opts = ["price_based", "close_based"]
            sl_type = st.radio("SL Exit", options=_sl_opts,
                               index=_sl_opts.index(st.session_state.get(f"{sk}_sl_type", params.get('sl_type', 'price_based'))),
                               format_func=lambda x: "Price-based (wick)" if x == "price_based" else "Close-based",
                               horizontal=True, key=f"{sk}_sl_type")
        with ex3:
            be_enabled = st.checkbox("Break-Even (BE)",
                                     value=bool(st.session_state.get(f"{sk}_be_enabled", False)),
                                     key=f"{sk}_be_enabled",
                                     help="Dời SL về entry khi lời đủ be_r × SL distance")
        with ex4:
            be_r = st.number_input("BE Trigger (R)",
                                   value=float(st.session_state.get(f"{sk}_be_r", 1.0)),
                                   min_value=0.1, max_value=10.0, step=0.1, format="%.1f",
                                   key=f"{sk}_be_r",
                                   help="BE kích hoạt khi lời đạt be_r × SL distance",
                                   disabled=not be_enabled)
        # sl_pips not used for pattern strategies (SL from candle + buffer_k)
        sl_pips = None if is_pattern else int(params.get('sl_pips', 30))

    if st.button("🚀 Khởi động Bot", type="primary", use_container_width=True, key=f"{sk}_start"):
        if not symbol:
            st.error("Symbol is required")
        else:
            try:
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
                    limit_order_candles=int(limit_order_candles),
                    be_enabled=be_enabled,
                    be_r=be_r,
                    ema_filter_enabled=ema_filter_enabled,
                    buy_ema_side=buy_ema_side,
                    sell_ema_side=sell_ema_side,
                    re_entry_after_sl=re_entry_after_sl,
                    c2_buy_upper_wick_max_pct=c2_buy_upper_wick_max_pct,
                    c2_buy_lower_wick_max_pct=c2_buy_lower_wick_max_pct,
                    c2_sell_upper_wick_max_pct=c2_sell_upper_wick_max_pct,
                    c2_sell_lower_wick_max_pct=c2_sell_lower_wick_max_pct,
                )

                if success:
                    st.success(f"Bot started! {msg}")
                    st.balloons()
                    st.rerun()
                else:
                    st.error(msg)
            except Exception as e:
                report_page_error(e, f"Bots / start_bot / {selected_strategy} / {symbol}")
                st.error(f"Lỗi khi start bot: {type(e).__name__}: {e}")

    # Quick start buttons
    st.markdown("---")
    st.caption("KHỞI ĐỘNG NHANH (TEST)")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("XAUUSD", use_container_width=True):
            try:
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
            except Exception as e:
                report_page_error(e, "Bots / quick_start / XAUUSD")
                st.error(f"Lỗi: {type(e).__name__}: {e}")

    with col2:
        if st.button("BTCUSD", use_container_width=True):
            try:
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
            except Exception as e:
                report_page_error(e, "Bots / quick_start / BTCUSD")
                st.error(f"Lỗi: {type(e).__name__}: {e}")

    with col3:
        if st.button("ETHUSD", use_container_width=True):
            try:
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
            except Exception as e:
                report_page_error(e, "Bots / quick_start / ETHUSD")
                st.error(f"Lỗi: {type(e).__name__}: {e}")


def show_bot_history():
    """Tab 3: xem, tìm kiếm, đổi tên, xóa các session bot đã chạy."""
    from src.bot_history_manager import get_sessions, rename_session, delete_session

    st.subheader("Bot History")
    admin = is_admin(username)

    # ── Filters ──────────────────────────────────────────────────────────────
    fc1, fc2, fc3, fc4 = st.columns([2, 1, 1, 1])
    with fc1:
        search = st.text_input("Tìm theo tên / ID", placeholder="Nhập tên hoặc symbol...",
                               key="bh_search")
    with fc2:
        sym_filter = st.text_input("Symbol", placeholder="XAUUSDm", key="bh_sym")
    with fc3:
        mode_filter = st.radio("Mode", ["Tất cả", "Live", "Test"],
                               horizontal=True, key="bh_mode")
    with fc4:
        show_deleted = st.checkbox("Hiện đã xóa", value=False, key="bh_deleted")

    from src.bot_history_manager import cleanup_orphaned_sessions
    cleanup_orphaned_sessions()

    sessions = get_sessions(include_deleted=show_deleted,
                            user=None if admin else username)

    # Apply filters
    if search:
        kw = search.lower()
        sessions = [s for s in sessions
                    if kw in (s.get("name") or "").lower()
                    or kw in s["id"].lower()
                    or kw in s["symbol"].lower()]
    if sym_filter:
        sessions = [s for s in sessions
                    if sym_filter.lower() in s["symbol"].lower()]
    if mode_filter != "Tất cả":
        sessions = [s for s in sessions
                    if s["mode"] == mode_filter.lower()]

    if not sessions:
        st.info("Không có session nào.")
        return

    st.caption(f"{len(sessions)} session(s)")

    # ── Session list ──────────────────────────────────────────────────────────
    for s in sessions:
        is_deleted = s.get("deleted", False)
        stats = s.get("stats", {})
        pnl = stats.get("pnl_usd", 0.0)
        pnl_color = "green" if pnl >= 0 else "red"
        mode_badge = "🔴 LIVE" if s["mode"] == "live" else "🧪 TEST"
        status_badge = "~~xóa~~" if is_deleted else ("🟢 running" if not s.get("stopped_at") else "⏹ stopped")
        display_name = s.get("name") or s["id"]

        with st.expander(f"{mode_badge} **{display_name}** | {s['symbol']} | "
                         f"W{stats.get('win',0)}/L{stats.get('loss',0)} | "
                         f":{pnl_color}[${pnl:+.2f}] | {status_badge}",
                         expanded=False):

            # Info row
            ic1, ic2, ic3 = st.columns(3)
            with ic1:
                st.markdown(f"**Strategy:** {s['strategy']}")
                st.markdown(f"**Symbol:** {s['symbol']} | {mode_badge}")
                st.markdown(f"**User:** {s['user']}")
            with ic2:
                st.markdown(f"**Start:** {s['started_at']}")
                st.markdown(f"**Stop:** {s.get('stopped_at') or '(đang chạy)'}")
            with ic3:
                st.metric("Tổng lệnh", stats.get("total", 0))
                st.metric("PNL (USD)", f"${pnl:+.2f}")
                wr = (stats.get("win", 0) / stats.get("total", 1) * 100) if stats.get("total") else 0
                st.metric("Win rate", f"{wr:.0f}%")

            # Rename
            if not is_deleted:
                with st.form(key=f"rename_{s['id']}"):
                    new_name = st.text_input("Đổi tên session",
                                             value=s.get("name") or "",
                                             key=f"rn_{s['id']}")
                    if st.form_submit_button("Lưu tên"):
                        try:
                            rename_session(s["id"], new_name)
                            st.success("Đã đổi tên.")
                            st.rerun()
                        except Exception as e:
                            report_page_error(e, f"Bots / rename_session / {s['id']}")
                            st.error(f"Lỗi: {type(e).__name__}: {e}")

            # Trades table
            trades = s.get("trades", [])
            if trades:
                st.markdown("**Danh sách lệnh:**")
                import pandas as pd
                df_t = pd.DataFrame(trades)[
                    ["order_id", "direction", "entry", "exit_price", "exit_type", "lot", "pnl_usd", "closed_at"]
                ]
                df_t.columns = ["Order ID", "Dir", "Entry", "Exit", "Type", "Lot", "PNL ($)", "Closed At"]
                st.dataframe(df_t, use_container_width=True, hide_index=True)

            # Log viewer
            log_path = s.get("log_path", "")
            if log_path and os.path.exists(log_path):
                with st.expander(f"📋 Log — {os.path.basename(log_path)}"):
                    if st.button("🔄 Refresh log", key=f"bh_refresh_{s['id']}"):
                        st.rerun()
                    with open(log_path, "r", encoding="utf-8", errors="replace") as _lf:
                        _lines = _lf.readlines()
                    st.code("".join(_lines[-100:]), language=None)
                    with open(log_path, "rb") as _dl:
                        st.download_button("⬇ Download log", data=_dl.read(),
                                           file_name=os.path.basename(log_path),
                                           mime="text/plain",
                                           key=f"bh_dl_{s['id']}")

            # Delete / restore
            if not is_deleted:
                if st.button("🗑 Xóa session này", key=f"del_{s['id']}", type="secondary"):
                    try:
                        delete_session(s["id"])
                        st.success("Đã xóa (soft delete).")
                        st.rerun()
                    except Exception as e:
                        report_page_error(e, f"Bots / delete_session / {s['id']}")
                        st.error(f"Lỗi: {type(e).__name__}: {e}")
            else:
                st.caption("Session này đã bị xóa.")


if __name__ == "__main__":
    main()
