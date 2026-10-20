"""Read-only Neon footprint and explicit bounded ephemeral-row maintenance.

Never delete character catalogs, owned_cards, card_transfers, variants,
group_settings, or image URL/file_id references. Default: DRY RUN.
This is a one-shot operator command, not an idle scheduler or Render timer.
No images are fetched, rendered, copied, or stored.
"""
import argparse
import json
import os

import psycopg
from psycopg.rows import dict_row

ALLOWED_TABLES = ("processed_updates", "gift_offers", "trade_offers")
# Deliberately more conservative than Telegram's typical retry window.
MIN_KEEP_DAYS = {"processed_updates": 14, "gift_offers": 90, "trade_offers": 90}
MAX_BATCH = 2000
CONFIRM = "PRUNE_EXPIRED_EPHEMERAL_ROWS"


def _ages(keep_updates=30, keep_offers=120):
    if (type(keep_updates) is not int or keep_updates < MIN_KEEP_DAYS["processed_updates"]
        or type(keep_offers) is not int or keep_offers < 90
        or keep_updates > 3650 or keep_offers > 3650):
        raise ValueError("Minimum retention is 14 days for update dedup, 90 for offers")
    return {"processed_updates": keep_updates, "gift_offers": keep_offers,
            "trade_offers": keep_offers}


def _relation_totals(db):
    rows = db.execute("""SELECT relname, pg_total_relation_size(oid) AS all_bytes,
                               pg_relation_size(oid) AS heap_bytes,
                               pg_indexes_size(oid) AS index_bytes
                        FROM pg_class WHERE relnamespace='public'::regnamespace
                          AND relkind='r' AND relname=ANY(%s)
                        ORDER BY pg_total_relation_size(oid) DESC""",
                        (list(ALLOWED_TABLES)+["characters","owned_cards",
                                              "character_variants","card_transfers",
                                              "group_settings"],)).fetchall()
    return [{k:r[k] for k in ("relname","all_bytes","heap_bytes","index_bytes")}
            for r in rows]


def audit(db, keep_updates=30, keep_offers=120):
    ages = _ages(keep_updates, keep_offers)
    per = {}
    for table in ALLOWED_TABLES:
        # Table is from hard-coded ALLOWED_TABLES, never user input.
        result = db.execute(
            f"""SELECT count(*) AS eligible FROM {table}
                 WHERE {('processed_at' if table=='processed_updates' else 'created_at')}
                    < now() - make_interval(days => %s)""",
            (ages[table],)).fetchone()
        per[table]={"eligible_old_ephemeral_rows": int(result["eligible"]),
                    "keep_days":ages[table]}
    database_size = db.execute(
        "SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
    return {"mode":"dry_run","database_bytes":int(database_size),
            "table_sizes":_relation_totals(db),"ephemeral":per,
            "image_bytes_downloaded":0,"owned_cards_deleted":0,
            "history_ledger_deleted":0}


def prune_one_batch(db, *, keep_updates=30, keep_offers=120, batch=500):
    """Apply one *bounded* transactional maintenance batch per allowed table.

    Call only after owner explicitly requests maintenance against selected DB.
    pg_total_relation_size may not shrink immediately after deletion: VACUUM
    must reclaim reusable space; VACUUM FULL is not performed.
    """
    ages=_ages(keep_updates,keep_offers)
    if type(batch) is not int or not 1<=batch<=MAX_BATCH:
        raise ValueError("Single-run batch must be in 1..2000")
    removed={}
    for table in ALLOWED_TABLES:
        pk = "update_id" if table == "processed_updates" else "id"
        timestamp = "processed_at" if table == "processed_updates" else "created_at"
        # Quote only fixed whitelisted identifiers. SKIP LOCKED minimizes impact
        # on active Telegram webhook and open exchange transactions.
        query=f"""WITH expired AS (
                    SELECT {pk} FROM {table}
                    WHERE {timestamp} < now() - make_interval(days => %s)
                    ORDER BY {timestamp},{pk}
                    LIMIT %s FOR UPDATE SKIP LOCKED
                )
                DELETE FROM {table} current_row USING expired
                WHERE current_row.{pk}=expired.{pk}"""
        cursor = db.execute(query, (ages[table],batch))
        removed[table]=int(cursor.rowcount)
    return {"mode":"bounded_manual_cleanup","deleted_ephemeral":removed,
            "owned_cards_deleted":0,"character_records_deleted":0,
            "history_ledger_deleted":0,"media_files_deleted":0}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply",action="store_true",
                   help="Required to delete only old processed updates and offers")
    p.add_argument("--confirm",default="")
    p.add_argument("--keep-updates-days",type=int,default=30)
    p.add_argument("--keep-offers-days",type=int,default=120)
    p.add_argument("--batch",type=int,default=500)
    args=p.parse_args()
    _ages(args.keep_updates_days,args.keep_offers_days)
    if type(args.batch) is not int or not 1<=args.batch<=MAX_BATCH:
        p.error("batch must be in 1..2000")
    if args.apply and args.confirm != CONFIRM:
        p.error("To prune old ephemeral rows, supply --confirm "+CONFIRM)
    # Do not silently use the main bot DATABASE_URL. Operator provides an
    # intentionally separate connection variable when ready to inspect.
    url=os.environ.get("MAINTENANCE_DATABASE_URL")
    if not url:
        p.error("MAINTENANCE_DATABASE_URL must be explicitly configured")
    with psycopg.connect(url,row_factory=dict_row) as db:
        if args.apply:
            result=prune_one_batch(db, keep_updates=args.keep_updates_days,
                                   keep_offers=args.keep_offers_days,
                                   batch=args.batch)
        else:
            # A dry run must leave the DB untouched, even on a read-only role.
            result=audit(db, keep_updates=args.keep_updates_days,
                         keep_offers=args.keep_offers_days)
    print(json.dumps(result,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
