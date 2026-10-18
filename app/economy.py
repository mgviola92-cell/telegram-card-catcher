"""Atomic gifts and leaderboard queries. All credits are fictional, not cash."""
from app.storage import connect

def gift_card(owner_id,receiver_id,code):
    if owner_id==receiver_id or not code or len(code)>32: return False
    with connect() as db:
        row=db.execute("""UPDATE owned_cards SET owner_id=%s,favorite=false
          WHERE code=%s AND owner_id=%s RETURNING id""",
          (receiver_id,code.upper(),owner_id)).fetchone()
        if not row: return False
        db.execute("""INSERT INTO card_transfers(card_id,from_user_id,to_user_id,reason)
          VALUES (%s,%s,%s,'gift')""",(row['id'],owner_id,receiver_id))
        return True

def leaderboard(chat_id=None,limit=10,today=False):
    limit=max(1,min(50,int(limit)))
    clauses=[]
    params=[]
    if chat_id is not None:
        clauses.append('caught_chat_id=%s')
        params.append(chat_id)
    if today:
        clauses.append("obtained_at >= date_trunc('day',now() AT TIME ZONE 'Asia/Yangon') AT TIME ZONE 'Asia/Yangon'")
    where='WHERE '+' AND '.join(clauses) if clauses else ''
    with connect() as db:
        return db.execute(f"""SELECT owner_id,count(*) AS total FROM owned_cards
            {where} GROUP BY owner_id ORDER BY total DESC,owner_id LIMIT %s""",
            (*params,limit)).fetchall()

def ownership(user_id,code):
    with connect() as db:
        return bool(db.execute('SELECT 1 FROM owned_cards WHERE owner_id=%s AND code=%s',
                               (user_id,code.upper())).fetchone())
