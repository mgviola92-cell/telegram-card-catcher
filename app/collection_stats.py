"""Efficient collection stats and real series progress using shared metadata.

Progress counts DISTINCT characters, not duplicate generations or variants;
owned-card rows store only IDs and ownership, never artwork.
"""
from app.storage import connect


def overview(user_id):
    if type(user_id) is not int or user_id <= 0:
        raise ValueError("Invalid Telegram user ID")
    with connect() as db:
        stats=db.execute("""SELECT count(*) AS owned,
                    count(DISTINCT character_id) AS unique_characters,
                    count(*) FILTER (WHERE favorite) AS favourites,
                    count(*) FILTER (WHERE variant_id IS NOT NULL) AS variants
                  FROM owned_cards WHERE owner_id=%s""",(user_id,)).fetchone()
        available=db.execute("""SELECT count(*) AS n FROM characters
                        WHERE enabled=true""").fetchone()["n"]
    return dict(stats,catalog_available=available)


def series_progress(user_id,series):
    if type(user_id) is not int or user_id<=0 or not isinstance(series,str):
        raise ValueError("Invalid user or series")
    series=series.strip()
    if not 1<=len(series)<=150:
        raise ValueError("Series must be 1..150 characters")
    with connect() as db:
        info=db.execute("""SELECT count(*) AS available,
                       count(*) FILTER (WHERE EXISTS (
                            SELECT 1 FROM owned_cards o
                            WHERE o.owner_id=%s AND o.character_id=c.id
                       )) AS collected
                       FROM characters c WHERE c.series=%s AND c.enabled=true""",
                        (user_id,series)).fetchone()
    return {"series":series,**info}


def recent_series_progress(user_id,limit=8):
    if type(user_id) is not int or user_id <= 0 or type(limit) is not int or not 1<=limit<=10:
        raise ValueError("Invalid owner or series page size")
    with connect() as db:
        return db.execute("""WITH seen AS (
                SELECT c.series,COUNT(DISTINCT o.character_id) AS collected
                FROM owned_cards o JOIN characters c ON o.character_id=c.id
                WHERE o.owner_id=%s AND c.enabled=true
                GROUP BY c.series
                ORDER BY collected DESC,c.series LIMIT %s
            )
            SELECT s.series,s.collected,
                  (SELECT count(*) FROM characters c
                   WHERE c.series=s.series AND c.enabled=true) AS available
            FROM seen s ORDER BY s.collected DESC,s.series""",
            (user_id,limit)).fetchall()


def duplicate_characters(user_id,limit=10):
    """Return characters owned more than once (not individual artwork copies)."""
    if type(user_id) is not int or user_id<=0 or type(limit) is not int or not 1<=limit<=12:
        raise ValueError("Invalid owner or duplicates page size")
    with connect() as db:
        return db.execute("""SELECT c.id AS character_id,c.name,c.series,
                         copies.n AS copies
                     FROM (
                       SELECT character_id,count(*) AS n
                       FROM owned_cards WHERE owner_id=%s
                       GROUP BY character_id HAVING count(*)>1
                     ) copies
                     JOIN characters c ON c.id=copies.character_id
                     ORDER BY copies.n DESC,c.name,c.id LIMIT %s""",
                     (user_id,limit)).fetchall()


def missing_characters(user_id,series,limit=12):
    """Return first few missing identities and total from *enabled* catalog."""
    if (type(user_id) is not int or user_id<=0
        or not isinstance(series,str) or not 1<=len(series.strip())<=150
        or type(limit) is not int or not 1<=limit<=12):
        raise ValueError("Missing characters requires a user and exact series title")
    series=series.strip()
    query="""FROM characters c
        WHERE c.enabled=true AND c.series=%s
          AND NOT EXISTS (
            SELECT 1 FROM owned_cards o
            WHERE o.owner_id=%s AND o.character_id=c.id
          )"""
    with connect() as db:
        total=db.execute("SELECT count(*) AS n "+query,(series,user_id)).fetchone()["n"]
        rows=db.execute("SELECT c.id,c.name,c.rarity "+query+
                        " ORDER BY c.name,c.id LIMIT %s",
                        (series,user_id,limit)).fetchall()
    return {"series":series,"missing":int(total),"characters":rows}
