"""Telegram-native visual/UI regression tests; no bot token or external media."""
import unittest
from app import card_ui

CARD={'name':'Alice','series':"Alice's Adventures in Wonderland",
      'rarity':'Common','generation':1,'code':'40QBIWXI8P',
      'favorite':False}
OWNER=1234567890123456789


class CardUITests(unittest.TestCase):
    def test_spawn_has_obvious_action_without_revealing_character_name(self):
        caption=card_ui.spawn_caption(CARD)
        self.assertIn('WILD CHARACTER APPEARED',caption)
        self.assertIn('Guess the name',caption)
        self.assertIn('15 minutes',caption)
        self.assertNotIn('>Alice<',caption)
        self.assertIn(CARD['series'],caption)

    def test_user_and_series_strings_are_html_escaped(self):
        danger=dict(CARD,name='<Alice & friends>',series='A <script> & B')
        caption=card_ui.owned_caption(danger)
        self.assertNotIn('<script>',caption)
        self.assertIn('A &lt;script&gt; &amp; B',caption)
        self.assertIn('&lt;Alice &amp; friends&gt;',caption)
        caught=card_ui.catch_text(danger,'<Admin & player>')
        self.assertIn('&lt;Admin &amp; player&gt;',caught)

    def test_collection_has_character_open_buttons(self):
        cards=[CARD,dict(CARD,name='Bob',code='BOB1234567',generation=2)]
        text=card_ui.collection_text(cards,2,0)
        self.assertIn('MY GLOBAL COLLECTION',text)
        self.assertIn('Showing 1–2',text)
        self.assertIn('40QBIWXI8P',text)
        kb=card_ui.collection_keyboard(OWNER,cards,0,2)
        allbuttons=[b for row in kb.keyboard for b in row]
        self.assertEqual(allbuttons[0].callback_data,f'cardview:{OWNER}:40QBIWXI8P')
        self.assertEqual(allbuttons[1].callback_data,f'cardview:{OWNER}:BOB1234567')
        self.assertEqual(allbuttons[-1].callback_data,'noop')
        self.assertTrue(all(len(b.callback_data.encode())<=64 for b in allbuttons))

    def test_keyboard_close_and_favorite_callback_size(self):
        kb=card_ui.open_card_keyboard(OWNER,CARD['code'],False)
        btns=kb.keyboard[0]
        self.assertEqual(btns[0].callback_data,f'cardfav:{OWNER}:40QBIWXI8P')
        self.assertEqual(btns[1].callback_data,f'cardclose:{OWNER}:40QBIWXI8P')
        self.assertTrue(all(len(b.callback_data.encode())<=64 for b in btns))
        self.assertIn('Unfavorite',card_ui.open_card_keyboard(OWNER,CARD['code'],True).keyboard[0][0].text)

    def test_caption_displays_card_code_and_favorite(self):
        text=card_ui.owned_caption(CARD)
        self.assertIn('<code>40QBIWXI8P</code>',text)
        self.assertIn('Collected',text)
        self.assertIn('Favorite',card_ui.owned_caption(dict(CARD,favorite=True)))
        self.assertNotIn('http',text)

    def test_catch_response_has_one_photo_open_button(self):
        text=card_ui.catch_text(CARD,'Ko Ko')
        self.assertIn('CHARACTER CAUGHT',text)
        self.assertIn('Ko Ko',text)
        self.assertIn('40QBIWXI8P',text)
        kb=card_ui.catch_keyboard(OWNER,CARD['code'])
        self.assertEqual(kb.keyboard[0][0].callback_data,f'cardview:{OWNER}:40QBIWXI8P')

    def test_empty_collection_still_renderable(self):
        text=card_ui.collection_text([],0,0)
        self.assertIn('empty',text)
        kb=card_ui.collection_keyboard(OWNER,[],0,0)
        self.assertEqual(kb.keyboard[0][0].callback_data,'noop')

    def test_page_navigation(self):
        cards=[CARD]
        kb=card_ui.collection_keyboard(OWNER,cards,1,17)
        btns=[b for row in kb.keyboard for b in row]
        self.assertIn(f'harem:{OWNER}:0',[x.callback_data for x in btns])
        self.assertIn(f'harem:{OWNER}:2',[x.callback_data for x in btns])


if __name__=='__main__':
    unittest.main()
