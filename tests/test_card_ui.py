"""Telegram-native visual/UI regression tests; no bot token or external media."""
import unittest
from app import card_ui

CARD={'name':'Alice','series':"Alice's Adventures in Wonderland",
      'rarity':'Common','generation':1,'card_id':6103,'code':'6103',
      'favorite':False}
OWNER=1234567890123456789


class CardUITests(unittest.TestCase):
    def test_spawn_has_obvious_action_without_revealing_character_name(self):
        caption=card_ui.spawn_caption(CARD)
        self.assertIn(card_ui.SPAWN_TITLE,caption)
        self.assertIn('GUESS THE NAME',caption)
        self.assertIn('15 minutes',caption)
        self.assertNotIn('>Alice<',caption)
        self.assertNotIn(CARD['series'],caption)  # Alice's name would spoil the answer
        self.assertIn('Hidden until caught',caption)

    def test_user_and_series_strings_are_html_escaped(self):
        danger=dict(CARD,name='<Alice & friends>',series='A <script> & B')
        caption=card_ui.owned_caption(danger)
        self.assertNotIn('<script>',caption)
        self.assertIn('A &lt;script&gt; &amp; B',caption)
        self.assertIn('&lt;Alice &amp; friends&gt;',caption)
        caught=card_ui.catch_text(danger,'<Admin & player>')
        self.assertIn('&lt;Admin &amp; player&gt;',caught)

    def test_collection_has_character_open_buttons(self):
        cards=[CARD,dict(CARD,name='Bob',card_id=6104,code='6104',generation=2)]
        text=card_ui.collection_text(cards,2,0)
        self.assertIn(card_ui.HAREM_TITLE,text)
        self.assertIn('Showing 1–2',text)
        self.assertIn('6103',text)
        kb=card_ui.collection_keyboard(OWNER,cards,0,2)
        allbuttons=[b for row in kb.keyboard for b in row]
        self.assertEqual(allbuttons[0].callback_data,f'cardview:{OWNER}:6103')
        self.assertEqual(allbuttons[1].callback_data,f'cardview:{OWNER}:6104')
        self.assertEqual(allbuttons[-1].callback_data,'noop')
        self.assertTrue(all(len(b.callback_data.encode())<=64 for b in allbuttons))

    def test_series_sections_have_public_numbers_and_no_fake_catalog_totals(self):
        cards=[dict(CARD,card_id=6103,name='Alice',series='Wonderland'),
               dict(CARD,card_id=6104,name='Rabbit',series='Wonderland'),
               dict(CARD,card_id=6105,name='Hero',series='Another Show')]
        text=card_ui.collection_text(cards,3,0)
        self.assertEqual(text.count('🍀'),2)
        self.assertIn('Wonderland</b>  ·  2 shown',text)
        self.assertIn('<code>6105</code>',text)
        self.assertNotIn('(2/999)',text)

    def test_keyboard_close_and_favorite_callback_size(self):
        kb=card_ui.open_card_keyboard(OWNER,CARD['code'],False)
        btns=kb.keyboard[0]
        self.assertEqual(btns[0].callback_data,f'cardfav:{OWNER}:6103')
        self.assertEqual(btns[1].callback_data,f'cardclose:{OWNER}:6103')
        self.assertTrue(all(len(b.callback_data.encode())<=64 for b in btns))
        self.assertIn('Unfavorite',card_ui.open_card_keyboard(OWNER,CARD['code'],True).keyboard[0][0].text)

    def test_caption_displays_card_code_and_favorite(self):
        text=card_ui.owned_caption(CARD)
        self.assertIn('<code>6103</code>',text)
        self.assertIn('Collected',text)
        self.assertIn('FAVOURITE',card_ui.owned_caption(dict(CARD,favorite=True)))
        self.assertNotIn('http',text)

    def test_catch_response_has_one_photo_open_button(self):
        text=card_ui.catch_text(CARD,'Ko Ko')
        self.assertIn(card_ui.CATCH_TITLE,text)
        self.assertIn('Ko Ko',text)
        self.assertIn('6103',text)
        kb=card_ui.catch_keyboard(OWNER,CARD['code'])
        self.assertEqual(kb.keyboard[0][0].callback_data,f'cardview:{OWNER}:6103')

    def test_empty_collection_still_renderable(self):
        text=card_ui.collection_text([],0,0)
        self.assertIn('empty',text)
        kb=card_ui.collection_keyboard(OWNER,[],0,0)
        self.assertEqual(kb.keyboard[0][0].callback_data,'noop')

    def test_labels_and_values_use_html_bold_not_downloaded_fonts(self):
        for text in (card_ui.catch_text(CARD,'Tester'),
                     card_ui.owned_caption(CARD),
                     card_ui.spawn_caption(CARD)):
            self.assertIn('<b>RARITY:</b>',text)
            self.assertIn('<b>Common</b>',text)
            self.assertIn('<b>SERIES:</b>',text)
            self.assertEqual(text.count('<b>'),text.count('</b>'))
            self.assertEqual(text.count('<i>'),text.count('</i>'))
        check=card_ui.owned_caption(CARD)
        self.assertIn('<b>NAME:</b> <b>Alice</b>',check)
        self.assertIn('<b>ID:</b> <code>6103</code>',check)
        self.assertIn('<b>GEN:</b> 1',check)

    def test_spawn_does_not_reveal_eponymous_series_or_alias(self):
        alice=dict(CARD,series="Alice's Adventures in Wonderland",aliases=[])
        result=card_ui.spawn_caption(alice)
        self.assertNotIn('Alice',result)
        self.assertIn('Hidden until caught',result)
        another=dict(CARD,name='Naruto',series='Naruto Shippuden')
        self.assertNotIn('Naruto',card_ui.spawn_caption(another))
        # Normal series titles should still help the players.
        unrelated=dict(CARD,name='Zoro',series='One Piece')
        self.assertIn('One Piece',card_ui.spawn_caption(unrelated))
        alias=dict(CARD,name='Long Name',aliases=['Sailor Moon'],
                   series='Pretty Guardian Sailor Moon')
        self.assertNotIn('Pretty Guardian',card_ui.spawn_caption(alias))

    def test_escape_burmese_and_punctuation_without_styling_dynamic_names(self):
        card=dict(CARD,name='မမ <Alice> & သူငယ်ချင်း',series='မြန်မာ & Anime')
        label=card_ui.owned_caption(card)
        self.assertIn('မမ &lt;Alice&gt; &amp; သူငယ်ချင်း',label)
        self.assertIn('မြန်မာ &amp; Anime',label)
        self.assertNotIn('<Alice>',label)
        self.assertIn('🟢 <b>Uncommon</b>',
                      card_ui.rarity_label('Uncommon'))

    def test_text_is_within_telegram_limits_for_long_inputs(self):
        big=dict(CARD,name='<A>'*500,series='Long & Special'*200)
        caption=card_ui.owned_caption(big)
        self.assertLess(len(caption),1024)
        self.assertTrue(caption.count('<b>')==caption.count('</b>'))
        cards=[dict(big,card_id=n) for n in range(101,109)]
        list_text=card_ui.collection_text(cards,8,0)
        self.assertLess(len(list_text),4096)

    def test_page_navigation(self):
        cards=[CARD]
        kb=card_ui.collection_keyboard(OWNER,cards,1,17)
        btns=[b for row in kb.keyboard for b in row]
        self.assertIn(f'harem:{OWNER}:0',[x.callback_data for x in btns])
        self.assertIn(f'harem:{OWNER}:2',[x.callback_data for x in btns])


if __name__=='__main__':
    unittest.main()
