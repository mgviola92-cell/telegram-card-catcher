"""Persistent, retry-aware Telegram webhook inbox.

Atomic claims mark each update *processing* (not yet completed). A successful
handler explicitly marks it done. A failure marks it failed so Telegram can
retry instead of silently losing it after an early dedup insert.

This is AT-LEAST-ONCE handling, NOT an outbox/exactly-once guarantee for
Telegram send_message/photo side effects. Card catch DB transactions are
separately serialized; delivery-side effects still need future outbox work.

No idle polling, no image downloads, no stored Telegram payloads.
"""
from app.storage import connect

LEASE_SECONDS = 180
MAX_UPDATE_ID = (1 << 63) - 1


def valid_update_id(update_id):
    return type(update_id) is int and 0 <= update_id <= MAX_UPDATE_ID


def claim_update(update_id):
    """Return ('claimed', attempt), ('done', None) or ('busy', None).

    Atomic INSERT/UPSERT protects concurrent Render workers; a crashed
    handler's *processing* lease can be recovered after 3 minutes. The
    attempt counter is a fencing token: a worker whose lease was replaced
    cannot mark another worker's update done.
    """
    if not valid_update_id(update_id):
        raise ValueError("Invalid Telegram update ID")
    with connect() as db:
        row = db.execute(
            """INSERT INTO processed_updates
                   (update_id,status,claimed_at,processed_at,attempt_count)
               VALUES (%s,'processing',now(),now(),1)
               ON CONFLICT (update_id) DO UPDATE SET
                   status='processing', claimed_at=now(),
                   attempt_count=processed_updates.attempt_count+1
               WHERE processed_updates.status='failed'
                  OR (processed_updates.status='processing'
                      AND processed_updates.claimed_at < now()-interval '180 seconds')
               RETURNING attempt_count""",
            (update_id,),
        ).fetchone()
        if row:
            return "claimed", int(row["attempt_count"])
        existing=db.execute(
            "SELECT status FROM processed_updates WHERE update_id=%s",
            (update_id,),
        ).fetchone()
        if existing is None:
            # Unexpected race; returning retry keeps Telegram from losing it.
            return "busy", None
        return ("done" if existing["status"] == "done" else "busy"), None


def mark_completed(update_id, attempt):
    if (not valid_update_id(update_id) or type(attempt) is not int or attempt < 1):
        raise ValueError("Invalid webhook completion token")
    with connect() as db:
        completed=db.execute(
            """UPDATE processed_updates SET status='done',processed_at=now()
               WHERE update_id=%s AND attempt_count=%s AND status='processing'
               RETURNING update_id""",
            (update_id,attempt),
        ).fetchone()
        return completed is not None


def mark_failed(update_id, attempt):
    if (not valid_update_id(update_id) or type(attempt) is not int or attempt < 1):
        raise ValueError("Invalid webhook failure token")
    with connect() as db:
        changed=db.execute(
            """UPDATE processed_updates SET status='failed',processed_at=now()
               WHERE update_id=%s AND attempt_count=%s AND status='processing'
               RETURNING update_id""",
            (update_id,attempt),
        ).fetchone()
        return changed is not None
