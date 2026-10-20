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
