import unittest
from scripts.catalog_audit import audit

class CatalogAuditTests(unittest.TestCase):
    def record(self,key,name='Hero',series='Sample'):
        return dict(source_key=key,name=name,series=series,
                    image_url='https://example.org/character.jpg')
    def test_duplicate_names_are_reported(self):
        result=audit([self.record('original:001'),self.record('original:002')])
        self.assertEqual(result['total'],2)
        self.assertEqual(result['same_name_series_duplicates'],1)
    def test_unique_series_count(self):
        result=audit([self.record('original:001'),self.record('original:002',series='Other')])
        self.assertEqual(result['unique_series'],2)
    def test_invalid_record_not_silently_imported(self):
        with self.assertRaises(ValueError):
            audit([self.record('original:001'),self.record('original:001')])
