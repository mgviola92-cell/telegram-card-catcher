"""Opt-in, expiring virtual-card gifts and two-way trades.

All card identifiers are the existing owned_cards.id numeric PK (legacy
alphanumeric codes also accepted). Settlement locks offers and card rows in a
stable order, rechecks owners, transfers atomically, and records an audit row.
No real money, no image bytes, no per-owner image URL or file_id.
"""
from app.card_refs import parse_card_ref
from app.storage import connect

OFFER_MINUTES = 10
MAX_ACTIVE_OFFERS = 8


def _ids(sender_id, receiver_id):
    return (type(sender_id) is int and type(receiver_id) is int
            and sender_id > 0 and receiver_id > 0 and sender_id != receiver_id)


def _card(db, ref):
    parsed = parse_card_ref(ref)
    if parsed is None:
        return None
    kind, val = parsed
    field = "id" if kind == "id" else "code"
    return db.execute(
        f"SELECT id,owner_id,code FROM owned_cards WHERE {field}=%s",
        (val,)).fetchone()


def _max_pending(db, table, sender):
    # Table name comes ONLY from static local literals, never from a command.
    if table not in ("trade_offers", "gift_offers"):
        raise ValueError("Unexpected offer table")
    result = db.execute(
        f"""SELECT count(*) AS n FROM {table} WHERE sender_id=%s
        AND status='pending' AND created_at >= now() - interval '10 minutes'""",
        (sender,)).fetchone()
    return result["n"] >= MAX_ACTIVE_OFFERS


def create_gift(sender, receiver, card_ref):
    if not _ids(sender, receiver) or parse_card_ref(card_ref) is None:
        return None
    with connect() as db:
        if _max_pending(db, "gift_offers", sender):
            return None
        card = _card(db, card_ref)
        if not card or card["owner_id"] != sender:
            return None
        offer = db.execute(
            """INSERT INTO gift_offers(sender_id,receiver_id,card_id)
            VALUES (%s,%s,%s) RETURNING id""",
            (sender, receiver, card["id"])).fetchone()
        return {"offer_id":offer["id"], "card_id":card["id"],
                "sender_id":sender,"receiver_id":receiver}


def create_trade(sender, receiver, my_ref, their_ref):
    if not _ids(sender, receiver):
        return None
    if parse_card_ref(my_ref) is None or parse_card_ref(their_ref) is None:
        return None
    with connect() as db:
        if _max_pending(db, "trade_offers", sender):
            return None
        mine = _card(db, my_ref)
        theirs = _card(db, their_ref)
        if (not mine or not theirs or mine["id"] == theirs["id"]
            or mine["owner_id"] != sender or theirs["owner_id"] != receiver):
            return None
        offer = db.execute(
            """INSERT INTO trade_offers
                (sender_id,receiver_id,sender_card_id,receiver_card_id)
                VALUES (%s,%s,%s,%s) RETURNING id""",
            (sender,receiver,mine["id"],theirs["id"])).fetchone()
        return {"offer_id":offer["id"],"sender_card_id":mine["id"],
                "receiver_card_id":theirs["id"],
                "sender_id":sender,"receiver_id":receiver}


def _read_offer(db, kind, offer_id):
    if kind not in ("gift","trade"):
        raise ValueError("Unknown offer type")
    if type(offer_id) is not int or offer_id <= 0 or offer_id > 9223372036854775807:
        return None
    table = "gift_offers" if kind == "gift" else "trade_offers"
    # The offer row locks first; a second callback cannot settle it twice.
    return db.execute(
        f"""SELECT *, created_at >= now()-interval '10 minutes' AS live
        FROM {table} WHERE id=%s FOR UPDATE""",
        (offer_id,)).fetchone()


def finish_offer(kind, offer_id, actor, accept):
    """Return {status, ...} or None; only the designated recipient may act.

    Row locks are ordered by numeric card ID, protecting against two concurrent
    reversed trades. Rollback keeps cards, offer and ledger in sync.
    """
    if (kind not in ("gift","trade") or type(actor) is not int
        or actor <= 0 or type(accept) is not bool
        or type(offer_id) is not int or not 1 <= offer_id <= 9223372036854775807):
        return None
    table = "gift_offers" if kind == "gift" else "trade_offers"
    with connect() as db:
        offer = _read_offer(db, kind, offer_id)
        if not offer or offer["receiver_id"] != actor or offer["status"] != "pending":
            return None
        if not offer["live"]:
            db.execute(f"UPDATE {table} SET status='expired' WHERE id=%s", (offer_id,))
            return {"status":"expired"}
        if not accept:
            db.execute(f"UPDATE {table} SET status='declined' WHERE id=%s", (offer_id,))
            return {"status":"declined"}
        card_ids = ([offer["card_id"]] if kind == "gift" else
                    [offer["sender_card_id"],offer["receiver_card_id"]])
        cards = db.execute(
            """SELECT id,owner_id FROM owned_cards
               WHERE id=ANY(%s) ORDER BY id FOR UPDATE""",
            (card_ids,)).fetchall()
        indexed = {r["id"]:r for r in cards}
        valid = (len(indexed)==len(card_ids) and
                 indexed[card_ids[0]]["owner_id"] == offer["sender_id"])
        if kind == "trade":
            valid = valid and indexed[card_ids[1]]["owner_id"] == offer["receiver_id"]
        if not valid:
            db.execute(f"UPDATE {table} SET status='invalid' WHERE id=%s", (offer_id,))
            return {"status":"invalid"}
        if kind == "gift":
            db.execute(
                """UPDATE owned_cards SET owner_id=%s,favorite=false
                   WHERE id=%s""", (offer["receiver_id"],card_ids[0]))
            db.execute(
                """INSERT INTO card_transfers(card_id,from_user_id,to_user_id,reason)
                   VALUES (%s,%s,%s,'gift')""",
                (card_ids[0],offer["sender_id"],offer["receiver_id"]))
        else:
            db.execute(
                """UPDATE owned_cards SET owner_id=CASE
                     WHEN id=%s THEN %s WHEN id=%s THEN %s END,
                     favorite=false WHERE id=ANY(%s)""",
                (card_ids[0],offer["receiver_id"],card_ids[1],
                 offer["sender_id"],card_ids))
            db.execute(
                """INSERT INTO card_transfers(card_id,from_user_id,to_user_id,reason)
                   VALUES (%s,%s,%s,'trade'),(%s,%s,%s,'trade')""",
                (card_ids[0],offer["sender_id"],offer["receiver_id"],
                 card_ids[1],offer["receiver_id"],offer["sender_id"]))
        db.execute(f"UPDATE {table} SET status='accepted' WHERE id=%s",(offer_id,))
        return {"status":"accepted", "card_ids":card_ids,
                "sender_id":offer["sender_id"],
                "receiver_id":offer["receiver_id"]}
