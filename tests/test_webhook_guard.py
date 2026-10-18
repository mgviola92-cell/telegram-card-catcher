import unittest
from unittest.mock import patch, MagicMock
from app.webhook_guard import begin_update, complete_update, release_failed_update

class WebhookLeaseTests(unittest.TestCase):
    @patch('app.webhook_guard.connect')
    def test_new_update_acquired(self,connect):
        db=MagicMock()
        connect.return_value.__enter__.return_value=db
        db.execute.return_value.fetchone.return_value={'update_id':123}
        self.assertEqual(begin_update(123),'acquired')

    @patch('app.webhook_guard.connect')
    def test_duplicate_in_flight_retried(self,connect):
        db=MagicMock()
        connect.return_value.__enter__.return_value=db
        db.execute.return_value.fetchone.side_effect=[None,{'status':'processing'}]
        self.assertEqual(begin_update(123),'processing')

    @patch('app.webhook_guard.connect')
    def test_completed_duplicate_acknowledged(self,connect):
        db=MagicMock()
        connect.return_value.__enter__.return_value=db
        db.execute.return_value.fetchone.side_effect=[None,{'status':'done'}]
        self.assertEqual(begin_update(123),'done')

    @patch('app.webhook_guard.connect')
    def test_complete_marks_done(self,connect):
        db=MagicMock()
        connect.return_value.__enter__.return_value=db
        complete_update(123)
        self.assertIn("status='done'",db.execute.call_args.args[0])

    @patch('app.webhook_guard.connect')
    def test_release_only_processing(self,connect):
        db=MagicMock()
        connect.return_value.__enter__.return_value=db
        release_failed_update(456)
        self.assertIn("status='processing'",db.execute.call_args.args[0])
