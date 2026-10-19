"""ACDB character↔title integrity: read-only aggregate audit, no row exports.

Uses official SQL gzip dumps, checks DDL column order, and verifies that each
assignment's cid and pid exist in the corresponding ID inventories.
Neither character names nor titles nor image URLs are printed or written.
Raw/unreviewed source content is never imported to Neon or bot collections.
"""
import argparse
import gzip
import json
from pathlib import Path

from scripts.acdb_id_audit import _scan_ids, CREATE, COLUMN
from scripts.acdb_schema_audit import INSERT_PREFIX, MAX_FRAGMENT, MAX_BYTES


class AssignmentRelations:
    """Count integer cid/pid tuples across bounded input fragments."""
    def __init__(self, characters, titles, max_pairs=1_000_000):
        self.characters = characters
        self.titles = titles
        self.depth = 0
        self.token = bytearray()
        self.fields = []
        self.done = False
        self.rows = 0
        self.duplicates = 0
        self.seen_pairs = set()
        self.missing_character_rows = 0
        self.missing_title_rows = 0
        self.missing_both_rows = 0
        self.missing_characters = set()
        self.missing_titles = set()
        self.linked_characters = set()
        self.linked_titles = set()
        self.max_pairs = max_pairs

    def _field(self):
        word = bytes(self.token).strip()
        if not word or not word.isdigit():
            raise ValueError('Non-numeric ACDB assignment key')
        self.fields.append(int(word))
        self.token.clear()
        if len(self.fields) > 2:
            raise ValueError('Assignment tuple must contain exactly cid,pid')

    def _row(self):
        if len(self.fields) != 2:
            raise ValueError('Assignment must contain precisely two fields')
        cid, pid = self.fields
        self.rows += 1
        if self.rows > self.max_pairs:
            raise ValueError('Assignment count exceeds safety bound')
        pair=(cid,pid)
        if pair in self.seen_pairs:
            self.duplicates += 1
        self.seen_pairs.add(pair)
        good_character = cid in self.characters
        good_title = pid in self.titles
        if not good_character:
            self.missing_character_rows += 1
            self.missing_characters.add(cid)
        if not good_title:
            self.missing_title_rows += 1
            self.missing_titles.add(pid)
        if not good_character and not good_title:
            self.missing_both_rows += 1
        if good_character and good_title:
            self.linked_characters.add(cid)
            self.linked_titles.add(pid)
        self.fields.clear()

    def feed(self, data):
        for c in data:
            if self.done:
                break
            if self.depth == 0:
                if c == 40:  # (
                    self.depth = 1
                    self.fields.clear()
                    self.token.clear()
                elif c == 59:  # ;
                    self.done = True
                elif c not in b' \r\n\t,':
                    raise ValueError('Unexpected syntax between assignment tuples')
            elif c == 44:  # , within tuple
                self._field()
            elif c == 41:  # )
                self._field()
                self._row()
                self.depth = 0
            elif c == 40:
                raise ValueError('Nested assignment tuple')
            elif c in b'0123456789 \t\r\n':
                if len(self.token) >= 32:
                    raise ValueError('Oversized assignment key')
                self.token.append(c)
            else:
                raise ValueError('Unsupported assignment value syntax')

    def result(self):
        return {
            'assignment_rows': self.rows,
            'unique_assignment_pairs': len(self.seen_pairs),
            'repeated_assignment_pairs': self.duplicates,
            'assignments_with_missing_characters': self.missing_character_rows,
            'assignments_with_missing_titles': self.missing_title_rows,
            'assignments_with_both_missing': self.missing_both_rows,
            'distinct_missing_character_ids': len(self.missing_characters),
            'distinct_missing_title_ids': len(self.missing_titles),
            'characters_with_valid_title': len(self.linked_characters),
            'titles_with_valid_character': len(self.linked_titles),
            'characters_without_valid_title': len(self.characters - self.linked_characters),
            'titles_without_valid_character': len(self.titles - self.linked_titles),
            'all_references_valid': (self.missing_character_rows == 0 and self.missing_title_rows == 0),
        }


def inspect_relationships(characters_gz, publishers_gz, assignments_gz,
                          max_uncompressed_bytes=MAX_BYTES):
    char_report, character_ids = _scan_ids(characters_gz, 'characters', max_uncompressed_bytes)
    title_report, title_ids = _scan_ids(publishers_gz, 'publishers', max_uncompressed_bytes)
    parser = AssignmentRelations(character_ids,title_ids)
    observed_columns=[]
    ddl=False
    active=False
    scanned=0
    with gzip.open(assignments_gz,'rb') as stream:
        while True:
            frag=stream.readline(MAX_FRAGMENT)
            if not frag:
                break
            scanned += len(frag)
            if scanned > max_uncompressed_bytes:
                raise ValueError('ACDB assignment decompression safety limit exceeded')
            if active:
                parser.feed(frag)
                if parser.done:
                    active=False
                continue
            create=CREATE.match(frag)
            if create:
                ddl = create.group(1).decode('ascii').lower() == 'assignments'
            elif ddl:
                col=COLUMN.match(frag)
                if col:
                    observed_columns.append(col.group(1).decode('ascii').lower())
                if frag.lstrip().startswith(b')') and b';' in frag:
                    ddl=False
            insert=INSERT_PREFIX.match(frag)
            if insert and insert.group(1).decode('ascii').lower() == 'assignments':
                if observed_columns != ['cid','pid']:
                    raise ValueError('Unexpected assignment DDL columns; refuse to infer keys')
                parser.done=False
                parser.feed(frag[insert.end():])
                active=not parser.done
    if observed_columns != ['cid','pid'] or active or parser.depth != 0:
        raise ValueError('Missing schema verification or incomplete assignments')
    return {
        'source':'ACDB official metadata SQL',
        'metadata_only':True,
        'unique_character_ids':char_report['unique_first_column_ids'],
        'unique_title_ids':title_report['unique_first_column_ids'],
        **parser.result(),
        'raw_characters_exported':0,
        'raw_titles_exported':0,
        'images_downloaded':0,
        'approved_artworks':0,
        'spawn_ready_characters':0,
        'cross_source_union_unique':None,
        'notice':'Integrity counts do not establish content suitability, license clearance or cross-source identity. No auto-import.',
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('characters_gz')
    p.add_argument('publishers_gz')
    p.add_argument('assignments_gz')
    p.add_argument('--output')
    a=p.parse_args()
    report=inspect_relationships(a.characters_gz,a.publishers_gz,a.assignments_gz)
    output=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if a.output:
        dest=Path(a.output)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(output,encoding='utf-8')
    print(output)


if __name__=='__main__':
    main()
