"""Persistent update deduplication across Render restarts.

Telegram may deliver the same update more than once. Record it before processing
to prevent duplicate spawns/claims. A crashed handler may lose one update;
production requires a transactional inbox/outbox for guaranteed delivery.
"""
from app.storage import connect


def begin_update(update_id):
    with connect() as db:
        row = db.execute(
            """INSERT INTO processed_updates(update_id) VALUES (%s)
               ON CONFLICT(update_id) DO NOTHING RETURNING update_id""",
            (update_id,),
        ).fetchone()
        # Keep small: cleanup is bounded to occasional requests elsewhere.
        return row is not None


def prune_updates():
    with connect() as db:
        db.execute("DELETE FROM processed_updates WHERE processed_at < now()-interval '3 days'")


def release_failed_update(update_id):
    """Reset the dedup record after an exception so Telegram can redeliver."""
    with connect() as db:
        db.execute('DELETE FROM processed_updates WHERE update_id=%s', (update_id,))
