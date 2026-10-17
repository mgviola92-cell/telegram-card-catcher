"""Durable trade offers with atomic acceptance and ownership checks."""
from app.storage import connect

def create_offer(sender,receiver,sender_code,receiver_code):
    a,b=sender_code.strip().upper(),receiver_code.strip().upper()
    if sender==receiver or a==b or not a or not b: return None
    with connect() as db:
        # Only owned cards can be offered; revalidate at acceptance.
        mine=db.execute('SELECT 1 FROM owned_cards WHERE owner_id=%s AND code=%s',(sender,a)).fetchone()
        theirs=db.execute('SELECT 1 FROM owned_cards WHERE owner_id=%s AND code=%s',(receiver,b)).fetchone()
        if not mine or not theirs: return None
        row=db.execute("""INSERT INTO trade_offers(sender_id,receiver_id,sender_code,receiver_code)
           VALUES (%s,%s,%s,%s) RETURNING id""",(sender,receiver,a,b)).fetchone()
        return row['id']

def finish_offer(offer_id,accepter,accept):
    with connect() as db:
        row=db.execute("""SELECT * FROM trade_offers WHERE id=%s FOR UPDATE""",(offer_id,)).fetchone()
        if not row or row['receiver_id']!=accepter or row['status']!='pending': return False
        # Use the offer's timestamp in SQL, preserving server-side clock.
        live=db.execute("""SELECT created_at > now()-interval '10 minutes' AS live
                             FROM trade_offers WHERE id=%s""",(offer_id,)).fetchone()['live']
        if not live:
            db.execute("UPDATE trade_offers SET status='expired' WHERE id=%s",(offer_id,))
            return False
        if not accept:
            db.execute("UPDATE trade_offers SET status='declined' WHERE id=%s",(offer_id,))
            return True
        codes=[row['sender_code'],row['receiver_code']]
        cards=db.execute("""SELECT code,owner_id FROM owned_cards WHERE code=ANY(%s)
                         ORDER BY code FOR UPDATE""",(codes,)).fetchall()
        owners={c['code']:c['owner_id'] for c in cards}
        if owners.get(row['sender_code'])!=row['sender_id'] or owners.get(row['receiver_code'])!=row['receiver_id']:
            db.execute("UPDATE trade_offers SET status='invalid' WHERE id=%s",(offer_id,))
            return False
        db.execute("""UPDATE owned_cards SET owner_id=CASE
          WHEN code=%s THEN %s WHEN code=%s THEN %s END, favorite=false
          WHERE code IN (%s,%s)""",(row['sender_code'],row['receiver_id'],
            row['receiver_code'],row['sender_id'],*codes))
        db.execute("UPDATE trade_offers SET status='accepted' WHERE id=%s",(offer_id,))
        return True
