"""Safe ownership storage and duplicate-index experiment checks."""
import unittest
from unittest.mock import patch

from scripts.benchmark_owned_cards import measure, safe_local_test_url, SCHEMA_PATH
from tests.test_db_integration import safe_test_database_url


class OwnedCardFootprintTests(unittest.TestCase):
    def test_never_uses_production_fallback(self):
        with patch('scripts.benchmark_owned_cards.safe_test_database_url', return_value=None):
            with self.assertRaises(RuntimeError):
                safe_local_test_url()

    def test_remote_even_with_test_name_is_refused(self):
        with patch('scripts.benchmark_owned_cards.safe_test_database_url',
                   return_value='postgresql://user:pw@remote.example.org:5432/cardkout_test_remote'):
            with self.assertRaises(RuntimeError):
                safe_local_test_url()

    def test_refuses_unbounded_or_noninteger_sizes(self):
        for n in (0, -1, 99, 1_000_001, True, 10.5):
            with self.subTest(n=n), self.assertRaises(ValueError):
                measure(n)

    def test_new_schema_skips_duplicate_index(self):
        schema = SCHEMA_PATH.read_text(encoding='utf-8')
        self.assertIn('CREATE UNIQUE INDEX IF NOT EXISTS owned_cards_generation_unique', schema)
        self.assertNotIn('CREATE INDEX IF NOT EXISTS owned_cards_by_character', schema)

    def test_real_postgres_isolated_index_footprint(self):
        if not safe_test_database_url():
            self.skipTest('Disposable local PostgreSQL not configured')
        report=measure(1000)
        self.assertEqual(report['synthetic_owned_cards'], 1000)
        self.assertEqual(report['shared_character_records'],100)
        self.assertGreater(report['owned_heap_bytes'],0)
        self.assertGreater(report['owned_indexes_bytes'],0)
        self.assertGreater(report['owned_total_bytes_without_duplicate'],0)
        self.assertGreater(report['owned_bytes_per_card_amortized'],0)
        self.assertTrue(report['legacy_duplicate_index_simulated_in_test'])
        if report['legacy_duplicate_index_present']:
            self.assertGreater(report['duplicate_index_bytes_removed_in_isolated_schema'],0)
            self.assertGreater(report['owned_total_bytes_with_duplicate'],
                               report['owned_total_bytes_without_duplicate'])


if __name__ == '__main__':
    unittest.main()
