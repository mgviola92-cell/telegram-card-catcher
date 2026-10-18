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
                try:
                    storage.clear_cached_image(art['character_id'],art.get('variant_id'),cached)
                except Exception:
                    logging.exception('Stale image cache cleanup failed')
            continue
        if source==url and message.photo:
            try:
                storage.cache_image(art['character_id'],message.photo[-1].file_id,
                                    art.get('variant_id'),url)
            except Exception:
                # The photo has already been delivered. Do not retry sending it.
                logging.exception('Image sent, but Telegram file_id cache save failed')
        return message
    return None
