"""HTTP webhook regression tests without a real Telegram or PostgreSQL connection."""
import importlib
import os
import unittest
from unittest.mock import patch

class WebhookRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.dict(os.environ,{'BOT_TOKEN':'123456:TESTTOKEN','WEBHOOK_SECRET':'test-secret'}), \
             patch('app.storage.initialize'):
            cls.main=importlib.import_module('main')

    def post(self):
        return self.main.app.test_client().post(
            '/telegram/test-secret',
            json={'update_id':123,'message':{'message_id':1,
                 'date':1,'chat':{'id':1,'type':'private'},'text':'test'}},
            headers={'X-Telegram-Bot-Api-Secret-Token':'test-secret'})

    def test_handler_failure_with_failed_release_still_retries(self):
        with patch.object(self.main,'begin_update',return_value=('acquired','token')), \
             patch.object(self.main.bot,'process_new_updates',side_effect=RuntimeError('handler')), \
             patch.object(self.main,'release_failed_update',side_effect=RuntimeError('db')), \
             patch.object(self.main,'complete_update') as complete:
            self.assertEqual(self.post().status_code,503)
            complete.assert_not_called()

    def test_completion_failure_returns_retry_without_releasing_lease(self):
        with patch.object(self.main,'begin_update',return_value=('acquired','token')), \
             patch.object(self.main.bot,'process_new_updates'), \
             patch.object(self.main,'complete_update',side_effect=RuntimeError('db')), \
             patch.object(self.main,'release_failed_update') as release:
            self.assertEqual(self.post().status_code,503)
            release.assert_not_called()

    def test_done_update_acknowledged_without_replay(self):
        with patch.object(self.main,'begin_update',return_value=('done',None)), \
             patch.object(self.main.bot,'process_new_updates') as process:
            self.assertEqual(self.post().status_code,200)
            process.assert_not_called()
