"""Atomic gifting, swaps and leaderboards. No real-money value."""
from app.storage import connect

def gift_card(owner_id, receiver_id, code):
    if owner_id == receiver_id: return False
    with connect() as db:
        row=db.execute("""UPDATE owned_cards SET owner_id=%s, favorite=false
          WHERE code=%s AND owner_id=%s RETURNING id""",(receiver_id,code.upper(),owner_id)).fetchone()
        return bool(row)

def trade_cards(user_a, user_b, code_a, code_b):
    if user_a==user_b or code_a.upper()==code_b.upper(): return False
    with connect() as db:
        # Lock in deterministic code order to avoid concurrent trade deadlocks.
        rows=db.execute("""SELECT code,owner_id FROM owned_cards WHERE code=ANY(%s)
            ORDER BY code FOR UPDATE""",([code_a.upper(),code_b.upper()],)).fetchall()
        owners={r['code']:r['owner_id'] for r in rows}
        if owners.get(code_a.upper())!=user_a or owners.get(code_b.upper())!=user_b: return False
        db.execute("""UPDATE owned_cards SET owner_id=CASE
           WHEN code=%s THEN %s WHEN code=%s THEN %s END, favorite=false
           WHERE code IN (%s,%s)""",
           (code_a.upper(),user_b,code_b.upper(),user_a,code_a.upper(),code_b.upper()))
        return True

def leaderboard(chat_id=None, limit=10):
    with connect() as db:
        # Global ranking until group catch attribution is introduced.
        return db.execute("""SELECT owner_id,count(*) AS total FROM owned_cards
            GROUP BY owner_id ORDER BY total DESC, owner_id LIMIT %s""",(limit,)).fetchall()

def ownership(user_id,code):
    with connect() as db:
        return bool(db.execute('SELECT 1 FROM owned_cards WHERE owner_id=%s AND code=%s',
                               (user_id,code.upper())).fetchone())
