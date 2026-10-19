"""Count distinct first-column ACDB SQL IDs without exporting any source row.

Metadata-only, no image requests, no database connections, no character names.
Use with official downloaded .sql.gz files in a disposable network-capable job.
Source column assumptions must be confirmed against real DDL; character/title ID
duplicates and assignment coverage do not prove safe or licensed catalog rows.
"""
import argparse
import gzip
import json
import re
from pathlib import Path

from scripts.acdb_schema_audit import INSERT_PREFIX, MAX_FRAGMENT, MAX_BYTES

EXPECTED = {'characters': 'id', 'publishers': 'id', 'assignments': 'cid'}
COLUMN = re.compile(rb'^\s*\x60([A-Za-z_][A-Za-z0-9_]*)\x60\s+', re.I)
CREATE = re.compile(rb'^\s*CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+\x60?([A-Za-z0-9_]+)\x60?', re.I)


class FirstColumnIDs:
    """Stream parser: track top-level tuples, quote/escape state, first integer."""
    def __init__(self, max_ids=1_000_000):
        self.depth = 0
        self.quote = None
        self.escaped = False
        self.first = None
        self.first_closed = False
        self.ids = set()
        self.rows = 0
        self.unreadable = 0
        self.max_ids = max_ids
        self.done = False

    def feed(self, data):
        for c in data:
            if self.done:
                break
            if self.escaped:
                self.escaped = False
                continue
            if self.quote is not None:
                if c == 92:
                    self.escaped = True
                elif c == self.quote:
                    self.quote = None
                continue
            if c in (39, 34):
                self.quote = c
                continue
            if c == 40:
                self.depth += 1
                if self.depth == 1:
                    self.first = bytearray()
                    self.first_closed = False
            elif c == 41:
                if self.depth == 1:
                    self.rows += 1
                    token = bytes(self.first or b'').strip()
                    if not token.isdigit():
                        self.unreadable += 1
                    else:
                        self.ids.add(int(token))
                        if len(self.ids) > self.max_ids:
                            raise ValueError('Distinct ID safety bound exceeded')
                    self.first = None
                if self.depth:
                    self.depth -= 1
            elif c == 44 and self.depth == 1:
                self.first_closed = True
            elif c == 59 and self.depth == 0:
                self.done = True
            elif self.depth == 1 and not self.first_closed:
                if len(self.first) >= 32:
                    raise ValueError('First SQL ID token too long')
                self.first.append(c)

    def result(self):
        return {'inserted_tuples': self.rows, 'unique_first_column_ids':len(self.ids),
                'repeated_first_column_ids':self.rows-len(self.ids)-self.unreadable,
                'unreadable_first_column_ids':self.unreadable}


def inspect_ids(path, table, max_uncompressed_bytes=MAX_BYTES):
    if table not in EXPECTED:
        raise ValueError('Unsupported table')
    path = Path(path)
    if path.suffix != '.gz':
        raise ValueError('Expected compressed SQL .gz file')
    if type(max_uncompressed_bytes) is not int or max_uncompressed_bytes < 1:
        raise ValueError('Invalid decompression bound')
    parser = FirstColumnIDs()
    current = None
    active = False
    observed_columns = []
    ddl = False
    bytes_out = 0
    with gzip.open(path, 'rb') as stream:
        while True:
            frag = stream.readline(MAX_FRAGMENT)
            if not frag:
                break
            bytes_out += len(frag)
            if bytes_out > max_uncompressed_bytes:
                raise ValueError('Decompression bound exceeded')
            if active:
                current.feed(frag)
                if current.done:
                    active = False
                continue
            # SQL DDL is checked before IDs are accepted. Do not guess order.
            create = CREATE.match(frag)
            if create:
                ddl = create.group(1).decode('ascii').lower() == table
            elif ddl:
                col = COLUMN.match(frag)
                if col:
                    observed_columns.append(col.group(1).decode('ascii').lower())
                if re.match(rb'^\s*\)\s*[^\n]*;', frag):
                    ddl = False
            insert = INSERT_PREFIX.match(frag)
            if insert and insert.group(1).decode('ascii').lower() == table:
                if not observed_columns or observed_columns[0] != EXPECTED[table]:
                    raise ValueError('Unknown first-column SQL mapping; refuse count')
                current = parser
                current.done = False
                current.feed(frag[insert.end():])
                active = not current.done
    if not observed_columns or observed_columns[0] != EXPECTED[table]:
        raise ValueError('Could not verify first-column ID mapping')
    if parser.depth != 0 or parser.quote is not None or active:
        raise ValueError('Incomplete SQL INSERT found')
    return {'table':table, 'verified_first_column':observed_columns[0],
            **parser.result(), 'raw_records_exported':0,
            'image_rights_approved':0}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('characters_gz')
    p.add_argument('publishers_gz')
    p.add_argument('assignments_gz')
    p.add_argument('--output')
    a=p.parse_args()
    results=[inspect_ids(a.characters_gz,'characters'),
             inspect_ids(a.publishers_gz,'publishers'),
             inspect_ids(a.assignments_gz,'assignments')]
    out={'source':'ACDB official dumps','metadata_only':True,
         'tables':results,'staged_characters':0,'approved_artworks':0,
         'cross_source_union_unique':None,
         'notice':'Unique SQL IDs are not deduped across other catalogs, nor filtered for audience/suitability.'}
    text=json.dumps(out,indent=2)+'\n'
    if a.output:
        path=Path(a.output)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(text,encoding='utf-8')
    print(text)


if __name__=='__main__':
    main()
