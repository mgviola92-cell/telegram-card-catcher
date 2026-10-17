"""Server-side pending trade requests, short expiration, ownership rechecked at acceptance."""
from app.storage import connect
from app.economy import trade_cards

def create_offer(sender, receiver, sender_code, receiver_code):
    if sender==receiver or not sender_code or not receiver_code: return None
    with connect() as db:
        row=db.execute("""INSERT INTO trade_offers(sender_id,receiver_id,sender_code,receiver_code)
            VALUES (%s,%s,%s,%s) RETURNING id""",
            (sender,receiver,sender_code.upper(),receiver_code.upper())).fetchone()
        return row['id']

def finish_offer(offer_id, accepter, accept):
    with connect() as db:
        offer=db.execute("""SELECT * FROM trade_offers WHERE id=%s FOR UPDATE""",(offer_id,)).fetchone()
        if not offer or offer['receiver_id']!=accepter or offer['status']!='pending': return False
        if offer['created_at'].timestamp() < __import__('time').time()-600:
            db.execute("UPDATE trade_offers SET status='expired' WHERE id=%s",(offer_id,))
            return False
        if not accept:
            db.execute("UPDATE trade_offers SET status='declined' WHERE id=%s",(offer_id,))
            return True
        if not trade_cards(offer['sender_id'],offer['receiver_id'],
                           offer['sender_code'],offer['receiver_code']): return False
        db.execute("UPDATE trade_offers SET status='accepted' WHERE id=%s",(offer_id,))
        return True
