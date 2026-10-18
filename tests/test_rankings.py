import unittest
from unittest.mock import MagicMock,patch
from app import economy

class RankingTests(unittest.TestCase):
    @patch('app.economy.connect')
    def test_group_uses_chat_filter(self, conn):
        db=MagicMock()
        conn.return_value.__enter__.return_value=db
        db.execute.return_value.fetchall.return_value=[]
        economy.leaderboard(chat_id=-100123,limit=10)
        sql,params=db.execute.call_args.args
        self.assertIn('caught_chat_id=%s',sql)
        self.assertEqual(params,(-100123,10))

    @patch('app.economy.connect')
    def test_today_uses_myanmar_day(self, conn):
        db=MagicMock()
        conn.return_value.__enter__.return_value=db
        db.execute.return_value.fetchall.return_value=[]
        economy.leaderboard(today=True)
        sql,_=db.execute.call_args.args
        self.assertIn("Asia/Yangon",sql)

    def test_self_gift_rejected(self):
        self.assertFalse(economy.gift_card(10,10,'EXAMPLE'))

if __name__=='__main__':
    unittest.main()
