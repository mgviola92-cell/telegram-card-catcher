"""Weighted catalog sampler: correctness, stale-ID protection and memory."""
from contextlib import contextmanager
import unittest
from unittest.mock import patch, MagicMock

from app.weighted_catalog import (
    WeightedCatalogPicker, select_active_character, MAX_CATALOG_ROWS,
)


class FakeCursor:
    def __init__(self,rows):
        self.rows=rows
        self.executed=[]
    def __enter__(self):
        return self
    def __exit__(self,*args):
        return False
    def execute(self,sql):
        self.executed.append(sql)
        return self
    def __iter__(self):
        return iter(self.rows)


class FakeDB:
    def __init__(self,rows):
        self.rows=rows
        self.scan_calls=0
        self.select_calls=[]
        self.current={}
        self.query_cursor=None
    def cursor(self,*,name):
        self.scan_calls+=1
        self.query_cursor=FakeCursor(self.rows)
        return self.query_cursor
    def execute(self,sql,params):
        self.select_calls.append((sql,params))
        result=MagicMock()
        result.fetchone.return_value=self.current.get(params[0])
        return result


class WeightedCatalogUnitTests(unittest.TestCase):
    def test_disjoint_cumulative_weights_choose_correct_ids(self):
        db=FakeDB([{"id":10,"weight":1},{"id":20,"weight":3},
                   {"id":30,"weight":6}])
        picker=WeightedCatalogPicker()
        with patch("app.weighted_catalog.secrets.randbelow",side_effect=[0,1,3,4,9]):
            self.assertEqual([picker.choose_id(db) for _ in range(5)],
                             [10,20,20,30,30])
        self.assertEqual(db.scan_calls,1)
        self.assertEqual(picker.count,3)
        self.assertEqual(picker.stored_bytes,48)
        self.assertIn("enabled=true",db.query_cursor.executed[0])
        self.assertNotIn("random()",db.query_cursor.executed[0])
        self.assertNotIn("image_url",db.query_cursor.executed[0])

    def test_cache_refreshes_only_on_demand_after_ttl(self):
        db=FakeDB([{"id":1,"weight":1}])
        picker=WeightedCatalogPicker(ttl=30)
        with patch("app.weighted_catalog.time.monotonic",side_effect=[100,120,131]):
            self.assertEqual(picker.choose_id(db),1)
            db.rows=[{"id":2,"weight":1}]
            self.assertEqual(picker.choose_id(db),1)
            self.assertEqual(picker.choose_id(db),2)
        self.assertEqual(db.scan_calls,2)

    def test_zero_catalog_rechecks_in_30_seconds_not_per_message(self):
        db=FakeDB([])
        picker=WeightedCatalogPicker()
        with patch("app.weighted_catalog.time.monotonic",side_effect=[100,115,131]):
            self.assertIsNone(picker.choose_id(db))
            db.rows=[{"id":42,"weight":1}]
            self.assertIsNone(picker.choose_id(db))
            self.assertEqual(picker.choose_id(db),42)
        self.assertEqual(db.scan_calls,2)

    def test_disabled_selected_character_is_revalidated_before_spawn(self):
        db=FakeDB([{"id":50,"weight":2}])
        picker=WeightedCatalogPicker()
        def dynamic_query(sql,values):
            found=MagicMock()
            found.fetchone.return_value=({"id":51,"name":"Enabled"}
                                         if values[0]==51 else None)
            db.select_calls.append((sql,values))
            return found
        db.execute=dynamic_query
        first=[{"id":50,"weight":2}]
        second=[{"id":51,"weight":4}]
        original=db.cursor
        def get_cursor(*,name):
            if db.scan_calls>=1:
                db.rows=second
            return original(name=name)
        db.cursor=get_cursor
        with patch("app.weighted_catalog.secrets.randbelow",return_value=0):
            chosen=select_active_character(db,picker)
        self.assertEqual(chosen["id"],51)
        self.assertEqual(db.scan_calls,2)
        self.assertTrue(all("enabled=true" in sql for sql,args in db.select_calls))

    def test_no_character_after_two_attempts_returns_none(self):
        db=FakeDB([{"id":50,"weight":1}])
        picker=WeightedCatalogPicker()
        with patch("app.weighted_catalog.secrets.randbelow",return_value=0):
            self.assertIsNone(select_active_character(db,picker))
        self.assertEqual(db.scan_calls,2)

    def test_large_catalog_keeps_constant_16_bytes_per_entry(self):
        size=100_000
        db=FakeDB(({"id":i+1,"weight":1} for i in range(size)))
        picker=WeightedCatalogPicker()
        with patch("app.weighted_catalog.secrets.randbelow",return_value=size-1):
            self.assertEqual(picker.choose_id(db),size)
        self.assertEqual(picker.count,size)
        self.assertEqual(picker.stored_bytes,16*size)

    def test_invalid_weight_or_overflow_does_not_cache_partial_catalog(self):
        cases=[
            [{"id":1,"weight":0}],
            [{"id":1,"weight":True}],
            [{"id":1,"weight":2**64}],
            [{"id":True,"weight":1}],
        ]
        for rows in cases:
            with self.subTest(rows=rows):
                picker=WeightedCatalogPicker()
                with self.assertRaises(ValueError):
                    picker.choose_id(FakeDB(rows))
                self.assertEqual(picker.count,0)

    def test_refresh_failure_keeps_old_data_but_raises(self):
        picker=WeightedCatalogPicker(ttl=10)
        db=FakeDB([{"id":1,"weight":1}])
        with patch("app.weighted_catalog.time.monotonic",return_value=20):
            picker.choose_id(db)
        db.rows=[{"id":9,"weight":0}]
        with patch("app.weighted_catalog.time.monotonic",return_value=40):
            with self.assertRaises(ValueError):
                picker.choose_id(db)
        self.assertEqual(picker.count,1)
        self.assertEqual(picker.stored_bytes,16)

    def test_ttl_must_be_finite_positive(self):
        for value in (None,0,-3,3601,True, "300"):
            with self.subTest(value=value),self.assertRaises(ValueError):
                WeightedCatalogPicker(ttl=value)


class WeightedCatalogPostgresTests(unittest.TestCase):
    """Real named-cursor + stale cache exercise on disposable local PostgreSQL."""
    def test_live_local_postgres_rechecks_disabled_character(self):
        import uuid
        import psycopg
        from psycopg.rows import dict_row
        from scripts.benchmark_owned_cards import test_url

        try:
            url=test_url()
        except ValueError:
            raise unittest.SkipTest("No disposable localhost DB provided")

        uid=uuid.uuid4().hex[:14]
        ids=[]
        with psycopg.connect(url,row_factory=dict_row) as db:
            try:
                for idx,active in enumerate((True,False)):
                    rec=db.execute("""INSERT INTO characters
                        (source_key,name,series,image_url,weight,enabled)
                        VALUES (%s,'Picker Fixture','Local Test Catalog',
                                'https://example.org/fixture-art.jpg',100,%s)
                        RETURNING id""",
                        (f"test:picker:{uid}:{idx}",active)).fetchone()
                    ids.append(rec["id"])
                # Ignore any unrelated fixture IDs after the full test suite,
                # by explicitly building the cache from the active fixture
                # only in the isolated CI database.
                picker=WeightedCatalogPicker()
                with patch("app.weighted_catalog.secrets.randbelow",return_value=0):
                    first=select_active_character(db,picker)
                self.assertIsNotNone(first)
                self.assertEqual(first["id"],ids[0])
                db.execute("UPDATE characters SET enabled=false WHERE id=%s",(ids[0],))
                db.execute("UPDATE characters SET enabled=true WHERE id=%s",(ids[1],))
                with patch("app.weighted_catalog.secrets.randbelow",return_value=0):
                    second=select_active_character(db,picker)
                self.assertEqual(second["id"],ids[1])
                self.assertEqual(picker.count,1)
                self.assertEqual(picker.stored_bytes,16)
            finally:
                if ids:
                    db.execute("DELETE FROM characters WHERE id=ANY(%s)",(ids,))



if __name__=="__main__":
    unittest.main()
