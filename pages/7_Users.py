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

username, name = require_auth()

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def main():
    st.title("👥 User Management")

    # Admin only
    if not is_admin(username):
        st.error("Access denied. Admin only.")
        st.stop()

    st.success(f"Admin: {name}")

    now = datetime.now(TIMEZONE)
    st.markdown(f"**Current Time:** {now.strftime('%H:%M:%S %d/%m/%Y')} (HCM)")

    st.divider()

    # Current users
    st.subheader("📋 Current Users")

    config = load_config()
    users_data = []

    for uname, udata in config['credentials']['usernames'].items():
        users_data.append({
            "Username": uname,
            "Name": udata.get('name', ''),
            "Email": udata.get('email', ''),
            "Role": udata.get('role', 'user').upper()
        })

    if users_data:
        st.dataframe(users_data, width='stretch', hide_index=True)
    else:
        st.info("No users found")

    st.divider()

    # Register new user
    st.subheader("➕ Register New User")

    with st.form("register_form"):
        col1, col2 = st.columns(2)

        with col1:
            new_username = st.text_input("Username*", placeholder="johndoe")
            new_name = st.text_input("Full Name*", placeholder="John Doe")
            new_email = st.text_input("Email", placeholder="john@example.com")

        with col2:
            new_password = st.text_input("Password*", type="password", placeholder="Min 6 characters")
            new_password_confirm = st.text_input("Confirm Password*", type="password")
            new_role = st.selectbox("Role", ["user", "admin"])

        submitted = st.form_submit_button("Register User", width='stretch', type="primary")

        if submitted:
            # Validation
            if not new_username or not new_name or not new_password:
                st.error("Please fill in all required fields (*)")
            elif len(new_password) < 6:
                st.error("Password must be at least 6 characters")
            elif new_password != new_password_confirm:
                st.error("Passwords do not match")
            elif new_username in config['credentials']['usernames']:
                st.error(f"Username '{new_username}' already exists")
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
                    st.success(f"User '{new_username}' registered successfully!")
                    st.rerun()
                else:
                    st.error("Failed to register user")

    st.divider()

    # Delete user
    st.subheader("🗑️ Delete User")

    users_to_delete = [u for u in config['credentials']['usernames'].keys() if u != username]

    if users_to_delete:
        user_to_delete = st.selectbox("Select user to delete", users_to_delete)

        if st.button("Delete User", type="secondary"):
            if user_to_delete == username:
                st.error("Cannot delete yourself")
            else:
                del config['credentials']['usernames'][user_to_delete]
                save_config(config)
                st.success(f"User '{user_to_delete}' deleted")
                st.rerun()
    else:
        st.info("No users to delete (only you exist)")

    st.divider()

    # Change password
    st.subheader("🔑 Change User Password")

    all_users = list(config['credentials']['usernames'].keys())
    target_user = st.selectbox("Select user", all_users, key="pwd_user")

    with st.form("change_pwd_form"):
        new_pwd = st.text_input("New Password", type="password")
        new_pwd_confirm = st.text_input("Confirm New Password", type="password")

        if st.form_submit_button("Change Password"):
            if not new_pwd or len(new_pwd) < 6:
                st.error("Password must be at least 6 characters")
            elif new_pwd != new_pwd_confirm:
                st.error("Passwords do not match")
            else:
                config['credentials']['usernames'][target_user]['password'] = hash_password(new_pwd)
                save_config(config)
                st.success(f"Password changed for '{target_user}'")


if __name__ == "__main__":
    main()
