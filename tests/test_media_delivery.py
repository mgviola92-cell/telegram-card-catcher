import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from telebot.apihelper import ApiTelegramException
from app.media_delivery import send_photo

ART={'character_id':42,'variant_id':9,'image_url':'https://example.org/art.jpg','telegram_file_id':'old-file'}

class MediaDeliveryTests(unittest.TestCase):
    def test_cached_id_needs_no_reupload(self):
        bot=Mock()
        storage=Mock()
        result=send_photo(bot,storage,123,ART,caption='Hi')
        self.assertIs(result,bot.send_photo.return_value)
        bot.send_photo.assert_called_once_with(123,'old-file',caption='Hi')
        storage.cache_image.assert_not_called()
    def test_invalid_file_id_falls_back_to_url(self):
        bot=Mock()
        storage=Mock()
        error=ApiTelegramException('sendPhoto',Mock(status_code=400,reason='Bad Request'),{'error_code':400,'description':'Bad Request: wrong file identifier'})
        bot.send_photo.side_effect=[error,SimpleNamespace(photo=[SimpleNamespace(file_id='new-file')])]
        result=send_photo(bot,storage,123,ART)
        self.assertIsNotNone(result)
        storage.clear_cached_image.assert_called_once_with(42,9,'old-file')
        storage.cache_image.assert_called_once_with(42,'new-file',9,'https://example.org/art.jpg')
    def test_no_source_returns_none(self):
        self.assertIsNone(send_photo(Mock(),Mock(),123,{'telegram_file_id':None,'image_url':None}))
    def test_url_failure_returns_none(self):
        bot=Mock()
        bot.send_photo.side_effect=ApiTelegramException('sendPhoto',Mock(status_code=400,reason='Bad Request'),{'error_code':400,'description':'Bad Request'})
        self.assertIsNone(send_photo(bot,Mock(),123,{'image_url':'https://example.org/missing.jpg','character_id':1}))
