"""Real PostgreSQL batch import benchmark against disposable test DB only.

Usage: TEST_DATABASE_URL=postgresql://.../cardkout_test... \
 python -m scripts.benchmark_catalog_postgres --records 1000

Writes temporary synthetic catalog rows, then removes them. NEVER use production.
"""
import argparse
import json
from time import perf_counter
from uuid import uuid4
import psycopg
from psycopg.rows import dict_row
from unittest.mock import patch
from scripts.benchmark_catalog_import import build_records
from scripts.import_characters import import_batch
from tests.test_db_integration import safe_test_database_url


def benchmark(records=1000, batch_size=250):
    if type(records) is not int or not 1 <= records <= 10000:
        raise ValueError('records must be 1..10000')
    if type(batch_size) is not int or not 1 <= batch_size <= 1000:
        raise ValueError('batch_size must be 1..1000')
    url=safe_test_database_url()
    if not url:
        raise RuntimeError('TEST_DATABASE_URL is required')
    prefix=f'benchmark:{uuid4().hex}:'
    data=build_records(records)
    for i, item in enumerate(data):
        item['source_key']=prefix+str(i)
    def test_connect():
        return psycopg.connect(url,row_factory=dict_row)
    try:
        with patch('scripts.import_characters.connect',test_connect):
            started=perf_counter()
            inserted=import_batch(data,batch_size=batch_size)
            elapsed=perf_counter()-started
        with test_connect() as db:
            actual=db.execute('SELECT count(*) AS n FROM characters WHERE source_key LIKE %s',(prefix+'%',)).fetchone()['n']
        if actual!=records:
            raise RuntimeError(f'Expected {records} rows, found {actual}')
        return {'mode':'disposable_postgres','records':inserted,'batches':(records+batch_size-1)//batch_size,
                'batch_size':batch_size,'seconds':round(elapsed,4),
                'records_per_second':round(records/elapsed,1) if elapsed else None}
    finally:
        # Cleanup is scoped to unique generated source keys, never other catalog entries.
        with test_connect() as db:
            db.execute('DELETE FROM characters WHERE source_key LIKE %s',(prefix+'%',))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--records',type=int,default=1000)
    parser.add_argument('--batch-size',type=int,default=250)
    args=parser.parse_args()
    print(json.dumps(benchmark(args.records,args.batch_size),indent=2))
