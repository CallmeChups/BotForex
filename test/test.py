from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import os
import requests
import MetaTrader5 as mt5
import pandas as pd
import time

load_dotenv()

######################################## %%%%% TELEGRAM %%%%% ########################################

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_ERROR_CHAT_ID = os.getenv("TELEGRAM_ERROR_CHAT_ID")

def send_telegram(text: str, is_error: bool = False) -> bool:
    chat_id = TELEGRAM_ERROR_CHAT_ID if is_error else TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    response = requests.post(url, json=payload)
    return response.ok

######################################## %%%%% CONNECT WITH MT5 %%%%% ########################################

account = int(os.getenv("MT5_LOGIN"))
password = os.getenv("MT5_PASSWORD")
server = os.getenv("MT5_SERVER")

if not mt5.initialize():
    send_telegram("❌ MT5 initialization failed", is_error=True)
    quit()

if not mt5.login(login=account, password=password, server=server):
    send_telegram(f"❌ MT5 login failed: {mt5.last_error()}", is_error=True)
    quit()

account_info = mt5.account_info()._asdict()
print(f"Connected: {account_info['name']} | Balance: {account_info['balance']} | Leverage: 1:{account_info['leverage']}")


######################################## %%%%% DEFINE VARIABLE %%%%% ########################################

SYMBOL = "ETHUSDm"
TRADE_FRAME = mt5.TIMEFRAME_M1
timezone = ZoneInfo("Asia/Ho_Chi_Minh")

######################################## %%%%% GET DATA %%%%% ########################################

while True:
    date_to = datetime.now(tz=timezone)
    date_from = date_to - timedelta(hours=1)  # Get last 1 hour of data
    short_data = pd.DataFrame(mt5.copy_rates_range(SYMBOL, TRADE_FRAME, date_from, date_to))

    if short_data.empty:
        send_telegram(f"❌ No data for {SYMBOL}", is_error=True)
        mt5.shutdown()
        quit()

    # Convert timestamp to readable time
    short_data['real_time'] = pd.to_datetime(short_data['time'], unit='s').dt.tz_localize('UTC').dt.tz_convert(timezone)
    short_data['real_time'] = short_data['real_time'].dt.strftime('%Y-%m-%d %H:%M:%S')
    print(short_data.tail())
    time.sleep(1)
######################################## %%%%% SEND TO TELEGRAM %%%%% ########################################

# Get latest candle
latest = short_data.iloc[-1]

message = f"""<b>📊 {SYMBOL} - M5 Data</b>

<b>Time:</b> {latest['real_time']}
<b>Open:</b> {latest['open']:.2f}
<b>High:</b> {latest['high']:.2f}
<b>Low:</b> {latest['low']:.2f}
<b>Close:</b> {latest['close']:.2f}
<b>Volume:</b> {int(latest['tick_volume'])}

<i>Total candles fetched: {len(short_data)}</i>"""

if send_telegram(message):
    print("[OK] Data sent to Telegram")
else:
    print("[ERROR] Failed to send to Telegram")

mt5.shutdown()