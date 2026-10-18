import unittest
from app.collection_ui import PAGE_SIZE,normalized_page,page_markup,card_markup

class CollectionNavigationTests(unittest.TestCase):
    def test_requested_page_clamped_after_gift(self):
        self.assertEqual(normalized_page(3,2),0)
        self.assertEqual(normalized_page(2,7),1)
        self.assertEqual(normalized_page(-8,20),0)
        self.assertEqual(normalized_page(99,0),0)

    def test_navigation_buttons_respect_page_count(self):
        cards=[dict(code='ABC123',name='Example',favorite=False)]
        buttons=page_markup(101,cards,0,PAGE_SIZE+1).keyboard
        callbacks=[button.callback_data for row in buttons for button in row]
        self.assertIn('harem:101:1',callbacks)
        self.assertNotIn('harem:101:-1',callbacks)
        self.assertIn('card:101:ABC123:0',callbacks)

    def test_card_back_returns_to_same_page(self):
        callbacks=[button.callback_data for row in card_markup(101,'ABC123',2,False).keyboard for button in row]
        self.assertIn('cardback:101:2',callbacks)
