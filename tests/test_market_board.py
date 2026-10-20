"""Real trade-board testing against disposable LOCAL Postgres only.

No Telegram API, production Neon/Render, real-money features, images, or
automatic card transfers. Market listings reference numeric owned-card IDs.
"""
import os
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from app import market_board,market_board_ui,collection_stats,collection_stats_ui


def test_database_url():
    url=os.environ.get("TEST_DATABASE_URL","")
    if not url:
        return None
    parts=conninfo_to_dict(url)
    if (parts.get("host") not in ("localhost","127.0.0.1","::1")
        or not parts.get("dbname","").startswith("cardkout_test")
        or url==os.environ.get("DATABASE_URL")):
        raise RuntimeError("Market tests refuse all production or remote databases")
    return url


class MarketUnitTests(unittest.TestCase):
    def test_invalid_id_rejected_without_db(self):
        with patch("app.market_board.connect") as db:
            for code in (None,"",0,-1,True,"1 OR 1=1"):
                with self.subTest(code=code):
                    self.assertIsNone(market_board.list_card(101,-100001,code))
                    self.assertFalse(market_board.unlist_card(101,code))
            for user,chat in ((True,-100),(0,-100),(10,0),(-10,-100)):
                self.assertIsNone(market_board.list_card(user,chat,"4"))
            db.assert_not_called()

    def test_market_markup_escapes_untrusted_text(self):
        text=market_board_ui.market_caption([{
            "card_id":340,"seller_id":54,"name":"Bad <script>&",
            "series":"Foo & Bar", "rarity":"Rare",
        }])
        self.assertIn("Bad &lt;script&gt;&amp;",text)
        self.assertNotIn("<script>",text)
        self.assertIn("Foo &amp; Bar",text)
        self.assertIn("<code>340</code>",text)
        self.assertIn("/trade MY_ID THEIR_ID",text)
        self.assertIn("24 hours",text)
        self.assertIn("No active",market_board_ui.market_caption([]))
        self.assertIn("<code>340</code>",market_board_ui.listed_caption(340))

    def test_board_rejects_boolean_limit(self):
        for kwargs in ({"chat_id":True},{"chat_id":0},{"chat_id":-100,"limit":0},
                       {"chat_id":-100,"limit":True},{"chat_id":-100,"limit":100}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                market_board.group_market(**kwargs)


class MarketPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url=test_database_url()
        if not cls.url:
            raise unittest.SkipTest("Disposable localhost PostgreSQL is not configured")
        with psycopg.connect(cls.url) as db:
            db.execute(Path("database/schema.sql").read_text(encoding="utf8"))

    def connect(self):
        return psycopg.connect(self.url,row_factory=dict_row)

    def setUp(self):
        tag=uuid.uuid4().hex[:15]
        self.owner=88001010
        self.other=88002020
        self.group=-10099110020
        self.another_group=-10099110030
        self.codes=[]
        self.card_ids=[]
        with self.connect() as db:
            self.charid=db.execute("""INSERT INTO characters
                (name,series,source_key,image_url,enabled)
                VALUES ('Market Test','Test Markets',%s,
                        'https://upload.wikimedia.org/synthetic-shared.jpg',false)
                RETURNING id""",(f"test:market:{tag}",)).fetchone()["id"]
            for i in range(7):
                code=f"MK{tag.upper()}{i}"
                card=db.execute("""INSERT INTO owned_cards
                    (code,character_id,owner_id,generation)
                    VALUES (%s,%s,%s,%s) RETURNING id""",
                    (code,self.charid,self.owner if i<6 else self.other,i+1)).fetchone()
                self.codes.append(code)
                self.card_ids.append(card["id"])
        self.patches=[patch("app.market_board.connect",self.connect),
                      patch("app.collection_stats.connect",self.connect)]
        for item in self.patches:
            item.start()

    def tearDown(self):
        try:
            with self.connect() as db:
                db.execute("DELETE FROM market_listings WHERE card_id=ANY(%s)",(self.card_ids,))
                db.execute("DELETE FROM owned_cards WHERE id=ANY(%s)",(self.card_ids,))
                db.execute("DELETE FROM characters WHERE id=%s",(self.charid,))
        finally:
            for item in reversed(self.patches):
                item.stop()

    def test_owner_can_list_browse_refresh_and_unlist_numeric_and_legacy(self):
        first=market_board.list_card(self.owner,self.group,str(self.card_ids[0]))
        self.assertEqual(first["card_id"],self.card_ids[0])
        self.assertEqual(first["seller_id"],self.owner)
        self.assertIsNone(market_board.list_card(self.other,self.group,str(self.card_ids[1])))
        listings=market_board.group_market(self.group)
        self.assertEqual(len(listings),1)
        self.assertEqual(listings[0]["card_id"],self.card_ids[0])
        self.assertEqual(listings[0]["name"],"Market Test")
        self.assertEqual(len(market_board.group_market(self.another_group)),0)
        refreshed=market_board.list_card(self.owner,self.group,self.codes[0])
        self.assertEqual(refreshed["card_id"],self.card_ids[0])
        self.assertFalse(market_board.unlist_card(self.other,self.codes[0]))
        self.assertTrue(market_board.unlist_card(self.owner,self.codes[0]))
        self.assertFalse(market_board.unlist_card(self.owner,self.codes[0]))
        self.assertEqual(market_board.group_market(self.group),[])

    def test_five_active_listings_limit_and_owner_refresh(self):
        for cid in self.card_ids[:5]:
            self.assertIsNotNone(market_board.list_card(self.owner,self.group,cid))
        self.assertIsNone(market_board.list_card(self.owner,self.group,self.card_ids[5]))
        self.assertIsNotNone(market_board.list_card(self.owner,self.group,self.card_ids[1]))
        self.assertEqual(len(market_board.group_market(self.group)),5)
        self.assertTrue(market_board.unlist_card(self.owner,self.card_ids[0]))
        self.assertIsNotNone(market_board.list_card(self.owner,self.group,self.card_ids[5]))

    def test_expired_or_transferred_listings_are_invisible_and_not_quota(self):
        for cid in self.card_ids[:5]:
            market_board.list_card(self.owner,self.group,cid)
        with self.connect() as db:
            db.execute("""UPDATE market_listings SET expires_at=now()-interval '1 minute'
                        WHERE card_id=%s""",(self.card_ids[0],))
            db.execute("UPDATE owned_cards SET owner_id=%s WHERE id=%s",
                       (self.other,self.card_ids[1]))
        self.assertEqual(len(market_board.group_market(self.group)),3)
        self.assertIsNotNone(market_board.list_card(self.owner,self.group,self.card_ids[5]))
        self.assertFalse(market_board.unlist_card(self.owner,self.card_ids[1]))
        self.assertIsNotNone(market_board.list_card(self.other,self.group,self.card_ids[1]))
        with self.connect() as db:
            table=db.execute("""SELECT card_id,seller_id FROM market_listings
                               WHERE card_id=%s""",(self.card_ids[1],)).fetchone()
        self.assertEqual(table["seller_id"],self.other)

    def test_ownership_stays_constant_until_separate_consent_trade(self):
        cid=self.card_ids[0]
        market_board.list_card(self.owner,self.group,cid)
        with self.connect() as db:
            owned=db.execute("SELECT owner_id FROM owned_cards WHERE id=%s",(cid,)).fetchone()
            transfers=db.execute("SELECT count(*) AS n FROM card_transfers WHERE card_id=%s",(cid,)).fetchone()
            columns={r["column_name"] for r in db.execute(
                """SELECT column_name FROM information_schema.columns
                   WHERE table_name='market_listings' AND table_schema='public'""")}
        self.assertEqual(owned["owner_id"],self.owner)
        self.assertEqual(transfers["n"],0)
        self.assertEqual(columns,{"card_id","seller_id","chat_id","listed_at","expires_at"})

    def test_duplicate_and_missing_catalog_ignore_per_owner_copies(self):
        with self.connect() as db:
            db.execute("UPDATE characters SET enabled=true WHERE id=%s",(self.charid,))
        duplicates=collection_stats.duplicate_characters(self.owner)
        matching=[x for x in duplicates if x["character_id"]==self.charid]
        self.assertEqual(len(matching),1)
        self.assertEqual(matching[0]["copies"],6)
        no_missing=collection_stats.missing_characters(self.owner,"Test Markets")
        self.assertEqual(no_missing["missing"],0)
        self.assertEqual(no_missing["characters"],[])
        missing=collection_stats.missing_characters(88003333,"Test Markets")
        self.assertEqual(missing["missing"],1)
        self.assertEqual(missing["characters"][0]["id"],self.charid)
        self.assertIn("×6",collection_stats_ui.duplicates_text(matching))
        self.assertIn("Market Test",collection_stats_ui.missing_text(missing))

    def test_collection_queries_validate_inputs(self):
        for args in ((True,10),(0,10),(self.owner,0),(self.owner,13)):
            with self.subTest(args=args),self.assertRaises(ValueError):
                collection_stats.duplicate_characters(*args)
        for values in ((True,"Test Markets"),(self.owner,""),(self.owner,"a"*160)):
            with self.subTest(values=values),self.assertRaises(ValueError):
                collection_stats.missing_characters(*values)


if __name__=="__main__":
    unittest.main()
