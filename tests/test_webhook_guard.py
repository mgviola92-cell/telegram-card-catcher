import unittest
from unittest.mock import patch, MagicMock
from app.webhook_guard import begin_update, complete_update, release_failed_update

class WebhookLeaseTests(unittest.TestCase):
    @patch('app.webhook_guard.connect')
    def test_new_update_acquired(self,connect):
        db=MagicMock()
        connect.return_value.__enter__.return_value=db
        db.execute.return_value.fetchone.return_value={'update_id':123}
        state,token=begin_update(123)
        self.assertEqual(state,'acquired')
        self.assertEqual(len(token),32)

    @patch('app.webhook_guard.connect')
    def test_duplicate_in_flight_retried(self,connect):
        db=MagicMock()
        connect.return_value.__enter__.return_value=db
        db.execute.return_value.fetchone.side_effect=[None,{'status':'processing'}]
        self.assertEqual(begin_update(123),('processing',None))

    @patch('app.webhook_guard.connect')
    def test_completed_duplicate_acknowledged(self,connect):
        db=MagicMock()
        connect.return_value.__enter__.return_value=db
        db.execute.return_value.fetchone.side_effect=[None,{'status':'done'}]
        self.assertEqual(begin_update(123),('done',None))

    @patch('app.webhook_guard.connect')
    def test_complete_requires_matching_lease_token(self,connect):
        db=MagicMock()
        connect.return_value.__enter__.return_value=db
        db.execute.return_value.fetchone.return_value={'update_id':123}
        self.assertTrue(complete_update(123,'owned-token'))
        self.assertIn('lease_token=%s',db.execute.call_args.args[0])
        self.assertEqual(db.execute.call_args.args[1],(123,'owned-token'))

    @patch('app.webhook_guard.connect')
    def test_expired_owner_cannot_complete(self,connect):
        db=MagicMock()
        connect.return_value.__enter__.return_value=db
        db.execute.return_value.fetchone.return_value=None
        self.assertFalse(complete_update(123,'old-token'))

    @patch('app.webhook_guard.connect')
    def test_release_requires_matching_lease_token(self,connect):
        db=MagicMock()
        connect.return_value.__enter__.return_value=db
        release_failed_update(456,'old-token')
        self.assertIn('lease_token=%s',db.execute.call_args.args[0])
        self.assertEqual(db.execute.call_args.args[1],(456,'old-token'))
