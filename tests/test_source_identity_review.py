"""Source identity matching cannot silently merge, import or approve artwork."""
import unittest
from scripts.source_identity_review import (
    inspect_sources, apply_human_decisions, normalize, MAX_ROWS)


def row(key, name="Sample Hero", series="Sample Show"):
    return {"source_key":key, "name":name, "series":series}


def decision(a, b, status, note="Independent matching canonical identifier evidence"):
    return {"left_key":a,"right_key":b,"status":status,
            "evidence_url":"https://www.wikidata.org/wiki/Q42",
            "review_note":note}


class SourceReviewTests(unittest.TestCase):
    def test_unicode_whitespace_candidates_require_review(self):
        report=inspect_sources({
            "mal":[row("mal:1","SAMPLE  HERO","Example Show")],
            "acdb":[row("acdb:2","sample hero","example   show")],
        })
        self.assertEqual(report["distinct_keys"],2)
        self.assertEqual(len(report["candidate_pairs"]),1)
        self.assertEqual(report["candidate_pairs"][0]["status"],"pending")
        self.assertIsNone(report["candidate_pairs"][0]["evidence_url"])
        self.assertNotIn("image_url", report["candidate_pairs"][0])
        summary=apply_human_decisions(report,[])
        self.assertEqual(summary["human_reviewed_same_pairs"],0)
        self.assertEqual(summary["unreviewed_candidate_pairs"],1)
        self.assertIsNone(summary["globally_verified_unique_characters"])
        self.assertEqual(summary["artwork_approved"],0)

    def test_same_name_not_enough_for_different_series(self):
        report=inspect_sources({"a":[row("a:1",series="A")],
                                "b":[row("b:1",series="B")]})
        self.assertEqual(report["candidate_pairs"],[])

    def test_generic_series_and_short_names_not_candidates(self):
        report=inspect_sources({"a":[row("a:1","Mr","Unknown Series")],
                                "b":[row("b:1","Mr","Unknown Series")]})
        self.assertEqual(report["candidate_pairs"],[])

    def test_same_source_only_not_candidate(self):
        report=inspect_sources({"a":[row("a:1"),row("a:2")]})
        self.assertEqual(len(report["candidate_pairs"]),0)

    def test_no_unverified_import_and_explicit_evidence_review(self):
        report=inspect_sources({"a":[row("a:1")],"b":[row("b:1")]})
        summary=apply_human_decisions(report,[decision("a:1","b:1","same")])
        self.assertEqual(summary["human_reviewed_same_pairs"],1)
        self.assertEqual(summary["human_reviewed_identity_clusters"],[["a:1","b:1"]])
        self.assertEqual(summary["claimed_redundant_source_keys_within_reviewed_clusters"],1)
        self.assertEqual(summary["characters_imported"],0)
        self.assertEqual(summary["artwork_approved"],0)

    def test_distinct_decision_never_deletes_source(self):
        report=inspect_sources({"a":[row("a:1")],"b":[row("b:1")]})
        result=apply_human_decisions(report,[decision("a:1","b:1","different")])
        self.assertEqual(result["human_reviewed_identity_clusters"],[])
        self.assertEqual(result["unreviewed_candidate_pairs"],0)
        self.assertIsNone(result["globally_verified_unique_characters"])

    def test_transitive_conflict_is_rejected(self):
        report=inspect_sources({"a":[row("a:1")],"b":[row("b:1")],
                                "c":[row("c:1")]})
        judgments=[decision("a:1","b:1","same"),
                   decision("b:1","c:1","same"),
                   decision("a:1","c:1","different")]
        with self.assertRaises(ValueError):
            apply_human_decisions(report,judgments)

    def test_merging_multiple_identifiers_of_same_source_forbidden(self):
        report=inspect_sources({"a":[row("a:1"),row("a:2")],
                                "b":[row("b:1")]})
        with self.assertRaises(ValueError):
            apply_human_decisions(report,[decision("a:1","b:1","same"),
                                           decision("a:2","b:1","same")])

    def test_disallow_duplicate_or_unknown_judgments(self):
        report=inspect_sources({"a":[row("a:1")],"b":[row("b:1")]})
        one=decision("a:1","b:1","same")
        for decisions in ([one,dict(one)], [decision("a:1","other","same")]):
            with self.subTest(decisions=decisions),self.assertRaises(ValueError):
                apply_human_decisions(report,decisions)

    def test_evidence_and_rationale_are_required(self):
        report=inspect_sources({"a":[row("a:1")],"b":[row("b:1")]})
        for change in ({"evidence_url":"http://example.org"},
                       {"evidence_url":"https://username:pass@example.com/"},
                       {"review_note":"yes"},
                       {"status":"pending"},
                       {"status":"auto_approved"}):
            item=decision("a:1","b:1","same")
            item.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):
                apply_human_decisions(report,[item])

    def test_input_duplicates_and_bounds_refuse_silent_loss(self):
        with self.assertRaises(ValueError):
            inspect_sources({"a":[row("x"),row("x")]})
        with self.assertRaises(ValueError):
            inspect_sources({"a":[row("x")],"b":[row("x")]})
        with self.assertRaises(ValueError):
            inspect_sources({"a":[row("a:1"),row("a:2")]},max_rows=1)
        with self.assertRaises(ValueError):
            inspect_sources({"a":[row("a:1")],"b":[row("b:1")]},
                            max_pairs=0)

    def test_crowded_name_bucket_does_not_explode_quadratically(self):
        sources={f"s{i}":[row(f"s{i}:1")] for i in range(7)}
        review=inspect_sources(sources,max_bucket=3)
        self.assertEqual(review["crowded_name_series_buckets_skipped"],1)
        self.assertEqual(review["rows_in_crowded_buckets_skipped"],7)
        self.assertEqual(review["candidate_pairs"],[])

    def test_large_input_100k_keeps_constant_candidate_output(self):
        sources={"one":[row(f"one:{i}", f"Person {i}") for i in range(50_000)],
                 "two":[row(f"two:{i}", f"Other {i}") for i in range(50_000)]}
        review=inspect_sources(sources)
        self.assertEqual(review["rows_scanned"],100_000)
        self.assertEqual(review["distinct_keys"],100_000)
        self.assertEqual(len(review["candidate_pairs"]),0)

    def test_candidates_lexicographically_deterministic(self):
        sources={"one":[row("one:2","Zed"),row("one:1","Hero")],
                 "two":[row("two:9","Hero"),row("two:8","Zed")]}
        a=inspect_sources(sources)
        b=inspect_sources({"two":sources["two"][::-1],
                           "one":sources["one"][::-1]})
        self.assertEqual(a["candidate_pairs"],b["candidate_pairs"])
        self.assertEqual(normalize("ＡＢＣ  Test"),"abc test")


if __name__=="__main__":
    unittest.main()
