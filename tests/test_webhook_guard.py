"""Durable Telegram update processing tests; no remote Telegram or Neon."""
import unittest
from unittest.mock import patch, MagicMock
import os
import uuid
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from app.webhook_guard import (
    valid_update_id, claim_update, mark_completed, mark_failed
)


class WebhookInboxUnitTests(unittest.TestCase):
    def test_reject_bad_update_ids_before_database(self):
        for item in (None,True,False,-1,1.5,"123",2**63):
            with self.subTest(item=item),patch("app.webhook_guard.connect") as db:
                self.assertFalse(valid_update_id(item))
                with self.assertRaises(ValueError):
                    claim_update(item)
                db.assert_not_called()

    def test_first_claim_returns_fencing_token(self):
        db=MagicMock()
        db.execute.return_value.fetchone.return_value={"attempt_count":1}
        with patch("app.webhook_guard.connect") as c:
            c.return_value.__enter__.return_value=db
            self.assertEqual(claim_update(123),("claimed",1))
        sql,_=db.execute.call_args.args
        self.assertIn("ON CONFLICT",sql)
        self.assertIn("claimed_at < now()-interval '180 seconds'",sql)
        self.assertIn("attempt_count=processed_updates.attempt_count+1",sql)

    def test_completed_repeat_is_acknowledged_without_reprocessing(self):
        db=MagicMock()
        first=MagicMock()
        first.fetchone.return_value=None
        last=MagicMock()
        last.fetchone.return_value={"status":"done"}
        db.execute.side_effect=[first,last]
        with patch("app.webhook_guard.connect") as c:
            c.return_value.__enter__.return_value=db
            self.assertEqual(claim_update(123),("done",None))

    def test_inflight_not_silently_acknowledged(self):
        db=MagicMock()
        first=MagicMock()
        first.fetchone.return_value=None
        last=MagicMock()
        last.fetchone.return_value={"status":"processing"}
        db.execute.side_effect=[first,last]
        with patch("app.webhook_guard.connect") as c:
            c.return_value.__enter__.return_value=db
            self.assertEqual(claim_update(123),("busy",None))

    def test_only_claiming_attempt_can_mark_finished_or_failed(self):
        db=MagicMock()
        db.execute.return_value.fetchone.return_value={"update_id":123}
        with patch("app.webhook_guard.connect") as conn:
            conn.return_value.__enter__.return_value=db
            self.assertTrue(mark_completed(123,1))
            sql,params=db.execute.call_args.args
            self.assertIn("status='done'",sql)
            self.assertIn("attempt_count=%s",sql)
            self.assertEqual(params,(123,1))
            self.assertTrue(mark_failed(123,2))
            sql,params=db.execute.call_args.args
            self.assertIn("status='failed'",sql)
            self.assertEqual(params,(123,2))

    def test_invalid_fencing_tokens_no_database(self):
        for token in (0,-1,1.2,True,"1"):
            with self.subTest(token=token),patch("app.webhook_guard.connect") as conn:
                with self.assertRaises(ValueError):
                    mark_completed(123,token)
                with self.assertRaises(ValueError):
                    mark_failed(123,token)
                conn.assert_not_called()


def safe_test_url():
    url=os.environ.get("TEST_DATABASE_URL")
    if not url:
        return None
    cfg=conninfo_to_dict(url)
    if (cfg.get("host") not in ("localhost","127.0.0.1","::1") or
        not cfg.get("dbname","").startswith("cardkout_test") or
        url==os.environ.get("DATABASE_URL")):
        raise RuntimeError("Refuse non-disposable webhook inbox test DB")
    return url


class WebhookInboxPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url=safe_test_url()
        if not cls.url:
            raise unittest.SkipTest("Disposable localhost DB unavailable")
        with psycopg.connect(cls.url) as db:
            db.execute(Path("database/schema.sql").read_text(encoding="utf8"))

    def connection(self):
        return psycopg.connect(self.url,row_factory=dict_row)

    def setUp(self):
        self.ids=[int(uuid.uuid4().int % 1_000_000_000)+8_000_000_000_000_000]
        self.connpatch=patch("app.webhook_guard.connect",self.connection)
        self.connpatch.start()

    def tearDown(self):
        try:
            with self.connection() as db:
                db.execute("DELETE FROM processed_updates WHERE update_id=ANY(%s)",(self.ids,))
        finally:
            self.connpatch.stop()

    def test_claim_fail_reclaim_complete_and_repeat(self):
        update_id=self.ids[0]
        self.assertEqual(claim_update(update_id),("claimed",1))
        self.assertEqual(claim_update(update_id),("busy",None))
        self.assertTrue(mark_failed(update_id,1))
        self.assertEqual(claim_update(update_id),("claimed",2))
        self.assertFalse(mark_completed(update_id,1))
        self.assertFalse(mark_failed(update_id,1))
        self.assertTrue(mark_completed(update_id,2))
        self.assertEqual(claim_update(update_id),("done",None))
        self.assertFalse(mark_completed(update_id,2))
        with self.connection() as db:
            state=db.execute("SELECT status,attempt_count FROM processed_updates WHERE update_id=%s",
                             (update_id,)).fetchone()
        self.assertEqual((state["status"],state["attempt_count"]),("done",2))

    def test_legacy_processed_update_is_never_replayed(self):
        update_id=self.ids[0]
        with self.connection() as db:
            db.execute("INSERT INTO processed_updates(update_id) VALUES (%s)",(update_id,))
        self.assertEqual(claim_update(update_id),("done",None))
        with self.connection() as db:
            row=db.execute("SELECT status,attempt_count FROM processed_updates WHERE update_id=%s",
                           (update_id,)).fetchone()
        self.assertEqual(row["status"],"done")
        self.assertEqual(row["attempt_count"],0)

    def test_orphan_claim_can_be_recovered_after_lease_expiry(self):
        update_id=self.ids[0]
        self.assertEqual(claim_update(update_id),("claimed",1))
        with self.connection() as db:
            db.execute("""UPDATE processed_updates SET claimed_at=now()-interval '4 minutes'
                          WHERE update_id=%s""",(update_id,))
        self.assertEqual(claim_update(update_id),("claimed",2))
        self.assertFalse(mark_completed(update_id,1))
        self.assertTrue(mark_completed(update_id,2))


if __name__=="__main__":
    unittest.main()
