"""Actual PostgreSQL exchange/leaderboard tests: disposable localhost DB ONLY.

Never uses production DATABASE_URL or Telegram API. Tests clean up their own
temporary rows and do not download images.
"""
import os
from pathlib import Path
from unittest.mock import patch
import unittest
import uuid
import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from app import card_exchange, catch_rankings, storage


def safe_test_url():
    text=os.environ.get("TEST_DATABASE_URL","")
    if not text:
        return None
    args=conninfo_to_dict(text)
    if (args.get("host") not in ("127.0.0.1","localhost","::1")
        or not args.get("dbname","").startswith("cardkout_test")
        or text==os.environ.get("DATABASE_URL")):
        raise RuntimeError("Refusing non-local disposable PostgreSQL")
    return text


class CardSocialDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url=safe_test_url()
        if not cls.url:
            raise unittest.SkipTest("No local disposable test database configured")
        with psycopg.connect(cls.url) as db:
            db.execute(Path("database/schema.sql").read_text(encoding="utf8"))

    def conn(self):
        return psycopg.connect(self.url,row_factory=dict_row)

    def setUp(self):
        self.patches=[patch("app.card_exchange.connect",self.conn),
                      patch("app.catch_rankings.connect",self.conn),
                      patch("app.storage.connect",self.conn)]
        for p in self.patches:p.start()
        suffix=uuid.uuid4().hex
        self.cards=[]
        self.owners=[510001,510002]
        self.chat=-100987441
        with self.conn() as db:
            for index in (0,1):
                char=db.execute(
                    """INSERT INTO characters(name,series,source_key,image_url)
                      VALUES ('Fixture Character','Test Series',%s,
                              'https://upload.wikimedia.org/no-download.jpg')
                      RETURNING id""",
                    (f"test:social:{suffix}:{index}",)).fetchone()["id"]
                if not hasattr(self,"char_ids"):
                    self.char_ids=[]
                self.char_ids.append(char)
                owned=db.execute(
                    """INSERT INTO owned_cards
                      (code,character_id,owner_id,generation,catcher_id,caught_chat_id,favorite)
                      VALUES (%s,%s,%s,1,%s,%s,true) RETURNING id""",
                    (f"T{suffix[:15]}{index}",char,self.owners[index],
                     self.owners[index],self.chat)).fetchone()["id"]
                self.cards.append(owned)

    def tearDown(self):
        try:
            with self.conn() as db:
                db.execute("DELETE FROM gift_offers WHERE card_id=ANY(%s)",(self.cards,))
                db.execute("""DELETE FROM trade_offers
                   WHERE sender_card_id=ANY(%s) OR receiver_card_id=ANY(%s)""",
                   (self.cards,self.cards))
                db.execute("DELETE FROM card_transfers WHERE card_id=ANY(%s)",(self.cards,))
                db.execute("DELETE FROM owned_cards WHERE id=ANY(%s)",(self.cards,))
                db.execute("DELETE FROM characters WHERE id=ANY(%s)",(self.char_ids,))
        finally:
            for p in reversed(self.patches):p.stop()

    def card(self,id):
        with self.conn() as db:
            return db.execute("SELECT * FROM owned_cards WHERE id=%s",(id,)).fetchone()

    def test_recipient_accepted_gift_exactly_once_and_audit(self):
        a=self.cards[0]
        offer=card_exchange.create_gift(self.owners[0],self.owners[1],str(a))
        self.assertIsNotNone(offer)
        self.assertIsNone(card_exchange.finish_offer("gift",offer["offer_id"],
                                                     self.owners[0],True))
        accepted=card_exchange.finish_offer("gift",offer["offer_id"],
                                            self.owners[1],True)
        self.assertEqual(accepted["status"],"accepted")
        self.assertEqual(accepted["card_ids"],[a])
        self.assertIsNone(card_exchange.finish_offer("gift",offer["offer_id"],
                                                     self.owners[1],True))
        self.assertEqual(self.card(a)["owner_id"],self.owners[1])
        self.assertFalse(self.card(a)["favorite"])
        with self.conn() as db:
            transfers=db.execute(
                "SELECT reason,from_user_id,to_user_id FROM card_transfers WHERE card_id=%s",
                (a,)).fetchall()
            self.assertEqual(len(transfers),1)
            self.assertEqual(transfers[0]["reason"],"gift")
            self.assertEqual(transfers[0]["from_user_id"],self.owners[0])
        # Existing short ID lookup continues to point to the same card.
        self.assertEqual(storage.get_card(str(a))["owner_id"],self.owners[1])

    def test_mutual_trade_is_atomic_and_idempotent(self):
        a,b=self.cards
        offer=card_exchange.create_trade(self.owners[0],self.owners[1],a,b)
        self.assertIsNotNone(offer)
        self.assertIsNone(card_exchange.finish_offer("trade",offer["offer_id"],
                                                     self.owners[0],True))
        self.assertEqual(card_exchange.finish_offer("trade",offer["offer_id"],
                            self.owners[1],True)["status"],"accepted")
        self.assertEqual(self.card(a)["owner_id"],self.owners[1])
        self.assertEqual(self.card(b)["owner_id"],self.owners[0])
        with self.conn() as db:
            count=db.execute("""SELECT count(*) AS n FROM card_transfers
                WHERE card_id=ANY(%s) AND reason='trade'""",(self.cards,)).fetchone()["n"]
        self.assertEqual(count,2)
        self.assertIsNone(card_exchange.finish_offer("trade",offer["offer_id"],
                                                    self.owners[1],True))

    def test_recipient_can_decline_and_expired_offer_cannot_transfer(self):
        first=card_exchange.create_gift(self.owners[0],self.owners[1],self.cards[0])
        self.assertEqual(card_exchange.finish_offer("gift",first["offer_id"],
                        self.owners[1],False)["status"],"declined")
        self.assertEqual(self.card(self.cards[0])["owner_id"],self.owners[0])
        second=card_exchange.create_gift(self.owners[0],self.owners[1],self.cards[0])
        with self.conn() as db:
            db.execute("UPDATE gift_offers SET created_at=now()-interval '11 minutes' WHERE id=%s",
                       (second["offer_id"],))
        self.assertEqual(card_exchange.finish_offer("gift",second["offer_id"],
                        self.owners[1],True)["status"],"expired")
        self.assertEqual(self.card(self.cards[0])["owner_id"],self.owners[0])

    def test_changed_card_owner_invalidates_trade_without_side_effects(self):
        a,b=self.cards
        offer=card_exchange.create_trade(self.owners[0],self.owners[1],a,b)
        with self.conn() as db:
            db.execute("UPDATE owned_cards SET owner_id=510003 WHERE id=%s",(a,))
        self.assertEqual(card_exchange.finish_offer("trade",offer["offer_id"],
                         self.owners[1],True)["status"],"invalid")
        self.assertEqual(self.card(b)["owner_id"],self.owners[1])
        with self.conn() as db:
            count=db.execute("SELECT count(*) AS n FROM card_transfers WHERE card_id=ANY(%s)",
                             (self.cards,)).fetchone()["n"]
        self.assertEqual(count,0)

    def test_original_catches_remain_in_group_and_global_rankings(self):
        a=self.cards[0]
        offer=card_exchange.create_gift(self.owners[0],self.owners[1],a)
        self.assertEqual(card_exchange.finish_offer("gift",offer["offer_id"],
                         self.owners[1],True)["status"],"accepted")
        global_top=catch_rankings.catch_leaderboard()
        group=catch_rankings.catch_leaderboard(chat_id=self.chat)
        day=catch_rankings.catch_leaderboard(today=True)
        def by_id(rows):
            return {r["user_id"]:r["catches"] for r in rows}
        self.assertGreaterEqual(by_id(global_top).get(self.owners[0],0),1)
        self.assertEqual(by_id(group)[self.owners[0]],1)
        self.assertGreaterEqual(by_id(day).get(self.owners[0],0),1)
        with self.conn() as db:
            fields={x["column_name"] for x in db.execute(
                """SELECT column_name FROM information_schema.columns
                   WHERE table_schema='public' AND table_name='owned_cards'""")}
        for prohibited in ("image_url","image_bytes","telegram_file_id","photo_blob"):
            self.assertNotIn(prohibited,fields)


if __name__=="__main__":
    unittest.main()
