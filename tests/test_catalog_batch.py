import unittest
from unittest.mock import patch, MagicMock
from scripts.import_characters import import_batch

def sample(i):
    return dict(source_key=f'qa:char:{i}',name=f'Hero {i}',series='QA',
                image_url=f'https://example.org/{i}.png')

class CatalogBatchTests(unittest.TestCase):
    @patch('scripts.import_characters.connect')
    def test_chunk_boundaries(self, connect):
        db=MagicMock()
        cur=MagicMock()
        connect.return_value.__enter__.return_value=db
        db.cursor.return_value.__enter__.return_value=cur
        self.assertEqual(import_batch([sample(i) for i in range(501)],batch_size=250),501)
        self.assertEqual([len(call.args[1]) for call in cur.executemany.call_args_list],[250,250,1])

    @patch('scripts.import_characters.connect')
    def test_empty_catalog_no_queries(self, connect):
        db=MagicMock()
        cur=MagicMock()
        connect.return_value.__enter__.return_value=db
        db.cursor.return_value.__enter__.return_value=cur
        self.assertEqual(import_batch([]),0)
        cur.executemany.assert_not_called()

    @patch('scripts.import_characters.connect')
    def test_bad_batch_size_rejected_before_database(self, connect):
        for size in (0,-1,1001,True,1.5):
            with self.subTest(size=size), self.assertRaises(ValueError):
                import_batch([sample(0)],batch_size=size)
        connect.assert_not_called()

    @patch('scripts.import_characters.connect')
    def test_validation_precedes_database(self, connect):
        invalid=sample(1)
        invalid['image_url']='http://localhost/a.png'
        with self.assertRaises(ValueError):
            import_batch([sample(0),invalid])
        connect.assert_not_called()
