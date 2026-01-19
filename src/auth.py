"""
Authentication module for BotForex Dashboard
"""

import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import os
import bcrypt

AUTH_FILE = "config/auth.yaml"


def load_config():
    """Load authentication config from YAML file"""
    if os.path.exists(AUTH_FILE):
        with open(AUTH_FILE) as file:
            return yaml.load(file, Loader=SafeLoader)
    return None


def save_config(config):
    """Save authentication config to YAML file"""
    os.makedirs("config", exist_ok=True)
    with open(AUTH_FILE, 'w') as file:
        yaml.dump(config, file, default_flow_style=False)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def get_authenticator():
    """Get or create the authenticator object"""
    config = load_config()

    if config is None:
        st.error("Authentication config not found. Please create config/auth.yaml")
        st.stop()

    authenticator = stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days'],
    )

    return authenticator, config


def check_auth():
    """
    Check authentication status. Must be called at the start of each page.

    Returns:
        tuple: (is_authenticated, username, user_role)
    """
    if 'authentication_status' not in st.session_state:
        st.session_state['authentication_status'] = None
    if 'username' not in st.session_state:
        st.session_state['username'] = None
    if 'name' not in st.session_state:
        st.session_state['name'] = None

    return (
        st.session_state.get('authentication_status'),
        st.session_state.get('username'),
        st.session_state.get('name')
    )


def require_auth():
    """
    Require authentication to access the page.
    Reads cookie to restore session if needed.
    If not authenticated, shows login form and stops execution.
    """
    # First check if already authenticated in session
    auth_status, username, name = check_auth()

    # If not authenticated, try to restore from cookie
    if not auth_status:
        try:
            authenticator, config = get_authenticator()
            # This reads the cookie and restores session
            authenticator.login()

            # Check again after cookie read
            auth_status = st.session_state.get('authentication_status')
            username = st.session_state.get('username')
            name = st.session_state.get('name')
        except Exception as e:
            pass

    if not auth_status:
        st.warning("Please log in from the main page to access this content.")
        st.page_link("app.py", label="Go to Login", icon="🔐")
        st.stop()

    return username, name


def get_user_role(username: str) -> str:
    """Get user role from config"""
    config = load_config()
    if config and username in config['credentials']['usernames']:
        return config['credentials']['usernames'][username].get('role', 'user')
    return 'user'


def is_admin(username: str) -> bool:
    """Check if user is admin"""
    return get_user_role(username) == 'admin'


def register_user(username: str, name: str, password: str, email: str, role: str = 'user') -> bool:
    """Register a new user"""
    config = load_config()

    if username in config['credentials']['usernames']:
        return False  # User already exists

    config['credentials']['usernames'][username] = {
        'name': name,
        'password': hash_password(password),
        'email': email,
        'role': role,
        'mt5': {
            'login': '',
            'password': '',
            'server': ''
        }
    }

    save_config(config)
    return True


def get_user_mt5_credentials(username: str) -> dict:
    """Get user's MT5 credentials"""
    config = load_config()
    if config and username in config['credentials']['usernames']:
        user_data = config['credentials']['usernames'][username]
        mt5_creds = user_data.get('mt5', {})
        return {
            'login': mt5_creds.get('login', ''),
            'password': mt5_creds.get('password', ''),
            'server': mt5_creds.get('server', '')
        }
    return {'login': '', 'password': '', 'server': ''}


def set_user_mt5_credentials(username: str, login: str, password: str, server: str) -> bool:
    """Set user's MT5 credentials"""
    config = load_config()
    if config and username in config['credentials']['usernames']:
        if 'mt5' not in config['credentials']['usernames'][username]:
            config['credentials']['usernames'][username]['mt5'] = {}

        config['credentials']['usernames'][username]['mt5'] = {
            'login': login,
            'password': password,
            'server': server
        }
        save_config(config)
        return True
    return False


def has_mt5_credentials(username: str) -> bool:
    """Check if user has MT5 credentials configured"""
    creds = get_user_mt5_credentials(username)
    return bool(creds['login'] and creds['password'] and creds['server'])
