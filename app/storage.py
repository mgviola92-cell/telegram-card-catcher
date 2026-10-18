"""PostgreSQL persistence; no character images stored on Render disk."""
import os
import secrets
import string
import psycopg
from psycopg.rows import dict_row

ALPHABET = string.ascii_uppercase + string.digits
RARITIES = ('Common', 'Uncommon', 'Rare', 'Legendary', 'Mystical',
            'Divine', 'CrossVerse', 'Cataphract', 'Supreme', 'CNFT')


def connect():
    return psycopg.connect(os.environ['DATABASE_URL'], row_factory=dict_row)


def initialize():
    with connect() as db:
        with open('database/schema.sql', encoding='utf-8') as schema:
            db.execute(schema.read())


def get_cards(user_id, page=0, size=8):
    page = max(0, min(int(page), 99999))
    with connect() as db:
        total = db.execute('SELECT count(*) AS n FROM owned_cards WHERE owner_id=%s', (user_id,)).fetchone()['n']
        cards = db.execute("""SELECT o.code,o.character_id,o.variant_id,o.generation,o.favorite,c.name,c.series,COALESCE(v.rarity,c.rarity) AS rarity,CASE WHEN o.variant_id IS NULL THEN c.telegram_file_id ELSE v.telegram_file_id END AS telegram_file_id,CASE WHEN o.variant_id IS NULL THEN c.image_url ELSE v.image_url END AS image_url
            FROM owned_cards o JOIN characters c ON c.id=o.character_id
            LEFT JOIN character_variants v ON v.id=o.variant_id
            WHERE o.owner_id=%s ORDER BY o.obtained_at DESC,o.id DESC
            LIMIT %s OFFSET %s""", (user_id, size, page * size)).fetchall()
        return cards, total


def get_card(code):
    with connect() as db:
        return db.execute("""SELECT o.code,o.character_id,o.variant_id,o.generation,o.owner_id,o.favorite,c.name,c.series,COALESCE(v.rarity,c.rarity) AS rarity,COALESCE(v.image_url,c.image_url) AS image_url,CASE WHEN o.variant_id IS NULL THEN c.telegram_file_id ELSE v.telegram_file_id END AS telegram_file_id
            FROM owned_cards o JOIN characters c ON c.id=o.character_id LEFT JOIN character_variants v ON v.id=o.variant_id WHERE o.code=%s""",
            (code.upper(),)).fetchone()


def try_spawn(chat_id, default_every):
    with connect() as db:
        with db.cursor() as cur:
            cur.execute("""INSERT INTO group_settings(chat_id,spawn_every) VALUES (%s,%s)
                ON CONFLICT (chat_id) DO NOTHING""", (chat_id,default_every))
            setting = cur.execute('SELECT * FROM group_settings WHERE chat_id=%s FOR UPDATE', (chat_id,)).fetchone()
            if setting['active_character_id'] is not None:
                # A dropped spawn must not permanently block the group.
                expired = cur.execute("""SELECT COALESCE(%s < now()-interval '15 minutes',true) AS expired""",
                    (setting['last_spawn'],)).fetchone()['expired']
                if not expired:
                    return None
                cur.execute('UPDATE group_settings SET active_character_id=NULL,active_variant_id=NULL WHERE chat_id=%s', (chat_id,))
            count = setting['message_count'] + 1
            if count < setting['spawn_every']:
                cur.execute('UPDATE group_settings SET message_count=%s WHERE chat_id=%s', (count,chat_id))
                return None
            # Weighted selection; no image downloads or SQL random sort per row.
            char = cur.execute("""SELECT * FROM characters WHERE enabled=true AND weight>0
                ORDER BY -ln(greatest(random(),0.000001))/weight LIMIT 1""").fetchone()
            if char is None:
                cur.execute('UPDATE group_settings SET message_count=0 WHERE chat_id=%s', (chat_id,))
                return None
            variant = cur.execute("""SELECT * FROM character_variants
                WHERE character_id=%s AND enabled=true AND spawn_weight>0
                ORDER BY -ln(greatest(random(),0.000001))/spawn_weight LIMIT 1""",
                (char['id'],)).fetchone()
            # Base character art remains a possible choice alongside variants.
            if variant and secrets.randbelow(100) < 25:
                char = dict(char, image_url=variant['image_url'],
                            telegram_file_id=variant['telegram_file_id'],
                            rarity=variant['rarity'], variant_id=variant['id'],
                            variant_label=variant['label'])
            else:
                char = dict(char,variant_id=None,variant_label='Original')
            cur.execute("""UPDATE group_settings SET message_count=0,active_character_id=%s,
                active_variant_id=%s,last_spawn=now() WHERE chat_id=%s""",
                (char['id'],char['variant_id'],chat_id))
            return char


def cache_image(character_id, file_id, variant_id=None, expected_url=None):
    """Cache a Telegram photo against the exact art identity and source URL."""
    with connect() as db:
        if variant_id is not None:
            result = db.execute("""UPDATE character_variants SET telegram_file_id=%s
              WHERE id=%s AND character_id=%s AND image_url=%s RETURNING id""",
              (file_id, variant_id, character_id, expected_url)).fetchone()
        else:
            result = db.execute("""UPDATE characters SET telegram_file_id=%s
              WHERE id=%s AND image_url=%s RETURNING id""",
              (file_id, character_id, expected_url)).fetchone()
        return bool(result)


def clear_cached_image(character_id, variant_id, expected_file_id):
    """Remove failed Telegram cache ID only if it has not changed."""
    with connect() as db:
        if variant_id is not None:
            db.execute("""UPDATE character_variants SET telegram_file_id=NULL
                WHERE id=%s AND character_id=%s AND telegram_file_id=%s""",
                (variant_id, character_id, expected_file_id))
        else:
            db.execute("""UPDATE characters SET telegram_file_id=NULL
                WHERE id=%s AND telegram_file_id=%s""",
                (character_id, expected_file_id))


def clear_spawn(chat_id, character_id):
    with connect() as db:
        db.execute('UPDATE group_settings SET active_character_id=NULL,active_variant_id=NULL WHERE chat_id=%s AND active_character_id=%s',
                   (chat_id,character_id))


def claim(chat_id, user_id, guessed):
    guessed = normalize_name(guessed)
    if not guessed or len(guessed)>120:
        return None
    with connect() as db:
        with db.cursor() as cur:
            setting = cur.execute("""SELECT active_character_id,active_variant_id,last_spawn FROM group_settings
                WHERE chat_id=%s FOR UPDATE""", (chat_id,)).fetchone()
            if not setting or not setting['active_character_id']:
                return None
            if setting['last_spawn'] is None:
                return None
            recent = cur.execute("""SELECT %s >= now()-interval '15 minutes' AS recent""",
                                 (setting['last_spawn'],)).fetchone()['recent']
            if not recent:
                cur.execute('UPDATE group_settings SET active_character_id=NULL,active_variant_id=NULL WHERE chat_id=%s', (chat_id,))
                return None
            char = cur.execute('SELECT * FROM characters WHERE id=%s', (setting['active_character_id'],)).fetchone()
            if guessed not in {normalize_name(n) for n in [char['name'],*char['aliases']]}:
                return None
            # Across groups, generation allocation for the same character is serialized.
            cur.execute('SELECT pg_advisory_xact_lock(%s)', (char['id'],))
            generation = cur.execute("""SELECT COALESCE(max(generation),0)+1 AS next FROM owned_cards
                WHERE character_id=%s""", (char['id'],)).fetchone()['next']
            for _ in range(12):
                code = ''.join(secrets.choice(ALPHABET) for _ in range(10))
                if not cur.execute('SELECT 1 FROM owned_cards WHERE code=%s', (code,)).fetchone():
                    break
            else:
                raise RuntimeError('Unable to allocate card code')
            cur.execute("""INSERT INTO owned_cards(code,character_id,owner_id,catcher_id,generation,caught_chat_id,variant_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s)""", (code,char['id'],user_id,user_id,generation,chat_id,setting['active_variant_id']))
            cur.execute('UPDATE group_settings SET active_character_id=NULL,active_variant_id=NULL WHERE chat_id=%s', (chat_id,))
            variant=cur.execute('SELECT label,rarity FROM character_variants WHERE id=%s', (setting['active_variant_id'],)).fetchone() if setting['active_variant_id'] else None
            return dict(char,code=code,generation=generation,variant_id=setting['active_variant_id'],variant_label=variant['label'] if variant else 'Original',rarity=variant['rarity'] if variant else char['rarity'])


def normalize_name(value):
    return ' '.join(value.casefold().split())


def set_spawn_rate(chat_id, count):
    with connect() as db:
        db.execute("""INSERT INTO group_settings(chat_id,spawn_every) VALUES (%s,%s)
            ON CONFLICT(chat_id) DO UPDATE SET spawn_every=EXCLUDED.spawn_every""", (chat_id,count))


def set_favorites(user_id, codes, enabled=True):
    """All-or-nothing, only the requesting owner's cards can change."""
    codes = list(dict.fromkeys(c.strip().upper() for c in codes if c.strip()))
    if not codes or len(codes) > 20 or any(len(c) > 32 for c in codes):
        return 0
    with connect() as db:
        with db.cursor() as cur:
            rows = cur.execute('SELECT code FROM owned_cards WHERE owner_id=%s AND code=ANY(%s) FOR UPDATE',
                               (user_id, codes)).fetchall()
            if len(rows) != len(codes):
                return 0
            cur.execute('UPDATE owned_cards SET favorite=%s WHERE owner_id=%s AND code=ANY(%s)',
                        (enabled, user_id, codes))
            return len(codes)



def toggle_favorite(user_id, code):
    """Atomically toggle only a card still owned by this user."""
    with connect() as db:
        return db.execute("""UPDATE owned_cards SET favorite=NOT favorite
            WHERE owner_id=%s AND code=%s RETURNING favorite""",
            (user_id,code.upper())).fetchone()


def search_characters(term, limit=10):
    term = term.strip()
    if len(term) < 2 or len(term) > 80:
        return []
    escaped = term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    with connect() as db:
        return db.execute('''SELECT id,name,series,rarity FROM characters
            WHERE enabled=true AND (name ILIKE %s ESCAPE '\\' OR series ILIKE %s ESCAPE '\\')
            ORDER BY name,id LIMIT %s''', ('%'+escaped+'%', '%'+escaped+'%', limit)).fetchall()
