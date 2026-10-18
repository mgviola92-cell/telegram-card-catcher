"""Read-only Neon/Postgres storage diagnostics. No data changes or credentials logged.

Usage: python -m scripts.database_footprint
Uses DATABASE_URL; never modifies tables or indexes.
"""
import json
from app.storage import connect

SIZE_SQL="""SELECT pg_database_size(current_database())::bigint AS database_bytes,
       pg_size_pretty(pg_database_size(current_database())) AS readable_size"""
TABLE_SQL="""SELECT relname AS table_name,
       pg_total_relation_size(relid)::bigint AS total_bytes,
       pg_relation_size(relid)::bigint AS table_bytes,
       pg_indexes_size(relid)::bigint AS index_bytes,
       n_live_tup::bigint AS estimated_rows,
       n_dead_tup::bigint AS estimated_dead_rows
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC"""

def audit(db):
    size=db.execute(SIZE_SQL).fetchone()
    tables=db.execute(TABLE_SQL).fetchall()
    return {'database_bytes':size['database_bytes'],
            'readable_size':size['readable_size'],
            'tables':[{k:v for k,v in row.items()} for row in tables],
            'notes':[
              'Row counts from pg_stat_user_tables are estimates.',
              'Index sizes are included in total_bytes; do not sum both.',
              'Do not delete owned_cards, card_transfers or character rows to reduce storage.',
              'Artwork URLs/file IDs are stored in PostgreSQL; image bytes are not.'
            ]}

if __name__=='__main__':
    with connect() as db:
        print(json.dumps(audit(db),ensure_ascii=False,indent=2))
