"""Local PostgreSQL proof: shared licensed artist/source works after variants.

TEST_DATABASE_URL must be localhost cardkout_test*. No real Telegram sends,
Neon writes, image downloads, Render disks, or production imports.
"""
import os
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch
import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from scripts.import_characters import import_batch
from scripts.import_variants import apply as import_variants
from app import storage, card_ui

AUTHOR="Kasuga"
LICENSE="CC BY-SA 3.0"
LICENSE_URL="https://creativecommons.org/licenses/by-sa/3.0/"


def local_test_url():
    raw=os.environ.get("TEST_DATABASE_URL","")
    if not raw:
        return None
    cfg=conninfo_to_dict(raw)
    if (cfg.get("host") not in ("localhost","127.0.0.1","::1") or
        not cfg.get("dbname","").startswith("cardkout_test") or
        raw==os.environ.get("DATABASE_URL")):
        raise RuntimeError("Art-credit tests refuse any remote/production database")
    return raw


def credit(page):
    return {"artwork_author":AUTHOR,
            "artwork_license_name":LICENSE,
            "artwork_license_url":LICENSE_URL,
            "artwork_page_url":page}


class ArtworkCreditDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url=local_test_url()
        if not cls.url:
            raise unittest.SkipTest("No disposable localhost Postgres provided")
        with psycopg.connect(cls.url) as db:
            db.execute(Path("database/schema.sql").read_text(encoding="utf8"))

    def conn(self):
        return psycopg.connect(self.url,row_factory=dict_row)

    def test_original_and_variant_license_is_shared_across_owned_cards(self):
        tag=uuid.uuid4().hex[:12]
        source="test:credited:"+tag
        first_page="https://commons.wikimedia.org/wiki/File:Wikipe-tan_sailor_fuku.png"
        variant_page="https://commons.wikimedia.org/wiki/File:Wikipe-tan_head.png"
        base_url="https://upload.wikimedia.org/wikipedia/commons/0/0e/Wikipe-tan_sailor_fuku.png"
        alt_url="https://upload.wikimedia.org/wikipedia/commons/a/ac/Wikipe-tan_head.png"
        character={"source_key":source,"name":"Wikipe-tan",
                   "series":"Wikimedia Anime and Manga Project",
                   "category":"other","rarity":"Common",
                   "image_url":base_url,**credit(first_page)}
        approved={"source_key":source,"status":"approved",
                  "image_url":base_url,
                  "permission_reference":first_page,**credit(first_page)}
        identity=None
        card_id=None
        variant_id=None
        try:
            with patch("scripts.import_characters.connect",self.conn):
                self.assertEqual(import_batch([character],[approved]),1)
            with self.conn() as db:
                original=db.execute("""SELECT id,artwork_author,artwork_license_url
                   FROM characters WHERE source_key=%s""",(source,)).fetchone()
                self.assertEqual(original["artwork_author"],AUTHOR)
                self.assertEqual(original["artwork_license_url"],LICENSE_URL)
                identity=original["id"]
                card_id=db.execute("""INSERT INTO owned_cards
                    (code,character_id,owner_id,generation) VALUES (%s,%s,70002001,1)
                    RETURNING id""",(f"CREDIT{tag}",identity)).fetchone()["id"]

            with patch("app.storage.connect",self.conn):
                base=storage.get_card(str(card_id))
                self.assertEqual(base["artwork_page_url"],first_page)
                self.assertEqual(base["artwork_license_name"],LICENSE)
                self.assertIn("Kasuga",card_ui.owned_caption(base))
                self.assertIn("Source</a>",card_ui.owned_caption(base))

            variant={"character_source_key":source,"variant_key":"head",
                     "label":"Wikipe-tan head","rarity":"Uncommon",
                     "image_url":alt_url,"spawn_weight":100,**credit(variant_page)}
            permission={"character_source_key":source,"variant_key":"head",
                        "status":"approved","image_url":alt_url,
                        "permission_reference":variant_page,
                        "artwork_identity_verified":True,
                        "reuse_rights_verified":True,
                        "content_suitability_verified":True,
                        "upstream_terms_verified":True,
                        "review_note":"Human reviewed distinct matching artwork and correct CC license.",
                        **credit(variant_page)}
            with patch("scripts.import_variants.connect",self.conn):
                self.assertEqual(import_variants([variant],[permission]),1)
            with self.conn() as db:
                variant_id=db.execute("""SELECT id FROM character_variants
                    WHERE character_id=%s AND variant_key='head'""",
                    (identity,)).fetchone()["id"]
                db.execute("UPDATE owned_cards SET variant_id=%s WHERE id=%s",
                           (variant_id,card_id))

            with patch("app.storage.connect",self.conn):
                viewed=storage.get_card(str(card_id))
                self.assertEqual(viewed["artwork_page_url"],variant_page)
                self.assertEqual(viewed["image_url"],alt_url)
                self.assertEqual(viewed["artwork_author"],AUTHOR)
                caption=card_ui.owned_caption(viewed)
                self.assertIn("CC BY-SA 3.0",caption)
                self.assertIn("Kasuga",caption)
                self.assertIn("Source</a>",caption)
                self.assertLess(len(caption),1024)

            with self.conn() as db:
                columns={r["column_name"] for r in db.execute(
                    """SELECT column_name FROM information_schema.columns
                       WHERE table_schema='public' AND table_name='owned_cards'""")}
                for banned in ("image_bytes","image_url","telegram_file_id",
                               "artwork_author","artwork_license_url","artwork_page_url"):
                    self.assertNotIn(banned,columns)
        finally:
            with self.conn() as db:
                if card_id is not None:
                    db.execute("DELETE FROM owned_cards WHERE id=%s",(card_id,))
                if variant_id is not None:
                    db.execute("DELETE FROM character_variants WHERE id=%s",(variant_id,))
                if identity is not None:
                    db.execute("DELETE FROM characters WHERE id=%s",(identity,))


if __name__=="__main__":
    unittest.main()
