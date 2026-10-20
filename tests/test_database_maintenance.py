"""Conservative DB maintenance regression tests; no production/Neon access."""
import os
from pathlib import Path
from unittest.mock import patch
import unittest
import uuid

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from scripts import database_maintenance as maintenance


def disposable_url():
    url=os.environ.get("TEST_DATABASE_URL","")
    if not url:
        return None
    parts=conninfo_to_dict(url)
    if (parts.get("host") not in ("localhost","127.0.0.1","::1")
        or not parts.get("dbname","").startswith("cardkout_test")
        or url == os.environ.get("DATABASE_URL")):
        raise RuntimeError("Must use localhost disposable cardkout_test database")
    return url


class MaintenanceValidationTests(unittest.TestCase):
    def test_refuse_too_aggressive_prune(self):
        for options in (dict(keep_updates=3),dict(keep_offers=10),
                        dict(keep_updates=True),dict(keep_updates=3651),
                        dict(keep_market=0),dict(keep_market=True),
                        dict(keep_market=3651)):
            with self.subTest(options=options),self.assertRaises(ValueError):
                maintenance._ages(**options)
        for batch in (0,-1,2001,True,1.5):
            with self.subTest(batch=batch),self.assertRaises(ValueError):
                maintenance.prune_one_batch(None,batch=batch)

    def test_no_connection_without_explicit_maintenance_env(self):
        with patch.dict(os.environ,{},clear=True),patch("sys.argv",["prog"]):
            with patch("scripts.database_maintenance.psycopg.connect") as connector:
                with self.assertRaises(SystemExit):
                    maintenance.main()
                connector.assert_not_called()

    def test_apply_needs_confirmation_before_database_connection(self):
        with patch("sys.argv",["prog","--apply"]):
            with patch("scripts.database_maintenance.psycopg.connect") as connector:
                with self.assertRaises(SystemExit):
                    maintenance.main()
                connector.assert_not_called()


class MaintenancePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url=disposable_url()
        if not cls.url:
            raise unittest.SkipTest("No local disposable test database provided")
        with psycopg.connect(cls.url) as conn:
            conn.execute(Path("database/schema.sql").read_text(encoding="utf8"))

    def test_cleanup_only_older_ephemeral_rows_and_keeps_card_history(self):
        suffix=uuid.uuid4().hex[:20]
        old_update=70000000000000+int(uuid.uuid4().int % 1000000000)
        fresh_update=old_update+1
        stuck_update=old_update+2
        source="test:maintenance:"+suffix
        code="MAINT"+suffix
        cardid=None
        secondary_id=None
        character_id=None
        try:
            with psycopg.connect(self.url,row_factory=dict_row) as conn:
                character_id=conn.execute("""INSERT INTO characters
                    (name,series,source_key,image_url)
                    VALUES ('Maintenance','Local Tests',%s,'https://example.org/art.jpg')
                    RETURNING id""",(source,)).fetchone()["id"]
                cardid=conn.execute("""INSERT INTO owned_cards
                    (code,character_id,owner_id,generation)
                    VALUES (%s,%s,4001,1) RETURNING id""",
                    (code,character_id)).fetchone()["id"]
                secondary_id=conn.execute("""INSERT INTO owned_cards
                    (code,character_id,owner_id,generation)
                    VALUES (%s,%s,4002,2) RETURNING id""",
                    (code+"B",character_id)).fetchone()["id"]
                conn.execute("""INSERT INTO card_transfers
                    (card_id,from_user_id,to_user_id,reason)
                    VALUES (%s,3999,4001,'gift')""",(cardid,))
                conn.execute("""INSERT INTO processed_updates(update_id,processed_at)
                   VALUES (%s,now()-interval '45 days'),(%s,now())""",
                   (old_update,fresh_update))
                conn.execute("""INSERT INTO processed_updates(
                    update_id,processed_at,claimed_at,status,attempt_count)
                    VALUES (%s,now()-interval '50 days',
                               now()-interval '50 days','processing',1)""",
                    (stuck_update,))
                conn.execute("""INSERT INTO gift_offers
                    (sender_id,receiver_id,card_id,created_at)
                    VALUES (4001,4002,%s,now()-interval '160 days'),
                           (4001,4002,%s,now())""",(cardid,cardid))
                conn.execute("""INSERT INTO trade_offers
                    (sender_id,receiver_id,sender_card_id,receiver_card_id,created_at)
                    VALUES (4001,4002,%s,%s,now()-interval '160 days'),
                           (4001,4002,%s,%s,now())""",
                           (cardid,secondary_id,cardid,secondary_id))
                conn.execute("""INSERT INTO market_listings(
                    card_id,seller_id,chat_id,expires_at)
                    VALUES (%s,4001,-1005544,now()-interval '21 days'),
                           (%s,4002,-1005544,now()+interval '1 day')""",
                    (cardid,secondary_id))
            with psycopg.connect(self.url,row_factory=dict_row) as conn:
                before=maintenance.audit(conn)
                self.assertGreaterEqual(
                    before["ephemeral"]["processed_updates"]["eligible_old_ephemeral_rows"],1)
                self.assertGreater(before["database_bytes"],0)
                self.assertIn("owned_cards",{x["relname"] for x in before["table_sizes"]})
                self.assertEqual(before["owned_cards_deleted"],0)
                cleanup=maintenance.prune_one_batch(conn,batch=100)
                self.assertGreaterEqual(cleanup["deleted_ephemeral"]["processed_updates"],1)
                self.assertGreaterEqual(cleanup["deleted_ephemeral"]["gift_offers"],1)
                self.assertGreaterEqual(cleanup["deleted_ephemeral"]["trade_offers"],1)
                self.assertEqual(cleanup["history_ledger_deleted"],0)
                self.assertGreaterEqual(cleanup["deleted_ephemeral"]["market_listings"],1)
            with psycopg.connect(self.url,row_factory=dict_row) as conn:
                self.assertIsNone(conn.execute(
                    "SELECT 1 FROM processed_updates WHERE update_id=%s",
                    (old_update,)).fetchone())
                self.assertIsNotNone(conn.execute(
                    "SELECT 1 FROM processed_updates WHERE update_id=%s",
                    (fresh_update,)).fetchone())
                self.assertIsNotNone(conn.execute(
                    "SELECT 1 FROM processed_updates WHERE update_id=%s",
                    (stuck_update,)).fetchone())
                self.assertIsNone(conn.execute(
                    "SELECT 1 FROM market_listings WHERE card_id=%s",
                    (cardid,)).fetchone())
                self.assertIsNotNone(conn.execute(
                    "SELECT 1 FROM market_listings WHERE card_id=%s",
                    (secondary_id,)).fetchone())
                self.assertEqual(conn.execute("""SELECT count(*) AS n FROM gift_offers
                    WHERE card_id=%s""",(cardid,)).fetchone()["n"],1)
                self.assertEqual(conn.execute("""SELECT count(*) AS n FROM trade_offers
                    WHERE sender_card_id=%s""",(cardid,)).fetchone()["n"],1)
                self.assertIsNotNone(conn.execute(
                    "SELECT 1 FROM owned_cards WHERE id=%s",(cardid,)).fetchone())
                self.assertIsNotNone(conn.execute(
                    "SELECT 1 FROM card_transfers WHERE card_id=%s",(cardid,)).fetchone())
        finally:
            with psycopg.connect(self.url) as conn:
                conn.execute("DELETE FROM processed_updates WHERE update_id IN (%s,%s,%s)",
                             (old_update,fresh_update,stuck_update))
                if cardid is not None:
                    conn.execute("DELETE FROM market_listings WHERE card_id IN (%s,%s)",
                                 (cardid,secondary_id))
                if cardid is not None:
                    conn.execute("DELETE FROM trade_offers WHERE sender_card_id=%s",
                                 (cardid,))
                    conn.execute("DELETE FROM gift_offers WHERE card_id=%s",(cardid,))
                    conn.execute("DELETE FROM card_transfers WHERE card_id=%s",(cardid,))
                    conn.execute("DELETE FROM owned_cards WHERE id=%s",(cardid,))
                    if secondary_id is not None:
                        conn.execute("DELETE FROM owned_cards WHERE id=%s",(secondary_id,))
                if character_id is not None:
                    conn.execute("DELETE FROM characters WHERE id=%s",(character_id,))


if __name__=="__main__":
    unittest.main()
