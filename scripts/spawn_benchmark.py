"""Explain spawn query costs on a disposable PostgreSQL test database.

Usage: TEST_DATABASE_URL=... python -m scripts.spawn_benchmark
No data is imported, and no writes are performed.
"""
import json
import psycopg
from tests.test_db_integration import safe_test_database_url

QUERIES={
    "weighted_character": """SELECT id FROM characters
       WHERE enabled=true AND weight>0
       ORDER BY -ln(greatest(random(),0.000001))/weight LIMIT 1""",
    "weighted_variant": """SELECT id FROM character_variants
       WHERE character_id=(SELECT id FROM characters LIMIT 1)
         AND enabled=true AND spawn_weight>0
       ORDER BY -ln(greatest(random(),0.000001))/spawn_weight LIMIT 1""",
}

def run(url, sample_size=5000):
    if not 1<=sample_size<=20000:
        raise ValueError("sample_size must be 1..20000")
    with psycopg.connect(url) as db:
        # Populate disposable rows in a transaction and roll everything back.
        db.execute("""INSERT INTO characters(name,series,image_url,weight)
          SELECT 'Benchmark '||i,'Benchmark','https://example.org/placeholder.jpg',
          1+mod(i,100) FROM generate_series(1,%s) AS i""",(sample_size,))
        db.execute("ANALYZE characters")
        results={"sample_characters":sample_size}
        for name,query in QUERIES.items():
            plan=db.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) "+query).fetchone()[0][0]
            results[name]={
                "planning_ms":plan["Planning Time"],
                "execution_ms":plan["Execution Time"],
                "plan":plan["Plan"]["Node Type"],
            }
        db.rollback()
        return results

if __name__=="__main__":
    url=safe_test_database_url()
    if not url:
        raise SystemExit("Set TEST_DATABASE_URL for a disposable cardkout_test* database")
    print(json.dumps(run(url),indent=2))
