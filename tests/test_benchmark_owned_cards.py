"""Local-only measured ownership storage tests: never run against Neon."""
import os
from unittest.mock import patch
import unittest

import psycopg
from psycopg.rows import dict_row

from scripts.benchmark_owned_cards import measure, test_url, MIN_ROWS, MAX_ROWS, main


class OwnershipBenchmarkTests(unittest.TestCase):
    def test_refuse_remote_or_missing_test_url_before_opening_database(self):
        for data in (
            {},
            {"TEST_DATABASE_URL":"postgresql://owner:pwd@production.neon.tech/testdb"},
            {"TEST_DATABASE_URL":"postgresql://owner:pwd@127.0.0.1:5432/actual_production"},
        ):
            with self.subTest(data=data),patch.dict(os.environ,data,clear=True):
                with self.assertRaises(ValueError):
                    measure(1000)

    def test_reject_excessive_or_invalid_counts(self):
        for value in (True,0,5,999,200001,1.1,"5000"):
            with self.subTest(value=value),self.assertRaises(ValueError):
                measure(value)

    def test_default_cli_does_not_connect_or_write(self):
        with patch("sys.argv",["benchmark","--rows","10000"]):
            with patch("scripts.benchmark_owned_cards.psycopg.connect") as connector:
                self.assertEqual(main(),0)
                connector.assert_not_called()

    def test_rollback_keeps_the_catalog_and_owner_counts(self):
        try:
            url=test_url()
        except ValueError:
            raise unittest.SkipTest("No disposable local Postgres database provided")
        with psycopg.connect(url,row_factory=dict_row) as db:
            before=db.execute("""SELECT
                (SELECT count(*) FROM characters WHERE source_key LIKE 'bench:owner:%') AS chars,
                (SELECT count(*) FROM owned_cards WHERE code LIKE 'BM%') AS copies""").fetchone()
        report=measure(3000)
        self.assertEqual(report["synthetic_copies"],3000)
        self.assertGreaterEqual(report["total_delta_bytes"],0)
        self.assertGreaterEqual(report["heap_delta_bytes"],0)
        self.assertGreaterEqual(report["index_delta_bytes"],0)
        self.assertEqual(report["production_rows_written"],0)
        self.assertTrue(report["no_image_bytes"])
        with psycopg.connect(url,row_factory=dict_row) as db:
            after=db.execute("""SELECT
                (SELECT count(*) FROM characters WHERE source_key LIKE 'bench:owner:%') AS chars,
                (SELECT count(*) FROM owned_cards WHERE code LIKE 'BM%') AS copies""").fetchone()
        self.assertEqual(after,before)


if __name__=="__main__":
    unittest.main()
