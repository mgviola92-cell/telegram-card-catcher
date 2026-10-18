"""Reply-based two-card offers, atomic settlement and transfer audit."""
from app.storage import connect

def create_offer(sender,receiver,sender_code,receiver_code):
    a,b=sender_code.strip().upper(),receiver_code.strip().upper()
    if sender==receiver or a==b or not a or not b or len(a)>32 or len(b)>32: return None
    with connect() as db:
        mine=db.execute('SELECT 1 FROM owned_cards WHERE owner_id=%s AND code=%s',(sender,a)).fetchone()
        theirs=db.execute('SELECT 1 FROM owned_cards WHERE owner_id=%s AND code=%s',(receiver,b)).fetchone()
        if not mine or not theirs: return None
        offer=db.execute("""INSERT INTO trade_offers(sender_id,receiver_id,sender_code,receiver_code)
          VALUES (%s,%s,%s,%s) RETURNING id""",(sender,receiver,a,b)).fetchone()
        return offer['id']

def finish_offer(offer_id,accepter,accept):
    with connect() as db:
        offer=db.execute("""SELECT * FROM trade_offers WHERE id=%s FOR UPDATE""",
                         (offer_id,)).fetchone()
        if not offer or offer['receiver_id']!=accepter or offer['status']!='pending':
            return False
        # Compare against server clock, not client time.
        live=db.execute("""SELECT created_at > now()-interval '10 minutes' AS live
            FROM trade_offers WHERE id=%s""",(offer_id,)).fetchone()['live']
        if not live:
            db.execute("UPDATE trade_offers SET status='expired' WHERE id=%s",(offer_id,))
            return False
        if not accept:
            db.execute("UPDATE trade_offers SET status='declined' WHERE id=%s",(offer_id,))
            return True
        codes=[offer['sender_code'],offer['receiver_code']]
        # Lock both card rows in stable order. Locks protect ownership against
        # concurrent gifting/trades after the offer was created.
        cards=db.execute("""SELECT id,code,owner_id FROM owned_cards
          WHERE code=ANY(%s) ORDER BY code FOR UPDATE""",(codes,)).fetchall()
        by_code={c['code']:c for c in cards}
        first=by_code.get(codes[0])
        second=by_code.get(codes[1])
        if not first or not second or first['owner_id']!=offer['sender_id'] or second['owner_id']!=offer['receiver_id']:
            db.execute("UPDATE trade_offers SET status='invalid' WHERE id=%s",(offer_id,))
            return False
        db.execute("""UPDATE owned_cards SET owner_id=CASE
          WHEN id=%s THEN %s WHEN id=%s THEN %s END,favorite=false
          WHERE id IN (%s,%s)""",
          (first['id'],offer['receiver_id'],second['id'],offer['sender_id'],first['id'],second['id']))
        db.execute("""INSERT INTO card_transfers(card_id,from_user_id,to_user_id,reason)
          VALUES (%s,%s,%s,'trade'),(%s,%s,%s,'trade')""",
          (first['id'],offer['sender_id'],offer['receiver_id'],
           second['id'],offer['receiver_id'],offer['sender_id']))
        db.execute("UPDATE trade_offers SET status='accepted' WHERE id=%s",(offer_id,))
        return True
