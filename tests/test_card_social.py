"""Exchange validation and Telegram-native command/button regressions."""
import unittest
from unittest.mock import MagicMock,patch

from app import card_exchange,card_social_ui,catch_rankings


class CardExchangeUnitTests(unittest.TestCase):
    def test_invalid_gift_or_trade_never_opens_database(self):
        with patch("app.card_exchange.connect") as connection:
            self.assertIsNone(card_exchange.create_gift(7,7,"1"))
            self.assertIsNone(card_exchange.create_gift(7,8,"0"))
            self.assertIsNone(card_exchange.create_gift(7,8,"1;DROP"))
            self.assertIsNone(card_exchange.create_trade(7,7,"1","2"))
            self.assertIsNone(card_exchange.create_trade(7,8,"","2"))
            self.assertIsNone(card_exchange.create_trade(7,8,"1","-2"))
            self.assertIsNone(card_exchange.finish_offer("gift",-5,8,True))
            self.assertIsNone(card_exchange.finish_offer("gift",1,8,"yes"))
            connection.assert_not_called()

    def test_gift_offer_created_only_when_owned_and_within_limit(self):
        db=MagicMock()
        queries=[]
        def query(sql,values):
            queries.append((sql,values))
            cur=MagicMock()
            if "count(*) AS n" in sql:
                cur.fetchone.return_value={"n":0}
            elif "FROM owned_cards" in sql:
                cur.fetchone.return_value={"id":6103,"owner_id":7,"code":"ABC"}
            elif "INSERT INTO gift_offers" in sql:
                cur.fetchone.return_value={"id":21}
            else: raise AssertionError(sql)
            return cur
        db.execute.side_effect=query
        with patch("app.card_exchange.connect") as connector:
            connector.return_value.__enter__.return_value=db
            result=card_exchange.create_gift(7,8,"6103")
        self.assertEqual(result["offer_id"],21)
        self.assertEqual(result["card_id"],6103)
        self.assertIn("id=%s",queries[1][0])
        self.assertEqual(queries[1][1],(6103,))
        self.assertIn("RETURNING id",queries[2][0])

    def test_wrong_owner_or_offer_quota_is_rejected(self):
        for count,owner in [(8,7),(0,99)]:
            db=MagicMock()
            def query(sql,vals):
                cursor=MagicMock()
                if "count(*) AS n" in sql:
                    cursor.fetchone.return_value={"n":count}
                elif "FROM owned_cards" in sql:
                    cursor.fetchone.return_value={"id":11,"owner_id":owner}
                else:raise AssertionError("Offer must not be created")
                return cursor
            db.execute.side_effect=query
            with self.subTest(count=count,owner=owner),patch("app.card_exchange.connect") as conn:
                conn.return_value.__enter__.return_value=db
                self.assertIsNone(card_exchange.create_gift(7,8,"11"))

    def test_trade_rejects_same_card_and_wrong_receiver_owner(self):
        db=MagicMock()
        rows=[{"n":0},{"id":11,"owner_id":7},
              {"id":11,"owner_id":7}]
        db.execute.side_effect=lambda sql,args: self._next(rows)
        with patch("app.card_exchange.connect") as connector:
            connector.return_value.__enter__.return_value=db
            self.assertIsNone(card_exchange.create_trade(7,8,11,11))
        self.assertEqual(db.execute.call_count,3)

    @staticmethod
    def _next(rows):
        cursor=MagicMock()
        cursor.fetchone.return_value=rows.pop(0)
        return cursor

    def test_recipient_only_declines_and_second_callback_refused(self):
        db=MagicMock()
        offer={"receiver_id":8,"sender_id":7,"status":"pending","live":True,
               "card_id":11}
        def query(sql,args):
            cursor=MagicMock()
            if "FROM gift_offers" in sql:
                cursor.fetchone.return_value=offer
            return cursor
        db.execute.side_effect=query
        with patch("app.card_exchange.connect") as conn:
            conn.return_value.__enter__.return_value=db
            self.assertIsNone(card_exchange.finish_offer("gift",5,7,False))
            self.assertEqual(card_exchange.finish_offer("gift",5,8,False),
                             {"status":"declined"})
        updates=[x for x in db.execute.call_args_list if "UPDATE gift_offers" in x.args[0]]
        self.assertEqual(len(updates),1)
        self.assertIn("status='declined'",updates[0].args[0])

    def test_invalid_card_ownership_prevents_settlement(self):
        db=MagicMock()
        offer={"receiver_id":8,"sender_id":7,"status":"pending","live":True,
               "card_id":11}
        def query(sql,args):
            cursor=MagicMock()
            if "FROM gift_offers" in sql:
                cursor.fetchone.return_value=offer
            elif "SELECT id,owner_id" in sql:
                cursor.fetchall.return_value=[{"id":11,"owner_id":99}]
            return cursor
        db.execute.side_effect=query
        with patch("app.card_exchange.connect") as conn:
            conn.return_value.__enter__.return_value=db
            self.assertEqual(card_exchange.finish_offer("gift",5,8,True),
                             {"status":"invalid"})
        self.assertFalse(any("INSERT INTO card_transfers" in x.args[0]
                             for x in db.execute.call_args_list))

    def test_offer_buttons_within_telegram_64_byte_limit(self):
        for kind in ("gift","trade"):
            kb=card_social_ui.exchange_keyboard(kind,987654321234567890)
            actions=[btn.callback_data for row in kb.keyboard for btn in row]
            self.assertEqual(len(actions),2)
            self.assertTrue(all(len(x.encode("utf8"))<64 for x in actions))

    def test_html_escape_and_numeric_refs_are_copyable(self):
        caption=card_social_ui.offer_caption("trade","<Sender>","X & Y",
                                             [6103,6104])
        self.assertIn("&lt;Sender&gt;",caption)
        self.assertIn("X &amp; Y",caption)
        self.assertIn("<code>6103</code>",caption)
        self.assertIn("<code>6104</code>",caption)
        self.assertNotIn("<Sender>",caption)

    def test_leaderboard_templates_and_empty_results(self):
        result=card_social_ui.leaderboard_caption(
            [{"user_id":10002,"catches":7},{"user_id":10003,"catches":3}],
            "group")
        self.assertIn("𝗚𝗥𝗢𝗨𝗣",result)
        self.assertIn("tg://user?id=10002",result)
        self.assertIn("<b>7</b>",result)
        self.assertIn("Older catches",result)
        self.assertIn("No catches",card_social_ui.leaderboard_caption([]))

    def test_rankings_parameters_use_group_and_myanmar_today(self):
        db=MagicMock()
        db.execute.return_value.fetchall.return_value=[]
        with patch("app.catch_rankings.connect") as connect:
            connect.return_value.__enter__.return_value=db
            catch_rankings.catch_leaderboard(chat_id=-10099,today=True,limit=10)
        sql,args=db.execute.call_args.args
        self.assertIn("caught_chat_id=%s",sql)
        self.assertIn("Asia/Yangon",sql)
        self.assertEqual(args,(-10099,10))
        for opts in (dict(limit=0),dict(limit=True),dict(today="yes"),dict(chat_id="x")):
            with self.assertRaises(ValueError):
                catch_rankings.catch_leaderboard(**opts)


if __name__=="__main__":
    unittest.main()
