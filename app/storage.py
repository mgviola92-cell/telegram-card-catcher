import os
import secrets
import string
import psycopg
from psycopg.rows import dict_row

ALPHABET = string.ascii_uppercase + string.digits


def connect():
    return psycopg.connect(os.environ['DATABASE_URL'], row_factory=dict_row)


def initialize():
    with connect() as db:
        with db.cursor() as cur:
            with open('database/schema.sql', encoding='utf-8') as schema:
                cur.execute(schema.read())


def get_cards(user_id, limit=10):
    with connect() as db:
        return db.execute('''SELECT o.code, o.generation, c.name, c.rarity
            FROM owned_cards o JOIN characters c ON c.id=o.character_id
            WHERE o.owner_id=%s ORDER BY o.obtained_at DESC LIMIT %s''', (user_id, limit)).fetchall()


def try_spawn(chat_id, configured_every):
    with connect() as db:
        with db.cursor() as cur:
            cur.execute('''INSERT INTO group_settings(chat_id, spawn_every) VALUES (%s,%s)
                ON CONFLICT (chat_id) DO NOTHING''', (chat_id, configured_every))
            cur.execute('SELECT * FROM group_settings WHERE chat_id=%s FOR UPDATE', (chat_id,))
            setting = cur.fetchone()
            if setting['active_character_id'] is not None:
                return None
            count = setting['message_count'] + 1
            if count < setting['spawn_every']:
                cur.execute('UPDATE group_settings SET message_count=%s WHERE chat_id=%s', (count, chat_id))
                return None
            char = cur.execute('SELECT * FROM characters WHERE enabled=true ORDER BY random() LIMIT 1').fetchone()
            if char is None:
                cur.execute('UPDATE group_settings SET message_count=0 WHERE chat_id=%s', (chat_id,))
                return None
            cur.execute('''UPDATE group_settings SET message_count=0,active_character_id=%s,
                last_spawn=now() WHERE chat_id=%s''', (char['id'],chat_id))
            return char


def cache_image(character_id, file_id):
    with connect() as db:
        db.execute('UPDATE characters SET telegram_file_id=%s WHERE id=%s', (file_id,character_id))


def claim(chat_id, user_id, guessed):
    with connect() as db:
        with db.cursor() as cur:
            settings = cur.execute('SELECT active_character_id FROM group_settings WHERE chat_id=%s FOR UPDATE', (chat_id,)).fetchone()
            if not settings or not settings['active_character_id']:
                return None
            char = cur.execute('SELECT * FROM characters WHERE id=%s', (settings['active_character_id'],)).fetchone()
            match = lambda s: ' '.join(s.casefold().split()) == ' '.join(guessed.casefold().split())
            if not (match(char['name']) or any(match(alias) for alias in char['aliases'])):
                return None
            cur.execute('SELECT pg_advisory_xact_lock(%s)', (char['id'],))
            generation = cur.execute('SELECT count(*) AS n FROM owned_cards WHERE character_id=%s', (char['id'],)).fetchone()['n'] + 1
            for _ in range(8):
                code = ''.join(secrets.choice(ALPHABET) for _ in range(9))
                if not cur.execute('SELECT 1 FROM owned_cards WHERE code=%s', (code,)).fetchone():
                    break
            else:
                raise RuntimeError('Unable to reserve unique code')
            cur.execute('INSERT INTO owned_cards(code, character_id, owner_id, generation) VALUES (%s,%s,%s,%s)',
                        (code,char['id'],user_id,generation))
            cur.execute('UPDATE group_settings SET active_character_id=NULL WHERE chat_id=%s', (chat_id,))
            return dict(char, code=code, generation=generation)


def set_spawn_rate(chat_id, count):
    with connect() as db:
        db.execute('''INSERT INTO group_settings(chat_id, spawn_every) VALUES (%s,%s)
            ON CONFLICT(chat_id) DO UPDATE SET spawn_every=EXCLUDED.spawn_every''', (chat_id,count))
