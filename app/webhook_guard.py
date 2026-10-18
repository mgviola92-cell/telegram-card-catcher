"""Persistent Telegram webhook leases, fenced by a per-attempt token."""
import secrets
from app.storage import connect

def begin_update(update_id):
    """Return (state, token); only an acquired attempt receives a token."""
    token=secrets.token_hex(16)
    with connect() as db:
        row=db.execute("""INSERT INTO processed_updates(update_id,status,lease_token)
            VALUES (%s,'processing',%s)
            ON CONFLICT(update_id) DO UPDATE
            SET status='processing', processed_at=now(),lease_token=EXCLUDED.lease_token
            WHERE processed_updates.status='processing'
              AND processed_updates.processed_at < now()-interval '2 minutes'
            RETURNING update_id""",(update_id,token)).fetchone()
        if row:
            return 'acquired',token
        current=db.execute('SELECT status FROM processed_updates WHERE update_id=%s',
                           (update_id,)).fetchone()
        return (current['status'] if current else 'processing'),None

def complete_update(update_id,token):
    with connect() as db:
        result=db.execute("""UPDATE processed_updates
            SET status='done',processed_at=now(),lease_token=NULL
            WHERE update_id=%s AND status='processing' AND lease_token=%s
            RETURNING update_id""",(update_id,token)).fetchone()
        return result is not None

def release_failed_update(update_id,token):
    with connect() as db:
        db.execute("""DELETE FROM processed_updates
            WHERE update_id=%s AND status='processing' AND lease_token=%s""",
                   (update_id,token))

def prune_updates():
    with connect() as db:
        db.execute("""DELETE FROM processed_updates
            WHERE (status='done' AND processed_at < now()-interval '3 days')
               OR (status='processing' AND processed_at < now()-interval '7 days')""")
