"""Catch-count rankings, not ownership counts: transfers never erase catches.

Older cards without catcher_id fall back to the first transfer origin or
current owner; missing legacy caught_chat_id cannot be invented.
"""
from app.storage import connect


def catch_leaderboard(*, chat_id=None, today=False, limit=10):
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError("Leaderboard limit must be 1..20")
    if chat_id is not None and (type(chat_id) is not int or chat_id == 0):
        raise ValueError("Group chat id must be a Telegram integer")
    if type(today) is not bool:
        raise ValueError("today must be boolean")
    conditions=[]
    params=[]
    if chat_id is not None:
        conditions.append("o.caught_chat_id=%s")
        params.append(chat_id)
    if today:
        conditions.append("""o.obtained_at >=
           date_trunc('day', now() AT TIME ZONE 'Asia/Yangon')
                  AT TIME ZONE 'Asia/Yangon'""")
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    with connect() as db:
        return db.execute(f"""
            SELECT COALESCE(o.catcher_id, original.from_user_id, o.owner_id) AS user_id,
                   count(*) AS catches
            FROM owned_cards o
            LEFT JOIN LATERAL (
                SELECT t.from_user_id FROM card_transfers t
                WHERE t.card_id=o.id ORDER BY t.id LIMIT 1
            ) original ON o.catcher_id IS NULL
            {where}
            GROUP BY COALESCE(o.catcher_id, original.from_user_id, o.owner_id)
            ORDER BY catches DESC, user_id LIMIT %s
        """, (*params,limit)).fetchall()
