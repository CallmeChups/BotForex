"""
User Management Page - Admin only
"""

import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import os

load_dotenv()

st.set_page_config(
    page_icon="👥",
    page_title="User Management",
    layout="wide",
)

# Auth check
from src.auth import require_auth, is_admin, load_config, register_user, hash_password, save_config
from src.i18n import t, lang_toggle_button

username, name = require_auth()

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def main():
    lang_toggle_button(st.sidebar)
    st.title(f"👥 {t('page_users')}")

    # Admin only
    if not is_admin(username):
        st.error(t("access_denied"))
        st.stop()

    st.success(t("admin_logged", name=name))

    now = datetime.now(TIMEZONE)
    st.markdown(f"**{t('current_time')}:** {now.strftime('%H:%M:%S %d/%m/%Y')} (HCM)")

    st.divider()

    # Current users
    st.subheader(f"📋 {t('current_users')}")

    config = load_config()
    users_data = []

    for uname, udata in config['credentials']['usernames'].items():
        users_data.append({
            t("username"): uname,
            t("name"): udata.get('name', ''),
            t("email"): udata.get('email', ''),
            t("role"): udata.get('role', 'user').upper()
        })

    if users_data:
        st.dataframe(users_data, width='stretch', hide_index=True)
    else:
        st.info(t("no_users"))

    st.divider()

    # Register new user
    st.subheader(f"➕ {t('register_user')}")

    with st.form("register_form"):
        col1, col2 = st.columns(2)

        with col1:
            new_username = st.text_input(f"{t('username')}*", placeholder="johndoe")
            new_name = st.text_input(t("full_name"), placeholder="John Doe")
            new_email = st.text_input(t("email"), placeholder="john@example.com")

        with col2:
            new_password = st.text_input(f"{t('password')}*", type="password")
            new_password_confirm = st.text_input(t("confirm_password"), type="password")
            new_role = st.selectbox(t("role"), ["user", "admin"])

        submitted = st.form_submit_button(t("register_btn"), width='stretch', type="primary")

        if submitted:
            # Validation
            if not new_username or not new_name or not new_password:
                st.error(t("fill_required"))
            elif len(new_password) < 6:
                st.error(t("password_min"))
            elif new_password != new_password_confirm:
                st.error(t("password_mismatch"))
            elif new_username in config['credentials']['usernames']:
                st.error(t("username_exists", u=new_username))
            else:
                # Register
                success = register_user(
                    username=new_username,
                    name=new_name,
                    password=new_password,
                    email=new_email or f"{new_username}@botforex.com",
                    role=new_role
                )

                if success:
                    st.success(t("user_registered", u=new_username))
                    st.rerun()
                else:
                    st.error(t("failed_register"))

    st.divider()

    # Delete user
    st.subheader(f"🗑️ {t('delete_user')}")

    users_to_delete = [u for u in config['credentials']['usernames'].keys() if u != username]

    if users_to_delete:
        user_to_delete = st.selectbox(t("select_user_delete"), users_to_delete)

        if st.button(t("delete_user_btn"), type="secondary"):
            if user_to_delete == username:
                st.error(t("cant_delete_self"))
            else:
                del config['credentials']['usernames'][user_to_delete]
                save_config(config)
                st.success(t("user_deleted", u=user_to_delete))
                st.rerun()
    else:
        st.info(t("no_users_to_delete"))

    st.divider()

    # Change password
    st.subheader(f"🔑 {t('change_password')}")

    all_users = list(config['credentials']['usernames'].keys())
    target_user = st.selectbox(t("select_user"), all_users, key="pwd_user")

    with st.form("change_pwd_form"):
        new_pwd = st.text_input(t("new_password"), type="password")
        new_pwd_confirm = st.text_input(t("confirm_new_password"), type="password")

        if st.form_submit_button(t("change_password_btn")):
            if not new_pwd or len(new_pwd) < 6:
                st.error(t("password_min"))
            elif new_pwd != new_pwd_confirm:
                st.error(t("password_mismatch"))
            else:
                config['credentials']['usernames'][target_user]['password'] = hash_password(new_pwd)
                save_config(config)
                st.success(t("password_changed", u=target_user))


if __name__ == "__main__":
    main()
