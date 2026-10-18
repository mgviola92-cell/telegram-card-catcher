"""PostgreSQL import benchmark integration checks, test database only."""
import unittest
from unittest.mock import patch
from scripts.benchmark_catalog_postgres import benchmark
from tests.test_db_integration import safe_test_database_url

class PostgresCatalogBenchmarkTests(unittest.TestCase):
    def test_refuses_missing_test_database(self):
        with patch('scripts.benchmark_catalog_postgres.safe_test_database_url',return_value=None):
            with self.assertRaises(RuntimeError):
                benchmark(1)

    def test_rejects_unbounded_requests_before_connect(self):
        for value in (0,-1,10001,True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                benchmark(value)
        with self.assertRaises(ValueError):
            benchmark(1,1001)

    def test_actual_batch_import_and_cleanup(self):
        if not safe_test_database_url():
            self.skipTest('Disposable PostgreSQL not configured')
        result=benchmark(records=51,batch_size=25)
        self.assertEqual(result['mode'],'disposable_postgres')
        self.assertEqual(result['records'],51)
        self.assertEqual(result['batches'],3)
