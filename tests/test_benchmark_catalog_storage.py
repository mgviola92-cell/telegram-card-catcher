"""Actual disposable Postgres fixture; never writes owner Neon data."""
import os
import unittest
from unittest.mock import patch
import psycopg
from psycopg.rows import dict_row

from scripts.benchmark_catalog_storage import measure,main
from scripts.benchmark_owned_cards import test_url


class CatalogStorageBenchmarkTests(unittest.TestCase):
    def test_reject_remote_or_actual_production_url_first(self):
        for env in ({},{"TEST_DATABASE_URL":"postgresql://a:b@db.neon.tech/cardkout_test"},
                    {"TEST_DATABASE_URL":"postgresql://a:b@127.0.0.1/live"}):
            with self.subTest(env=env),patch.dict(os.environ,env,clear=True):
                with self.assertRaises(ValueError):
                    measure(1000)

    def test_bad_counts_refused_before_connect(self):
        for rows in (0,True,999,150001,"50000"):
            with self.subTest(rows=rows),self.assertRaises(ValueError):
                measure(rows)

    def test_dry_run_does_not_connect(self):
        with patch("sys.argv",["prog"]),patch(
            "scripts.benchmark_catalog_storage.psycopg.connect") as connector:
            self.assertEqual(main(),0)
            connector.assert_not_called()

    def test_actual_local_pg_table_indexes_and_rollback(self):
        try:
            url=test_url()
        except ValueError:
            raise unittest.SkipTest("TEST_DATABASE_URL not configured on disposable localhost")
        with psycopg.connect(url,row_factory=dict_row) as db:
            before=db.execute("""SELECT count(*) AS n FROM characters
                   WHERE source_key LIKE 'bench:catalog:%'""").fetchone()["n"]
        report=measure(2500)
        self.assertEqual(report["synthetic_catalog_characters"],2500)
        self.assertGreater(report["total_delta_bytes"],0)
        self.assertGreater(report["index_delta_bytes"],0)
        self.assertGreater(report["heap_delta_bytes"],0)
        self.assertEqual(report["production_rows_written"],0)
        self.assertEqual(report["binary_image_storage_bytes"],0)
        self.assertIn("execution_ms",report["query_plans"]["exact_series"])
        self.assertIn("execution_ms",report["query_plans"]["substring_name"])
        with psycopg.connect(url,row_factory=dict_row) as db:
            after=db.execute("""SELECT count(*) AS n FROM characters
                   WHERE source_key LIKE 'bench:catalog:%'""").fetchone()["n"]
        self.assertEqual(after,before)


if __name__=="__main__":
    unittest.main()
