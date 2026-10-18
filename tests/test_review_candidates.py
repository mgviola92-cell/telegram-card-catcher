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
        verified=[x for x in records if x['metadata_status']=='source_verified']
        self.assertEqual({x['source_key'] for x in verified}, {'wikidata:Q931','wikidata:Q477948'})
        self.assertTrue(all(x['metadata_source_url']=='https://www.wikidata.org/wiki/'+x['source_key'].split(':')[1] for x in verified))
        unverified=[x for x in records if x['metadata_status']=='awaiting_source_verification']
        self.assertEqual(len(unverified),6)
        self.assertTrue(all(x['source_key'] is None for x in unverified))
