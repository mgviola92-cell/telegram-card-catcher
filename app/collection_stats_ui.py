"""Telegram-native progress texts only; no image cards or custom fonts."""
from app.card_ui import clean


def overview_text(row):
    return (
        "📊 <b>𝗠𝗬 𝗖𝗢𝗟𝗟𝗘𝗖𝗧𝗜𝗢𝗡 𝗦𝗧𝗔𝗧𝗦</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"🃏 <b>Owned copies:</b> {int(row['owned'])}\n"
        f"🌸 <b>Unique characters:</b> {int(row['unique_characters'])}\n"
        f"⭐ <b>Favourite cards:</b> {int(row['favourites'])}\n"
        f"🎨 <b>Alternate-art cards:</b> {int(row['variants'])}\n"
        f"🌍 <b>Available catalog characters:</b> {int(row['catalog_available'])}\n\n"
        "<i>Duplicates and different generations count as copies, "
        "not extra unique characters.</i>"
    )


def progress_text(rows):
    lines=["📚 <b>𝗠𝗬 𝗦𝗘𝗥𝗜𝗘𝗦 𝗣𝗥𝗢𝗚𝗥𝗘𝗦𝗦</b>","━━━━━━━━━━━━━━"]
    if not rows:
        lines.append("Catch cards to start collecting a series.")
    for row in rows[:10]:
        total=int(row["available"])
        count=int(row["collected"])
        pct=round(100*count/total,1) if total else 0
        lines.append(f"🍀 <b>{clean(row['series'],75)}</b> "
                     f"— <b>{count}/{total}</b> ({pct:g}%)")
    lines.append("\n<i>Counts distinct characters in the enabled catalog.</i>")
    return "\n".join(lines)


def series_text(row):
    total=int(row["available"])
    count=int(row["collected"])
    pct=round(100*count/total,1) if total else 0
    if not total:
        return ("🔎 No enabled catalog series exactly matches "
                f"<b>{clean(row['series'],95)}</b>.")
    return ("📚 <b>𝗦𝗘𝗥𝗜𝗘𝗦 𝗣𝗥𝗢𝗚𝗥𝗘𝗦𝗦</b>\n"
            "━━━━━━━━━━━━━━\n"
            f"🎬 <b>{clean(row['series'],95)}</b>\n"
            f"🌸 Unique collected: <b>{count}/{total}</b> ({pct:g}%)\n"
            "<i>Multiple owned generations count once.</i>")


def duplicates_text(rows):
    lines=["🃏 <b>𝗠𝗬 𝗗𝗨𝗣𝗟𝗜𝗖𝗔𝗧𝗘𝗦</b>","━━━━━━━━━━━━━━"]
    if not rows:
        lines.append("No characters owned more than once.")
    for row in rows[:12]:
        lines.append(
            f"🌸 <b>{clean(row['name'],70)}</b> · <b>×{int(row['copies'])}</b>\n"
            f"    🎬 {clean(row['series'],80)}"
        )
    lines.append("\n<i>Variants/generations of the same character count as copies.</i>")
    return "\n".join(lines)


def missing_text(result):
    rows=result["characters"]
    total=int(result["missing"])
    lines=["🔎 <b>𝗠𝗜𝗦𝗦𝗜𝗡𝗚 𝗖𝗛𝗔𝗥𝗔𝗖𝗧𝗘𝗥𝗦</b>","━━━━━━━━━━━━━━",
           f"🎬 <b>{clean(result['series'],95)}</b>",
           f"🌸 <b>{total} character(s)</b> not collected"]
    for row in rows[:12]:
        lines.append(f"• <b>{clean(row['name'],75)}</b>")
    if total>len(rows):
        lines.append(f"…and {total-len(rows)} more.")
    if not total:
        lines.append("✅ Everything in this enabled series catalog is collected (or no enabled entries exist).")
    lines.append("\n<i>Catalog progress only; this shows no other players’ owned IDs.</i>")
    return "\n".join(lines)
