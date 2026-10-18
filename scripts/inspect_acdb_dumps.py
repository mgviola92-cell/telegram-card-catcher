"""Inspect ACDB official SQL gzip dumps before designing a bulk importer.

No database writes, image fetching, or guessed SQL column mapping.
Run with three downloaded official dumps:
python -m scripts.inspect_acdb_dumps characters.sql.gz publishers.sql.gz assignments.sql.gz
"""
import argparse
from collections import Counter
import gzip
import json
import re
from pathlib import Path

TABLE=re.compile(r'^\s*(?:INSERT\s+INTO|CREATE\s+TABLE)\s+`?([A-Za-z0-9_]+)`?',re.I)

def summarize_file(path):
    path=Path(path)
    if path.suffix!='.gz':
        raise ValueError('Expected official .sql.gz file')
    counter=Counter()
    statements=0
    create=Counter()
    bytes_read=0
    with gzip.open(path,'rt',encoding='utf-8',errors='replace') as stream:
        for line in stream:
            bytes_read+=len(line.encode('utf-8'))
            match=TABLE.match(line)
            if match:
                table=match.group(1)
                if line.lstrip().upper().startswith('CREATE'):
                    create[table]+=1
                else:
                    counter[table]+=1
                    statements+=1
    return {'file':path.name,'uncompressed_bytes':bytes_read,
            'insert_statements':statements,'inserts_by_table':dict(counter),
            'create_statements_by_table':dict(create),
            'note':'INSERT statement counts are not character counts; one statement may insert many rows.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('dumps',nargs='+')
    args=parser.parse_args()
    print(json.dumps([summarize_file(p) for p in args.dumps],indent=2))
