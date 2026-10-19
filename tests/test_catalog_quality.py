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

    def test_inconsistent_series_spellings_block_batch(self):
        a=item('original:one',name='First')
        b=item('original:two',name='Second',url='https://example.org/second.png')
        a['series']='One Piece'
        b['series']=' one  piece '
        result=report([a,b])
        self.assertFalse(result['passed'])
        self.assertIn('one piece',result['inconsistent_series'])
        with self.assertRaises(ValueError):
            require_approval([a,b])

    def test_same_series_spelling_is_accepted(self):
        a=item('original:one',name='First')
        b=item('original:two',name='Second',url='https://example.org/second.png')
        a['series']=b['series']='One Piece'
        self.assertTrue(report([a,b])['passed'])

    def test_alias_conflict_in_same_series_blocks_batch(self):
        a=item('anime:one',name='Alpha')
        a['aliases']=['The Captain']
        b=item('anime:two',name='The Captain',url='https://example.org/second.png')
        result=report([a,b])
        self.assertFalse(result['passed'])
        self.assertIn('demo / the captain',result['alias_conflicts'])
        with self.assertRaises(ValueError):
            require_approval([a,b])

    def test_alias_variants_on_same_character_are_safe(self):
        a=item('anime:one',name='Alpha')
        a['aliases']=['alpha','  ALPHA ', 'Captain']
        self.assertTrue(report([a])['passed'])

    def test_same_alias_across_different_series_is_not_a_conflict(self):
        a=item('anime:one',name='Alpha')
        a['aliases']=['Captain']
        b=item('anime:two',name='Beta',url='https://example.org/second.png')
        b['series']='Another Show'
        b['aliases']=['captain']
        self.assertTrue(report([a,b])['passed'])
