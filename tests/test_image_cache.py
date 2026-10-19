import unittest
from unittest.mock import MagicMock, patch
from app import storage

class ImageCacheTests(unittest.TestCase):
    @patch('app.storage.connect')
    def test_variant_media_updates_variant_table_only(self, connector):
        db=MagicMock()
        connector.return_value.__enter__.return_value=db
        db.execute.return_value.fetchone.return_value={'id':8}
        result=storage.cache_image(17,'telegram-photo',8,'https://example.org/variant.jpg')
        sql,params=db.execute.call_args.args
        self.assertTrue(result)
        self.assertIn('UPDATE character_variants',sql)
        self.assertEqual(params,('telegram-photo',8,17,'https://example.org/variant.jpg'))

    @patch('app.storage.connect')
    def test_base_media_updates_character_only(self, connector):
        db=MagicMock()
        connector.return_value.__enter__.return_value=db
        db.execute.return_value.fetchone.return_value={'id':17}
        storage.cache_image(17,'base-photo',None,'https://example.org/base.jpg')
        sql,params=db.execute.call_args.args
        self.assertIn('UPDATE characters SET',sql)
        self.assertEqual(params,('base-photo',17,'https://example.org/base.jpg'))

    @patch('app.storage.connect')
    def test_source_changed_prevents_caching_stale_photo(self, connector):
        db=MagicMock()
        connector.return_value.__enter__.return_value=db
        db.execute.return_value.fetchone.return_value=None
        self.assertFalse(storage.cache_image(17,'old',None,'https://example.org/old.jpg'))

if __name__=='__main__':
    unittest.main()
