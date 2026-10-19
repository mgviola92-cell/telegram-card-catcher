"""Opt-in seed of ONE permitted Telegram pilot card in a disposable/test DB.

Default is offline preflight (no database access). --apply requires
TEST_DATABASE_URL pointing to a database beginning with cardkout_test,
and refuses the exact DATABASE_URL. Never accesses Telegram or sends photos.
Use a SEPARATE Telegram test bot / webhook when exercising the test DB.
"""
import argparse
import json
from pathlib import Path
from unittest.mock import patch
import psycopg
from psycopg.rows import dict_row

from scripts.import_characters import import_batch
from scripts.pilot_preflight import check
from tests.test_db_integration import safe_test_database_url

CATALOG = Path(__file__).resolve().parent.parent/'data'/'telegram_pilot_catalog.json'
APPROVALS = Path(__file__).resolve().parent.parent/'data'/'telegram_pilot_artwork_approvals.json'
SCHEMA = Path(__file__).resolve().parent.parent/'database'/'schema.sql'


def seed_test_pilot(apply=False):
    cards = json.loads(CATALOG.read_text(encoding='utf8'))
    approvals = json.loads(APPROVALS.read_text(encoding='utf8'))
    ready=check(cards,approvals)
    if not ready['can_pilot'] or len(cards)!=1:
        raise ValueError('Single-card pilot preflight failed; refusing any import')
    report = {'mode':'test_db_seed' if apply else 'offline_pilot_preflight',
              'pilot_records':1,
              'rights_manifest_valid':True,
              'source_key':cards[0]['source_key'],
              'media_bytes_stored':0,
              'production_database_changed':False}
    if not apply:
        return report
    url=safe_test_database_url()
    if not url:
        raise RuntimeError('--apply requires TEST_DATABASE_URL for a disposable test database')
    with psycopg.connect(url,row_factory=dict_row) as db:
        # Idempotent schema initialization ONLY on the named disposable test DB.
        db.execute(SCHEMA.read_text(encoding='utf8'))
    with patch('scripts.import_characters.connect',
               lambda: psycopg.connect(url,row_factory=dict_row)):
        inserted=import_batch(cards,batch_size=1)
    with psycopg.connect(url,row_factory=dict_row) as db:
        row=db.execute('SELECT id,source_key,image_url,enabled FROM characters WHERE source_key=%s',
                       (cards[0]['source_key'],)).fetchone()
        if not row or row['image_url']!=cards[0]['image_url'] or not row['enabled']:
            raise RuntimeError('Test pilot seeding did not resolve expected art row')
        report['inserted_or_updated_metadata']=inserted
        report['artwork_reference_available']=True
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply',action='store_true',
                   help='Explicitly apply to a named disposable TEST_DATABASE_URL only')
    args=p.parse_args()
    print(json.dumps(seed_test_pilot(apply=args.apply),indent=2))
