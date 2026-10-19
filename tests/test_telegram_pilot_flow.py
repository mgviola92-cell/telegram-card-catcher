"""Pilot catalog end-to-end checks against disposable PostgreSQL; no Telegram token.

Only one public-domain media pointer is used; no image bytes are downloaded.
Real Telegram webhook/sending still requires a separately approved deployment.
"""
from contextlib import nullcontext
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

import psycopg
from psycopg.rows import dict_row

from app import storage, media_delivery
from scripts.catalog_readiness import readiness
from scripts.import_characters import validate
from tests.test_db_integration import safe_test_database_url


CATALOG = json.loads(Path('data/telegram_pilot_catalog.json').read_text(encoding='utf-8'))
APPROVALS = json.loads(Path('data/telegram_pilot_artwork_approvals.json').read_text(encoding='utf-8'))


class TelegramPilotFixtures(unittest.TestCase):
    def test_pilot_data_is_one_verified_non_anime_card(self):
        self.assertEqual(len(CATALOG), 1)
        self.assertEqual(validate(CATALOG)[0][6], APPROVALS[0]['image_url'])
        self.assertTrue(readiness(CATALOG, APPROVALS)['ready_to_import'])
        self.assertEqual(CATALOG[0]['category'], 'other')
        self.assertIn('commons.wikimedia.org', APPROVALS[0]['permission_reference'])
        self.assertTrue(CATALOG[0]['image_url'].startswith('https://upload.wikimedia.org/'))

    def test_pilot_importer_never_contains_copyrighted_mass_catalog(self):
        self.assertNotIn('acdb', CATALOG[0]['source_key'])
        self.assertEqual(APPROVALS[0]['status'], 'approved')
        self.assertNotIn('telegram_file_id', CATALOG[0])
        self.assertNotIn('image_bytes', CATALOG[0])


class TelegramPilotDatabaseFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url=safe_test_database_url()
        if not cls.url:
            raise unittest.SkipTest('Disposable TEST_DATABASE_URL not configured')
        with psycopg.connect(cls.url) as db:
            db.execute(Path('database/schema.sql').read_text(encoding='utf-8'))

    def test_spawn_catch_and_telegram_reuse_share_one_image(self):
        with psycopg.connect(self.url,row_factory=dict_row) as db:
            db.execute('BEGIN')
            # Do not modify any data outside this rollback-protected disposable DB.
            # Other catalog entries are temporarily ineligible for THIS test only.
            db.execute('UPDATE characters SET enabled=FALSE')
            char=db.execute("""INSERT INTO characters
                (source_key,name,series,aliases,category,rarity,image_url,weight)
                VALUES (%s,%s,%s,%s,%s,%s,%s,100)
                RETURNING id""",
                (CATALOG[0]['source_key'],CATALOG[0]['name'],CATALOG[0]['series'],
                 CATALOG[0]['aliases'],CATALOG[0]['category'],CATALOG[0]['rarity'],
                 CATALOG[0]['image_url'])).fetchone()['id']
            chat=-990020267
            db.execute('DELETE FROM group_settings WHERE chat_id=%s',(chat,))
            with patch('app.storage.connect',return_value=nullcontext(db)):
                spawn=storage.try_spawn(chat,1,message_id=490000)
                self.assertIsNotNone(spawn)
                self.assertEqual(spawn['id'], char)
                self.assertIsNone(storage.claim(chat,900101,'incorrect',message_id=490001))
                captured=storage.claim(chat,900101,'Alice',message_id=490002)
                self.assertIsNotNone(captured)
                self.assertEqual(captured['generation'],1)
                first=storage.get_card(captured['code'])
                self.assertEqual(first['image_url'],CATALOG[0]['image_url'])
                self.assertEqual(first['owner_id'],900101)
                bot=Mock()
                bot.send_photo.return_value=SimpleNamespace(
                    photo=[SimpleNamespace(file_id='telegram-pilot-cached-image')])
                sent=media_delivery.send_photo(bot,storage,chat,first,caption='Pilot')
                self.assertIsNotNone(sent)
                bot.send_photo.assert_called_once_with(chat,CATALOG[0]['image_url'],caption='Pilot')
                repeat=storage.get_card(captured['code'])
                self.assertEqual(repeat['telegram_file_id'],'telegram-pilot-cached-image')
                cards,total=storage.get_cards(900101)
                self.assertEqual(total,1)
                self.assertEqual(cards[0]['image_url'],CATALOG[0]['image_url'])
                self.assertEqual(cards[0]['telegram_file_id'],'telegram-pilot-cached-image')
                bot.send_photo.reset_mock()
                self.assertIsNotNone(media_delivery.send_photo(bot,storage,chat,repeat))
                bot.send_photo.assert_called_once_with(chat,'telegram-pilot-cached-image')
                self.assertEqual(db.execute('SELECT count(*) AS n FROM characters WHERE id=%s',
                                            (char,)).fetchone()['n'],1)
                cols={r['column_name'] for r in db.execute(
                    """SELECT column_name FROM information_schema.columns
                       WHERE table_schema='public' AND table_name='owned_cards'""").fetchall()}
                self.assertNotIn('image_url',cols)
                self.assertNotIn('telegram_file_id',cols)
                self.assertNotIn('image_bytes',cols)
            # The connection context will rollback only if an exception is raised,
            # so explicitly rollback all pilot rows even when the test succeeds.
            db.rollback()


if __name__=='__main__':
    unittest.main()
