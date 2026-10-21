"""An actual source-schema stream, no network, no images and no Neon."""
import gzip
import json
from pathlib import Path
import tempfile
import unittest

from scripts.anime_offline_stream import stage_snapshot, snapshot_records
from scripts.bulk_metadata_stage import stage_sources


class OfflineSnapshotTests(unittest.TestCase):
    def setUp(self):
        d=tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.root=Path(d.name)
        self.source=self.root/"characters.json"
        self.mid=self.root/"mapped.jsonl"
        self.final=self.root/"dedup.jsonl"

    def item(self,n):
        return {"mal_id":n,"name":f"Character {n}",
                "nicknames":["Alias"],"images":{"jpg":"https://notlicensed.example/pic.jpg"},
                "animeAppearances":[{"anime":{"title":"Shōnen Series"}}]}

    def test_actual_jikan_schema_adapter_then_bulk_namespace(self):
        sample={"meta":{"schemaVersion":"1.0.0","license":{"name":"ODbL + DbCL"}},
                "data":[self.item(9),self.item(9),self.item(11),{
                    **self.item(12),"isAdult":True},{
                    **self.item(13),"animeAppearances":[]}]}
        self.source.write_text(json.dumps(sample,ensure_ascii=False),encoding="utf8")
        info=stage_snapshot(self.source,self.mid)
        self.assertEqual(info["source_rows"],5)
        self.assertEqual(info["normalized_rows"],3)
        self.assertEqual(info["flagged_adult"],1)
        self.assertEqual(info["without_series"],1)
        report=stage_sources({"mal":self.mid},self.final)
        self.assertEqual(report["accepted_distinct_metadata"],2)
        self.assertEqual(report["identical_source_id_repeats"],1)
        row=json.loads(self.final.read_text(encoding="utf8").splitlines()[0])
        self.assertEqual(row["source_key"],"mal:character:11")
        self.assertIsNone(row["image_url"])
        self.assertFalse(row["approved_for_import"])
        self.assertNotIn("notlicensed.example",self.final.read_text())

    def test_gzipped_snapshot_and_unicode(self):
        path=self.root/"characters.json.gz"
        with gzip.open(path,"wt",encoding="utf8") as stream:
            json.dump({"data":[self.item(1)]},stream,ensure_ascii=False)
        r=stage_snapshot(path,self.mid)
        self.assertEqual(r["normalized_rows"],1)
        self.assertIn("Shōnen",self.mid.read_text(encoding="utf8"))

    def test_empty_missing_data_is_rejected_no_partial_output(self):
        for data in ('{"meta":{}}','{"data":{bad}','{"data":[{}]','{"unknown":1,"data":[]}'):
            with self.subTest(data=data):
                self.source.write_text(data,encoding="utf8")
                with self.assertRaises(ValueError):
                    stage_snapshot(self.source,self.mid)
                self.assertFalse(self.mid.exists())

    def test_same_path_and_row_cap_rejected(self):
        self.source.write_text('{"data":[{},{}]}',encoding="utf8")
        with self.assertRaises(ValueError):
            stage_snapshot(self.source,self.source)
        with self.assertRaisesRegex(ValueError,"row limit"):
            stage_snapshot(self.source,self.mid,max_records=1)

    def test_stream_50k_records_with_bounded_memory(self):
        n=50_000
        with self.source.open("w",encoding="utf8") as out:
            out.write('{"meta":{"schemaVersion":"1"},"data":[')
            for i in range(n):
                if i:out.write(',')
                out.write(json.dumps(self.item(i+1),ensure_ascii=False))
            out.write(']}')
        report=stage_snapshot(self.source,self.mid)
        self.assertEqual(report["source_rows"],n)
        self.assertEqual(report["normalized_rows"],n)
        self.assertEqual(sum(1 for _ in self.mid.open(encoding="utf8")),n)
        self.assertEqual(report["photo_files_downloaded"],0)


if __name__=="__main__":
    unittest.main()
