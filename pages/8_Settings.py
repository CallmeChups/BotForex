"""
Settings Page - Configure bot settings
"""

import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv, set_key
import os

load_dotenv()

st.set_page_config(
    page_icon="⚙️",
    page_title="Settings",
    layout="wide",
)

# Auth check
from src.auth import require_auth, is_admin, get_user_mt5_credentials, set_user_mt5_credentials, has_mt5_credentials
from src.i18n import t, lang_toggle_button
username, name = require_auth()

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
ENV_FILE = ".env"


def main():
    lang_toggle_button(st.sidebar)
    st.title(f"⚙️ {t('page_settings')}")

    # Show admin status
    if is_admin(username):
        st.success(t("logged_as_admin", name=name))
    else:
        st.info(t("logged_as_user", name=name))

    now = datetime.now(TIMEZONE)
    st.markdown(f"**{t('current_time')}:** {now.strftime('%H:%M:%S %d/%m/%Y')} (HCM)")

    st.divider()

    # MT5 Settings - Per user
    st.subheader(t("mt5_account"))

    # Get current user's MT5 credentials
    user_mt5 = get_user_mt5_credentials(username)

    if has_mt5_credentials(username):
        st.success(t("mt5_configured"))
    else:
        st.warning(t("mt5_not_configured"))

    with st.form("mt5_form"):
        col1, col2 = st.columns(2)

        with col1:
            mt5_login = st.text_input(
                t("mt5_login"),
                value=user_mt5.get('login', ''),
                type="default",
                placeholder=t("mt5_login_placeholder")
            )
            mt5_server = st.text_input(
                t("mt5_server"),
                value=user_mt5.get('server', ''),
                placeholder=t("mt5_server_placeholder")
            )

        with col2:
            mt5_password = st.text_input(
                t("mt5_password"),
                value=user_mt5.get('password', ''),
                type="password",
                placeholder=t("mt5_password_placeholder")
            )
            symbol = st.text_input(
                t("trading_symbol"),
                value=os.getenv("SYMBOL", "XAUUSD"),
                help=t("mt5_symbol_help")
            )

        if st.form_submit_button(t("save_mt5_creds"), type="primary", width='stretch'):
            if not mt5_login or not mt5_password or not mt5_server:
                st.error(t("fill_mt5_fields"))
            else:
                success = set_user_mt5_credentials(username, mt5_login, mt5_password, mt5_server)
                if success:
                    st.success(t("save_mt5_success"))
                    st.rerun()
                else:
                    st.error(t("save_failed"))

    st.divider()

    # Test MT5 connection
    st.subheader(t("test_connection"))

    if st.button(t("test_mt5_conn"), width='stretch'):
        try:
            import MetaTrader5 as mt5
        except ImportError:
            st.error(t("no_mt5"))
            st.stop()

        # Use user's credentials
        user_creds = get_user_mt5_credentials(username)

        try:
            if not mt5.initialize():
                st.error(t("mt5_init_failed"))
            else:
                login = int(user_creds.get('login') or 0)
                password = user_creds.get('password', '')
                server = user_creds.get('server', '')

                if not login or not password or not server:
                    st.error(t("mt5_creds_not_configured"))
                elif mt5.login(login=login, password=password, server=server):
                    account = mt5.account_info()._asdict()
                    st.success(t("connected_balance", bal=account['balance']))
                    mt5.shutdown()
                else:
                    st.error(t("login_failed", err=mt5.last_error()))
                    mt5.shutdown()
        except Exception as e:
            st.error(f"Error: {e}")

    # Admin-only sections
    if is_admin(username):
        st.divider()

        # Telegram Settings (Admin only)
        st.subheader(t("telegram_config"))

        col1, col2 = st.columns(2)

        with col1:
            telegram_token = st.text_input(
                t("bot_token"),
                value=os.getenv("TELEGRAM_BOT_TOKEN", ""),
                type="password"
            )
            telegram_chat_id = st.text_input(
                t("main_chat_id"),
                value=os.getenv("TELEGRAM_CHAT_ID", ""),
                help=t("telegram_signal_help")
            )

        with col2:
            telegram_error_chat_id = st.text_input(
                t("error_chat_id"),
                value=os.getenv("TELEGRAM_ERROR_CHAT_ID", ""),
                help=t("telegram_error_help")
            )
            telegram_test_chat_id = st.text_input(
                t("test_chat_id"),
                value=os.getenv("TELEGRAM_TEST_CHAT_ID", ""),
                help=t("telegram_test_help")
            )

        if st.button(t("test_telegram"), width='stretch'):
            try:
                import requests

                token = os.getenv("TELEGRAM_BOT_TOKEN")
                chat_id = os.getenv("TELEGRAM_TEST_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")

                url = f"https://api.telegram.org/bot{token}/sendMessage"
                payload = {
                    "chat_id": chat_id,
                    "text": "Test from BotForex Settings",
                    "parse_mode": "HTML"
                }
                response = requests.post(url, json=payload)

                if response.ok:
                    st.success(t("msg_sent"))
                else:
                    st.error(f"Failed: {response.text}")
            except Exception as e:
                st.error(f"Error: {e}")

        st.divider()

        # Log Management (Admin only)
        st.subheader(t("log_management"))

        from src.log_manager import get_log_summary, cleanup_empty_logs, cleanup_old_logs

        summary = get_log_summary()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(t("total_log_files"), summary["total_count"])
        m2.metric(t("empty_log_files"), summary["empty_count"])
        m3.metric(t("log_size_mb"), f"{summary['total_size_mb']}")
        m4.metric(
            t("newest_log"),
            summary["newest_dt"].strftime("%m/%d %H:%M") if summary["newest_dt"] else "-",
        )

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button(t("clean_empty_logs"), key="btn_clean_empty"):
                n = cleanup_empty_logs()
                st.success(t("cleaned_empty", n=n))
                st.rerun()
        with col_b:
            days = st.number_input(t("max_age_days"), min_value=1, max_value=90, value=7, key="clean_age_days")
            if st.button(t("clean_old_logs"), key="btn_clean_old"):
                n = cleanup_old_logs(max_age_days=int(days))
                st.success(t("cleaned_old", n=n))
                st.rerun()

        st.divider()

        # Current .env display (Admin only)
        st.subheader(t("system_config"))

        with st.expander(t("view_env")):
            st.code(f"""
# Trading
SYMBOL={os.getenv('SYMBOL', '')}

# Telegram
TELEGRAM_BOT_TOKEN=********
TELEGRAM_CHAT_ID={os.getenv('TELEGRAM_CHAT_ID', '')}
TELEGRAM_ERROR_CHAT_ID={os.getenv('TELEGRAM_ERROR_CHAT_ID', '')}
TELEGRAM_TEST_CHAT_ID={os.getenv('TELEGRAM_TEST_CHAT_ID', '')}
            """)

    st.divider()

    # Info
    st.subheader(t("information"))

    st.markdown(f"""
    **{t('mt5_account_info')}**

    **{t('timeframe')}:**
    - {t('mt5_standard_info')}
    - {t('mt5_pro_info')}
    """)

    # App info
    st.divider()
    col1, col2, col3 = st.columns(3)

    with col1:
        st.caption(f"**{t('version')}:** 0.1.0")

    with col2:
        st.caption(f"**{t('strategy')}:** Master Candle")

    with col3:
        st.caption(f"**{t('timeframe')}:** M5")


if __name__ == "__main__":
    main()
