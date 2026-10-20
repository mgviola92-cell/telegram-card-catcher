"""Telegram-native captions and collection UI. No image rendering or fonts/assets.

Use Telegram HTML bold for emphasis, and Unicode-styled text ONLY for static
English headings. Actual Telegram font rendering depends on the client.
Artwork is delivered via shared URL/file_id, not stored on a per-card basis.
"""
from html import escape
import re
from telebot import types
from app.card_refs import public_card_id

PAGE_SIZE = 8
MAX_NAME = 85
MAX_SERIES = 100
RULE = "━━━━━━━━━━━━━━"

# Static headings may use Unicode math sans bold. Names, series, and IDs remain
# normal, searchable/copyable characters (with Telegram-native HTML emphasis).
SPAWN_TITLE = "𝗪𝗜𝗟𝗗 𝗖𝗛𝗔𝗥𝗔𝗖𝗧𝗘𝗥!"
CATCH_TITLE = "𝗖𝗛𝗔𝗥𝗔𝗖𝗧𝗘𝗥 𝗖𝗔𝗨𝗚𝗛𝗧!"
CARD_TITLE = "𝗖𝗛𝗔𝗥𝗔𝗖𝗧𝗘𝗥 𝗖𝗔𝗥𝗗"
HAREM_TITLE = "𝗚𝗟𝗢𝗕𝗔𝗟 𝗛𝗔𝗥𝗘𝗠"

RARITY_SYMBOLS = {
    "common": "⚪",
    "uncommon": "🟢",
    "rare": "🔵",
    "legendary": "🟠",
    "mystical": "🟣",
    "divine": "✨",
    "crossverse": "🔮",
    "cataphract": "🛡️",
    "supreme": "👑",
    "cnft": "💠",
}


def clean(value, limit=MAX_NAME):
    """Escape potentially untrusted catalog/player strings for Telegram HTML."""
    raw = str(value or "").strip()
    if len(raw) > limit:
        raw = raw[:limit - 1].rstrip() + "…"
    return escape(raw, quote=False)


def rarity_label(value):
    plain = str(value or "Unknown").strip()
    symbol = RARITY_SYMBOLS.get(plain.casefold(), "💎")
    return f"{symbol} <b>{clean(plain, 30)}</b>"


def spawn_series(character):
    """Avoid revealing answers when the series title contains the character name.

    E.g. Alice must not be accidentally revealed by 'Alice's Adventures in
    Wonderland'. We deliberately do not hide very short one-letter aliases.
    """
    series = str(character.get("series") or "").strip()
    if not series:
        return "Unknown"
    names = [character.get("name"), *(character.get("aliases") or [])]
    for name in names:
        if not isinstance(name, str):
            continue
        name = name.strip()
        if len(name) < 3:
            continue
        if re.search(r"(?<!\w)" + re.escape(name.casefold()) + r"(?!\w)",
                     series.casefold()):
            return "Hidden until caught 🎭"
    return series


def spawn_caption(character):
    return (
        f"✨ <b>{SPAWN_TITLE}</b>\n"
        f"{RULE}\n"
        f"🎬 <b>SERIES:</b> {clean(spawn_series(character), MAX_SERIES)}\n"
        f"💎 <b>RARITY:</b> {rarity_label(character.get('rarity'))}\n\n"
        "🔎 <b>GUESS THE NAME</b>\n"
        "💬 <i>First correct answer wins this card.</i>\n"
        "⏳ <i>15 minutes to catch</i>"
    )


def catch_text(character, display_name):
    return (
        f"🎉 <b>{CATCH_TITLE}</b>\n"
        f"{RULE}\n"
        f"👤 <b>PLAYER:</b> {clean(display_name, 45)}\n"
        f"🌸 <b>NAME:</b> <b>{clean(character.get('name'))}</b>\n"
        f"💎 <b>RARITY:</b> {rarity_label(character.get('rarity'))}\n"
        f"🎬 <b>SERIES:</b> {clean(character.get('series'), MAX_SERIES)}\n"
        f"🆔 <b>ID:</b> <code>{clean(public_card_id(character), 32)}</code>"
        f"  ·  <b>GEN:</b> {int(character['generation'])}\n\n"
        "✅ <i>Added to your global collection.</i>"
    )


def owned_caption(character):
    return (
        f"🃏 <b>{CARD_TITLE}</b>\n"
        f"{RULE}\n"
        f"🌸 <b>NAME:</b> <b>{clean(character.get('name'))}</b>\n"
        f"💎 <b>RARITY:</b> {rarity_label(character.get('rarity'))}\n"
        f"🎬 <b>SERIES:</b> {clean(character.get('series'), MAX_SERIES)}\n"
        f"🆔 <b>ID:</b> <code>{clean(public_card_id(character), 32)}</code>"
        f"  ·  <b>GEN:</b> {int(character['generation'])}\n"
        + (f"🎨 <b>ARTWORK:</b> {clean(character.get('variant_label'),45)}\n"
           if character.get('variant_label') else "")
        + ("⭐ <b>FAVOURITE</b>" if character.get("favorite") else "✦ <i>Collected</i>")
    )


def favourite_text(card, added=True):
    """A readable Telegram status like the reference screenshot, no new image."""
    title = "𝗡𝗘𝗪 𝗙𝗔𝗩𝗢𝗨𝗥𝗜𝗧𝗘!" if added else "𝗙𝗔𝗩𝗢𝗨𝗥𝗜𝗧𝗘 𝗥𝗘𝗠𝗢𝗩𝗘𝗗"
    marker = "✅" if added else "☆"
    return (
        f"{marker} <b>{title}</b>\n"
        f"{RULE}\n"
        f"🌸 <b>NAME:</b> <b>{clean(card.get('name'))}</b>\n"
        f"💎 <b>RARITY:</b> {rarity_label(card.get('rarity'))}\n"
        f"🎬 <b>SERIES:</b> {clean(card.get('series'), MAX_SERIES)}\n"
        f"🆔 <b>ID:</b> <code>{clean(public_card_id(card),32)}</code>"
    )


def search_text(found):
    """Catalog IDs are NOT owned-card IDs; make the distinction explicit."""
    lines = [
        "🔎 <b>𝗖𝗛𝗔𝗥𝗔𝗖𝗧𝗘𝗥 𝗦𝗘𝗔𝗥𝗖𝗛</b>",
        RULE,
    ]
    for card in found:
        lines.append(f"🔖 <b>Catalog #{int(card['id'])}</b>  "
                     f"<b>{clean(card.get('name'), 70)}</b>")
        lines.append(f"    🎬 {clean(card.get('series'), MAX_SERIES)}")
        lines.append(f"    💎 {rarity_label(card.get('rarity'))}")
    lines.append("\n<i>Catalog IDs identify characters, not owned cards. "
                 "Use /harem for your card IDs.</i>")
    return "\n".join(lines)


def collection_text(cards, total, page):
    """One readable paged group list (not a generated image or fake totals)."""
    if not cards:
        return (
            f"🃏 <b>{HAREM_TITLE}</b>\n"
            f"{RULE}\n"
            "Your collection is empty. Catch a character in a group!"
        )
    first = page * PAGE_SIZE + 1
    last = first + len(cards) - 1
    lines = [
        f"🃏 <b>{HAREM_TITLE}</b>",
        RULE,
        f"📚 <b>{total}</b> cards  ·  Showing {first}–{last}",
    ]
    # Only group the current page; never invent all-series collection totals.
    groups = {}
    for card in cards:
        groups.setdefault(str(card.get("series") or "Other"), []).append(card)
    for series, members in groups.items():
        lines.append(f"\n🍀 <b>{clean(series, MAX_SERIES)}</b>  ·  {len(members)} shown")
        for card in members:
            star = "⭐ " if card.get("favorite") else ""
            lines.append(f"<code>{clean(public_card_id(card),32)}</code>  "
                         f"{star}<b>{clean(card.get('name'),44)}</b>")
            lines.append(f"    💎 {rarity_label(card.get('rarity'))}"
                         f"  ·  <b>Gen {int(card['generation'])}</b>")
    lines.append("\n👇 <i>Tap a name below to view the original artwork.</i>")
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
