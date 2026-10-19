import json
import unittest
from pathlib import Path

class CatalogSourceRegistryTests(unittest.TestCase):
    def test_sources_are_explicitly_review_only(self):
        data=json.loads(Path('data/catalog_sources.review.json').read_text(encoding='utf-8'))
        self.assertGreaterEqual(len(data),15)
        self.assertEqual(len({source['source'] for source in data}),len(data))
        self.assertTrue(all(source['enabled_for_import'] is False for source in data))
        self.assertTrue(all(source['review'] and source['image_rights'] for source in data))
        self.assertTrue(all(all(url.startswith('https://') for url in source['urls']) for source in data))
        self.assertIn('ACDB',{entry['source'] for entry in data})
        self.assertIn('anime-characters-2M',{entry['source'] for entry in data})
