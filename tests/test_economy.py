import unittest
from unittest.mock import patch
from app.economy import gift_card,trade_cards

class TradeSafetyTests(unittest.TestCase):
    def test_self_gift_rejected(self):
        self.assertFalse(gift_card(123,123,'ABCD'))
    def test_self_trade_rejected(self):
        self.assertFalse(trade_cards(1,1,'A','B'))
    def test_same_code_trade_rejected(self):
        self.assertFalse(trade_cards(1,2,'A','a'))

if __name__=='__main__': unittest.main()
