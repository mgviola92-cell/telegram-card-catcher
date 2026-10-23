"""No live photo or Neon work; source-key image candidate join."""
import json
from pathlib import Path
import tempfile
import unittest
from scripts.bulk_metadata_stage import stage_sources
from scripts.bulk_artwork_match import join


class ArtworkJoinTests(unittest.TestCase):
    def setUp(self):
        d=tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.root=Path(d.name)
        self.raw=self.root/"raw.jsonl"
        self.stage=self.root/"staged.jsonl"
        self.art=self.root/"photos.jsonl"
        self.out=self.root/"pending.jsonl"
        self.raw.write_text('{"id":1,"name":"Hero","series":"Saga"}\n',encoding="utf8")
        stage_sources({"src":self.raw},self.stage)

    def items(self,rows):
        self.art.write_text("".join(json.dumps(r)+"\n" for r in rows),encoding="utf8")

    def run_join(self):
        return join(self.stage,self.art,self.out,allowed_hosts=["art.example.org"])

    def test_only_exact_source_key_and_original_host(self):
        self.items([
          {"source_key":"src:character:1","candidate_image_url":"https://art.example.org/hero.png","approved_for_import":False},
          {"source_key":"other:character:1","candidate_image_url":"https://art.example.org/wrong.png","approved_for_import":False},
          {"source_key":"src:character:1","candidate_image_url":"https://art.example.org.bad.example/a.png","approved_for_import":False},
          {"source_key":"src:character:1","candidate_image_url":"https://art.example.org/hero.png","approved_for_import":False}])
        result=self.run_join()
        self.assertEqual(result["matched_pending"],1)
        self.assertEqual(result["unmatched_source_key"],1)
        self.assertEqual(result["rejected_art"],1)
        self.assertEqual(result["duplicate_art"],1)
        row=json.loads(self.out.read_text(encoding="utf8"))
        self.assertIsNone(row["image_url"])
        self.assertFalse(row["reuse_rights_verified"])
        self.assertFalse(row["approved_for_import"])

    def test_claimed_approval_never_becomes_import_ready(self):
        self.items([{"source_key":"src:character:1",
                     "candidate_image_url":"https://art.example.org/p.jpg",
                     "approved_for_import":True}])
        report=self.run_join()
        self.assertEqual(report["matched_pending"],0)
        self.assertEqual(report["artwork_approved"],0)
        self.assertEqual(report["database_writes"],0)

    def test_10000_artwork_candidates_offline(self):
        n=10_000
        with self.raw.open("w",encoding="utf8") as f,self.art.open("w",encoding="utf8") as a:
            for i in range(n):
                f.write(json.dumps({"id":i+1,"name":f"Hero{i}","series":"Series"})+"\n")
                a.write(json.dumps({"source_key":f"src:character:{i+1}",
                                    "candidate_image_url":f"https://art.example.org/{i}.jpg",
                                    "approved_for_import":False})+"\n")
        stage_sources({"src":self.raw},self.stage)
        report=self.run_join()
        self.assertEqual(report["matched_pending"],n)
        self.assertEqual(sum(1 for _ in self.out.open(encoding="utf8")),n)
        self.assertEqual(report["image_files_downloaded"],0)

    def test_invalid_host_config_and_input_overwrite_rejected(self):
        self.items([])
        with self.assertRaises(ValueError):
            join(self.stage,self.art,self.out,allowed_hosts=[])
        with self.assertRaises(ValueError):
            join(self.stage,self.art,self.art,allowed_hosts=["art.example.org"])


if __name__=="__main__":
    unittest.main()
