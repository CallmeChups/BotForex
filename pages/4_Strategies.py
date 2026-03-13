"""
Strategies Page - Manage trading strategies
"""

import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import yaml

load_dotenv()

st.set_page_config(
    page_icon="📖",
    page_title="Strategies",
    layout="wide",
)

# Auth check
from src.auth import require_auth
username, name = require_auth()

from src.i18n import t, lang_toggle_button
from src.strategy_manager import (
    list_strategies,
    get_strategy,
    save_strategy,
    delete_strategy,
    toggle_strategy,
    create_default_strategy
)

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def main():
    lang_toggle_button(st.sidebar)
    st.title(t("page_strategies"))

    now = datetime.now(TIMEZONE)
    st.markdown(f"**{t('current_time')}:** {now.strftime('%H:%M:%S %d/%m/%Y')} (HCM)")

    st.divider()

    # Tabs for different views
    tab1, tab2, tab3 = st.tabs([t("all_strategies"), t("create_strategy"), t("view_edit_strategy")])

    with tab1:
        show_strategy_list()

    with tab2:
        show_create_form()

    with tab3:
        show_view_edit()


def show_strategy_list():
    """Show list of all strategies"""
    st.subheader(t("all_strategies"))

    strategies = list_strategies()

    if not strategies:
        st.info(t("no_strategies_info"))
        return

    # Display strategies as cards
    for strat in strategies:
        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])

            with col1:
                status_icon = "●" if strat['enabled'] else "○"
                status_color = "green" if strat['enabled'] else "gray"

                st.markdown(f"**{strat['name']}** `v{strat['version']}`")
                st.caption(f":{status_color}[{status_icon}] {t('enabled') if strat['enabled'] else t('disabled')} | "
                          f"{strat['timeframe']} | {strat['entry_time']} | by {strat['author']}")

                # Short description
                desc = strat.get('description', '')
                if desc:
                    short_desc = desc[:100] + "..." if len(desc) > 100 else desc
                    st.caption(short_desc.replace('\n', ' '))

            with col2:
                # Toggle enable/disable
                if strat['enabled']:
                    if st.button(t("disable_btn"), key=f"disable_{strat['id']}", type="secondary"):
                        toggle_strategy(strat['id'], False)
                        st.rerun()
                else:
                    if st.button(t("enable_btn"), key=f"enable_{strat['id']}", type="primary"):
                        toggle_strategy(strat['id'], True)
                        st.rerun()

            with col3:
                # Delete button
                if st.button(t("delete"), key=f"delete_{strat['id']}", type="secondary"):
                    success, msg = delete_strategy(strat['id'])
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

            st.divider()


def show_create_form():
    """Show form to create new strategy"""
    st.subheader(t("create_strategy"))

    with st.form("create_strategy"):
        col1, col2 = st.columns(2)

        with col1:
            strat_id = st.text_input(
                t("strategy_id"),
                placeholder="my_strategy",
                help="Unique identifier (lowercase, no spaces)"
            )
            strat_name = st.text_input(
                t("strategy_name"),
                placeholder="My Strategy"
            )
            strat_author = st.text_input(
                t("author"),
                value=username
            )

        with col2:
            strat_version = st.text_input(
                t("version"),
                value="1.0"
            )
            strat_timeframe = st.selectbox(
                t("timeframe"),
                options=["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
                index=1
            )
            strat_entry_time = st.text_input(
                t("entry_time"),
                value="21:05",
                help="Format: HH:MM"
            )

        strat_description = st.text_area(
            t("description"),
            placeholder="Describe the strategy rules and logic...",
            height=100
        )

        st.markdown(f"**{t('parameters')}**")
        col1, col2, col3 = st.columns(3)

        with col1:
            sl_pips = st.number_input(t("sl_pips"), value=30, min_value=1)
        with col2:
            rr_ratio = st.number_input(t("rr_ratio"), value=2.0, min_value=0.5, step=0.5)
        with col3:
            max_candles = st.number_input(t("max_candles"), value=7, min_value=1)

        st.markdown(f"**{t('exit_types')}**")
        col1, col2 = st.columns(2)

        with col1:
            tp_type = st.selectbox(t("tp_type"), ["price_based", "close_based"], index=0)
        with col2:
            sl_type = st.selectbox(t("sl_type"), ["close_based", "price_based"], index=0)

        symbols = st.text_input(
            t("symbols_input"),
            value="XAUUSD, BTCUSD, ETHUSD"
        )

        submitted = st.form_submit_button(t("create_strategy_btn"), type="primary", width='stretch')

        if submitted:
            if not strat_id or not strat_name:
                st.error(t("strategy_id_required"))
            else:
                # Build strategy dict
                strategy = {
                    'id': strat_id.lower().replace(' ', '_'),
                    'name': strat_name,
                    'version': strat_version,
                    'description': strat_description,
                    'author': strat_author,
                    'enabled': True,
                    'entry': {
                        'timeframe': strat_timeframe,
                        'time': strat_entry_time,
                        'timezone': 'Asia/Ho_Chi_Minh',
                        'rules': {
                            'bullish': 'close > open -> BUY',
                            'bearish': 'close < open -> SELL',
                            'doji': 'close == open -> SKIP'
                        }
                    },
                    'exit': {
                        'tp': {'type': tp_type},
                        'sl': {'type': sl_type},
                        'time_limit': {
                            'enabled': True,
                            'max_candles': max_candles
                        }
                    },
                    'parameters': {
                        'sl_pips': sl_pips,
                        'rr_ratio': rr_ratio,
                        'lot_size': 0.01
                    },
                    'symbols': [s.strip() for s in symbols.split(',')]
                }

                success, msg = save_strategy(strategy)
                if success:
                    st.success(t("strategy_created", name=strat_name))
                    st.rerun()
                else:
                    st.error(msg)


def show_view_edit():
    """Show strategy details and edit form"""
    st.subheader(t("view_edit_strategy"))

    strategies = list_strategies()

    if not strategies:
        st.info(t("no_strategies_avail"))
        return

    # Strategy selector
    strat_options = {s['name']: s['id'] for s in strategies}
    selected_name = st.selectbox(t("select_strategy"), options=list(strat_options.keys()))
    selected_id = strat_options[selected_name]

    # Load full strategy
    strategy = get_strategy(selected_id)

    if not strategy:
        st.error(t("failed_load_strategy"))
        return

    # Display tabs
    view_tab, yaml_tab, edit_tab = st.tabs(["View", "YAML", "Edit"])

    with view_tab:
        # Display strategy details
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"**ID:** `{strategy.get('id')}`")
            st.markdown(f"**{t('version')}:** {strategy.get('version')}")
            st.markdown(f"**{t('author')}:** {strategy.get('author')}")
            st.markdown(f"**{t('created')}:** {strategy.get('created')}")
            st.markdown(f"**{t('enabled')}:** {t('yes') if strategy.get('enabled') else t('no')}")

        with col2:
            entry = strategy.get('entry', {})
            st.markdown(f"**{t('timeframe')}:** {entry.get('timeframe')}")
            st.markdown(f"**{t('entry_time')}:** {entry.get('time')}")
            st.markdown(f"**Timezone:** {entry.get('timezone')}")

        st.markdown("---")
        st.markdown(f"**{t('description')}:**")
        st.markdown(strategy.get('description', 'No description'))

        st.markdown("---")
        st.markdown(f"**{t('entry_rules')}**")
        rules = strategy.get('entry', {}).get('rules', {})
        for rule_name, rule_value in rules.items():
            st.markdown(f"- **{rule_name}:** {rule_value}")

        st.markdown("---")
        st.markdown(f"**{t('exit_config')}**")
        exit_config = strategy.get('exit', {})
        st.markdown(f"- **{t('tp_type')}:** {exit_config.get('tp', {}).get('type')}")
        st.markdown(f"- **{t('sl_type')}:** {exit_config.get('sl', {}).get('type')}")
        st.markdown(f"- **{t('max_candles')}:** {exit_config.get('time_limit', {}).get('max_candles')} candles")

        st.markdown("---")
        st.markdown(f"**{t('parameters')}**")
        params = strategy.get('parameters', {})
        for param_name, param_value in params.items():
            st.markdown(f"- **{param_name}:** {param_value}")

        st.markdown("---")
        st.markdown(f"**{t('symbols_label')}**")
        st.markdown(", ".join(strategy.get('symbols', [])))

    with yaml_tab:
        # Show raw YAML
        yaml_str = yaml.dump(strategy, default_flow_style=False, allow_unicode=True, sort_keys=False)
        st.code(yaml_str, language='yaml')

    with edit_tab:
        st.warning(t("edit_strategy_warn"))

        with st.form("edit_strategy"):
            col1, col2 = st.columns(2)

            with col1:
                edit_name = st.text_input(t("name"), value=strategy.get('name', ''))
                edit_version = st.text_input(t("version"), value=strategy.get('version', ''))
                edit_author = st.text_input(t("author"), value=strategy.get('author', ''))

            with col2:
                entry = strategy.get('entry', {})
                edit_timeframe = st.selectbox(
                    t("timeframe"),
                    options=["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
                    index=["M1", "M5", "M15", "M30", "H1", "H4", "D1"].index(entry.get('timeframe', 'M5'))
                )
                edit_entry_time = st.text_input(t("entry_time"), value=entry.get('time', ''))

            edit_description = st.text_area(t("description"), value=strategy.get('description', ''), height=100)

            st.markdown(f"**{t('parameters')}**")
            params = strategy.get('parameters', {})
            col1, col2, col3 = st.columns(3)

            with col1:
                edit_sl_pips = st.number_input(t("sl_pips"), value=params.get('sl_pips', 30))
            with col2:
                edit_rr_ratio = st.number_input(t("rr_ratio"), value=float(params.get('rr_ratio', 2.0)))
            with col3:
                exit_config = strategy.get('exit', {})
                edit_max_candles = st.number_input(
                    t("max_candles"),
                    value=exit_config.get('time_limit', {}).get('max_candles', 7)
                )

            edit_symbols = st.text_input(t("symbols_label"), value=", ".join(strategy.get('symbols', [])))

            if st.form_submit_button("Save Changes", type="primary", width='stretch'):
                # Update strategy
                strategy['name'] = edit_name
                strategy['version'] = edit_version
                strategy['author'] = edit_author
                strategy['description'] = edit_description
                strategy['entry']['timeframe'] = edit_timeframe
                strategy['entry']['time'] = edit_entry_time
                strategy['parameters']['sl_pips'] = edit_sl_pips
                strategy['parameters']['rr_ratio'] = edit_rr_ratio
                strategy['exit']['time_limit']['max_candles'] = edit_max_candles
                strategy['symbols'] = [s.strip() for s in edit_symbols.split(',')]

                success, msg = save_strategy(strategy)
                if success:
                    st.success("Strategy updated!")
                    st.rerun()
                else:
                    st.error(msg)


if __name__ == "__main__":
    main()
