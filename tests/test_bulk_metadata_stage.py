"""Large metadata pipeline guarantees, without network or database touches."""
import gzip
import json
from pathlib import Path
import tempfile
import unittest

from scripts.bulk_metadata_stage import stage_sources,MAX_INPUT_ROWS


class BulkMetadataStageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.src=self.root/"anime.jsonl"
        self.out=self.root/"staged.jsonl"

    def write(self,items,filename=None):
        p=filename or self.src
        with p.open("w",encoding="utf8") as f:
            for row in items:
                f.write(json.dumps(row,ensure_ascii=False)+"\n")
        return p

    def load(self):
        return [json.loads(s) for s in self.out.read_text(encoding="utf8").splitlines()]

    def test_source_namespaced_stable_output_no_image_leaks(self):
        self.write([
          {"id":1,"name":"Hero","series":"Open Story","category":"anime",
           "image_url":"https://provider.invalid/copyrighted.png",
           "telegram_file_id":"SECRET","aliases":["The Hero"]},
          {"id":2,"name":"Villain","series":"Open Story","category":"game"},
          {"id":1,"name":"Hero","series":"Open Story","category":"anime",
           "image_url":"https://other.invalid/ignored.png","aliases":["The Hero"]},
        ])
        report=stage_sources({"db":self.src},self.out,report_path=self.root/"audit.json")
        self.assertEqual(report["accepted_distinct_metadata"],2)
        self.assertEqual(report["identical_source_id_repeats"],1)
        self.assertEqual(report["artwork_approved"],0)
        self.assertEqual(report["production_database_writes"],0)
        rows=self.load()
        self.assertEqual(rows[0]["source_key"],"db:character:1")
        self.assertIsNone(rows[0]["image_url"])
        self.assertEqual(rows[0]["artwork_status"],
                         "pending_identity_rights_quality_and_telegram")
        self.assertNotIn("telegram_file_id",rows[0])
        self.assertNotIn("provider.invalid",self.out.read_text(encoding="utf8"))

    def test_sources_are_never_name_merged(self):
        self.write([{"id":1,"name":"Same","series":"Same"}])
        second=self.root/"other.jsonl"
        self.write([{"id":1,"name":"Same","series":"Same"}],second)
        report=stage_sources({"a":self.src,"b":second},self.out)
        self.assertEqual(report["accepted_distinct_metadata"],2)
        self.assertEqual({x["source_key"] for x in self.load()},
                         {"a:character:1","b:character:1"})

    def test_conflicting_source_key_rejected_atomically(self):
        self.write([{"id":1,"name":"Hero","series":"One"},
                    {"id":1,"name":"Hero","series":"Other"}])
        with self.assertRaisesRegex(ValueError,"Conflicting records"):
            stage_sources({"source":self.src},self.out)
        self.assertFalse(self.out.exists())

    def test_adult_and_invalid_metadata_not_transferred_to_catalog(self):
        self.write([{"id":1,"name":"A","series":"S","isAdult":True},
                    {"id":2,"name":"B","series":"S","rating":"18+"},
                    {"id":3,"name":"C","series":"S","category":"invalid"},
                    {"id":4,"name":"D","series":"S","isAdult":False}])
        report=stage_sources({"a":self.src},self.out)
        self.assertEqual(report["flagged_unsuitable_rows_skipped"],2)
        self.assertEqual(report["invalid_rows_skipped"],1)
        self.assertEqual([x["name"] for x in self.load()],["D"])

    def test_gzipped_jsonl_and_csv_paths_supported_offline(self):
        gz=self.root/"a.jsonl.gz"
        with gzip.open(gz,"wt",encoding="utf8") as f:
            f.write('{"id":"7","name":"Seven","series":"Series"}\n')
        csv_path=self.root/"b.csv"
        csv_path.write_text("id,name,series,category\n8,Eight,Series,webtoon\n",encoding="utf8")
        result=stage_sources({"a":gz,"b":csv_path},self.out)
        self.assertEqual(result["accepted_distinct_metadata"],2)
        self.assertEqual(len(self.load()),2)

    def test_output_cannot_clobber_source_or_exceed_limits(self):
        self.write([{"id":1,"name":"Hero","series":"Show"}])
        for kwargs in ({"output":self.src},
                       {"output":self.out,"max_rows":0},
                       {"output":self.out,"max_rows":MAX_INPUT_ROWS+1}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                stage_sources({"a":self.src},**kwargs)
        with self.assertRaises(ValueError):
            stage_sources({"a":self.src},self.out,report_path=self.src)

    def test_reject_malformed_json_without_partially_published_file(self):
        self.src.write_text('{"id":1,"name":"A","series":"S"}\n{bad\n',encoding="utf8")
        with self.assertRaises(json.JSONDecodeError):
            stage_sources({"source":self.src},self.out)
        self.assertFalse(self.out.exists())

    def test_100k_streaming_records_real_pipeline_not_artwork(self):
        total=100_000
        with self.src.open("w",encoding="utf8") as f:
            for i in range(total):
                f.write(json.dumps({"id":i+1,"name":f"Hero {i}",
                                    "series":f"Series {i%100}","category":"game",
                                    "image_url":"https://not-approved.example/p.png"})+"\n")
        report=stage_sources({"bulk":self.src},self.out)
        self.assertEqual(report["accepted_distinct_metadata"],total)
        self.assertEqual(report["input_rows"],total)
        self.assertEqual(report["artwork_approved"],0)
        self.assertEqual(report["image_urls_copied"],0)
        self.assertEqual(sum(1 for _ in self.out.open(encoding="utf8")),total)


if __name__=="__main__":
    unittest.main()
