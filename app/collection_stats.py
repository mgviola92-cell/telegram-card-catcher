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
