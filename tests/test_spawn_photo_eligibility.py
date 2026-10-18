"""Guard against selecting cards that cannot be shown as Telegram photos."""
import unittest
from unittest.mock import MagicMock,patch
from app.storage import try_spawn


class SpawnPhotoEligibilityTests(unittest.TestCase):
    @patch('app.storage.connect')
    def test_spawn_selection_requires_usable_photo_source(self,connect):
        db=MagicMock()
        cur=MagicMock()
        connect.return_value.__enter__.return_value=db
        db.cursor.return_value.__enter__.return_value=cur
        setting={'active_character_id':None,'message_count':0,'spawn_every':1}
        def execute(sql,params=None):
            if 'SELECT * FROM group_settings' in sql:
                cur.fetchone.return_value=setting
            elif 'INSERT INTO counted_messages' in sql:
                cur.fetchone.return_value={'message_id':10}
            elif 'SELECT * FROM characters' in sql:
                cur.fetchone.return_value=None
            return cur
        cur.execute.side_effect=execute
        self.assertIsNone(try_spawn(-100,1,10))
        queries=[call.args[0] for call in cur.execute.call_args_list]
        candidate=next(q for q in queries if 'SELECT * FROM characters' in q)
        self.assertIn("image_url LIKE 'https://%'",candidate)
        self.assertIn("NULLIF(btrim(telegram_file_id),'')",candidate)
