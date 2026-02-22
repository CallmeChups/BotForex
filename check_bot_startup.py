"""
Diagnostic script to test bot startup and see actual errors
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.auth import get_user_mt5_credentials, list_users

print("=== Bot Startup Diagnostic ===\n")

# 1. Check available users
print("1. Checking available users...")
users = list_users()
print(f"   Found {len(users)} users:")
for user in users:
    print(f"   - {user['username']}")

# 2. Ask which user
print("\n2. Which user are you trying to run bots with?")
username = input("   Enter username: ").strip()

# 3. Check MT5 credentials
print(f"\n3. Checking MT5 credentials for '{username}'...")
credentials = get_user_mt5_credentials(username)

if not credentials:
    print(f"   ❌ ERROR: No credentials found for user '{username}'")
    print("   Solution: Go to Settings page and configure MT5 account")
    sys.exit(1)

if not credentials.get('login'):
    print(f"   ❌ ERROR: MT5 login not configured")
    print(f"   Credentials found: {credentials}")
    print("   Solution: Go to Settings page and configure MT5 account")
    sys.exit(1)

print(f"   ✓ Login: {credentials['login']}")
print(f"   ✓ Server: {credentials['server']}")
print(f"   ✓ Password: {'*' * len(credentials.get('password', ''))}")

# 4. Test MT5 connection
print(f"\n4. Testing MT5 connection...")
try:
    import MetaTrader5 as mt5

    if not mt5.initialize():
        print(f"   ❌ ERROR: MT5 initialization failed")
        sys.exit(1)

    print(f"   ✓ MT5 initialized")

    login = int(credentials.get('login') or 0)
    password = credentials.get('password', '')
    server = credentials.get('server', '')

    if not mt5.login(login=login, password=password, server=server):
        error = mt5.last_error()
        print(f"   ❌ ERROR: MT5 login failed: {error}")
        mt5.shutdown()
        sys.exit(1)

    print(f"   ✓ MT5 login successful")

    # Get account info
    account_info = mt5.account_info()
    if account_info:
        print(f"   ✓ Account: {account_info.name}")
        print(f"   ✓ Balance: ${account_info.balance:.2f}")
        print(f"   ✓ Equity: ${account_info.equity:.2f}")

    mt5.shutdown()
    print(f"\n✅ ALL CHECKS PASSED!")
    print(f"\nBot should be able to start for user '{username}'")
    print(f"If bot still doesn't start, check the log file at: logs/bot_<pid>.log")

except ImportError:
    print(f"   ❌ ERROR: MetaTrader5 not installed")
    print(f"   Solution: pip install MetaTrader5")
    sys.exit(1)
except Exception as e:
    print(f"   ❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
