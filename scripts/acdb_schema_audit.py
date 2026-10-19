"""Read-only ACDB SQL gzip schema/volume audit. Never imports rows or artworks.

Input dumps are provided by ACDB as database metadata; characters may reference
restricted series. This tool emits schema identifiers and aggregate SQL counts
only, never names, images, or raw records. Counts are *not* distinct characters.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re

STATEMENT = re.compile(r"^\s*(INSERT\s+INTO|CREATE\s+TABLE)(?:\s+IF\s+NOT\s+EXISTS)?\s+`?([A-Za-z0-9_]+)`?", re.I)
COLUMN = re.compile(r"^\s*`([A-Za-z_][A-Za-z0-9_]*)`\s+", re.I)
MAX_FRAGMENT = 65536
MAX_BYTES = 1_000_000_000


def inspect_file(path, max_uncompressed_bytes=MAX_BYTES):
    """Stream one local gzip; bounded line fragments prevent multi-MB SQL rows in RAM."""
    source = Path(path)
    if source.suffix != '.gz':
        raise ValueError('Expected .sql.gz source')
    if type(max_uncompressed_bytes) is not int or max_uncompressed_bytes < 1:
        raise ValueError('Positive decompression size limit required')
    tables_created = Counter()
    inserts = Counter()
    columns = {}
    bytes_out = 0
    long_lines = 0
    current_ddl = None
    is_continuation = False
    with gzip.open(source, 'rb') as stream:
        while True:
            frag = stream.readline(MAX_FRAGMENT)
            if not frag:
                break
            bytes_out += len(frag)
            if bytes_out > max_uncompressed_bytes:
                raise ValueError('Decompressed SQL exceeds safety limit')
            line_done = frag.endswith(b'\n')
            if is_continuation:
                if line_done:
                    is_continuation = False
                continue
            if not line_done and len(frag) == MAX_FRAGMENT:
                long_lines += 1
                is_continuation = True
            line = frag.decode('utf-8', 'replace')
            match = STATEMENT.match(line)
            if match:
                action, table = match.group(1).upper(), match.group(2)
                if action.startswith('CREATE'):
                    tables_created[table] += 1
                    current_ddl = table
                    columns.setdefault(table, [])
                elif action.startswith('INSERT'):
                    inserts[table] += 1
            elif current_ddl:
                col = COLUMN.match(line)
                if col and col.group(1) not in columns[current_ddl]:
                    columns[current_ddl].append(col.group(1))
            if current_ddl and re.match(r'^\s*\)\s*[^\n]*;', line):
                current_ddl = None
    with open(source, 'rb') as raw:
        sha = hashlib.file_digest(raw, 'sha256').hexdigest()
    return {
        'file': source.name,
        'compressed_bytes': source.stat().st_size,
        'compressed_sha256': sha,
        'uncompressed_bytes': bytes_out,
        'create_statements_by_table': dict(sorted(tables_created.items())),
        'columns_by_table': dict(sorted(columns.items())),
        'insert_statements_by_table': dict(sorted(inserts.items())),
        'overlong_sql_lines_skipped': long_lines,
        'character_rows_measured': False,
        'rights_approved_artworks': 0,
        'notice': 'Metadata SQL inspection only. INSERT count is not row count. Age/content filters and image rights are NOT approved.',
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('dumps', nargs='+')
    p.add_argument('--output', help='Write small JSON audit only')
    args = p.parse_args()
    report = {'source': 'ACDB official dumps', 'files': [inspect_file(x) for x in args.dumps],
              'staged_characters': 0, 'import_ready_artworks': 0,
              'pipeline_status': 'schema_only_pending_content_safety_and_license_review'}
    raw = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        dest = Path(args.output)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(raw, encoding='utf-8')
    print(raw)


if __name__ == '__main__':
    main()
