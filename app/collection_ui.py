"""Collection card browser: compact callback payloads, strict owner checks."""
from telebot import types

PAGE_SIZE=6

def page_markup(user_id, cards, page, total):
    kb=types.InlineKeyboardMarkup(row_width=2)
    for card in cards:
        code=card['code']
        label=f"{'⭐ ' if card['favorite'] else ''}{card['name'][:24]}"
        kb.add(types.InlineKeyboardButton(label,callback_data=f'card:{user_id}:{code}:{page}'))
    nav=[]
    pages=max(1,(total+PAGE_SIZE-1)//PAGE_SIZE)
    if page>0:
        nav.append(types.InlineKeyboardButton('◀️ Back',callback_data=f'harem:{user_id}:{page-1}'))
    nav.append(types.InlineKeyboardButton(f'{page+1}/{pages}',callback_data='noop'))
    if page+1<pages:
        nav.append(types.InlineKeyboardButton('Next ▶️',callback_data=f'harem:{user_id}:{page+1}'))
    kb.row(*nav)
    return kb

def card_markup(user_id, code, page, favorite):
    kb=types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton('☆ Unfavorite' if favorite else '⭐ Favorite',
        callback_data=f'cardfav:{user_id}:{code}:{page}'))
    kb.add(types.InlineKeyboardButton('◀️ Back to Harem',callback_data=f'cardback:{user_id}:{page}'))
    return kb

def card_caption(card):
    return (f"🃏 {card['name']}\n"
            f"📖 {card['series']}\n"
            f"💎 {card['rarity']} · Gen {card['generation']}\n"
            f"🆔 {card['code']}\n"
            f"{'⭐ Favorite' if card['favorite'] else '✦ Collected'}")

def normalized_page(requested, total):
    """Keep page inside the current collection even after gifts/trades."""
    pages=max(1,(total+PAGE_SIZE-1)//PAGE_SIZE)
    return min(max(0,int(requested)),pages-1)

def recent_markup(user_id, page, total):
    """Text-only recent navigation; avoids photo uploads and extra card messages."""
    kb=types.InlineKeyboardMarkup(row_width=3)
    pages=max(1,(total+PAGE_SIZE-1)//PAGE_SIZE)
    buttons=[]
    if page>0:
        buttons.append(types.InlineKeyboardButton('◀️ Back',callback_data=f'recent:{user_id}:{page-1}'))
    buttons.append(types.InlineKeyboardButton(f'{page+1}/{pages}',callback_data='noop'))
    if page+1<pages:
        buttons.append(types.InlineKeyboardButton('Next ▶️',callback_data=f'recent:{user_id}:{page+1}'))
    kb.row(*buttons)
    return kb
