"""50k-100k synthetic shared-URL character catalog size + query benchmark.

DISPOSABLE localhost PostgreSQL only. This transaction ALWAYS rolls back;
test_url() rejects Neon, remote DBs and production DATABASE_URL. It measures
actual table/index growth and sampled query plans in that particular fixture,
not production capacity. No image bytes, downloads or Telegram calls.
"""
import argparse
import json
import uuid

import psycopg
from psycopg.rows import dict_row

from scripts.benchmark_owned_cards import test_url

MIN_ROWS=1000
MAX_ROWS=150_000


def _sizes(db):
    result=db.execute("""SELECT pg_relation_size('characters')::bigint AS heap,
             pg_indexes_size('characters')::bigint AS indexes,
             pg_total_relation_size('characters')::bigint AS total""").fetchone()
    return {key:int(result[key]) for key in ("heap","indexes","total")}


def _plan(db,query,params):
    row=db.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) "+query,params).fetchone()
    plan=row["QUERY PLAN"]
    if not isinstance(plan,list) or not plan:
        raise RuntimeError("PostgreSQL did not return plan JSON")
    root=plan[0]
    return {
        "top_plan_node":root["Plan"].get("Node Type"),
        "planning_ms":round(float(root.get("Planning Time",0)),3),
        "execution_ms":round(float(root.get("Execution Time",0)),3),
        "blocks_hit":root["Plan"].get("Shared Hit Blocks"),
        "blocks_read":root["Plan"].get("Shared Read Blocks"),
        "warning":"Fixture EXPLAIN, not representative of Neon cache, IO or traffic."
    }


def measure(rows,*,connection_factory=None):
    if type(rows) is not int or not MIN_ROWS<=rows<=MAX_ROWS:
        raise ValueError("Use 1,000..150,000 local synthetic characters")
    url=test_url() # NEVER contact a remote host.
    connect=connection_factory or psycopg.connect
    tag=uuid.uuid4().hex[:12]
    db=connect(url,row_factory=dict_row)
    try:
        before=_sizes(db)
        result=db.execute("""INSERT INTO characters
              (name,series,source_key,category,image_url,weight,enabled)
              SELECT 'Synthetic Hero '||g::text,
                     'Benchmark Series '||(g %% 200)::text,
                     'bench:catalog:'||%s||':'||g::text,
                     'anime','https://example.org/fake-shared-meta-only.png',100,true
              FROM generate_series(1,%s) AS g""",(tag,rows))
        if result.rowcount!=rows:
            raise RuntimeError("Synthetic catalog inserted row count mismatched")
        after=_sizes(db)
        exact=_plan(db,"""SELECT id,name FROM characters
             WHERE enabled=true AND series=%s ORDER BY id LIMIT 20""",
             ("Benchmark Series 42",))
        like=_plan(db,"""SELECT id,name FROM characters
             WHERE enabled=true AND name ILIKE %s ORDER BY name,id LIMIT 10""",
             ("%Synthetic Hero 999%",))
        return {
            "synthetic_catalog_characters":rows,
            "heap_delta_bytes":after["heap"]-before["heap"],
            "index_delta_bytes":after["indexes"]-before["indexes"],
            "total_delta_bytes":after["total"]-before["total"],
            "observed_bytes_per_character":round((after["total"]-before["total"])/rows,2),
            "query_plans":{"exact_series":exact,"substring_name":like},
            "binary_image_storage_bytes":0,"production_rows_written":0,
            "warning":"One disposable PostgreSQL 16 fixture, not Neon sizing. "
                      "Image URL is placeholder text, not usable artwork. "
                      "All fixture rows roll back; no schema changes."
        }
    finally:
        db.rollback()
        db.close()


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--rows",type=int,default=50000)
    cli.add_argument("--run",action="store_true")
    a=cli.parse_args()
    if not a.run:
        print(json.dumps({"mode":"dry_run","rows_requested":a.rows,
                          "db_connections":0,"production_writes":0}))
        return 0
    print(json.dumps(measure(a.rows),indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
