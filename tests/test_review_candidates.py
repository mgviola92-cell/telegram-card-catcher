import json
import unittest
from pathlib import Path

class ReviewCandidateTests(unittest.TestCase):
    def test_real_character_starter_remains_review_only(self):
        records=json.loads(Path('data/character_candidates.review.json').read_text(encoding='utf-8'))
        self.assertEqual(len(records),8)
        self.assertEqual(len({x['candidate_id'] for x in records}),8)
        self.assertTrue(all(x['name'] and x['series'] for x in records))
        self.assertTrue(all(x['image_url'] is None for x in records))
        self.assertTrue(all(x['artwork_status']=='awaiting_permission_review' for x in records))
        expected={'Naruto Uzumaki':'Q931','Sasuke Uchiha':'Q1740',
                  'Sakura Haruno':'Q203240','Monkey D. Luffy':'Q477948',
                  'Roronoa Zoro':'Q858432','Nami':'Q877964',
                  'Son Goku':'Q2142','Vegeta':'Q180916'}
        self.assertEqual({x['name'] for x in records},set(expected))
        for item in records:
            with self.subTest(name=item['name']):
                ident=expected[item['name']]
                self.assertEqual(item['metadata_status'],'source_verified')
                self.assertEqual(item['source_key'],'wikidata:'+ident)
                self.assertEqual(item['metadata_source_url'],'https://www.wikidata.org/wiki/'+ident)
