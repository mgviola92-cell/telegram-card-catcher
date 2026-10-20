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
from app import card_ui
from app import card_exchange, catch_rankings, card_social_ui
from app import collection_stats, collection_stats_ui
from app.card_refs import public_card_id

logging.basicConfig(level=logging.INFO)
TOKEN = os.environ['BOT_TOKEN']
SECRET = os.environ['WEBHOOK_SECRET']
SPAWN_MESSAGES = int(os.environ.get('SPAWN_MESSAGES','35'))
bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
storage.initialize()


def collection_text(user_id, page):
    cards, total = storage.get_cards(user_id, page)
    pages = max(1, (total + card_ui.PAGE_SIZE - 1) // card_ui.PAGE_SIZE)
    page = min(max(0, page), pages - 1)
    if page * card_ui.PAGE_SIZE >= total and total:
        cards, total = storage.get_cards(user_id, page)
    return (card_ui.collection_text(cards, total, page),
            card_ui.collection_keyboard(user_id, cards, page, total))


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
                              reply_markup=keyboard,
                              parse_mode='HTML' if action == 'harem' else None)
    except telebot.apihelper.ApiTelegramException as exc:
        if 'message is not modified' not in str(exc).lower():
            raise
    bot.answer_callback_query(q.id)


@bot.message_handler(commands=['harem','collection','recent'])
def harem(msg):
    text,keyboard = collection_text(msg.from_user.id,0)
    bot.reply_to(msg,text,reply_markup=keyboard,parse_mode='HTML')


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
        bot.edit_message_text(text,q.message.chat.id,q.message.message_id,reply_markup=keyboard,parse_mode='HTML')
        bot.answer_callback_query(q.id)
    except (ValueError,TypeError):
        bot.answer_callback_query(q.id,'Invalid page.')


@bot.callback_query_handler(
    func=lambda q: bool(q.data) and q.data.startswith(('cardview:','cardfav:','cardclose:')))
def card_actions(q):
    try:
        action, owner, code = q.data.split(':')
        if int(owner) != q.from_user.id or len(code) > 32:
            bot.answer_callback_query(q.id,'This is not your card.',show_alert=True)
            return
        row = storage.get_card(code)
        if not row or row['owner_id'] != q.from_user.id:
            bot.answer_callback_query(q.id,'Card is no longer in your collection.',show_alert=True)
            return
        if action == 'cardclose':
            try:
                bot.delete_message(q.message.chat.id,q.message.message_id)
            except telebot.apihelper.ApiTelegramException:
                bot.answer_callback_query(q.id,'Could not close this card.')
                return
            bot.answer_callback_query(q.id)
            return
        if action == 'cardfav':
            enabled = not row['favorite']
            if storage.set_favorites(q.from_user.id,[public_card_id(row)],enabled) != 1:
                bot.answer_callback_query(q.id,'Card could not be updated.',show_alert=True)
                return
            card = dict(row, favorite=enabled)
            markup = card_ui.open_card_keyboard(owner,code,enabled)
            if q.message.content_type == 'photo':
                bot.edit_message_caption(card_ui.owned_caption(card),q.message.chat.id,
                                         q.message.message_id,reply_markup=markup,
                                         parse_mode='HTML')
            else:
                bot.edit_message_text(card_ui.owned_caption(card),q.message.chat.id,
                                      q.message.message_id,reply_markup=markup,
                                      parse_mode='HTML')
            bot.answer_callback_query(q.id,'Favorite updated ⭐')
            return
        if action != 'cardview':
            bot.answer_callback_query(q.id,'Invalid card action.',show_alert=True)
            return
        caption = card_ui.owned_caption(row)
        markup = card_ui.open_card_keyboard(owner,code,row['favorite'])
        if not send_owned_card(bot,storage,q.message.chat.id,row,caption=caption,
                               parse_mode='HTML',reply_markup=markup):
            bot.send_message(q.message.chat.id,caption,parse_mode='HTML',
                             reply_markup=markup)
        bot.answer_callback_query(q.id,'Card opened!')
    except (ValueError,TypeError,IndexError):
        bot.answer_callback_query(q.id,'Invalid card request.',show_alert=True)


@bot.message_handler(commands=['check','view'])
def check(msg):
    parts = msg.text.split(maxsplit=1)
    if len(parts)<2:
        bot.reply_to(msg,'Usage: /check ID')
        return
    row=storage.get_card(parts[1].strip())
    if not row:
        bot.reply_to(msg,'Card not found.')
        return
    caption=card_ui.owned_caption(row)
    markup=card_ui.open_card_keyboard(row['owner_id'],public_card_id(row),row['favorite'])
    if send_owned_card(bot,storage,msg.chat.id,row,caption=caption,
                       parse_mode='HTML',reply_markup=markup):
        return
    bot.reply_to(msg,caption,parse_mode='HTML',reply_markup=markup)



@bot.message_handler(commands=['fav','mfav','unfav'])
def favorites_command(msg):
    command = msg.text.split()[0].split('@')[0].lower()
    codes = msg.text.split()[1:]
    if command == '/fav' and len(codes) != 1:
        bot.reply_to(msg, 'Usage: /fav ID')
        return
    if command == '/mfav' and not 1 <= len(codes) <= 20:
        bot.reply_to(msg, 'Usage: /mfav ID1 ID2 ... (up to 20)')
        return
    if command == '/unfav' and len(codes) != 1:
        bot.reply_to(msg, 'Usage: /unfav ID')
        return
    enabled = command != '/unfav'
    changed = storage.set_favorites(msg.from_user.id, codes, enabled)
    if changed == 1 and len(codes) == 1:
        card = storage.get_card(codes[0])
        if card and card['owner_id'] == msg.from_user.id:
            bot.reply_to(msg, card_ui.favourite_text(card, enabled),
                         parse_mode='HTML')
            return
    if changed:
        bot.reply_to(msg, f"✅ <b>{changed} card(s) updated.</b>",
                     parse_mode='HTML')
    else:
        bot.reply_to(msg, 'No changes. Check that you own every card ID.')


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
    bot.reply_to(msg, card_ui.search_text(found), parse_mode='HTML')

@bot.message_handler(commands=['gift','trade'])
def exchange_command(msg):
    """Reply to a person: explicit recipient acceptance prevents silent transfer."""
    command = msg.text.split()[0].split('@')[0].lower()
    if msg.chat.type not in ('group','supergroup'):
        bot.reply_to(msg,'🎁 Gifts and trades must be offered in a group by replying to the person.')
        return
    target = getattr(getattr(msg,'reply_to_message',None),'from_user',None)
    if (not target or getattr(target,'is_bot',False)
        or getattr(msg.from_user,'is_bot',False)
        or target.id == msg.from_user.id):
        bot.reply_to(msg,'Reply to another real member’s message to make an offer.')
        return
    args=msg.text.split()[1:]
    if command=='/gift' and len(args)==1:
        offer=card_exchange.create_gift(msg.from_user.id,target.id,args[0])
        kind='gift'
    elif command=='/trade' and len(args)==2:
        offer=card_exchange.create_trade(msg.from_user.id,target.id,args[0],args[1])
        kind='trade'
    else:
        bot.reply_to(msg,'Usage (reply to a member): /gift MY_ID or /trade MY_ID THEIR_ID')
        return
    if not offer:
        bot.reply_to(msg,'Offer unavailable. Check card IDs, ownership and pending-offer limit.')
        return
    card_ids=([offer['card_id']] if kind=='gift' else
              [offer['sender_card_id'],offer['receiver_card_id']])
    caption=card_social_ui.offer_caption(
        kind, msg.from_user.first_name, target.first_name, card_ids)
    bot.reply_to(msg, caption, parse_mode='HTML',
                 reply_markup=card_social_ui.exchange_keyboard(kind,offer['offer_id']))


@bot.callback_query_handler(
    func=lambda q: bool(q.data) and q.data.startswith('exchange:'))
def exchange_callback(q):
    parts=q.data.split(':')
    if (len(parts)!=4 or parts[0]!='exchange'
        or parts[1] not in ('g','t')
        or parts[3] not in ('a','d') or not parts[2].isdigit()):
        bot.answer_callback_query(q.id,'Invalid offer.',show_alert=True)
        return
    offer_id=int(parts[2])
    kind='gift' if parts[1]=='g' else 'trade'
    result=card_exchange.finish_offer(kind,offer_id,q.from_user.id,parts[3]=='a')
    if result is None:
        bot.answer_callback_query(q.id,
            'Only the recipient can respond to an active offer.',show_alert=True)
        return
    response=card_social_ui.result_caption(kind,result['status'],
                                           result.get('card_ids'))
    try:
        bot.edit_message_text(response,q.message.chat.id,q.message.message_id,
                              parse_mode='HTML',reply_markup=None)
    except telebot.apihelper.ApiTelegramException:
        logging.exception('Gift/trade settled; Telegram message update failed')
    bot.answer_callback_query(q.id,result['status'].capitalize())


@bot.message_handler(commands=['top','gtop','today'])
def top_command(msg):
    command=msg.text.split()[0].split('@')[0].lower()
    if command=='/gtop':
        if msg.chat.type not in ('group','supergroup'):
            bot.reply_to(msg,'Use /gtop in a group.')
            return
        entries=catch_rankings.catch_leaderboard(chat_id=msg.chat.id)
        kind='group'
    elif command=='/today':
        entries=catch_rankings.catch_leaderboard(today=True)
        kind='today'
    else:
        entries=catch_rankings.catch_leaderboard()
        kind='global'
    bot.reply_to(msg,card_social_ui.leaderboard_caption(entries,kind),
                 parse_mode='HTML',disable_web_page_preview=True)


@bot.message_handler(commands=['stats','progress','series'])
def collection_stats_command(msg):
    cmd=msg.text.split()[0].split('@')[0].lower()
    if cmd=='/stats':
        response=collection_stats_ui.overview_text(
            collection_stats.overview(msg.from_user.id))
    elif cmd=='/progress':
        response=collection_stats_ui.progress_text(
            collection_stats.recent_series_progress(msg.from_user.id))
    else:
        args=msg.text.split(maxsplit=1)
        if len(args)!=2 or not 1<=len(args[1].strip())<=150:
            bot.reply_to(msg,'Usage: /series EXACT SERIES NAME')
            return
        row=collection_stats.series_progress(msg.from_user.id,args[1].strip())
        response=collection_stats_ui.series_text(row)
    bot.reply_to(msg,response,parse_mode='HTML')


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


def send_spawn(chat_id, char):
    """One Telegram photo attempt per source; cache failure never reposts."""
    caption = card_ui.spawn_caption(char)
    artwork = dict(char, character_id=char['id'])
    try:
        sent = send_owned_card(bot, storage, chat_id, artwork,
                              caption=caption, parse_mode='HTML')
    except Exception:
        logging.exception('Unexpected spawn photo delivery error')
        sent = None
    if sent:
        return
    # An invisible spawn cannot be guessed. If Telegram rejected the image,
    # unblock the group for the next activity-triggered spawn.
    storage.clear_spawn(chat_id, char['id'])
    logging.error('Spawn discarded: no usable image for character %s',char['id'])


@bot.message_handler(func=lambda m: m.chat.type in ('group','supergroup') and bool(m.text) and not m.text.startswith('/'),content_types=['text'])
def activity(msg):
    if msg.from_user.is_bot:
        return
    caught=storage.claim(msg.chat.id,msg.from_user.id,msg.text)
    if caught:
        bot.reply_to(msg,card_ui.catch_text(caught,msg.from_user.first_name),
                     parse_mode='HTML',
                     reply_markup=card_ui.catch_keyboard(msg.from_user.id,public_card_id(caught)))
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
