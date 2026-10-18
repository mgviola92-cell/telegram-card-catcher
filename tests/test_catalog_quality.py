import unittest
from scripts.catalog_quality import report,require_approval

def item(key,name='Hero',url='https://example.org/hero.png',rarity='Common',weight=100):
    return dict(source_key=key,name=name,series='Demo',image_url=url,rarity=rarity,weight=weight)

class QualityGateTests(unittest.TestCase):
    def test_healthy_catalog(self):
        x=report([item('original:one'),item('original:two','Second','https://example.org/second.png','Rare',25)])
        self.assertTrue(x['passed'])
        self.assertAlmostEqual(x['estimated_rarity_percent']['Common'],80.0)
    def test_repeated_artwork_blocks_import(self):
        data=[item('original:one'),item('original:two','Second')]
        self.assertEqual(report(data)['reused_image_urls'],1)
        with self.assertRaises(ValueError):
            require_approval(data)
    def test_same_name_and_series_blocks_import(self):
        data=[item('original:one'),item('original:two',url='https://example.org/second.png')]
        self.assertFalse(report(data)['passed'])
    def test_override_requires_explicit_flag(self):
        data=[item('original:one'),item('original:two','Second')]
        self.assertFalse(require_approval(data,allow_warnings=True)['passed'])
