"""Offline catalog import benchmark. NEVER connects to PostgreSQL.

Measures validation and batching overhead only, not Neon latency or real writes.
Usage: python -m scripts.benchmark_catalog_import --records 10000
"""
import argparse
import json
from time import perf_counter
from unittest.mock import MagicMock, patch
from scripts.import_characters import import_batch


def build_records(count):
    if type(count) is not int or not 0 <= count <= 100000:
        raise ValueError('records must be from 0 to 100000')
    return [
        {'source_key':f'benchmark:{i}', 'name':f'Character {i}',
         'series':f'Benchmark Series {i//100}', 'category':'anime',
         'image_url':f'https://example.org/art/{i}.jpg'}
        for i in range(count)
    ]


def benchmark(count=10000, batch_size=250):
    if type(batch_size) is not int or not 1 <= batch_size <= 1000:
        raise ValueError('batch_size must be 1..1000')
    items=build_records(count)
    connection=MagicMock()
    cursor=MagicMock()
    connection.__enter__.return_value=connection
    connection.cursor.return_value.__enter__.return_value=cursor
    start=perf_counter()
    with patch('scripts.import_characters.connect', return_value=connection):
        imported=import_batch(items,batch_size=batch_size)
    elapsed=perf_counter()-start
    sizes=[len(call.args[1]) for call in cursor.executemany.call_args_list]
    return {'mode':'offline_mock_no_database','records':imported,
            'batch_size':batch_size,'batches':len(sizes),
            'max_batch_records':max(sizes,default=0),
            'elapsed_seconds':round(elapsed,4),
            'records_per_second':round(imported/elapsed,1) if elapsed else None,
            'note':'No PostgreSQL writes or network calls; not a Neon throughput estimate.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--records',type=int,default=10000)
    parser.add_argument('--batch-size',type=int,default=250)
    args=parser.parse_args()
    print(json.dumps(benchmark(args.records,args.batch_size),indent=2))
