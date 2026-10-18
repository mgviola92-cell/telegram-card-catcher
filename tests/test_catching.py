import unittest
from types import SimpleNamespace
from app.catching import catch_name,catch_result

class CatchingTests(unittest.TestCase):
    def test_slash_command(self):
        self.assertEqual(catch_name('/catch Mayuri Kurotsuchi'), 'Mayuri Kurotsuchi')
        self.assertEqual(catch_name('/catch@Card_Kout_bot   Mayuri  '),'Mayuri')
    def test_plain_chat_and_other_commands(self):
        self.assertEqual(catch_name('Mayuri'), 'Mayuri')
        self.assertEqual(catch_name('/harem'), '')
        self.assertEqual(catch_name('/catch'), '')
    def test_result_has_card_identity(self):
        card=dict(name='Sample Hero',series='Demo Series',rarity='Rare',generation=2,code='ABC123')
        result=catch_result(card,SimpleNamespace(first_name='Tester'))
        for fragment in ['Tester','Sample Hero','Demo Series','Rare','Gen 2','ABC123','/harem']:
            self.assertIn(fragment,result)

    def test_result_shows_collection_total_when_present(self):
        card=dict(name='Demo',series='Series',rarity='Rare',generation=1,code='ABC',collection_total=17)
        result=catch_result(card,SimpleNamespace(first_name='Tester'))
        self.assertIn('Your collection: 17 cards',result)

    def test_result_without_total_remains_compatible(self):
        card=dict(name='Demo',series='Series',rarity='Rare',generation=1,code='ABC')
        result=catch_result(card,SimpleNamespace(first_name='Tester'))
        self.assertNotIn('Your collection:',result)

    def test_variant_artwork_name_is_shown(self):
        card=dict(name='Demo',series='Series',rarity='Rare',generation=1,
                  code='ABC',variant_label='Festival Edition')
        self.assertIn('Artwork: Festival Edition',
                      catch_result(card,SimpleNamespace(first_name='Tester')))

    def test_original_artwork_does_not_add_extra_line(self):
        card=dict(name='Demo',series='Series',rarity='Rare',generation=1,
                  code='ABC',variant_label='Original')
        self.assertNotIn('Artwork:',catch_result(card,SimpleNamespace(first_name='Tester')))
