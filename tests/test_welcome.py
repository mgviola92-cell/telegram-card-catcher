import unittest

from app import welcome


class WelcomeTests(unittest.TestCase):
    def test_welcome_has_actual_group_link(self):
        kb = welcome.welcome_keyboard()
        self.assertEqual(
            kb.keyboard[0][0].url,
            "https://t.me/Card_Kout_bot?startgroup=true",
        )

    def test_menu_callbacks_are_wired(self):
        kb = welcome.welcome_keyboard()
        callbacks = {button.callback_data
                     for row in kb.keyboard for button in row if button.callback_data}
        self.assertEqual(callbacks, {"ui:harem", "ui:cmds", "ui:guide"})

    def test_command_menu_only_lists_working_commands(self):
        for command in ('/harem', '/check', '/fav', '/search', '/changetime'):
            self.assertIn(command, welcome.COMMANDS_TEXT)
        self.assertNotIn('/market —', welcome.COMMANDS_TEXT)


if __name__ == '__main__':
    unittest.main()
