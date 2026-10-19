"""Import approved character artwork variants from a JSON file."""
import json
import sys
from app.storage import connect, RARITIES

def validate(items):
    if not isinstance(items,list):
        raise ValueError('Expected a JSON array')
    out=[]
    seen=set()
    for record in items:
        source=record.get('character_source_key')
        variant=record.get('variant_key')
        label=record.get('label')
        url=record.get('image_url')
        rarity=record.get('rarity','Common')
        weight=record.get('spawn_weight',100)
        if not all(isinstance(x,str) and 0<len(x)<=120 for x in (source,variant,label)):
            raise ValueError('Invalid identifying fields')
        if not isinstance(url,str) or not url.startswith('https://'):
            raise ValueError('Artwork needs an HTTPS URL')
        if rarity not in RARITIES or type(weight) is not int or not 0<=weight<=10000:
            raise ValueError('Invalid rarity/weight')
        if (source,variant) in seen:
            raise ValueError('Duplicate variant in batch')
        seen.add((source,variant))
        out.append((source,variant,label,url,rarity,weight))
    return out

def import_batch(items):
    rows=validate(items)
    with connect() as db:
        for source,variant,label,url,rarity,weight in rows:
            character=db.execute('SELECT id FROM characters WHERE source_key=%s',(source,)).fetchone()
            if not character:
                raise ValueError('Unknown character source_key: '+source)
            db.execute("""INSERT INTO character_variants
               (character_id,variant_key,label,image_url,rarity,spawn_weight)
               VALUES (%s,%s,%s,%s,%s,%s)
               ON CONFLICT(character_id,variant_key) DO UPDATE SET
               label=EXCLUDED.label,image_url=EXCLUDED.image_url,
               rarity=EXCLUDED.rarity,spawn_weight=EXCLUDED.spawn_weight,
               telegram_file_id=CASE WHEN character_variants.image_url IS DISTINCT FROM EXCLUDED.image_url
                  THEN NULL ELSE character_variants.telegram_file_id END""",
               (character['id'],variant,label,url,rarity,weight))
    return len(rows)

if __name__=='__main__':
    with open(sys.argv[1],encoding='utf-8') as file:
        print(import_batch(json.load(file)))
