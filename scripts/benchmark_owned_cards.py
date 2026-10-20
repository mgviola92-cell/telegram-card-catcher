"""Measure numeric ownership row/index footprint in a disposable localhost DB.

This benchmark never touches Neon. It inserts synthetic *image-free* copies
into a transaction, measures PostgreSQL on-disk relations and ROLLS BACK.
No persistent cards, photos, Telegram calls or rendered images. Running the
benchmark can leave reusable dead pages in its disposable test database;
drop that disposable database after the experiment.
"""
import argparse
import json
import os
import uuid

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

MIN_ROWS=1000
MAX_ROWS=200_000


def test_url():
    raw=os.environ.get("TEST_DATABASE_URL","")
    if not raw:
        raise ValueError("Provide a disposable TEST_DATABASE_URL on localhost")
    args=conninfo_to_dict(raw)
    if (args.get("host") not in ("localhost","127.0.0.1","::1")
        or not args.get("dbname","").startswith("cardkout_test")
        or raw == os.environ.get("DATABASE_URL")):
        raise ValueError("Benchmark refuses all production/remote database URLs")
    return raw


def ownership_table_sizes(db):
    row=db.execute("""SELECT pg_relation_size('owned_cards') AS heap,
                        pg_indexes_size('owned_cards') AS indexes,
                        pg_total_relation_size('owned_cards') AS total""").fetchone()
    return {key:int(row[key]) for key in ("heap","indexes","total")}


def measure(rows, *, connection_factory=None):
    if type(rows) is not int or not MIN_ROWS<=rows<=MAX_ROWS:
        raise ValueError("Use 1,000..200,000 synthetic cards")
    url=test_url()  # Guard BEFORE opening the connection.
    factory=connection_factory or psycopg.connect
    tag=uuid.uuid4().hex[:12]
    connection=factory(url,row_factory=dict_row)
    try:
        # The transaction is deliberately never committed, including if a
        # caller catches an error. This is a load/size test, NOT an importer.
        start=ownership_table_sizes(connection)
        char=connection.execute("""INSERT INTO characters
            (name,series,source_key,image_url,enabled)
            VALUES ('Benchmark Fixture','Benchmark Fixture',%s,
                    'https://example.org/metadata-only.jpg',false)
            RETURNING id""",("bench:owner:"+tag,)).fetchone()
        if not char:
            raise RuntimeError("Could not allocate local benchmark catalog row")
        cursor=connection.execute("""INSERT INTO owned_cards
            (code,character_id,owner_id,generation,catcher_id,caught_chat_id)
            SELECT 'BM'||%s||LPAD(g::text,8,'0'),%s,
                   100000+(g %% 2000),g,100000+(g %% 2000),-100000900
            FROM generate_series(1,%s) AS g""",
            (tag,char["id"],rows))
        if cursor.rowcount != rows:
            raise RuntimeError("Synthetic inserted-row count does not match")
        after=ownership_table_sizes(connection)
        report={
            "synthetic_copies":rows,
            "heap_delta_bytes":after["heap"]-start["heap"],
            "index_delta_bytes":after["indexes"]-start["indexes"],
            "total_delta_bytes":after["total"]-start["total"],
            "observed_bytes_per_owned_row":round((after["total"]-start["total"])/rows,2),
            "no_image_bytes":True,
            "production_rows_written":0,
            "notice":"One synthetic distribution, affected by indexes/page bloat; "
                     "NOT a Neon quota guarantee. This transaction is rolled back."
        }
        return report
    finally:
        connection.rollback()
        connection.close()


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--rows",type=int,default=10000)
    cli.add_argument("--run",action="store_true",
                     help="Explicitly create rolled-back fixture rows in local PostgreSQL")
    cli_args=cli.parse_args()
    if not cli_args.run:
        print(json.dumps({"mode":"dry_run","rows_requested":cli_args.rows,
                          "database_connections":0,"writes":0},indent=2))
        return 0
    print(json.dumps(measure(cli_args.rows),indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
