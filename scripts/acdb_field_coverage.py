"""Aggregate ACDB name/media-field coverage from official metadata SQL dumps.

This is a READ-ONLY metadata audit. It does not fetch/download any images and
never prints raw character/title names, raw URLs, IDs, or individual records.
A populated SQL `image` / `thumb` field is NOT proof of a valid artwork URL,
rights to use that artwork, a suitable title, or a spawn-ready character.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re

from scripts.acdb_schema_audit import INSERT_PREFIX, MAX_BYTES, MAX_FRAGMENT
from scripts.acdb_id_audit import CREATE, COLUMN

FIELDS = {
    'characters': ('romji', 'japanese', 'image', 'thumb'),
    'publishers': ('english', 'japanese', 'romjititle'),
}


class FieldPresence:
    """Streaming MySQL VALUES parser that retains ONLY field-presence flags."""
    def __init__(self, columns):
        self.columns=tuple(columns)
        self.indices={name:self.columns.index(name) for name in FIELDS[next(
            table for table,required in FIELDS.items() if all(c in columns for c in required)
        )]}
        self.depth=0
        self.quote=None
        self.escape=False
        self.quoted=False
        self.value_present=False
        self.unquoted=bytearray()
        self.field_index=0
        self.row_present=set()
        self.rows=0
        self.counters=Counter()
        # Hold fixed-length fingerprints for diversity COUNTS only; never output
        # or persist source filenames/URLs (and never request any artwork).
        self.media_indices={name:index for name,index in self.indices.items()
                            if name in ('image','thumb')}
        self.media_hashes={name:set() for name in self.media_indices}
        self.media_raw=bytearray()
        self.media_overflow=False
        self.media_oversized=Counter()
        self.done=False

    def _finish_field(self):
        if self.quote is not None:
            raise ValueError('Unterminated SQL quoted field')
        if self.quoted:
            present=self.value_present
        else:
            value=bytes(self.unquoted).strip().upper()
            present=bool(value) and value != b'NULL'
        for name,index in self.indices.items():
            if self.field_index==index and present:
                self.row_present.add(name)
                self.counters['present_'+name]+=1
        for name,index in self.media_indices.items():
            if self.field_index == index and present:
                if self.media_overflow:
                    self.media_oversized[name]+=1
                else:
                    self.media_hashes[name].add(
                        hashlib.blake2b(self.media_raw,digest_size=16).digest())
        self.media_raw.clear()
        self.media_overflow=False
        self.field_index+=1
        self.quoted=False
        self.value_present=False
        self.unquoted.clear()

    def _finish_row(self):
        if self.field_index != len(self.columns):
            raise ValueError('ACDB SQL tuple does not match verified DDL column count')
        self.rows+=1
        if self.rows>1_000_000:
            raise ValueError('ACDB row safety bound exceeded')
        if 'romji' in self.indices:
            if self.row_present.intersection({'romji','japanese'}):
                self.counters['has_name_hint']+=1
            if self.row_present.intersection({'image','thumb'}):
                self.counters['has_artwork_pointer_hint']+=1
            if self.row_present.intersection({'romji','japanese'}) and self.row_present.intersection({'image','thumb'}):
                self.counters['has_name_and_artwork_pointer_hints']+=1
        else:
            if self.row_present.intersection({'english','japanese','romjititle'}):
                self.counters['has_title_name_hint']+=1
        self.field_index=0
        self.row_present.clear()

    def feed(self, data):
        for value in data:
            if self.done:
                break
            if self.depth==1 and self.field_index in self.media_indices.values():
                # Ignore SQL field delimiters but preserve commas inside quotes.
                if self.quote is not None or self.escape or value not in (44,41):
                    if len(self.media_raw)<2048:
                        self.media_raw.append(value)
                    else:
                        self.media_overflow=True
            if self.escape:
                self.escape=False
                if self.depth==1 and value not in (9,10,13,32):
                    self.value_present=True
                continue
            if self.quote is not None:
                if value==92:  # Backslash in a MySQL quoted value.
                    self.escape=True
                elif value==self.quote:
                    self.quote=None
                elif value not in (9,10,13,32):
                    self.value_present=True
                continue
            if self.depth==0:
                if value==40:  # (
                    self.depth=1
                    self.field_index=0
                    self.row_present.clear()
                elif value==59:  # ;
                    self.done=True
                elif value not in b' \t\r\n,':
                    raise ValueError('Unsupported characters outside SQL VALUES tuple')
            elif value in (39,34):  # Single/double quote.
                self.quote=value
                self.quoted=True
            elif value==44:  # Field comma.
                self._finish_field()
            elif value==41:  # )
                self._finish_field()
                self._finish_row()
                self.depth=0
            elif value==40:  # No nested unquoted SQL functions/tuples.
                raise ValueError('Unexpected nested SQL VALUES tuple')
            else:
                # Only retain short unquoted NULL/numeric indicators; no data rows.
                if self.field_index in self.indices.values():
                    if len(self.unquoted)>=64:
                        raise ValueError('Unexpected long bare SQL value')
                    self.unquoted.append(value)

    def result(self):
        return {'sql_rows':self.rows,'nonblank_field_counts':{
                  name:self.counters['present_'+name] for name in self.indices},
                'characters_with_name_hint':self.counters['has_name_hint'],
                'characters_with_artwork_pointer_hint':self.counters['has_artwork_pointer_hint'],
                'characters_with_both_hints':self.counters['has_name_and_artwork_pointer_hints'],
                'titles_with_name_hint':self.counters['has_title_name_hint'],
                'distinct_media_pointer_hints':{
                    name:len(fingerprints) for name,fingerprints in self.media_hashes.items()},
                'oversized_media_pointers_excluded_from_diversity':{
                    name:self.media_oversized[name] for name in self.media_indices}}


def inspect_coverage(path, table, max_uncompressed_bytes=MAX_BYTES):
    if table not in FIELDS:
        raise ValueError('Unsupported ACDB metadata table')
    if type(max_uncompressed_bytes) is not int or max_uncompressed_bytes<1:
        raise ValueError('Invalid bounded input size')
    path=Path(path)
    if path.suffix!='.gz':
        raise ValueError('Expected a .sql.gz archive')
    columns=[]
    parser=None
    inside_ddl=False
    active=False
    bytes_out=0
    with gzip.open(path,'rb') as src:
        while True:
            fragment=src.readline(MAX_FRAGMENT)
            if not fragment:
                break
            bytes_out+=len(fragment)
            if bytes_out>max_uncompressed_bytes:
                raise ValueError('ACDB dump exceeds bounded decompression limit')
            if active:
                parser.feed(fragment)
                if parser.done:
                    active=False
                continue
            create=CREATE.match(fragment)
            if create:
                inside_ddl=(create.group(1).decode('ascii').lower()==table)
            elif inside_ddl:
                col=COLUMN.match(fragment)
                if col:
                    columns.append(col.group(1).decode('ascii').lower())
                if re.match(rb'^\s*\)\s*[^\n]*;',fragment):
                    inside_ddl=False
            insert=INSERT_PREFIX.match(fragment)
            if insert and insert.group(1).decode('ascii').lower()==table:
                if not columns or not all(name in columns for name in FIELDS[table]):
                    raise ValueError('Unverified ACDB SQL column map; refusing coverage claims')
                if parser is None:
                    parser=FieldPresence(columns)
                parser.done=False
                parser.feed(fragment[insert.end():])
                active=not parser.done
    if not columns or parser is None or parser.depth or parser.quote is not None or active:
        raise ValueError('Incomplete ACDB dump or absent verified DDL/INSERT')
    return {'table':table, **parser.result(), 'image_urls_verified':0,
            'image_rights_approved':0, 'audience_approved':0,
            'records_exported':0,
            'note':'Populated metadata pointers are unverified hints. No image retrieval or licensing decision.'}


def main():
    arg=argparse.ArgumentParser(description=__doc__)
    arg.add_argument('characters_gz')
    arg.add_argument('publishers_gz')
    arg.add_argument('--output')
    a=arg.parse_args()
    report={'source':'ACDB official SQL metadata',
            'checks':[inspect_coverage(a.characters_gz,'characters'),
                      inspect_coverage(a.publishers_gz,'publishers')],
            'imported_cards':0,'approved_images':0}
    output=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if a.output:
        target=Path(a.output)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(output,encoding='utf-8')
    print(output)


if __name__=='__main__':
    main()
