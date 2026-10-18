"""Catch input and success text shared by slash commands and normal chat."""
def catch_name(text):
    text=(text or '').strip()
    if not text:
        return ''
    first,_,rest=text.partition(' ')
    if first.split('@',1)[0].casefold()=='/catch':
        return rest.strip()
    if first.startswith('/'):
        return ''
    return text

def catch_result(card, user):
    name=(getattr(user,'first_name',None) or 'Player').strip()[:60]
    total=card.get("collection_total")
    progress=f"📚 Your collection: {total} cards\n" if isinstance(total,int) and total>=0 else ""
    return (f"🎉 {name}, YOU CAUGHT A CHARACTER!\n"
            f"🃏 {card['name']} — {card['series']}\n"
            f"✨ {card['rarity']} · Gen {card['generation']}\n"
            f"🆔 {card['code']}\n"
            f"{progress}"
            f"❄️ /harem မှာ ကြည့်နိုင်ပါတယ်။")
