"""Persistent webhook processing leases with retryable in-flight requests.

Unfinished leases expire after two minutes; completed updates remain deduplicated.
"""
from app.storage import connect

def begin_update(update_id):
    """Return 'acquired', 'processing', or 'done'."""
    with connect() as db:
        row=db.execute("""INSERT INTO processed_updates(update_id,status)
            VALUES (%s,'processing')
            ON CONFLICT(update_id) DO UPDATE
            SET status='processing', processed_at=now()
            WHERE processed_updates.status='processing'
              AND processed_updates.processed_at < now()-interval '2 minutes'
            RETURNING update_id""",(update_id,)).fetchone()
        if row:
            return 'acquired'
        current=db.execute('SELECT status FROM processed_updates WHERE update_id=%s',
                           (update_id,)).fetchone()
        return current['status'] if current else 'processing'

def complete_update(update_id):
    with connect() as db:
        db.execute("""UPDATE processed_updates SET status='done',processed_at=now()
            WHERE update_id=%s AND status='processing'""",(update_id,))

def release_failed_update(update_id):
    with connect() as db:
        db.execute("DELETE FROM processed_updates WHERE update_id=%s AND status='processing'",
                   (update_id,))

def prune_updates():
    with connect() as db:
        db.execute("""DELETE FROM processed_updates
            WHERE (status='done' AND processed_at < now()-interval '3 days')
               OR (status='processing' AND processed_at < now()-interval '7 days')""")
