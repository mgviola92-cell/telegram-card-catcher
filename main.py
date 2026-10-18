"""Telegram character catcher: Phase 1, no persistent local media."""
import logging
import os
from flask import Flask, abort, request
import telebot
from telebot import types
from app import storage
from app.webhook_guard import begin_update
from app import welcome
from app import economy, trading, collection_ui

logging.basicConfig(level=logging.INFO)
TOKEN = os.environ['BOT_TOKEN']
SECRET = os.environ['WEBHOOK_SECRET']
SPAWN_MESSAGES = int(os.environ.get('SPAWN_MESSAGES','35'))
bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
storage.initialize()


def collection_text(user_id, page):
    cards,total = storage.get_cards(user_id,page,size=collection_ui.PAGE_SIZE)
    pages = max(1,(total+collection_ui.PAGE_SIZE-1)//collection_ui.PAGE_SIZE)
    page = min(max(0,page),pages-1)
    if page*collection_ui.PAGE_SIZE>=total and total:
        cards,total = storage.get_cards(user_id,page,size=collection_ui.PAGE_SIZE)
    if not cards:
        return '🃏 Your harem is empty. Catch a character in a group!',None
    rows = [f"{'⭐ ' if c['favorite'] else ''}• {c['name']} · {c['rarity']} · Gen {c['generation']}\n  🆔 {c['code']}" for c in cards]
    keyboard = collection_ui.page_markup(user_id,cards,page,total)
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


@bot.message_handler(commands=['showcase'])
def showcase(msg):
    cards,total=storage.get_cards(msg.from_user.id,page=0,size=5)
    if not cards:
        bot.reply_to(msg,'🃏 Your harem is empty. Catch characters first!')
        return
    featured=next((c for c in cards if c['favorite']),cards[0])
    caption=(f"🃏 COLLECTION SHOWCASE • {total} CARDS\n"
             f"━━━━━━━━━━━━━━━━━━\n"
             f"✨ {featured['name']} — {featured['series']}\n"
             f"💎 {featured['rarity']} · Gen {featured['generation']}\n"
             f"🆔 {featured['code']}\n\n"
             "Recent catches:\n" +
             '\n'.join(f"• {c['name']} · {c['code']}" for c in cards))
    for source in (featured.get('telegram_file_id'),featured.get('image_url')):
        if not source:
            continue
        try:
            media=bot.send_photo(msg.chat.id,source,caption=caption)
            if source==featured.get('image_url') and media.photo:
                storage.cache_image(featured['character_id'],media.photo[-1].file_id,
                                    featured['variant_id'],featured['image_url'])
            return
        except telebot.apihelper.ApiTelegramException:
            logging.warning('Showcase artwork unavailable')
    bot.reply_to(msg,caption)


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


@bot.callback_query_handler(func=lambda q: bool(q.data) and q.data.startswith(('card:','cardfav:','cardback:')))
def browse_card(q):
    try:
        action, owner, value, *rest = q.data.split(':')
        if int(owner)!=q.from_user.id:
            bot.answer_callback_query(q.id,'Not your collection.',show_alert=True)
            return
        if action=='cardback':
            page=int(value)
            if not 0<=page<=99999:
                raise ValueError
            txt,kb=collection_text(q.from_user.id,page)
            bot.send_message(q.message.chat.id,txt,reply_markup=kb)
        else:
            if len(rest)!=1:
                raise ValueError
            page=int(rest[0])
            if not 0<=page<=99999:
                raise ValueError
            card=storage.get_card(value)
            if not card or card['owner_id']!=q.from_user.id:
                bot.answer_callback_query(q.id,'Card no longer in your collection.',show_alert=True)
                return
            if action=='cardfav':
                storage.set_favorites(q.from_user.id,[value],not card['favorite'])
                card=storage.get_card(value)
            caption=collection_ui.card_caption(card)
            keyboard=collection_ui.card_markup(q.from_user.id,value,page,card['favorite'])
            for source in (card.get('telegram_file_id'),card.get('image_url')):
                if not source:
                    continue
                try:
                    photo=bot.send_photo(q.message.chat.id,source,caption=caption,reply_markup=keyboard)
                    if photo.photo and source==card.get('image_url'):
                        storage.cache_image(card['character_id'],photo.photo[-1].file_id,
                                            card['variant_id'],card['image_url'])
                    break
                except telebot.apihelper.ApiTelegramException:
                    logging.warning('Card browser image rejected by Telegram')
            else:
                bot.send_message(q.message.chat.id,caption,reply_markup=keyboard)
        bot.answer_callback_query(q.id)
    except (ValueError,TypeError,IndexError):
        bot.answer_callback_query(q.id,'Invalid card page.',show_alert=True)


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
    caption=(f"🃏 {row['name']} — {row['series']}\n"
             f"✨ {row['rarity']} · Gen {row['generation']}\n"
             f"🆔 {row['code']}")
    # Request Telegram-hosted media first: zero Render image transfer.
    # Fall back to Telegram pulling public HTTPS source by URL.
    for source in (row.get('telegram_file_id'),row.get('image_url')):
        if not source:
            continue
        try:
            media=bot.send_photo(msg.chat.id,source,caption=caption)
            if media.photo and source==row.get('image_url'):
                storage.cache_image(row['character_id'],media.photo[-1].file_id,
                                    row['variant_id'],row['image_url'])
            return
        except telebot.apihelper.ApiTelegramException:
            logging.warning('Telegram rejected /check image source')
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


@bot.message_handler(commands=['gift'])
def gift_command(msg):
    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        bot.reply_to(msg, 'Reply to a player: /gift CODE')
        return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, 'Usage: reply to player with /gift CODE')
        return
    recipient = msg.reply_to_message.from_user
    if recipient.is_bot:
        bot.reply_to(msg, 'Cannot gift to bots.')
        return
    transferred = economy.gift_card(msg.from_user.id, recipient.id, args[1])
    bot.reply_to(msg, f'🎁 Card {args[1].upper()} gifted!' if transferred else
                 'Gift failed: card not owned or invalid receiver.')


@bot.message_handler(commands=['trade'])
def trade_command(msg):
    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        bot.reply_to(msg, 'Reply to another player: /trade YOUR_CODE THEIR_CODE')
        return
    tokens = msg.text.split()
    if len(tokens) != 3:
        bot.reply_to(msg, 'Usage: /trade YOUR_CODE THEIR_CODE')
        return
    other = msg.reply_to_message.from_user
    if other.is_bot:
        bot.reply_to(msg, 'Cannot trade with bots.')
        return
    offer_id = trading.create_offer(msg.from_user.id, other.id, tokens[1], tokens[2])
    if not offer_id:
        bot.reply_to(msg, 'Trade failed: check both codes and owners.')
        return
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton('✅ Accept', callback_data=f'trade:{offer_id}:yes'),
           types.InlineKeyboardButton('❌ Decline', callback_data=f'trade:{offer_id}:no'))
    bot.reply_to(msg, f'🤝 Trade offer #{offer_id}\n{tokens[1].upper()} ⇄ {tokens[2].upper()}\n'
                 'Only the recipient can accept within 10 minutes.',reply_markup=kb)


@bot.callback_query_handler(func=lambda q: bool(q.data) and q.data.startswith('trade:'))
def trade_callback(q):
    try:
        _,offer_id,decision=q.data.split(':')
        if decision not in ('yes','no'):
            raise ValueError
        ok=trading.finish_offer(int(offer_id),q.from_user.id,decision=='yes')
        bot.answer_callback_query(q.id,'Trade completed!' if ok and decision=='yes' else
                                  ('Trade declined.' if ok else 'Invalid or expired trade.'),show_alert=True)
        if ok:
            bot.edit_message_reply_markup(q.message.chat.id,q.message.message_id,reply_markup=None)
    except (ValueError, TypeError):
        bot.answer_callback_query(q.id,'Invalid trade request.',show_alert=True)


@bot.message_handler(commands=['top','gtop','todaygtop'])
def ranking_command(msg):
    command=msg.text.split()[0].split('@')[0].lower()
    if command=='/top' and msg.chat.type=='private':
        bot.reply_to(msg,'/top is available in groups. Use /gtop for global rankings.')
        return
    group_id=msg.chat.id if command=='/top' else None
    today=command=='/todaygtop'
    rows=economy.leaderboard(chat_id=group_id,today=today)
    if not rows:
        bot.reply_to(msg,'🏆 No catches recorded for this ranking yet.')
        return
    title=('/top Group Catchers' if group_id is not None else
           "Today's Global Catchers" if today else 'Global Top Catchers')
    lines=[f'🏆 {title}']
    for index,row in enumerate(rows,1):
        lines.append(f"{index}. User {row['owner_id']} — {row['total']} catches")
    bot.reply_to(msg,'\n'.join(lines))


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
            if message.photo and source == char.get('image_url'):
                storage.cache_image(char['id'],message.photo[-1].file_id,
                                    char.get('variant_id'),char['image_url'])
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
