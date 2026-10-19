"""Telegram pilot seeding never touches production Neon or real Telegram."""
import unittest
from unittest.mock import patch

from scripts.seed_telegram_pilot import seed_test_pilot
from tests.test_db_integration import safe_test_database_url


class SeedTelegramPilotTests(unittest.TestCase):
    def test_dry_run_never_connects_or_imports(self):
        with patch('scripts.seed_telegram_pilot.psycopg.connect') as connect, \
             patch('scripts.seed_telegram_pilot.import_batch') as importer:
            report=seed_test_pilot(apply=False)
        connect.assert_not_called()
        importer.assert_not_called()
        self.assertTrue(report['rights_manifest_valid'])
        self.assertEqual(report['pilot_records'],1)
        self.assertEqual(report['media_bytes_stored'],0)
        self.assertFalse(report['production_database_changed'])

    def test_apply_requires_safe_explicit_test_database(self):
        with patch('scripts.seed_telegram_pilot.safe_test_database_url',return_value=None), \
             patch('scripts.seed_telegram_pilot.psycopg.connect') as connect:
            with self.assertRaises(RuntimeError):
                seed_test_pilot(apply=True)
            connect.assert_not_called()

    def test_one_card_import_idempotent_in_disposable_postgres(self):
        if not safe_test_database_url():
            self.skipTest('Disposable TEST_DATABASE_URL unavailable')
        from scripts.seed_telegram_pilot import CATALOG
        from app.storage import connect
        import psycopg
        import json
        url=safe_test_database_url()
        card=json.loads(CATALOG.read_text(encoding='utf-8'))[0]
        try:
            first=seed_test_pilot(apply=True)
            second=seed_test_pilot(apply=True)
            self.assertEqual(first['inserted_or_updated_metadata'],1)
            self.assertEqual(second['inserted_or_updated_metadata'],1)
            with psycopg.connect(url) as db:
                cursor=db.execute('SELECT count(*) FROM characters WHERE source_key=%s',
                                  (card['source_key'],))
                self.assertEqual(cursor.fetchone()[0],1)
        finally:
            # Test DB only; do not touch any other user's card in this fixture.
            with psycopg.connect(url) as db:
                db.execute('DELETE FROM characters WHERE source_key=%s',
                           (card['source_key'],))


if __name__ == '__main__':
    unittest.main()
