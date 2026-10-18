import unittest
from scripts.stage_character_offline import coverage_report

class CharacterCoverageReportTests(unittest.TestCase):
    def test_counts_real_rows_ids_and_primary_series(self):
        items=[
            {'mal_id':7,'name':'One','animeAppearances':[{'anime':{'title':'Series A'}}]},
            {'mal_id':7,'name':'One updated','animeAppearances':[{'anime':{'title':'Series A'}}]},
            {'mal_id':8,'name':'Two','animeAppearances':[{'anime':{'title':'Series B'}}]},
            {'mal_id':9,'name':'Missing','animeAppearances':[]}]
        stats=coverage_report({'meta':{'totalCharacters':4},'data':items})
        self.assertEqual(stats['snapshot_rows'],4)
        self.assertEqual(stats['staged_unique_characters'],2)
        self.assertEqual(stats['repeated_source_ids_in_snapshot'],1)
        self.assertEqual(stats['unique_primary_series'],2)
        self.assertEqual(stats['reported_total'],4)
        self.assertEqual(stats['eligible_for_live_import'],0)

    def test_bad_input_rejected(self):
        with self.assertRaises(ValueError):
            coverage_report({'data':None})
