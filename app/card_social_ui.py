"""Telegram-native opt-in exchange and leaderboard captions. No generated art."""
from html import escape
from telebot import types


def exchange_keyboard(kind, offer_id):
    if kind not in ("gift", "trade") or type(offer_id) is not int or offer_id <= 0:
        raise ValueError("Invalid offer")
    prefix = "g" if kind == "gift" else "t"
    kb=types.InlineKeyboardMarkup(row_width=2)
    kb.row(
        types.InlineKeyboardButton("✅ Accept", callback_data=f"exchange:{prefix}:{offer_id}:a"),
        types.InlineKeyboardButton("✖️ Decline", callback_data=f"exchange:{prefix}:{offer_id}:d"),
    )
    return kb


def safe_name(text):
    return escape(str(text or "Player").strip()[:48],quote=False)


def offer_caption(kind, sender_name, receiver_name, ids):
    header = "🎁 <b>𝗖𝗔𝗥𝗗 𝗚𝗜𝗙𝗧</b>" if kind=="gift" else "🔄 <b>𝗖𝗔𝗥𝗗 𝗧𝗥𝗔𝗗𝗘</b>"
    lines=[
        header, "━━━━━━━━━━━━━━",
        f"👤 <b>From:</b> {safe_name(sender_name)}",
        f"🎯 <b>To:</b> {safe_name(receiver_name)}",
    ]
    if kind=="gift":
        lines.append(f"🃏 <b>Card:</b> <code>{int(ids[0])}</code>")
    elif kind=="trade":
        lines.append(f"📤 <b>Offered:</b> <code>{int(ids[0])}</code>")
        lines.append(f"📥 <b>Requested:</b> <code>{int(ids[1])}</code>")
    else:
        raise ValueError("Unknown exchange")
    lines.extend([
        "", "⏳ <i>Recipient must accept within 10 minutes.</i>",
        "🔒 <i>Ownership is checked again when accepted.</i>",
    ])
    return "\n".join(lines)


def result_caption(kind, status, card_ids=None):
    names={"accepted":"✅ Accepted","declined":"✖️ Declined",
           "expired":"⌛ Expired","invalid":"⚠️ Cards changed owners"}
    if kind not in ("gift","trade") or status not in names:
        raise ValueError("Unknown exchange outcome")
    title = "GIFT" if kind=="gift" else "TRADE"
    answer=f"🃏 <b>{title} — {names[status]}</b>"
    if card_ids and status=="accepted":
        answer+="\n"+("Card " if kind=="gift" else "Cards ")+", ".join(
            f"<code>{int(i)}</code>" for i in card_ids)
    return answer


def leaderboard_caption(entries, kind="global"):
    titles={"global":"🌍 𝗚𝗟𝗢𝗕𝗔𝗟 𝗧𝗢𝗣 𝗖𝗔𝗧𝗖𝗛𝗘𝗥𝗦",
            "group":"👥 𝗚𝗥𝗢𝗨𝗣 𝗧𝗢𝗣 𝗖𝗔𝗧𝗖𝗛𝗘𝗥𝗦",
            "today":"📅 𝗧𝗢𝗗𝗔𝗬'𝗦 𝗖𝗔𝗧𝗖𝗛𝗘𝗦"}
    if kind not in titles:
        raise ValueError("Unknown ranking kind")
    lines=[f"🏆 <b>{titles[kind]}</b>","━━━━━━━━━━━━━━"]
    for rank, item in enumerate(entries[:10],1):
        count = int(item["catches"])
        user_id=int(item["user_id"])
        if count < 0 or user_id <= 0:
            continue
        medal=("🥇","🥈","🥉")[rank-1] if rank<=3 else f"{rank}."
        lines.append(f"{medal} <a href=\"tg://user?id={user_id}\">Collector {user_id}</a> "
                     f"— <b>{count}</b>")
    if len(lines)==2:
        lines.append("No catches recorded yet.")
    lines.append("\n<i>Ranked by original catches, even after a gift/trade.</i>")
    if kind=="group":
        lines.append("<i>Older catches without group attribution are excluded.</i>")
    return "\n".join(lines)
