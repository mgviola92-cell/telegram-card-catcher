"""Ensure numeric card storage uses a single character+generation index.

Actual disposable PostgreSQL only; verifies no card or numeric ID deleted.
No production writes, art downloads, Telegram, or Render deployment.
"""
import os
from pathlib import Path
import unittest
import psycopg
from psycopg.rows import dict_row

from scripts.benchmark_owned_cards import test_url


class OwnershipIndexTests(unittest.TestCase):
    def test_nonredundant_character_generation_index_preserves_all_ownership(self):
        try:
            url=test_url()
        except ValueError:
            raise unittest.SkipTest("No safe localhost PostgreSQL test database")
        with psycopg.connect(url,row_factory=dict_row) as db:
            # The disposable CI database may be created by a different
            # test class; DDL is idempotent and NEVER connected to Neon.
            db.execute(Path("database/schema.sql").read_text(encoding="utf8"))
            indexed=db.execute("""SELECT indexname,indexdef FROM pg_indexes
                WHERE schemaname='public' AND tablename='owned_cards'""").fetchall()
            indexes={r["indexname"]:r["indexdef"] for r in indexed}
            self.assertNotIn("owned_cards_by_character",indexes)
            self.assertIn("owned_cards_generation_unique",indexes)
            self.assertIn("UNIQUE INDEX",indexes["owned_cards_generation_unique"])
            self.assertIn("(character_id, generation)",
                          indexes["owned_cards_generation_unique"])
            self.assertIn("owned_cards_pkey",indexes)
            self.assertIn("owned_cards_code_key",indexes)

            # Verify both legacy code and compact new NULL code are supported.
            char=db.execute("""INSERT INTO characters
                (name,series,source_key,image_url,enabled)
                VALUES ('Local Fixture','Local Fixture','test:idx:single',
                        'https://example.org/external-only.png',false)
                ON CONFLICT (source_key) WHERE source_key IS NOT NULL
                DO UPDATE SET name=EXCLUDED.name RETURNING id""").fetchone()["id"]
            a=db.execute("""INSERT INTO owned_cards
                (code,character_id,owner_id,generation)
                VALUES ('TESTIDX_LEGACY',%s,42420001,201)
                RETURNING id""",(char,)).fetchone()["id"]
            b=db.execute("""INSERT INTO owned_cards
                (character_id,owner_id,generation)
                VALUES (%s,42420001,202) RETURNING id""",(char,)).fetchone()["id"]
            self.assertGreater(a,0)
            self.assertGreater(b,a)
            results=db.execute("""SELECT id,code,owner_id FROM owned_cards
                WHERE id=ANY(%s) ORDER BY id""",([a,b],)).fetchall()
            self.assertEqual(len(results),2)
            self.assertEqual(results[0]["code"],"TESTIDX_LEGACY")
            self.assertIsNone(results[1]["code"])
            self.assertEqual([r["owner_id"] for r in results],[42420001]*2)
            # Roll back local fixture; never tamper with real owned cards.
            db.rollback()


if __name__=="__main__":
    unittest.main()
