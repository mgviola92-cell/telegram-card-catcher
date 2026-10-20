"""Readable Telegram HTML trading board without image-card rendering."""
from app.card_ui import clean,rarity_label


def market_caption(rows):
    lines=[
        "🔄 <b>𝗖𝗔𝗥𝗗 𝗧𝗥𝗔𝗗𝗘 𝗕𝗢𝗔𝗥𝗗</b>",
        "━━━━━━━━━━━━━━",
    ]
    if not rows:
        lines.append("No active trade listings in this group yet.")
    for row in rows[:10]:
        card_id=int(row["card_id"])
        seller=int(row["seller_id"])
        if card_id<=0 or seller<=0:
            continue
        lines.append(
            f"🃏 <b>{clean(row['name'],55)}</b>  <code>{card_id}</code>\n"
            f"    🎬 {clean(row['series'],65)}  ·  {rarity_label(row['rarity'])}\n"
            f"    👤 <a href=\"tg://user?id={seller}\">Collector {seller}</a>"
        )
    lines.extend([
        "",
        "💬 <i>To offer a swap, reply to the seller's group message:</i>",
        "<code>/trade MY_ID THEIR_ID</code>",
        "✅ <i>Both players must consent. No automatic exchange.</i>",
        "⏳ <i>Listings expire after 24 hours.</i>",
    ])
    return "\n".join(lines)


def listed_caption(card_id):
    return (
        "✅ <b>𝗖𝗔𝗥𝗗 𝗟𝗜𝗦𝗧𝗘𝗗</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"🃏 <b>Card:</b> <code>{int(card_id)}</code>\n"
        "⏳ <i>Listing lasts 24 hours.</i>\n"
        "🔒 <i>Listing never transfers your card.</i>\n"
        "🔄 <i>Use /market to browse or /unlist ID to remove.</i>"
    )
