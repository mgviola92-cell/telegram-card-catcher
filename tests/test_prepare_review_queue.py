"""Deterministic human-review queue remains pending even on source image hints."""
import unittest

from scripts.prepare_review_queue import make_queue
from scripts.build_reviewed_catalog import REQUIRED_CHECKS, assemble


def entry(k,name="Hero",series="Cartoon"):
    return {"source_key":k,"name":name,"series":series,
            "image_url":"https://unsafe.example/unknown-rights.jpg"}


class ReviewQueueTests(unittest.TestCase):
    def test_output_never_promotes_external_image_pointer(self):
        result=make_queue([entry("local:1")])
        self.assertEqual(result["review_queue_count"],1)
        card=result["review_queue"][0]
        self.assertEqual(card["status"],"pending")
        self.assertIsNone(card["image_url"])
        self.assertTrue(all(card["evidence"][x] is None for x in REQUIRED_CHECKS))
        self.assertEqual(result["approved_for_import"],0)
        self.assertNotIn("unsafe.example",str(result))
        self.assertEqual(assemble([entry("local:1")],result["review_queue"])["catalog"],[])

    def test_round_robin_selects_diverse_series(self):
        rows=[entry(f"a:{i}",f"A {i}","Show A") for i in range(20)]
        rows+= [entry(f"b:{i}",f"B {i}","Show B") for i in range(3)]
        rows+= [entry(f"c:{i}",f"C {i}","Show C") for i in range(3)]
        result=make_queue(rows,limit=6,max_per_series=2)
        self.assertEqual({x["source_series"] for x in result["review_queue"]},
                         {"Show A","Show B","Show C"})
        self.assertEqual([x["source_series"] for x in result["review_queue"]],
                         ["Show A","Show B","Show C","Show A","Show B","Show C"])

    def test_deterministic_against_input_permutation(self):
        data=[entry("s:1","B"),entry("s:2","A"),
              entry("q:2","Z","Second"),entry("q:1","D","Second")]
        self.assertEqual(make_queue(data)["review_queue"],
                         make_queue(data[::-1])["review_queue"])

    def test_repeated_ids_are_not_silently_merged(self):
        with self.assertRaises(ValueError):
            make_queue([entry("same:id"),entry("same:id")])

    def test_invalid_entries_are_counted_not_used(self):
        result=make_queue([entry("s:1"),None,{"source_key":"x"},
                           entry("s:2",name="",series="Unknown")])
        self.assertEqual(result["invalid_records_skipped"],3)
        self.assertEqual(result["review_queue_count"],1)

    def test_many_rows_have_small_output_cap(self):
        data=[entry(f"a:{i}",f"Name {i}","Show A") for i in range(90_000)]
        result=make_queue(data,limit=10,max_per_series=10)
        self.assertEqual(result["valid_source_records"],90_000)
        self.assertEqual(result["review_queue_count"],10)
        self.assertEqual(result["approved_for_import"],0)

    def test_bounds_reject_excessive_queue(self):
        with self.assertRaises(ValueError):
            make_queue([],limit=5001)
        with self.assertRaises(ValueError):
            make_queue([],max_per_series=101)
        with self.assertRaises(ValueError):
            make_queue({},limit=2)


if __name__=="__main__":
    unittest.main()
