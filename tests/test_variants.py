import unittest
from scripts.import_variants import validate

class VariantTests(unittest.TestCase):
    def example(self):
        return dict(character_source_key='original:hero',variant_key='winter',label='Winter',
                    image_url='https://example.org/winter.png',rarity='Rare',spawn_weight=10)
    def test_valid(self):
        self.assertEqual(len(validate([self.example()])),1)
    def test_duplicate(self):
        with self.assertRaises(ValueError):
            validate([self.example(),self.example()])
    def test_non_https(self):
        item=self.example()
        item['image_url']='http://invalid'
        with self.assertRaises(ValueError):
            validate([item])
    def test_weight(self):
        item=self.example()
        item['spawn_weight']=-10
        with self.assertRaises(ValueError):
            validate([item])
