"""Measure ownership storage in isolated PostgreSQL schema on localhost test DB.

Reads the repo's real schema; inserts synthetic cards, never imports images,
never connects to Neon or Telegram, and never changes public/application tables.

Run ONLY with TEST_DATABASE_URL for a local database named cardkout_test*:
  python -m scripts.benchmark_owned_cards --cards 100000

Reports table/index bytes and the measured cost of one duplicate index.
This benchmark is a disposable schema experiment, NOT a 1 GiB capacity guarantee.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from tests.test_db_integration import safe_test_database_url

SCHEMA_PATH = Path(__file__).resolve().parent.parent / 'database' / 'schema.sql'


def safe_local_test_url():
    url = safe_test_database_url()
    if not url:
        raise RuntimeError('TEST_DATABASE_URL is required; no production fallback')
    if urlsplit(url).hostname not in ('localhost', '127.0.0.1', '::1'):
        raise RuntimeError('Ownership benchmark requires a localhost disposable PostgreSQL')
    return url


def redundant_index_exists(db):
    """Check that the plain index's keys are fully covered by a UNIQUE index."""
    return db.execute("""SELECT a.indisunique
                  AND a.indkey = b.indkey
                  AND a.indnkeyatts = b.indnkeyatts
                  AND a.indexprs IS NULL AND b.indexprs IS NULL
                  AND a.indpred IS NULL AND b.indpred IS NULL AS safe
        FROM pg_index a JOIN pg_class a_class ON a_class.oid = a.indexrelid
        JOIN pg_index b ON b.indrelid = a.indrelid
        JOIN pg_class b_class ON b_class.oid = b.indexrelid
        WHERE a_class.relname = 'owned_cards_generation_unique'
          AND b_class.relname = 'owned_cards_by_character'
          AND a.indrelid = 'owned_cards'::regclass""").fetchone()


def measure(cards=100000):
    if type(cards) is not int or not 100 <= cards <= 1_000_000:
        raise ValueError('cards must be an integer from 100 through 1,000,000')
    url = safe_local_test_url()
    schema = 'footprint_' + uuid4().hex[:16]
    with psycopg.connect(url, row_factory=dict_row, connect_timeout=10) as db:
        db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        db.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(schema)))
        db.execute('SET LOCAL statement_timeout = 120000')
        db.execute(SCHEMA_PATH.read_text(encoding='utf-8'))
        key_prefix = schema + ':'
        db.execute("""INSERT INTO characters(name,series,source_key,image_url)
            SELECT 'Synthetic ' || n, 'Synthetic Series', %s || n::text,
                   'https://example.org/placeholder.jpg'
            FROM generate_series(0,99) AS n""", (key_prefix,))
        db.execute("""INSERT INTO owned_cards
            (code,character_id,owner_id,catcher_id,generation,caught_chat_id,caught_message_id)
            SELECT 'B' || lpad(n::text,9,'0'), c.id,
                   100000 + (n %% 1000), 100000 + (n %% 1000),
                   ((n - 1) / 100) + 1, -900000 - (n %% 20), n
            FROM generate_series(1,%s) AS n
            JOIN characters c ON c.source_key = %s || (n %% 100)::text""",
                   (cards, key_prefix))
        actual = db.execute('SELECT count(*) AS n FROM owned_cards').fetchone()['n']
        if actual != cards:
            raise RuntimeError(f'Seed mismatch: expected {cards}, found {actual}')
        # New schemas omit the redundant index. Re-create it ONLY inside the
        # disposable experiment so old-vs-new bytes remain measurable.
        simulated_legacy_index = not bool(redundant_index_exists(db))
        if simulated_legacy_index:
            db.execute('CREATE INDEX owned_cards_by_character ON owned_cards(character_id,generation)')
        before = db.execute("""SELECT
            pg_total_relation_size('owned_cards'::regclass) AS total_bytes,
            pg_relation_size('owned_cards'::regclass) AS heap_bytes,
            pg_indexes_size('owned_cards'::regclass) AS index_bytes""").fetchone()
        check = redundant_index_exists(db)
        legacy_index_present = bool(check)
        if check and not check['safe']:
            raise RuntimeError('Unsafe duplicate-index assumption; no drop performed')
        if legacy_index_present:
            redundant_bytes = db.execute("""SELECT pg_relation_size(
                 'owned_cards_by_character'::regclass) AS bytes""").fetchone()['bytes']
            db.execute('DROP INDEX owned_cards_by_character')
        else:
            redundant_bytes = 0
        after = db.execute("""SELECT
            pg_total_relation_size('owned_cards'::regclass) AS total_bytes,
            pg_relation_size('owned_cards'::regclass) AS heap_bytes,
            pg_indexes_size('owned_cards'::regclass) AS index_bytes""").fetchone()
        # Exact generation lookup and owner lookup must still succeed.
        probe = db.execute("""SELECT o.code FROM owned_cards o
            WHERE o.character_id = (SELECT id FROM characters
              WHERE source_key = %s || '1')
            ORDER BY o.generation LIMIT 1""", (key_prefix,)).fetchone()
        owner_probe = db.execute("""SELECT count(*) AS n FROM owned_cards
            WHERE owner_id = 100001""").fetchone()['n']
        if not probe or owner_probe < 1:
            raise RuntimeError('Ownership/gen lookup failed after index experiment')
        saved = before['total_bytes'] - after['total_bytes']
        if saved != redundant_bytes:
            raise RuntimeError('Unexpected difference after duplicate index drop')
        result = {
            'mode': 'localhost_disposable_postgresql_schema',
            'synthetic_owned_cards': actual,
            'shared_character_records': 100,
            'owned_heap_bytes': after['heap_bytes'],
            'owned_indexes_bytes': after['index_bytes'],
            'owned_total_bytes_without_duplicate': after['total_bytes'],
            'legacy_duplicate_index_present': legacy_index_present,
            'legacy_duplicate_index_simulated_in_test': simulated_legacy_index,
            'duplicate_index_bytes_removed_in_isolated_schema': saved,
            'owned_total_bytes_with_duplicate': before['total_bytes'],
            'owned_bytes_per_card_amortized': round(after['total_bytes'] / cards, 2),
            'notes': [
                'Real PostgreSQL bytes on synthetic rows, not Neon production measurements.',
                'The duplicate index is simulated if missing, only in the test schema.',
                'Only the experimental schema is changed/dropped; public and Neon untouched.',
                'Character and variant metadata, other tables, live usage and bloat are excluded.',
                'URLs are stored once per character; owned cards contain no image bytes or URLs.',
            ],
        }
        # The schema and seeded cards are destroyed before the test transaction ends.
        db.execute('SET LOCAL search_path TO public')
        db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
    return result


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--cards', type=int, default=100000)
    args = cli.parse_args()
    print(json.dumps(measure(args.cards), indent=2))
