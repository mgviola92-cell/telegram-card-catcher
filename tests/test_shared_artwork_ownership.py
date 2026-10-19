"""Prove per-user caught cards reuse shared artwork, not per-card image storage.

The optional integration test uses only a disposable PostgreSQL named
cardkout_test*, with test transaction rollback; no Telegram or Neon calls.
"""
import unittest
from unittest.mock import patch
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app import storage
from tests.test_db_integration import safe_test_database_url


class SharedOwnershipArtworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = safe_test_database_url()
        if not cls.url:
            raise unittest.SkipTest('Disposable TEST_DATABASE_URL not configured')
        cls.db = psycopg.connect(cls.url, row_factory=dict_row)
        cls.db.execute(Path('database/schema.sql').read_text(encoding='utf-8'))
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'db'):
            cls.db.close()

    def setUp(self):
        self.db.execute('BEGIN')
        self.connector = patch('app.storage.connect', return_value=self.db)
        self.connector.start()

    def tearDown(self):
        self.connector.stop()
        self.db.rollback()

    def test_many_ownerships_share_one_artwork_url_and_file_id(self):
        columns = {r['column_name'] for r in self.db.execute(
            """SELECT column_name FROM information_schema.columns
               WHERE table_schema='public' AND table_name='owned_cards'""").fetchall()}
        self.assertNotIn('image_url', columns)
        self.assertNotIn('telegram_file_id', columns)
        self.assertFalse({'image_bytes', 'image_blob', 'photo_data'} & columns)

        character = self.db.execute(
            """INSERT INTO characters(name,series,source_key,image_url,telegram_file_id)
               VALUES ('Artwork QA','Test Anime',
                       'qa:shared-artwork-identity',
                       'https://example.org/shared-image.png','telegram-shared-base')
               RETURNING id""").fetchone()['id']
        variant = self.db.execute(
            """INSERT INTO character_variants
                (character_id,variant_key,label,image_url,telegram_file_id)
               VALUES (%s,'alt','Alternate','https://example.org/shared-alt.png',
                       'telegram-shared-alt') RETURNING id""",
            (character,)).fetchone()['id']
        self.db.execute(
            """INSERT INTO owned_cards (code,character_id,variant_id,owner_id,generation)
               VALUES ('QAOWNEDA1',%s,NULL,12000001,1),
                      ('QAOWNEDB2',%s,NULL,12000002,2),
                      ('QAOWNEDC3',%s,%s,12000001,3)""",
            (character, character, character, variant))
        first=storage.get_card('QAOWNEDA1')
        second=storage.get_card('QAOWNEDB2')
        alt=storage.get_card('QAOWNEDC3')
        self.assertEqual(first['image_url'],'https://example.org/shared-image.png')
        self.assertEqual(second['image_url'],first['image_url'])
        self.assertEqual(first['telegram_file_id'],'telegram-shared-base')
        self.assertEqual(second['telegram_file_id'],first['telegram_file_id'])
        self.assertNotEqual(first['owner_id'], second['owner_id'])
        self.assertEqual(alt['image_url'],'https://example.org/shared-alt.png')
        self.assertEqual(alt['telegram_file_id'],'telegram-shared-alt')
        self.assertNotEqual(alt['image_url'],first['image_url'])
        cards,total=storage.get_cards(12000001)
        self.assertEqual(total,2)
        self.assertEqual({x['image_url'] for x in cards},
                         {'https://example.org/shared-image.png',
                          'https://example.org/shared-alt.png'})
        count=self.db.execute(
            'SELECT count(*) AS n FROM characters WHERE id=%s',
            (character,)).fetchone()['n']
        self.assertEqual(count,1)


if __name__=='__main__':
    unittest.main()
