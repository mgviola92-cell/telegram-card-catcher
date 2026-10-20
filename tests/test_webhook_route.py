"""Flask Telegram webhook ACKs ONLY after successful update completion.

The bot token here is a dummy format accepted for local object creation.
No Telegram API, Neon, Render or image URL is accessed in this suite.
"""
import importlib
import os
import sys
import unittest
from unittest.mock import patch


class WebhookRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # main imports storage.initialize(), which must NEVER reach Neon in CI.
        with patch.dict(os.environ,{
            "BOT_TOKEN":"123456:TEST_TOKEN_PLACEHOLDER_LOCAL_ONLY",
            "WEBHOOK_SECRET":"unit_webhook_secret"
        }),patch("app.storage.initialize"):
            cls.main=importlib.import_module("main")
        cls.secret=cls.main.SECRET

    def setUp(self):
        self.client=self.main.app.test_client()
        self.url=f"/telegram/{self.secret}"
        self.header={"X-Telegram-Bot-Api-Secret-Token":self.secret}
        self.data={"update_id":450}

    def test_bad_secret_cannot_touch_db_or_process(self):
        with patch.object(self.main,"claim_update") as claim:
            res=self.client.post(self.url,json=self.data)
            self.assertEqual(res.status_code,403)
            res=self.client.post("/telegram/bad",json=self.data,headers=self.header)
            self.assertEqual(res.status_code,403)
            claim.assert_not_called()

    def test_malformed_payload_and_boolean_id_are_not_claimed(self):
        with patch.object(self.main,"claim_update") as claim:
            for data in (None,{},{"update_id":True},{"update_id":-1},
                         {"update_id":"450"},{"update_id":2**63}):
                with self.subTest(data=data):
                    response=self.client.post(self.url,json=data,headers=self.header)
                    self.assertEqual(response.status_code,400)
            claim.assert_not_called()

    def test_completed_repeat_returns_ok_without_handler(self):
        with patch.object(self.main.types.Update,"de_json",return_value=object()),\
             patch.object(self.main,"claim_update",return_value=("done",None)),\
             patch.object(self.main.bot,"process_new_updates") as process:
            result=self.client.post(self.url,json=self.data,headers=self.header)
            self.assertEqual(result.status_code,200)
            process.assert_not_called()

    def test_active_other_worker_returns_retry_not_false_ack(self):
        with patch.object(self.main.types.Update,"de_json",return_value=object()),\
             patch.object(self.main,"claim_update",return_value=("busy",None)),\
             patch.object(self.main.bot,"process_new_updates") as process:
            result=self.client.post(self.url,json=self.data,headers=self.header)
            self.assertEqual(result.status_code,503)
            self.assertEqual(result.headers.get("Retry-After"),"2")
            process.assert_not_called()

    def test_success_marked_done_before_200(self):
        with patch.object(self.main.types.Update,"de_json",return_value=object()),\
             patch.object(self.main,"claim_update",return_value=("claimed",3)),\
             patch.object(self.main,"mark_completed",return_value=True) as complete,\
             patch.object(self.main,"mark_failed") as fail,\
             patch.object(self.main.bot,"process_new_updates") as process:
            result=self.client.post(self.url,json=self.data,headers=self.header)
            self.assertEqual(result.status_code,200)
            process.assert_called_once()
            complete.assert_called_once_with(450,3)
            fail.assert_not_called()

    def test_handler_exception_marks_failed_and_requests_retry(self):
        with patch.object(self.main.types.Update,"de_json",return_value=object()),\
             patch.object(self.main,"claim_update",return_value=("claimed",2)),\
             patch.object(self.main,"mark_completed") as complete,\
             patch.object(self.main,"mark_failed",return_value=True) as failed,\
             patch.object(self.main.bot,"process_new_updates",side_effect=RuntimeError("test-failure")):
            response=self.client.post(self.url,json=self.data,headers=self.header)
            self.assertEqual(response.status_code,503)
            complete.assert_not_called()
            failed.assert_called_once_with(450,2)

    def test_lost_fencing_token_is_not_acked(self):
        with patch.object(self.main.types.Update,"de_json",return_value=object()),\
             patch.object(self.main,"claim_update",return_value=("claimed",2)),\
             patch.object(self.main,"mark_completed",return_value=False),\
             patch.object(self.main.bot,"process_new_updates"):
            response=self.client.post(self.url,json=self.data,headers=self.header)
            self.assertEqual(response.status_code,503)

    def test_none_telegram_update_parse_is_rejected_without_claim(self):
        with patch.object(self.main.types.Update,"de_json",return_value=None),\
             patch.object(self.main,"claim_update") as claim:
            response=self.client.post(self.url,json=self.data,headers=self.header)
            self.assertEqual(response.status_code,400)
            claim.assert_not_called()

    def test_completion_database_error_never_sends_success_ack(self):
        with patch.object(self.main.types.Update,"de_json",return_value=object()),\
             patch.object(self.main,"claim_update",return_value=("claimed",3)),\
             patch.object(self.main,"mark_completed",side_effect=RuntimeError("db offline")),\
             patch.object(self.main.bot,"process_new_updates") as process:
            response=self.client.post(self.url,json=self.data,headers=self.header)
            self.assertEqual(response.status_code,503)
            process.assert_called_once()

    def test_bad_telegram_update_parse_never_claimed(self):
        with patch.object(self.main.types.Update,"de_json",side_effect=ValueError("bad JSON")),\
             patch.object(self.main,"claim_update") as claim:
            result=self.client.post(self.url,json=self.data,headers=self.header)
            self.assertEqual(result.status_code,400)
            claim.assert_not_called()


if __name__=="__main__":
    unittest.main()
