"""Simple Telegram notification test"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_message(text: str) -> bool:
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}

    response = requests.post(url, json=payload)

    if response.ok:
        print(f"Message sent successfully!")
        return True
    else:
        print(f"Failed: {response.text}")
        return False

if __name__ == "__main__":
    send_message("Test message from BotForex")
