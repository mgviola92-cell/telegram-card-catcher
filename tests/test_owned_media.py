"""Narrow live /check media-path regression tests; mock Telegram, no API access."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from telebot.apihelper import ApiTelegramException

from app.owned_media import send_owned_card

CARD={'character_id':123,'image_url':'https://upload.wikimedia.org/pilot.jpg',
      'telegram_file_id':'cache-123','owner_id':456,'code':'PILOT1'}


def error(code, description):
    return ApiTelegramException(
        'sendPhoto', Mock(status_code=code,reason='Bad Request'),
        {'error_code':code,'description':description})


class OwnedCardMediaTests(unittest.TestCase):
    def test_repeat_card_sends_using_shared_file_id_only(self):
        bot,storage=Mock(),Mock()
        self.assertIs(send_owned_card(bot,storage,5,CARD,caption='Card'),
                      bot.send_photo.return_value)
        bot.send_photo.assert_called_once_with(5,'cache-123',caption='Card')
        storage.cache_image.assert_not_called()

    def test_first_send_by_https_url_caches_once_on_shared_character(self):
        bot,storage=Mock(),Mock()
        bot.send_photo.return_value=SimpleNamespace(
            photo=[SimpleNamespace(file_id='saved-by-telegram')])
        row=dict(CARD,telegram_file_id=None)
        self.assertIsNotNone(send_owned_card(bot,storage,5,row))
        bot.send_photo.assert_called_once_with(5,CARD['image_url'])
        storage.cache_image.assert_called_once_with(123,'saved-by-telegram',variant_id=None,expected_url=CARD['image_url'])

    def test_invalid_cached_id_retries_original_url(self):
        bot,storage=Mock(),Mock()
        bot.send_photo.side_effect=[
            error(400,'Bad Request: wrong file identifier'),
            SimpleNamespace(photo=[SimpleNamespace(file_id='cache-new')])]
        self.assertIsNotNone(send_owned_card(bot,storage,5,CARD))
        self.assertEqual(bot.send_photo.call_count,2)
        self.assertEqual(bot.send_photo.call_args.args[1],CARD['image_url'])
        storage.cache_image.assert_called_once_with(123,'cache-new',variant_id=None,expected_url=CARD['image_url'])

    def test_rate_limit_forbidden_and_unrelated_bad_request_are_not_retried(self):
        for ex in [error(429,'Too Many Requests'),error(403,'Forbidden'),
                   error(400,'Bad Request: caption is too long')]:
            with self.subTest(ex=ex):
                bot,storage=Mock(),Mock()
                bot.send_photo.side_effect=ex
                self.assertIsNone(send_owned_card(bot,storage,5,CARD))
                bot.send_photo.assert_called_once()
                storage.cache_image.assert_not_called()

    def test_media_cache_save_failure_does_not_double_send(self):
        bot,storage=Mock(),Mock()
        storage.cache_image.side_effect=RuntimeError('offline')
        bot.send_photo.return_value=SimpleNamespace(
            photo=[SimpleNamespace(file_id='cached')])
        self.assertIsNotNone(send_owned_card(bot,storage,5,
                             dict(CARD,telegram_file_id=None)))
        bot.send_photo.assert_called_once()

    def test_no_sources_returns_none(self):
        self.assertIsNone(send_owned_card(Mock(),Mock(),5,{'character_id':123}))

    def test_none_result_never_caches_or_retries(self):
        bot,storage=Mock(),Mock()
        bot.send_photo.return_value=None
        self.assertIsNone(send_owned_card(bot,storage,5,CARD))
        bot.send_photo.assert_called_once()
        storage.cache_image.assert_not_called()


if __name__=='__main__':
    unittest.main()
