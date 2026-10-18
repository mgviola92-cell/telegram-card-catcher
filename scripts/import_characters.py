"""Import licensed/approved character metadata from a JSON file; no image download.

Usage: python -m scripts.import_characters data/characters.example.json
Each item requires unique source_key, name, series, image_url (public HTTPS image).
The script validates the entire batch before changing the database.
"""
import json
import re
import sys
import argparse
from urllib.parse import urlsplit
import ipaddress
from app.storage import connect, RARITIES

CATEGORIES = {'anime','manga','manhwa','webtoon','game','original_ai','other'}
KEY_PATTERN = re.compile(r'^[a-zA-Z0-9_.:-]{3,120}$')


def validate(items):
    if not isinstance(items,list):
        raise ValueError('JSON root must be an array')
    seen=set()
    validated=[]
    for index,item in enumerate(items):
        if not isinstance(item,dict):
            raise ValueError(f'Item {index} must be an object')
        key=item.get('source_key')
        if not isinstance(key,str) or not KEY_PATTERN.fullmatch(key) or key in seen:
            raise ValueError(f'Item {index} has invalid/duplicate source_key')
        seen.add(key)
        for field in ('name','series'):
            if not isinstance(item.get(field),str) or not 1<=len(item[field].strip())<=150:
                raise ValueError(f'Item {index} has invalid {field}')
        url=item.get('image_url')
        if not isinstance(url,str) or len(url)>2048:
            raise ValueError(f'Item {index} needs an HTTPS image_url')
        parsed=urlsplit(url)
        hostname=parsed.hostname or ''
        try:
            ipaddress.ip_address(hostname)
            unsafe=True
        except ValueError:
            unsafe=False
        try:
            port=parsed.port
        except ValueError:
            raise ValueError(f'Item {index} has an invalid URL port')
        if (parsed.scheme!='https' or not hostname or parsed.username or parsed.password
                or unsafe or hostname=='localhost' or hostname.endswith('.localhost')
                or port not in (None,443)):
            raise ValueError(f'Item {index} has an unsafe image_url')
        rarity=item.get('rarity','Common')
        category=item.get('category','anime')
        aliases=item.get('aliases',[])
        weight=item.get('weight',100)
        if rarity not in RARITIES or category not in CATEGORIES:
            raise ValueError(f'Item {index} has unknown category/rarity')
        if not isinstance(aliases,list) or len(aliases)>20 or any(not isinstance(a,str) or not 1<=len(a)<=120 for a in aliases):
            raise ValueError(f'Item {index} has invalid aliases')
        if type(weight) is not int or not 1<=weight<=10000:
            raise ValueError(f'Item {index} needs weight 1..10000')
        validated.append((key,item['name'].strip(),item['series'].strip(),aliases,
                          category,rarity,url,weight))
    return validated


def import_batch(items):
    rows=validate(items)
    with connect() as db:
        for key,name,series,aliases,category,rarity,url,weight in rows:
            db.execute("""INSERT INTO characters(source_key,name,series,aliases,category,rarity,image_url,weight)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (source_key) WHERE source_key IS NOT NULL DO UPDATE
                SET name=EXCLUDED.name, series=EXCLUDED.series, aliases=EXCLUDED.aliases,
                    category=EXCLUDED.category, rarity=EXCLUDED.rarity,
                    image_url=EXCLUDED.image_url, weight=EXCLUDED.weight,
                    telegram_file_id=CASE WHEN characters.image_url IS DISTINCT FROM EXCLUDED.image_url
                        THEN NULL ELSE characters.telegram_file_id END""",
                (key,name,series,aliases,category,rarity,url,weight))
    return len(rows)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Review and import approved character metadata')
    parser.add_argument('json_file')
    parser.add_argument('--apply',action='store_true',help='Write to PostgreSQL; default only validates')
    parser.add_argument('--allow-warnings',action='store_true',help='Override catalog duplicate/unknown-series warnings after review')
    args=parser.parse_args()
    with open(args.json_file,encoding='utf-8') as f:
        data=json.load(f)
    from scripts.catalog_quality import require_approval
    result=require_approval(data,allow_warnings=args.allow_warnings)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    rows=validate(data)
    print(f'Validated {len(rows)} character records.')
    if args.apply:
        print('Characters imported:',import_batch(data))
    else:
        print('Dry run only. Review image rights, then use --apply to import.')
