import unittest
from app.collection_ui import page_markup, card_markup, card_caption
class CardBrowserTests(unittest.TestCase):
 def card(self):
  return {'code':'ABC123','name':'Sample Hero','series':'Demo','rarity':'Rare','generation':2,'favorite':False}
 def test_callbacks_include_owner(self):
  kb=page_markup(88,[self.card()],0,1)
  self.assertEqual(kb.keyboard[0][0].callback_data,'card:88:ABC123:0')
 def test_card_buttons(self):
  kb=card_markup(88,'ABC123',0,False)
  self.assertIn('cardfav:88:ABC123:0',str(kb.to_dict()))
 def test_caption(self):
  self.assertIn('ABC123',card_caption(self.card()))
