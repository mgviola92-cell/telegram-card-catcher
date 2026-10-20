"""Telegram command wiring tests for new group board and collection tools.

No real Telegram calls, picture downloads, Render, or production PostgreSQL.
The dummy token is only used to build the local telebot object.
"""
import importlib
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def message(text,*,type="supergroup",chat_id=-1005550099,user=550001):
    return SimpleNamespace(
        text=text,
        from_user=SimpleNamespace(id=user,first_name="Tester",is_bot=False),
        chat=SimpleNamespace(id=chat_id,type=type),
    )


class GroupBoardCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.dict(os.environ,{
            "BOT_TOKEN":"123456:INERT_LOCAL_TEST_TOKEN",
            "WEBHOOK_SECRET":"unit_webhook_secret"
        }),patch("app.storage.initialize"):
            cls.main=importlib.import_module("main")

    def test_group_listcard_calls_owner_scoped_storage(self):
        msg=message("/listcard 34")
        with patch.object(self.main.market_board,"list_card",return_value={
            "card_id":34,"seller_id":msg.from_user.id,"chat_id":msg.chat.id
        }) as listed,patch.object(self.main.bot,"reply_to") as replied:
            self.main.market_command(msg)
        listed.assert_called_once_with(msg.from_user.id,msg.chat.id,"34")
        self.assertIn("<code>34</code>",replied.call_args.args[1])
        self.assertEqual(replied.call_args.kwargs["parse_mode"],"HTML")

    def test_group_market_displays_only_current_group_records(self):
        msg=message("/market")
        entries=[{"card_id":5,"seller_id":111,"name":"Safe & Hero",
                  "series":"Fiction","rarity":"Rare"}]
        with patch.object(self.main.market_board,"group_market",return_value=entries) as browse,\
             patch.object(self.main.bot,"reply_to") as replied:
            self.main.market_command(msg)
        browse.assert_called_once_with(msg.chat.id)
        self.assertIn("Safe &amp; Hero",replied.call_args.args[1])

    def test_private_market_cannot_query_any_database(self):
        for cmd in ("/market","/listcard 4","/unlist 4"):
            msg=message(cmd,type="private",chat_id=55)
            with self.subTest(cmd=cmd),\
                 patch.object(self.main.market_board,"group_market") as browse,\
                 patch.object(self.main.market_board,"list_card") as listing,\
                 patch.object(self.main.market_board,"unlist_card") as unlisting,\
                 patch.object(self.main.bot,"reply_to") as replied:
                self.main.market_command(msg)
                browse.assert_not_called()
                listing.assert_not_called()
                unlisting.assert_not_called()
                self.assertIn("inside a group",replied.call_args.args[1])

    def test_unlist_scoped_to_requesting_member(self):
        msg=message("/unlist ABCD12345")
        with patch.object(self.main.market_board,"unlist_card",return_value=True) as remove,\
             patch.object(self.main.bot,"reply_to") as replied:
            self.main.market_command(msg)
        remove.assert_called_once_with(msg.from_user.id,"ABCD12345")
        self.assertIn("removed",replied.call_args.args[1])

    def test_missing_and_duplicate_commands_use_calling_user_only(self):
        msg=message("/duplicates")
        with patch.object(self.main.collection_stats,"duplicate_characters",return_value=[]) as find,\
             patch.object(self.main.bot,"reply_to") as replied:
            self.main.completion_details_command(msg)
        find.assert_called_once_with(msg.from_user.id)
        self.assertIn("No characters owned more than once",replied.call_args.args[1])

        msg=message("/missing Example Saga")
        result={"series":"Example Saga","missing":1,
                "characters":[{"id":9,"name":"Missing","rarity":"Common"}]}
        with patch.object(self.main.collection_stats,"missing_characters",return_value=result) as find,\
             patch.object(self.main.bot,"reply_to") as replied:
            self.main.completion_details_command(msg)
        find.assert_called_once_with(msg.from_user.id,"Example Saga")
        self.assertIn("Missing",replied.call_args.args[1])

    def test_invalid_command_args_do_not_touch_database(self):
        for cmd in ("/listcard","/unlist","/market anything","/missing"):
            msg=message(cmd)
            with self.subTest(cmd=cmd),\
                 patch.object(self.main.market_board,"list_card") as listed,\
                 patch.object(self.main.market_board,"group_market") as browse,\
                 patch.object(self.main.collection_stats,"missing_characters") as find,\
                 patch.object(self.main.bot,"reply_to") as replied:
                if cmd=="/missing":
                    self.main.completion_details_command(msg)
                else:
                    self.main.market_command(msg)
                listed.assert_not_called()
                browse.assert_not_called()
                find.assert_not_called()
                self.assertIn("Usage:",replied.call_args.args[1])


if __name__=="__main__":
    unittest.main()
