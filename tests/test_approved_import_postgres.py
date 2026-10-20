"""Approved catalog import / shared Telegram media in LOCAL PostgreSQL only.

Integration is skipped if explicit localhost cardkout_test* database absent.
Never connects to production Neon. Tests demonstrate owner cards store no photos.
"""
import os
from pathlib import Path
import unittest
from urllib.parse import urlsplit

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from scripts.import_characters import import_batch
from app import storage


def safe_url():
    value=os.environ.get("TEST_DATABASE_URL","")
    if not value:
        return None
    try:
        info=conninfo_to_dict(value)
        host=info.get("host","")
        database=info.get("dbname","")
    except Exception:
        raise ValueError("Invalid TEST_DATABASE_URL")
    if host not in ("localhost","127.0.0.1","::1") or not database.startswith("cardkout_test"):
        raise ValueError("TEST_DATABASE_URL must point to a disposable localhost cardkout_test* database")
    if value==os.environ.get("DATABASE_URL"):
        raise ValueError("Test database must never be the production DATABASE_URL")
    return value


class ApprovedCatalogDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url=safe_url()
        if not cls.url:
            raise unittest.SkipTest("Disposable local PostgreSQL not provided")
        with psycopg.connect(cls.url) as db:
            db.execute(Path("database/schema.sql").read_text(encoding="utf8"))

    def test_approved_import_reuses_shared_image_after_catch_and_url_updates(self):
        from unittest.mock import patch
        source_key="test:approved-alice-image-sharing"
        first="https://upload.wikimedia.org/wikipedia/commons/3/39/Alice_in_Wonderland%2C_Drink_me_by_John_Tenniel.jpg"
        second="https://upload.wikimedia.org/wikipedia/commons/a/a0/Changed_only_for_test.jpg"
        character={"source_key":source_key,"name":"Licensed Demo",
                   "series":"Original Demonstration","image_url":first,
                   "category":"other","rarity":"Common"}
        proof={"source_key":source_key,"image_url":first,"status":"approved",
               "permission_reference":"https://commons.wikimedia.org/wiki/File:Alice_in_Wonderland"}
        code="LOCALTEST0001"
        owner_id=98760022
        # Only this *local disposable test DB* is ever affected.
        try:
            with patch("scripts.import_characters.connect",
                       lambda: psycopg.connect(self.url,row_factory=dict_row)):
                self.assertEqual(import_batch([character],[proof]),1)
            with psycopg.connect(self.url,row_factory=dict_row) as db:
                char=db.execute("SELECT id,image_url,telegram_file_id FROM characters WHERE source_key=%s",
                                (source_key,)).fetchone()
                self.assertEqual(char["image_url"],first)
                char_id=char["id"]
                self.assertIsNone(char["telegram_file_id"])
                owned=db.execute("""INSERT INTO owned_cards
                    (code,character_id,owner_id,generation)
                    VALUES (%s,%s,%s,1) RETURNING id""",
                    (code,char_id,owner_id)).fetchone()
                card_id=owned["id"]
                self.assertGreater(card_id,0)
                db.execute("UPDATE characters SET telegram_file_id=%s WHERE id=%s",
                           ("telegram:cached:shared-demo",char_id))
            with patch("app.storage.connect",lambda:psycopg.connect(
                 self.url,row_factory=dict_row)):
                card=storage.get_card(str(card_id))
                self.assertEqual(card["owner_id"],owner_id)
                self.assertEqual(card["telegram_file_id"],"telegram:cached:shared-demo")
                self.assertEqual(card["image_url"],first)
            # Reimport SAME art must not invalidate the Telegram media ID.
            with patch("scripts.import_characters.connect",
                       lambda: psycopg.connect(self.url,row_factory=dict_row)):
                import_batch([character],[proof])
            with psycopg.connect(self.url,row_factory=dict_row) as db:
                cached=db.execute("SELECT telegram_file_id FROM characters WHERE id=%s",
                                  (char_id,)).fetchone()["telegram_file_id"]
                self.assertEqual(cached,"telegram:cached:shared-demo")
            # Changed art *must* invalidate shared file ID, but NEVER ownership.
            updated=dict(character,image_url=second)
            approved=dict(proof,image_url=second)
            with patch("scripts.import_characters.connect",
                       lambda: psycopg.connect(self.url,row_factory=dict_row)):
                import_batch([updated],[approved])
            with psycopg.connect(self.url,row_factory=dict_row) as db:
                got=db.execute("""SELECT o.id,o.code,o.owner_id,c.image_url,
                                  c.telegram_file_id
                                  FROM owned_cards o
                                  JOIN characters c ON o.character_id=c.id
                                  WHERE o.code=%s""",(code,)).fetchone()
                self.assertEqual(got["id"],card_id)
                self.assertEqual(got["owner_id"],owner_id)
                self.assertEqual(got["image_url"],second)
                self.assertIsNone(got["telegram_file_id"])
                columns={r["column_name"] for r in db.execute(
                    """SELECT column_name FROM information_schema.columns
                       WHERE table_name='owned_cards' AND table_schema='public'""")}
                self.assertNotIn("image_url",columns)
                self.assertNotIn("telegram_file_id",columns)
                self.assertNotIn("image_bytes",columns)
        finally:
            with psycopg.connect(self.url) as db:
                db.execute("DELETE FROM owned_cards WHERE code=%s",(code,))
                db.execute("DELETE FROM characters WHERE source_key=%s",(source_key,))


if __name__=="__main__":
    unittest.main()
