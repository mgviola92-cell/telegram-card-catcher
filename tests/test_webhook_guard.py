import unittest
from unittest.mock import patch, MagicMock
from app.webhook_guard import begin_update


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
