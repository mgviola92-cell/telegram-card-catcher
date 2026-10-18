import unittest
from scripts.stage_character_offline import stage

class StageCharacterOfflineTests(unittest.TestCase):
    def test_bulk_metadata_never_grants_artwork(self):
        snapshot={'data':[{'mal_id':123,'name':'Hero','nicknames':['Ace'],
            'images':{'jpg':{'image_url':'https://elsewhere.example/image.jpg'}},
            'animeAppearances':[{'anime':{'mal_id':5,'title':'Series One'}},
                                {'anime':{'mal_id':6,'title':'Series Two'}}]}]}
        rows=stage(snapshot)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['source_key'],'mal:character:123')
        self.assertEqual(rows[0]['additional_series'],['Series Two'])
        self.assertIsNone(rows[0]['image_url'])
        self.assertEqual(rows[0]['artwork_status'],'awaiting_permission_review')

    def test_skips_rows_without_named_series(self):
        self.assertEqual(stage({'data':[{'mal_id':1,'name':'Hero','animeAppearances':[]}]}),[])

    def test_invalid_snapshot_rejected(self):
        with self.assertRaises(ValueError):
            stage([{}])
