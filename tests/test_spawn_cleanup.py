import unittest
from datetime import datetime,timezone
from unittest.mock import MagicMock,patch
from app.storage import clear_spawn

class SpawnCleanupTests(unittest.TestCase):
    @patch('app.storage.connect')
    def test_cleanup_requires_exact_appearance_timestamp(self, connect):
        connection=MagicMock()
        connect.return_value.__enter__.return_value=connection
        stamp=datetime(2026,10,18,tzinfo=timezone.utc)
        connection.execute.return_value.fetchone.return_value={'chat_id':-100}
        self.assertTrue(clear_spawn(-100,42,stamp))
        sql,params=connection.execute.call_args.args
        self.assertIn('last_spawn=%s',sql)
        self.assertEqual(params,(-100,42,stamp))

    @patch('app.storage.connect')
    def test_later_spawn_not_cleared(self,connect):
        connection=MagicMock()
        connect.return_value.__enter__.return_value=connection
        connection.execute.return_value.fetchone.return_value=None
        self.assertFalse(clear_spawn(-100,42,datetime.now(timezone.utc)))

    @patch('app.storage.connect')
    def test_missing_timestamp_fails_closed(self,connect):
        self.assertFalse(clear_spawn(-100,42,None))
        connect.assert_not_called()
