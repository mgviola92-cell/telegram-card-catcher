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
