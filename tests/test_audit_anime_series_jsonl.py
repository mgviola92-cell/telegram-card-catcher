import json
import unittest
from scripts.audit_anime_series_jsonl import summarize_jsonl

class AnimeSeriesJSONLAuditTests(unittest.TestCase):
    def test_release_metadata_skipped_and_series_counted(self):
        lines=[json.dumps({'meta':{'version':'2026-42'}}),
               json.dumps({'title':'Anime One','sources':['https://myanimelist.net/anime/1','https://anilist.co/anime/2']}),
               json.dumps({'title':'Anime One','sources':['https://myanimelist.net/anime/3']})]
        report=summarize_jsonl(lines)
        self.assertEqual(report['series_entries'],2)
        self.assertEqual(report['distinct_primary_titles'],1)
        self.assertEqual(report['source_domain_counts']['myanimelist.net'],2)
        self.assertIsNone(report['character_count'])
        self.assertEqual(report['artwork_approved'],0)

    def test_malformed_line_is_counted(self):
        report=summarize_jsonl(['{}','not-json'])
        self.assertEqual(report['invalid_lines'],1)
