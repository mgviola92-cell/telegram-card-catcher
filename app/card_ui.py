"""Compact Telegram-native UI for spawn, catch, and owned-card navigation.

No artwork is generated/downloaded: images still come directly from the
character's shared HTTPS URL or Telegram's reusable file_id.
"""
from html import escape
from telebot import types
from app.card_refs import public_card_id

PAGE_SIZE = 8
MAX_NAME = 85
MAX_SERIES = 100

def clean(value, limit=MAX_NAME):
    """Escape arbitrary source text for Telegram HTML without breaking tags."""
    text = str(value or "").strip()
    if len(text) > limit:
        text = text[:limit - 1].rstrip() + "…"
    return escape(text, quote=False)


def spawn_caption(character):
    return (
        "✨ <b>WILD CHARACTER APPEARED</b> ✨\n"
        "━━━━━━━━━━━━━━━━\n"
        f"🎬 <b>Series:</b> {clean(character.get('series'),MAX_SERIES)}\n"
        f"💠 <b>Rarity:</b> {clean(character.get('rarity'),30)}\n\n"
        "🔎 <b>Who's this character?</b>\n"
        "💬 Guess the name in chat to catch it!\n"
        "⏳ <i>15 minutes · First correct guess wins</i>"
    )


def catch_text(character, display_name):
    return (
        "🎉 <b>CHARACTER CAUGHT!</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"👤 <b>{clean(display_name, 45)}</b>\n"
        f"🃏 <b>{clean(character.get('name'))}</b>\n"
        f"🎬 {clean(character.get('series'),MAX_SERIES)}\n"
        f"💠 {clean(character.get('rarity'),30)} · "
        f"<b>Gen {int(character['generation'])}</b>\n"
        f"🆔 <code>{clean(public_card_id(character),32)}</code>\n\n"
        "✅ <i>Added to your global collection</i>"
    )


def owned_caption(character):
    return (
        "🃏 <b>MY CHARACTER CARD</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"✨ <b>{clean(character.get('name'))}</b>\n"
        f"🎬 {clean(character.get('series'),MAX_SERIES)}\n"
        f"💠 {clean(character.get('rarity'),30)} · "
        f"<b>Gen {int(character['generation'])}</b>\n"
        f"🆔 <code>{clean(public_card_id(character),32)}</code>\n"
        + ("⭐ <i>Favorite</i>" if character.get('favorite') else "✦ <i>Collected</i>")
    )


def collection_text(cards, total, page):
    if not cards:
        return ("🃏 <b>MY GLOBAL COLLECTION</b>\n"
                "━━━━━━━━━━━━━━━━\n"
                "Your collection is empty. Catch a character in a group!")
    first = page * PAGE_SIZE + 1
    last = first + len(cards) - 1
    lines = [
        "🃏 <b>MY GLOBAL COLLECTION</b>",
        "━━━━━━━━━━━━━━━━",
        f"📚 <b>{total}</b> cards · Showing {first}–{last}",
        "",
    ]
    for number, card in enumerate(cards, first):
        star = "⭐ " if card.get("favorite") else ""
        lines.append(f"<b>{number:02d}.</b> {star}<b>{clean(card.get('name'),42)}</b>")
        lines.append(f"    💠 {clean(card.get('rarity'),23)} · Gen {int(card['generation'])} "
                     f"· <code>{clean(public_card_id(card),32)}</code>")
    lines.append("\n👇 <i>Tap a character below to open its artwork.</i>")
    return "\n".join(lines)


def collection_keyboard(owner_id, cards, page, total):
    kb = types.InlineKeyboardMarkup(row_width=2)
    for card in cards:
        code = public_card_id(card)
        title = str(card.get("name") or "Character").strip()[:27]
        kb.add(types.InlineKeyboardButton(
            f"🖼 {title}", callback_data=f"cardview:{owner_id}:{code}"))
    pages = max(1, (int(total) + PAGE_SIZE - 1) // PAGE_SIZE)
    controls = []
    if page:
        controls.append(types.InlineKeyboardButton(
            "◀️ Back", callback_data=f"harem:{owner_id}:{page - 1}"))
    controls.append(types.InlineKeyboardButton(
        f"{page + 1} / {pages}", callback_data="noop"))
    if page + 1 < pages:
        controls.append(types.InlineKeyboardButton(
            "Next ▶️", callback_data=f"harem:{owner_id}:{page + 1}"))
    kb.row(*controls)
    return kb


def open_card_keyboard(owner_id, code, favorite=False):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(
        types.InlineKeyboardButton(
            "☆ Favorite" if not favorite else "⭐ Unfavorite",
            callback_data=f"cardfav:{owner_id}:{code}"),
        types.InlineKeyboardButton("✖️ Close",
                                   callback_data=f"cardclose:{owner_id}:{code}"),
    )
    return kb


def catch_keyboard(owner_id, code):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        "🖼 View caught card", callback_data=f"cardview:{owner_id}:{code}"))
    return kb
