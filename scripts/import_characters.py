"""Dry-run-first, rights-reviewed, batched character metadata importer.

Default CLI mode validates only. Writes require --apply, a manually reviewed
per-character artwork manifest, rights confirmation and an exact write phrase.
Imported images stay remote: Neon stores ONLY shared URLs/file_id strings.
No image rendering/downloading, no duplicate per-user image records.
"""
import argparse
import ipaddress
import json
import re
from urllib.parse import urlsplit

from app.storage import connect, RARITIES
from scripts.artwork_approval import require_artwork_approval
from scripts.artwork_attribution import credit_tuple

CATEGORIES={'anime','manga','manhwa','webtoon','game','original_ai','other'}
KEY_PATTERN=re.compile(r'^[a-zA-Z0-9_.:-]{3,120}$')
MAX_IMPORT_ROWS=100_000
CONFIRM_PHRASE='IMPORT_APPROVED_CARDS'


def safe_image_url(url):
    if not isinstance(url,str) or not 12<=len(url)<=2048:
        return False
    try:
        part=urlsplit(url)
        host=part.hostname
        port=part.port
        if (part.scheme!='https' or not host or port not in (None,443)
            or part.username is not None or part.password is not None
            or host=='localhost' or host.endswith('.localhost')):
            return False
        # Raw IP-address sources often expose internal services; our importer
        # accepts only hostnames, and never downloads source artwork itself.
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return True
        return False
    except ValueError:
        return False


def validate(items):
    if not isinstance(items,list) or len(items)>MAX_IMPORT_ROWS:
        raise ValueError(f'Catalog must be an array of at most {MAX_IMPORT_ROWS} records')
    seen=set()
    ready=[]
    for index,item in enumerate(items):
        if not isinstance(item,dict):
            raise ValueError(f'Item {index} must be an object')
        key=item.get('source_key')
        if not isinstance(key,str) or not KEY_PATTERN.fullmatch(key) or key in seen:
            raise ValueError(f'Item {index} invalid or repeated source_key')
        seen.add(key)
        for label in ('name','series'):
            value=item.get(label)
            if not isinstance(value,str) or not 1<=len(value.strip())<=150:
                raise ValueError(f'Item {index} invalid {label}')
        url=item.get('image_url')
        if not safe_image_url(url):
            raise ValueError(f'Item {index} requires a safe HTTPS image URL')
        rarity=item.get('rarity','Common')
        category=item.get('category','anime')
        aliases=item.get('aliases',[])
        weight=item.get('weight',100)
        if rarity not in RARITIES or category not in CATEGORIES:
            raise ValueError(f'Item {index} unknown category or rarity')
        if not isinstance(aliases,list) or len(aliases)>20 or any(
                not isinstance(v,str) or not 1<=len(v.strip())<=120 for v in aliases):
            raise ValueError(f'Item {index} invalid aliases')
        if type(weight) is not int or not 1<=weight<=10_000:
            raise ValueError(f'Item {index} weight must be 1..10000')
        ready.append((key,item['name'].strip(),item['series'].strip(),
                      [v.strip() for v in aliases],category,rarity,url,weight,
                      *credit_tuple(item)))
    return ready


QUERY="""INSERT INTO characters(source_key,name,series,aliases,category,rarity,
                image_url,weight,artwork_author,artwork_license_name,
                artwork_license_url,artwork_page_url)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON CONFLICT (source_key) WHERE source_key IS NOT NULL DO UPDATE
SET name=EXCLUDED.name, series=EXCLUDED.series, aliases=EXCLUDED.aliases,
    category=EXCLUDED.category, rarity=EXCLUDED.rarity,
    image_url=EXCLUDED.image_url, weight=EXCLUDED.weight,
    artwork_author=EXCLUDED.artwork_author,
    artwork_license_name=EXCLUDED.artwork_license_name,
    artwork_license_url=EXCLUDED.artwork_license_url,
    artwork_page_url=EXCLUDED.artwork_page_url,
    telegram_file_id=CASE
       WHEN characters.image_url IS DISTINCT FROM EXCLUDED.image_url
       THEN NULL ELSE characters.telegram_file_id END"""


def import_batch(items, approvals, batch_size=250):
    """Require an exact image approval for every item before opening the DB.

    All batches are run in a single transaction by psycopg context manager.
    A failed batch rolls back the whole call rather than leaving half a catalog.
    """
    rows=validate(items)
    require_artwork_approval(items,approvals)
    if type(batch_size) is not int or not 1<=batch_size<=1000:
        raise ValueError('batch_size must be 1..1000')
    with connect() as db:
        with db.cursor() as cursor:
            for start in range(0,len(rows),batch_size):
                cursor.executemany(QUERY,rows[start:start+batch_size])
    return len(rows)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('catalog',help='Manual reviewed JSON catalog')
    p.add_argument('--approval-manifest',help='Exact source_key/image_url approvals')
    p.add_argument('--apply',action='store_true',
                   help='Opt into a real DB write; default validates only')
    p.add_argument('--rights-reviewed',action='store_true',
                   help='Confirm independent source/image/suitability review')
    p.add_argument('--confirm-database-write',default='',
                   help='Must be exactly IMPORT_APPROVED_CARDS to authorize a write')
    p.add_argument('--batch-size',type=int,default=250)
    a=p.parse_args()
    with open(a.catalog,encoding='utf8') as stream:
        items=json.load(stream)
    rows=validate(items)
    manifest=[]
    if a.approval_manifest:
        with open(a.approval_manifest,encoding='utf8') as stream:
            manifest=json.load(stream)
        require_artwork_approval(items,manifest)
    if not a.apply:
        print(json.dumps({'mode':'dry_run','metadata_valid':True,
                          'records':len(rows),
                          'artwork_manifest_verified':bool(a.approval_manifest),
                          'database_writes':0,'images_downloaded':0},indent=2))
        return 0
    if not a.rights_reviewed or not a.approval_manifest or a.confirm_database_write!=CONFIRM_PHRASE:
        p.error('--apply requires --rights-reviewed, --approval-manifest and '
                '--confirm-database-write IMPORT_APPROVED_CARDS')
    if not items:
        p.error('Empty character catalog cannot be imported')
    inserted=import_batch(items,manifest,batch_size=a.batch_size)
    print(json.dumps({'mode':'explicit_approved_db_write',
                      'metadata_upserts':inserted,'images_downloaded':0},indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
