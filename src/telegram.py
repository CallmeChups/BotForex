import telebot
import requests
import time

TOKEN = "7363572293:AAHd595bWg7liBafg8qEmasPh8Zx1I2crWo"
url = f"https://api.telegram.org/bot{TOKEN}"
bot = telebot.TeleBot(TOKEN)

def send_message(
    msg,
    chat_id,
    max_retries=5,
    token=TOKEN,
    disable_notification=True,
    debug=False,
):
    if not debug:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        if isinstance(chat_id, str):
            chat_id = [chat_id]

        chat_id = set(chat_id)
        for ch in chat_id:
            if ch == "":
                continue
            data = {
                "chat_id": ch,
                "text": msg,
                "disable_notification": disable_notification,
            }
            for _ in range(max_retries):
                try:
                    requests.post(url, data)
                    break
                except:
                    time.sleep(5)
    else:
        print(msg)

chat_id = "-4870191713" 
send_message("ok nice", chat_id=chat_id, token = TOKEN)

# Handle '/start' and '/help'
# @bot.message_handler(commands=['help', 'start'])
# def send_welcome(message):
#     bot.reply_to(message, """\
# Hi there, I am EchoBot.
# I am here to echo your kind words back to you. Just say anything nice and I'll say the exact same thing to you!\
# """)


# # Handle all other messages with content_type 'text' (content_types defaults to ['text'])
# # @bot.message_handler(func=lambda message: True)
# # def echo_message(message):
# #     bot.reply_to(message, message.text)

# bot.infinity_polling()

