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
INSERT_PREFIX = re.compile(rb'^\s*INSERT\s+INTO\s+`?([A-Za-z0-9_]+)`?\s+VALUES\s*', re.I)
COLUMN = re.compile(r"^\s*`([A-Za-z_][A-Za-z0-9_]*)`\s+", re.I)
MAX_FRAGMENT = 65536
MAX_BYTES = 1_000_000_000


class SQLTupleCounter:
    """Count top-level MySQL VALUES tuples without exposing cell contents."""
    def __init__(self):
        self.depth = 0
        self.quote = None
        self.escaped = False
        self.count = 0
        self.finished = False

    def feed(self, chunk):
        for c in chunk:
            if self.escaped:
                self.escaped = False
                continue
            if self.quote is not None:
                if c == 92:  # MySQL backslash-escaped quote/character
                    self.escaped = True
                elif c == self.quote:
                    self.quote = None
                continue
            if c in (39, 34):
                self.quote = c
            elif c == 40:
                self.depth += 1
            elif c == 41 and self.depth:
                self.depth -= 1
                if not self.depth:
                    self.count += 1
            elif c == 59 and self.depth == 0:
                self.finished = True
                break


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
    row_counts = Counter()
    current_counter = None
    current_table = None
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
                if current_counter:
                    current_counter.feed(frag)
                    if current_counter.finished:
                        row_counts[current_table] += current_counter.count
                        current_counter = None
                        current_table = None
                if line_done:
                    is_continuation = False
                continue
            if not line_done and len(frag) == MAX_FRAGMENT:
                long_lines += 1
                is_continuation = True
            insert = INSERT_PREFIX.match(frag)
            if insert:
                current_table = insert.group(1).decode('ascii')
                current_counter = SQLTupleCounter()
                current_counter.feed(frag[insert.end():])
                if current_counter.finished:
                    row_counts[current_table] += current_counter.count
                    current_counter = None
                    current_table = None
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
        'inserted_tuples_by_table': dict(sorted(row_counts.items())),
        'character_rows_measured': 'characters' in row_counts,
        'rights_approved_artworks': 0,
        'notice': 'Metadata SQL inspection only; inserted tuple counts are not deduplicated IDs. Age/content filters and image rights are NOT approved.',
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
