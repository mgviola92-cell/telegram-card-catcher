"""Telegram character catcher: Phase 1, no persistent local media."""
import logging
import os
from flask import Flask, abort, request
import telebot
from telebot import types
from app import storage
from app.webhook_guard import begin_update
from app import welcome
from app.owned_media import send_owned_card

logging.basicConfig(level=logging.INFO)
TOKEN = os.environ['BOT_TOKEN']
SECRET = os.environ['WEBHOOK_SECRET']
SPAWN_MESSAGES = int(os.environ.get('SPAWN_MESSAGES','35'))
bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
storage.initialize()


def collection_text(user_id, page):
    cards,total = storage.get_cards(user_id,page)
    pages = max(1,(total+7)//8)
    page = min(max(0,page),pages-1)
    if page*8>=total and total:
        cards,total = storage.get_cards(user_id,page)
    if not cards:
        return '🃏 Your harem is empty. Catch a character in a group!',None
    rows = [f"{'⭐ ' if c['favorite'] else ''}• {c['name']} · {c['rarity']} · Gen {c['generation']}\n  🆔 {c['code']}" for c in cards]
    keyboard = types.InlineKeyboardMarkup()
    buttons = []
    if page:
        buttons.append(types.InlineKeyboardButton('◀️',callback_data=f'harem:{user_id}:{page-1}'))
    buttons.append(types.InlineKeyboardButton(f'{page+1}/{pages}',callback_data='noop'))
    if page+1<pages:
        buttons.append(types.InlineKeyboardButton('▶️',callback_data=f'harem:{user_id}:{page+1}'))
    keyboard.row(*buttons)
    return f'🃏 Global Harem · {total} cards\n\n'+'\n'.join(rows),keyboard


@bot.message_handler(commands=['start'])
def start_command(msg):
    bot.send_message(msg.chat.id, welcome.WELCOME_TEXT,
                     reply_markup=welcome.welcome_keyboard())


@bot.message_handler(commands=['help','cmds'])
def help_command(msg):
    bot.send_message(msg.chat.id, welcome.COMMANDS_TEXT,
                     reply_markup=welcome.return_keyboard())


@bot.callback_query_handler(func=lambda q: bool(q.data) and q.data.startswith('ui:'))
def welcome_menu_callback(q):
    action = q.data.partition(':')[2]
    if action == 'harem':
        text, keyboard = collection_text(q.from_user.id, 0)
    elif action == 'cmds':
        text, keyboard = welcome.COMMANDS_TEXT, welcome.return_keyboard()
    elif action == 'guide':
        text, keyboard = welcome.GUIDE_TEXT, welcome.return_keyboard()
    elif action == 'home':
        text, keyboard = welcome.WELCOME_TEXT, welcome.welcome_keyboard()
    else:
        bot.answer_callback_query(q.id, 'Unknown action')
        return
    # Edit existing menu where possible, rather than flooding the chat.
    try:
        bot.edit_message_text(text, q.message.chat.id, q.message.message_id,
                              reply_markup=keyboard)
    except telebot.apihelper.ApiTelegramException as exc:
        if 'message is not modified' not in str(exc).lower():
            raise
    bot.answer_callback_query(q.id)


@bot.message_handler(commands=['harem','collection','recent'])
def harem(msg):
    text,keyboard = collection_text(msg.from_user.id,0)
    bot.reply_to(msg,text,reply_markup=keyboard)


@bot.callback_query_handler(func=lambda q: q.data.startswith('harem:') or q.data=='noop')
def turn_page(q):
    if q.data=='noop':
        bot.answer_callback_query(q.id)
        return
    try:
        _,owner,page = q.data.split(':')
        if int(owner)!=q.from_user.id:
            bot.answer_callback_query(q.id,'This is not your collection.',show_alert=True)
            return
        page = int(page)
        if page<0 or page>99999:
            raise ValueError
        text,keyboard = collection_text(q.from_user.id,page)
        bot.edit_message_text(text,q.message.chat.id,q.message.message_id,reply_markup=keyboard)
        bot.answer_callback_query(q.id)
    except (ValueError,TypeError):
        bot.answer_callback_query(q.id,'Invalid page.')


@bot.message_handler(commands=['check','view'])
def check(msg):
    parts = msg.text.split(maxsplit=1)
    if len(parts)<2:
        bot.reply_to(msg,'Usage: /check CODE')
        return
    row=storage.get_card(parts[1].strip())
    if not row:
        bot.reply_to(msg,'Card not found.')
        return
    caption=f"🃏 {row['name']} — {row['series']}\n{row['rarity']} · Gen {row['generation']}\n🆔 {row['code']}"
    if send_owned_card(bot, storage, msg.chat.id, row, caption=caption):
        return
    bot.reply_to(msg,caption)




@bot.message_handler(commands=['fav','mfav','unfav'])
def favorites_command(msg):
    command = msg.text.split()[0].split('@')[0].lower()
    codes = msg.text.split()[1:]
    if command == '/fav' and len(codes) != 1:
        bot.reply_to(msg, 'Usage: /fav CODE')
        return
    if command == '/mfav' and not 1 <= len(codes) <= 20:
        bot.reply_to(msg, 'Usage: /mfav CODE1 CODE2 ... (up to 20)')
        return
    if command == '/unfav' and len(codes) != 1:
        bot.reply_to(msg, 'Usage: /unfav CODE')
        return
    changed = storage.set_favorites(msg.from_user.id, codes, command != '/unfav')
    bot.reply_to(msg, f'⭐ Updated {changed} card(s).' if changed else
                 'No changes. Check that you own every card code.')


@bot.message_handler(commands=['search'])
def search_command(msg):
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2 or not 2 <= len(parts[1].strip()) <= 80:
        bot.reply_to(msg, 'Usage: /search CHARACTER OR SERIES')
        return
    found = storage.search_characters(parts[1])
    if not found:
        bot.reply_to(msg, 'No matching characters found.')
        return
    lines = [f"#{c['id']} · {c['name']} — {c['series']} ({c['rarity']})" for c in found]
    bot.reply_to(msg, '🔎 Character Search\n' + '\n'.join(lines))

@bot.message_handler(commands=['changetime'])
def changetime(msg):
    if msg.chat.type=='private':
        bot.reply_to(msg,'Group admins only.')
        return
    member=bot.get_chat_member(msg.chat.id,msg.from_user.id)
    if member.status not in ('administrator','creator'):
        bot.reply_to(msg,'Group admins only.')
        return
    try:
        value=int(msg.text.split(maxsplit=1)[1])
        if not 10<=value<=500:
            raise ValueError
    except (ValueError,IndexError):
        bot.reply_to(msg,'Usage: /changetime 35 (10–500)')
        return
    storage.set_spawn_rate(msg.chat.id,value)
    bot.reply_to(msg,f'✅ Spawn every {value} messages.')


def send_spawn(chat_id,char):
    caption=f"✨ A character appeared!\nSeries: {char['series']} · {char['rarity']}\nGuess the name!"
    sources=[char.get('telegram_file_id'),char.get('image_url')]
    for source in filter(None,sources):
        try:
            message=bot.send_photo(chat_id,source,caption=caption)
            if message.photo and not char.get('telegram_file_id'):
                storage.cache_image(char['id'],message.photo[-1].file_id)
            return
        except Exception:
            logging.exception('Spawn image source failed')
    # Do not leave an uncatchable invisible card active.
    storage.clear_spawn(chat_id,char['id'])
    logging.error('Spawn discarded: no usable image for character %s',char['id'])


@bot.message_handler(func=lambda m: m.chat.type in ('group','supergroup') and bool(m.text) and not m.text.startswith('/'),content_types=['text'])
def activity(msg):
    if msg.from_user.is_bot:
        return
    caught=storage.claim(msg.chat.id,msg.from_user.id,msg.text)
    if caught:
        bot.reply_to(msg,f"🎉 {caught['name']} caught!\n{caught['rarity']} · Gen {caught['generation']}\n🆔 {caught['code']}")
        return
    spawned=storage.try_spawn(msg.chat.id,SPAWN_MESSAGES)
    if spawned:
        send_spawn(msg.chat.id,spawned)


@app.get('/')
def health():
    return {'status':'ok','phase':1}


@app.post('/telegram/<secret>')
def webhook(secret):
    if secret!=SECRET or request.headers.get('X-Telegram-Bot-Api-Secret-Token')!=SECRET:
        abort(403)
    data=request.get_json(silent=True)
    if not isinstance(data,dict) or 'update_id' not in data:
        abort(400)
    if not isinstance(data['update_id'], int):
        abort(400)
    if not begin_update(data['update_id']):
        return 'OK',200
    update=types.Update.de_json(data)
    bot.process_new_updates([update])
    return 'OK',200
