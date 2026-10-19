import csv
import tempfile
import unittest
from pathlib import Path
from scripts.catalog_review_sheet import review_rows, write_csv

class CatalogReviewSheetTests(unittest.TestCase):
    def setUp(self):
        self.records=[dict(source_key='review:hero',name='Hero',series='Demo',
                           category='anime',image_url='https://example.org/hero.png')]

    def test_review_is_pending_by_default(self):
        row=review_rows(self.records)[0]
        self.assertEqual(row['review_status'],'pending')
        self.assertEqual(row['permission_reference'],'')
        self.assertEqual(row['source_key'],'review:hero')

    def test_csv_output_preserves_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'review.csv'
            self.assertEqual(write_csv(self.records,path),1)
            with path.open(encoding='utf-8-sig',newline='') as stream:
                row=list(csv.DictReader(stream))[0]
            self.assertEqual(row['series'],'Demo')
            self.assertEqual(row['review_status'],'pending')

    def test_invalid_catalog_does_not_create_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'review.csv'
            bad=[dict(self.records[0],image_url='http://localhost/a.jpg')]
            with self.assertRaises(ValueError):
                write_csv(bad,path)
            self.assertFalse(path.exists())
