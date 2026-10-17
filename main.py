"""Phase 1 Telegram collectible-character bot (webhook MVP)."""
import os
import logging
from flask import Flask, abort, request
import telebot
from app import storage

logging.basicConfig(level=logging.INFO)
TOKEN = os.environ['BOT_TOKEN']
SECRET = os.environ['WEBHOOK_SECRET']
PUBLIC_BASE_URL = os.environ['PUBLIC_BASE_URL'].rstrip('/')
SPAWN_MESSAGES = int(os.environ.get('SPAWN_MESSAGES', '35'))
bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
storage.initialize()

@bot.message_handler(commands=['start','help'])
def help_command(msg):
    bot.reply_to(msg, '🃏 Character Catcher — Phase 1\n/harem — your collection\n/check CODE — inspect card\n/changetime COUNT — admins only\nCatch a spawn by typing its character name first!')

@bot.message_handler(commands=['harem','collection','recent'])
def harem(msg):
    cards = storage.get_cards(msg.from_user.id)
    if not cards:
        bot.reply_to(msg, 'Your harem is empty. Catch a character in a group!')
        return
    lines = [f"{r['code']} | {r['name']} | {r['rarity']} | Gen {r['generation']}" for r in cards]
    bot.reply_to(msg, '🃏 Recent cards\n' + '\n'.join(lines))

@bot.message_handler(commands=['check','view'])
def check(msg):
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(msg, 'Use /check CODE')
        return
    with storage.connect() as db:
        row = db.execute('''SELECT o.code,o.generation,c.name,c.series,c.rarity FROM owned_cards o
          JOIN characters c ON c.id=o.character_id WHERE o.code=%s''', (parts[1].strip().upper(),)).fetchone()
    bot.reply_to(msg, f"🃏 {row['name']} ({row['series']})\n{row['rarity']} • Gen {row['generation']}\nCode: {row['code']}" if row else 'Card not found.')

@bot.message_handler(commands=['changetime'])
def changetime(msg):
    if msg.chat.type == 'private':
        bot.reply_to(msg, 'This is a group admin command.')
        return
    member = bot.get_chat_member(msg.chat.id, msg.from_user.id)
    if member.status not in ('administrator','creator'):
        bot.reply_to(msg, 'Admins only.')
        return
    parts = msg.text.split(maxsplit=1)
    try:
        value = int(parts[1])
        if not 10 <= value <= 500:
            raise ValueError
    except (ValueError,IndexError):
        bot.reply_to(msg, 'Usage: /changetime 35 (10–500 messages)')
        return
    storage.set_spawn_rate(msg.chat.id, value)
    bot.reply_to(msg, f'Spawn rate updated: {value} messages.')

@bot.message_handler(func=lambda m: m.chat.type in ('group','supergroup') and bool(m.text) and not m.text.startswith('/'), content_types=['text'])
def activity(msg):
    char = storage.claim(msg.chat.id, msg.from_user.id, msg.text)
    if char:
        bot.reply_to(msg, f"🎉 Caught {char['name']}!\nRarity: {char['rarity']}\nGen {char['generation']} • Code: {char['code']}")
        return
    spawned = storage.try_spawn(msg.chat.id, SPAWN_MESSAGES)
    if not spawned:
        return
    caption = f"✨ A wild character appeared!\n{spawned['series']} • {spawned['rarity']}\nGuess the character's name in chat!"
    try:
        photo = bot.send_photo(msg.chat.id, spawned['telegram_file_id'] or spawned['image_url'], caption=caption)
        if photo.photo and not spawned['telegram_file_id']:
            storage.cache_image(spawned['id'], photo.photo[-1].file_id)
    except Exception:
        logging.exception('Image send failed, using text fallback')
        bot.send_message(msg.chat.id, caption)

@app.get('/')
def health():
    return {'status':'ok','phase':1}

@app.post('/telegram/<secret>')
def webhook(secret):
    if secret != SECRET or request.headers.get('X-Telegram-Bot-Api-Secret-Token') != SECRET:
        abort(403)
    update = telebot.types.Update.de_json(request.get_data(as_text=True))
    bot.process_new_updates([update])
    return 'OK', 200
