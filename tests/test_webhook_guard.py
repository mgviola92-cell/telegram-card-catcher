import unittest
from unittest.mock import patch, MagicMock
from app.webhook_guard import begin_update, release_failed_update


class DedupTests(unittest.TestCase):
    @patch('app.webhook_guard.connect')
    def test_first_delivery(self, connect):
        connection = MagicMock()
        connect.return_value.__enter__.return_value = connection
        connection.execute.return_value.fetchone.return_value = {'update_id': 123}
        self.assertTrue(begin_update(123))

    @patch('app.webhook_guard.connect')
    def test_repeat_delivery(self, connect):
        connection = MagicMock()
        connect.return_value.__enter__.return_value = connection
        connection.execute.return_value.fetchone.return_value = None
        self.assertFalse(begin_update(123))


if __name__ == '__main__':
    unittest.main()


class RetryTests(unittest.TestCase):
    @patch('app.webhook_guard.connect')
    def test_release_failed_update_removes_dedup_marker(self,connect):
        db=MagicMock()
        connect.return_value.__enter__.return_value=db
        release_failed_update(456)
        db.execute.assert_called_once_with('DELETE FROM processed_updates WHERE update_id=%s',(456,))
