"""Consent-only virtual-card community trading board.

A listing advertises a numeric card ID for *voluntary swaps*. It never
moves a card, charges points, offers currency or processes payments. Swap
settlement remains /trade replying to another person's group message, with
the recipient explicitly accepting. A listing becomes invisible if its
card changes hands or it expires. Shared artwork never gets copied.
"""
from app.card_refs import parse_card_ref
from app.storage import connect

LISTING_HOURS=24
MAX_ACTIVE_LISTINGS=5
MAX_MARKET_PAGE=10


def _valid_actor(user_id, chat_id):
    return (type(user_id) is int and 0 < user_id < 2**63 and
            type(chat_id) is int and -2**63 < chat_id < 2**63 and chat_id != 0)


def list_card(user_id,chat_id,card_ref):
    if not _valid_actor(user_id,chat_id):
        return None
    parsed=parse_card_ref(card_ref)
    if not parsed:
        return None
    kind,ref=parsed
    column="id" if kind=="id" else "code"
    with connect() as db:
        # Serialize per-owner listing quota, including simultaneous commands
        # in different groups. Negative key separates these from positive
        # per-character generation locks in the catching path.
        db.execute("SELECT pg_advisory_xact_lock(%s)",(-user_id,))
        card=db.execute(
            f"SELECT id,owner_id FROM owned_cards WHERE {column}=%s FOR UPDATE",
            (ref,)).fetchone()
        if not card or card["owner_id"]!=user_id:
            return None
        existing=db.execute(
            "SELECT seller_id FROM market_listings WHERE card_id=%s",
            (card["id"],)).fetchone()
        if not existing or existing["seller_id"] != user_id:
            quota=db.execute(
                """SELECT count(*) AS n FROM market_listings l
                   JOIN owned_cards o ON o.id=l.card_id
                   WHERE l.seller_id=%s AND l.expires_at>now()
                     AND o.owner_id=l.seller_id""",
                (user_id,)).fetchone()["n"]
            if quota >= MAX_ACTIVE_LISTINGS:
                return None
        db.execute(
            """INSERT INTO market_listings(card_id,seller_id,chat_id,listed_at,expires_at)
               VALUES (%s,%s,%s,now(),now()+interval '24 hours')
               ON CONFLICT(card_id) DO UPDATE
               SET seller_id=EXCLUDED.seller_id,chat_id=EXCLUDED.chat_id,
                   listed_at=now(),expires_at=now()+interval '24 hours'""",
            (card["id"],user_id,chat_id))
        return {"card_id":card["id"],"seller_id":user_id,"chat_id":chat_id}


def unlist_card(user_id,card_ref):
    if type(user_id) is not int or user_id <= 0:
        return False
    parsed=parse_card_ref(card_ref)
    if not parsed:
        return False
    kind,ref=parsed
    predicate="o.id=%s" if kind=="id" else "o.code=%s"
    with connect() as db:
        removed=db.execute(f"""DELETE FROM market_listings l
            USING owned_cards o
            WHERE l.card_id=o.id AND {predicate}
              AND l.seller_id=%s AND o.owner_id=%s RETURNING l.card_id""",
            (ref,user_id,user_id)).fetchone()
        return removed is not None


def group_market(chat_id,limit=8):
    if type(chat_id) is not int or chat_id==0 or type(limit) is not int or not 1<=limit<=MAX_MARKET_PAGE:
        raise ValueError("Market query requires a valid group and page size")
    with connect() as db:
        return db.execute(
            """SELECT l.card_id,l.seller_id,c.name,c.series,
                      COALESCE(v.rarity,c.rarity) AS rarity,
                      l.expires_at
               FROM market_listings l
               JOIN owned_cards o ON o.id=l.card_id
               JOIN characters c ON c.id=o.character_id
               LEFT JOIN character_variants v ON v.id=o.variant_id
               WHERE l.chat_id=%s AND l.expires_at>now()
                 AND o.owner_id=l.seller_id
               ORDER BY l.listed_at DESC,l.card_id DESC
               LIMIT %s""",
            (chat_id,limit)).fetchall()
