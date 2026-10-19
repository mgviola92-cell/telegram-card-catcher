import unittest
from scripts.benchmark_catalog_import import benchmark, build_records

class CatalogBenchmarkTests(unittest.TestCase):
    def test_ten_thousand_records_batched_without_database(self):
        result=benchmark(10000,250)
        self.assertEqual(result['mode'],'offline_mock_no_database')
        self.assertEqual(result['records'],10000)
        self.assertEqual(result['batches'],40)
        self.assertEqual(result['max_batch_records'],250)

    def test_partial_and_empty_batch(self):
        self.assertEqual(benchmark(501,250)['batches'],3)
        self.assertEqual(benchmark(0,250)['batches'],0)

    def test_invalid_limits_rejected(self):
        with self.assertRaises(ValueError): build_records(100001)
        with self.assertRaises(ValueError): benchmark(5,0)
        with self.assertRaises(ValueError): benchmark(-1,250)
