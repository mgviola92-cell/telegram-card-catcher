"""Real PostgreSQL COPY + upsert verification in disposable localhost only.

No remote Neon access, no images/media downloads, all test rows ROLLBACK.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid
import psycopg
from psycopg.rows import dict_row

from scripts.benchmark_owned_cards import test_url
from scripts.bulk_url_import import stage,apply,SQL_UPSERT


class BulkURLPostgresTests(unittest.TestCase):
    def test_copy_upsert_preserves_owned_ids_and_rolls_back(self):
        try:
            url=test_url()
        except ValueError:
            raise unittest.SkipTest("Missing disposable localhost TEST_DATABASE_URL")
        tag=uuid.uuid4().hex[:12]
        with tempfile.TemporaryDirectory() as folder:
            f=Path(folder)/"named.jsonl"
            g=Path(folder)/"reviewed.json"
            key=f"localtest:character:{tag}"
            catalog=[{
               "source_key":key, "name":"Test Licensed Hero",
               "series":"Original Fixture Game", "image_url":"https://art.example.org/hero.png",
               "artwork_author":"Original Fixture Artist",
               "artwork_page_url":"https://art.example.org/pages/hero"
            }]
            f.write_text("".join(json.dumps(row)+"\n" for row in catalog))
            grant={
                "catalog_sha256":hashlib.sha256(f.read_bytes()).hexdigest(),
                "review_status":"independently_reviewed",
                "scope_includes_every_image":True,
                "redistribution_to_telegram_permitted":True,
                "source_key_prefix":"localtest:character:",
                "image_hosts":["art.example.org"],
                "source_terms_url":"https://art.example.org/terms",
                "artwork_license_url":"https://creativecommons.org/licenses/by/4.0/",
                "artwork_license_name":"CC BY 4.0",
                "license_scope_evidence_url":"https://art.example.org/licensing",
                "credit_policy_url":"https://art.example.org/credit",
                "reviewed_by":"Local test runner",
                "review_note":"Synthetic test only, not a real license or permission.",
                "telegram_delivery_verified_for_source":False,
            }
            g.write_text(json.dumps(grant))
            tmp,local,stats=stage(f,g)
            try:
                db=psycopg.connect(url,row_factory=dict_row)
                try:
                    report=apply(db,local,stats)
                    self.assertEqual(report["new_characters_count_pre_upsert"],1)
                    char=db.execute("""SELECT id,image_url,artwork_author,enabled,telegram_file_id
                        FROM characters WHERE source_key=%s""",(key,)).fetchone()
                    self.assertIsNotNone(char)
                    self.assertFalse(char["enabled"])
                    self.assertIsNone(char["telegram_file_id"])
                    self.assertEqual(char["artwork_author"],"Original Fixture Artist")
                    card_id=db.execute("""INSERT INTO owned_cards
                        (character_id,owner_id,generation)
                        VALUES (%s,990077001,1) RETURNING id""",
                        (char["id"],)).fetchone()["id"]
                    db.execute("UPDATE characters SET telegram_file_id='old-media' WHERE id=%s",
                               (char["id"],))
                    # PostgreSQL temp table remains valid in same uncommitted tx.
                    # Changing art MUST drop only shared cached Telegram media.
                    db.execute("""UPDATE cardkout_bulk_urls
                        SET image_url='https://art.example.org/hero-updated.png',
                            enabled=false""")
                    db.execute(SQL_UPSERT)
                    changed=db.execute("""SELECT image_url,telegram_file_id
                        FROM characters WHERE id=%s""",(char["id"],)).fetchone()
                    self.assertEqual(changed["image_url"],
                                     "https://art.example.org/hero-updated.png")
                    self.assertIsNone(changed["telegram_file_id"])
                    card=db.execute("""SELECT owner_id,id,code FROM owned_cards
                        WHERE id=%s""",(card_id,)).fetchone()
                    self.assertEqual(card["owner_id"],990077001)
                    self.assertIsNone(card["code"])
                    self.assertEqual(card["id"],card_id)
                finally:
                    db.rollback()
                    db.close()
            finally:
                local.close()
                tmp.cleanup()
        with psycopg.connect(url,row_factory=dict_row) as db:
            self.assertIsNone(db.execute("SELECT id FROM characters WHERE source_key=%s",
                                         (key,)).fetchone())


if __name__=="__main__":
    unittest.main()
