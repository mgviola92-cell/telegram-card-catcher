"""Run ONCE after Render deploy, from a trusted environment with configured env vars."""
import os
import telebot

token = os.environ['BOT_TOKEN']
secret = os.environ['WEBHOOK_SECRET']
base = os.environ['PUBLIC_BASE_URL'].rstrip('/')
bot = telebot.TeleBot(token)
result = bot.set_webhook(url=f'{base}/telegram/{secret}', secret_token=secret, allowed_updates=['message'])
print('Webhook registered:', result)
