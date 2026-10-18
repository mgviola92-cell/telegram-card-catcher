"""Send Telegram-hosted artwork first, falling back to the approved HTTPS URL."""
import logging
from telebot.apihelper import ApiTelegramException

def send_photo(bot, storage, chat_id, art, **kwargs):
    cached=art.get('telegram_file_id')
    url=art.get('image_url')
    if not cached and not url:
        return None
    for source in dict.fromkeys(x for x in (cached,url) if x):
        try:
            message=bot.send_photo(chat_id,source,**kwargs)
        except ApiTelegramException:
            logging.warning('Telegram rejected artwork source; trying fallback')
            if source==cached:
                storage.clear_cached_image(art['character_id'],art.get('variant_id'),cached)
            continue
        if source==url and message.photo:
            storage.cache_image(art['character_id'],message.photo[-1].file_id,
                                art.get('variant_id'),url)
        return message
    return None
