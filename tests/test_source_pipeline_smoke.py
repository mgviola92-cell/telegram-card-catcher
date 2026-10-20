"""Synthetic source-review smoke must never automatically promote image links."""
import unittest
from scripts.source_pipeline_smoke import smoke


class SourcePipelineSmokeTests(unittest.TestCase):
    def test_sources_to_human_review_never_autoimport(self):
        r=smoke()
        self.assertEqual(r["mode"],"synthetic_offline_integration")
        self.assertEqual(r["staged_bangumi_characters"],1)
        self.assertEqual(r["unverified_cross_source_pairs"],1)
        self.assertEqual(r["human_identity_matches"],0)
        self.assertEqual(r["commons_review_candidates"],1)
        self.assertEqual(r["rights_approved_artworks"],0)
        self.assertEqual(r["import_ready_characters"],0)
        self.assertEqual(r["production_writes"],0)
        self.assertEqual(r["external_requests"],0)


if __name__=="__main__":
    unittest.main()
