"""Opt-in PostgreSQL integration suite; uses a disposable database only.

Required: TEST_DATABASE_URL. Refuses matching DATABASE_URL and non-test DB names.
Never run against a production database.
"""
import os
import unittest
import psycopg
from psycopg.rows import dict_row

def safe_test_database_url():
    url=os.environ.get("TEST_DATABASE_URL","")
    if not url:
        return None
    if url==os.environ.get("DATABASE_URL"):
        raise RuntimeError("TEST_DATABASE_URL must not equal DATABASE_URL")
    from urllib.parse import urlsplit
    name=urlsplit(url).path.lstrip("/")
    if not name.startswith("cardkout_test"):
        raise RuntimeError("Test database name must start with cardkout_test")
    return url

class DatabaseFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url=safe_test_database_url()
        if not cls.url:
            raise unittest.SkipTest("TEST_DATABASE_URL not configured")
        cls.db=psycopg.connect(cls.url,row_factory=dict_row)
        cls.db.autocommit=False
        cls.db.execute(open("database/schema.sql",encoding="utf-8").read())
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls,"db"):
            cls.db.close()

    def setUp(self):
        self.db.execute("BEGIN")

    def tearDown(self):
        self.db.rollback()

    def test_catalog_variant_and_card_ownership(self):
        db=self.db
        char=db.execute("""INSERT INTO characters
            (name,series,source_key,image_url)
            VALUES ('QA Hero','QA Series','test:integration-hero',
            'https://example.org/qa.png') RETURNING id""").fetchone()['id']
        variant=db.execute("""INSERT INTO character_variants
            (character_id,variant_key,label,image_url,rarity)
            VALUES (%s,'winter','Winter','https://example.org/winter.png','Rare')
            RETURNING id""",(char,)).fetchone()['id']
        db.execute("""INSERT INTO group_settings(chat_id,active_character_id,active_variant_id)
            VALUES (-1234567,%s,%s)""",(char,variant))
        db.execute("""INSERT INTO owned_cards
            (code,character_id,variant_id,owner_id,generation,caught_chat_id)
            VALUES ('TESTQA123',%s,%s,101,1,-1234567)""",(char,variant))
        result=db.execute("""SELECT o.code,v.label,v.rarity FROM owned_cards o
            LEFT JOIN character_variants v ON v.id=o.variant_id
            WHERE o.owner_id=101""").fetchone()
        self.assertEqual((result['code'],result['label'],result['rarity']),
                         ('TESTQA123','Winter','Rare'))
        db.execute("""UPDATE owned_cards SET owner_id=202 WHERE code='TESTQA123' AND owner_id=101""")
        owner=db.execute("SELECT owner_id FROM owned_cards WHERE code='TESTQA123'").fetchone()
        self.assertEqual(owner['owner_id'],202)

    def test_trade_schema(self):
        columns={r['column_name'] for r in self.db.execute(
            """SELECT column_name FROM information_schema.columns
            WHERE table_name='trade_offers'""").fetchall()}
        self.assertTrue({'sender_id','receiver_id','status','created_at'}<=columns)

if __name__=="__main__":
    unittest.main()
