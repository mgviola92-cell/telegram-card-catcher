"""Rights-scoped, source-digest-pinned 100k+ URL importer, no live Neon."""
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import MagicMock,patch
import tempfile
import unittest
from scripts.bulk_url_import import (
  normalize,valid_https,stage,run,validate_grant,apply,CONFIRM,
  RESERVE_BYTES,PER_NEW_CHARACTER_BUDGET,
)


class URLBulkImportTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.urls=self.root/"full.jsonl"
        self.grant=self.root/"grant.json"
        self.data=[{
            "source_key":"sample:character:1","name":"Hero",
            "series":"Open Fantasy","image_url":"https://art.sample.org/hero.png",
            "artwork_author":"Sample artist",
            "artwork_page_url":"https://art.sample.org/pages/hero",
            "category":"game",
        }]
        self.write()

    def write(self):
        self.urls.write_text("".join(json.dumps(r,ensure_ascii=False)+"\n"
                             for r in self.data),encoding="utf8")
        self.policy={
            "catalog_sha256":hashlib.sha256(self.urls.read_bytes()).hexdigest(),
            "review_status":"independently_reviewed",
            "scope_includes_every_image":True,
            "redistribution_to_telegram_permitted":True,
            "source_key_prefix":"sample:character:",
            "image_hosts":["art.sample.org"],
            "source_terms_url":"https://art.sample.org/terms",
            "artwork_license_url":"https://creativecommons.org/licenses/by/4.0/",
            "artwork_license_name":"CC BY 4.0",
            "license_scope_evidence_url":"https://art.sample.org/licensing",
            "credit_policy_url":"https://art.sample.org/credits",
            "reviewed_by":"Operator Example",
            "review_note":"Independent operator reviewed actual reuse terms for this full hypothetical fixture.",
            "telegram_delivery_verified_for_source":False,
        }
        self.grant.write_text(json.dumps(self.policy),encoding="utf8")

    def test_dry_run_has_no_database_connection_or_images(self):
        with patch("psycopg.connect") as connect:
            result=run(self.urls,self.grant)
            connect.assert_not_called()
        self.assertEqual(result["unique_characters"],1)
        self.assertEqual(result["database_connections"],0)
        self.assertEqual(result["image_files_downloaded"],0)
        self.assertEqual(result["mode"],"dry_run")

    def test_digest_scope_and_licence_required(self):
        self.urls.write_text(self.urls.read_text()+"\n",encoding="utf8")
        with self.assertRaisesRegex(ValueError,"exact batch scope"):
            run(self.urls,self.grant)
        self.write()
        self.policy["scope_includes_every_image"]=False
        self.grant.write_text(json.dumps(self.policy),encoding="utf8")
        with self.assertRaises(ValueError):
            run(self.urls,self.grant)

    def test_duplicate_identical_and_conflict_fail(self):
        self.data.append(dict(self.data[0]))
        self.write()
        outcome=run(self.urls,self.grant)
        self.assertEqual(outcome["identical_duplicates"],1)
        self.assertEqual(outcome["unique_characters"],1)
        self.data[-1]["name"]="Wrong replacement"
        self.write()
        with self.assertRaisesRegex(ValueError,"Conflicting source_key"):
            run(self.urls,self.grant)

    def test_reject_unlicensed_hostname_and_unsafe_urls(self):
        for bad in ("https://art.sample.org.evil.test/a.png",
                    "http://art.sample.org/a.png",
                    "https://127.0.0.1/a.jpg",
                    "https://art.sample.org:8443/a.png",
                    "https://user:secret@art.sample.org/a.png"):
            with self.subTest(bad=bad):
                self.data[0]["image_url"]=bad
                self.write()
                with self.assertRaises(ValueError):
                    run(self.urls,self.grant)

    def test_reject_no_character_identity_and_adult(self):
        self.data[0]["name"]=""
        self.write()
        with self.assertRaises(ValueError):
            run(self.urls,self.grant)
        self.data[0]["name"]="Hero"
        self.data[0]["age_rating"]="18+"
        self.write()
        with self.assertRaises(ValueError):
            run(self.urls,self.grant)

    def test_apply_requires_owner_authorization_before_any_database_io(self):
        with patch.dict(os.environ,{},clear=True),patch("psycopg.connect") as cn:
            with self.assertRaises(ValueError):
                run(self.urls,self.grant,allow_write=True)
            cn.assert_not_called()
        with patch.dict(os.environ,{"CARDKOUT_BULK_IMPORT_AUTHORIZED":"YES"}),patch(
            "psycopg.connect") as cn:
            with self.assertRaises(ValueError):
                run(self.urls,self.grant,allow_write=True,rights_reviewed=True,
                    confirm="wrong")
            cn.assert_not_called()

    def test_cannot_enable_without_source_photo_testing(self):
        with self.assertRaisesRegex(ValueError,"Telegram photo"):
            run(self.urls,self.grant,enable=True)

    def test_reserve_guard_blocks_without_copy_or_commit(self):
        tmp,local,stats=stage(self.urls,self.grant)
        try:
            mock=MagicMock()
            mock.execute.return_value.fetchone.return_value={"size":1_000_000_000}
            with self.assertRaisesRegex(ValueError,"Storage reserve"):
                apply(mock,local,stats)
            self.assertEqual(mock.execute.call_count,1)
        finally:
            local.close()
            tmp.cleanup()

    def test_one_hundred_thousand_REAL_input_rows_validation(self):
        n=100_000
        with self.urls.open("w",encoding="utf8") as f:
            for i in range(n):
                f.write(json.dumps({"source_key":f"sample:character:{i+1}",
                     "name":f"Named Hero {i}","series":f"Open Series {i%250}",
                     "image_url":f"https://art.sample.org/source/{i}.png",
                     "artwork_author":"Sample author",
                     "artwork_page_url":f"https://art.sample.org/source/{i}"})+"\n")
        self.policy["catalog_sha256"]=hashlib.sha256(self.urls.read_bytes()).hexdigest()
        self.grant.write_text(json.dumps(self.policy))
        result=run(self.urls,self.grant)
        self.assertEqual(result["unique_characters"],n)
        self.assertEqual(result["database_connections"],0)
        self.assertTrue(result["artwork_urls_stored_as_text_only"])
        self.assertEqual(result["image_files_downloaded"],0)


if __name__=="__main__":
    unittest.main()
