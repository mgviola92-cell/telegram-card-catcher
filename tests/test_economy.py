import unittest
from app.economy import gift_card
from app.trading import create_offer

class TradeSafetyTests(unittest.TestCase):
    def test_self_gift_rejected(self):
        self.assertFalse(gift_card(123,123,'ABCD'))
    def test_self_trade_rejected(self):
        self.assertIsNone(create_offer(1,1,'A','B'))
    def test_same_code_trade_rejected(self):
        self.assertIsNone(create_offer(1,2,'A','a'))

if __name__=='__main__':
    unittest.main()
