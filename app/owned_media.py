"""Reuse a character's Telegram-hosted image for every owned copy.

No card images or card-specific image URLs are stored in PostgreSQL.
This narrow module is safe for the current production schema.
"""
import logging
from telebot.apihelper import ApiTelegramException


def _invalid_media(exc):
    reason=(getattr(exc,'description','') or str(exc)).lower()
    return getattr(exc,'error_code',None)==400 and any(x in reason for x in (
        'wrong file identifier','invalid file identifier','file_id invalid',
        'file identifier is invalid','file reference expired','wrong file_id',
        'invalid file_id'))


def send_owned_card(bot, storage, chat_id, card, **kwargs):
    """Send one card photo; return message or None without duplicate delivery.

    Cached Telegram file IDs belong to the shared characters table, not owners.
    URL fallback is permitted ONLY for recognized invalid cached file ID errors.
    """
    cached=card.get('telegram_file_id')
    url=card.get('image_url')
    if not cached and not url:
        return None
    for source in dict.fromkeys(s for s in (cached,url) if s):
        try:
            result=bot.send_photo(chat_id,source,**kwargs)
        except ApiTelegramException as exc:
            if source==cached and _invalid_media(exc):
                logging.warning('Cached character image invalid, trying original URL')
                continue
            logging.warning('Telegram photo send failed (not retrying): %s',exc)
            return None
        if result is None:
            return None
        if source==url and getattr(result,'photo',None):
            try:
                storage.cache_image(card['character_id'],result.photo[-1].file_id,
                                    variant_id=card.get('variant_id'),
                                    expected_url=url)
            except Exception:
                logging.exception('Photo delivered but shared file ID cache update failed')
        return result
    return None
