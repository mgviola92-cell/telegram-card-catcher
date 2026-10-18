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
        cards = db.execute("""SELECT o.code,o.generation,o.favorite,c.name,c.series,c.rarity
            FROM owned_cards o JOIN characters c ON c.id=o.character_id
            WHERE o.owner_id=%s ORDER BY o.obtained_at DESC,o.id DESC
            LIMIT %s OFFSET %s""", (user_id, size, page * size)).fetchall()
        return cards, total


def get_card(code):
    with connect() as db:
        return db.execute("""SELECT o.code,o.generation,o.owner_id,c.name,c.series,c.rarity,c.image_url,c.telegram_file_id
            FROM owned_cards o JOIN characters c ON c.id=o.character_id WHERE o.code=%s""",
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
                cur.execute('UPDATE group_settings SET active_character_id=NULL WHERE chat_id=%s', (chat_id,))
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
            cur.execute("""UPDATE group_settings SET message_count=0,active_character_id=%s,
                last_spawn=now() WHERE chat_id=%s""", (char['id'],chat_id))
            return char


def cache_image(character_id, file_id):
    with connect() as db:
        db.execute('UPDATE characters SET telegram_file_id=%s WHERE id=%s', (file_id,character_id))


def clear_spawn(chat_id, character_id):
    with connect() as db:
        db.execute('UPDATE group_settings SET active_character_id=NULL WHERE chat_id=%s AND active_character_id=%s',
                   (chat_id,character_id))


def claim(chat_id, user_id, guessed):
    guessed = normalize_name(guessed)
    if not guessed or len(guessed)>120:
        return None
    with connect() as db:
        with db.cursor() as cur:
            setting = cur.execute("""SELECT active_character_id,last_spawn FROM group_settings
                WHERE chat_id=%s FOR UPDATE""", (chat_id,)).fetchone()
            if not setting or not setting['active_character_id']:
                return None
            if setting['last_spawn'] is None:
                return None
            recent = cur.execute("""SELECT %s >= now()-interval '15 minutes' AS recent""",
                                 (setting['last_spawn'],)).fetchone()['recent']
            if not recent:
                cur.execute('UPDATE group_settings SET active_character_id=NULL WHERE chat_id=%s', (chat_id,))
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
            cur.execute("""INSERT INTO owned_cards(code,character_id,owner_id,generation,caught_chat_id)
                VALUES (%s,%s,%s,%s,%s)""", (code,char['id'],user_id,generation,chat_id))
            cur.execute('UPDATE group_settings SET active_character_id=NULL WHERE chat_id=%s', (chat_id,))
            return dict(char,code=code,generation=generation)


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


def search_characters(term, limit=10):
    term = term.strip()
    if len(term) < 2 or len(term) > 80:
        return []
    escaped = term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    with connect() as db:
        return db.execute('''SELECT id,name,series,rarity FROM characters
            WHERE enabled=true AND (name ILIKE %s ESCAPE '\\' OR series ILIKE %s ESCAPE '\\')
            ORDER BY name,id LIMIT %s''', ('%'+escaped+'%', '%'+escaped+'%', limit)).fetchall()
