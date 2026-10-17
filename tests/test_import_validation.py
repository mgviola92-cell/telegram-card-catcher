import unittest
from scripts.import_characters import validate


class ValidationTests(unittest.TestCase):
    def character(self, **overrides):
        obj=dict(source_key='original:test-01',name='Example',series='Original',
                 image_url='https://example.org/approved.png')
        obj.update(overrides)
        return obj

    def test_valid(self):
        result=validate([self.character()])
        self.assertEqual(len(result),1)

    def test_duplicate_source_key_rejected(self):
        with self.assertRaises(ValueError):
            validate([self.character(),self.character()])

    def test_insecure_url_rejected(self):
        with self.assertRaises(ValueError):
            validate([self.character(image_url='http://example.org/p.png')])

    def test_unknown_rarity_rejected(self):
        with self.assertRaises(ValueError):
            validate([self.character(rarity='Unknown')])

    def test_non_int_weight_rejected(self):
        with self.assertRaises(ValueError):
            validate([self.character(weight=True)])


if __name__=='__main__':
    unittest.main()
