# Bulk catalog & database-first strategy — 2026-10-21 (development)

**Purpose:** 100,000+ metadata identities without manual per-character
insertion, while honoring the strongest requirement: zero image binaries in
Neon or Render, and no shared image_url/file_id replicated to owned_cards.

## Release firewall

Production main / Render / Neon ownership are NOT changed here. Metadata
rows are NOT spawnable characters and MUST NOT be imported to live characters
until matching approved picture(s), source terms and real Telegram delivery
are independently verified. Metadata source schema/term claims cannot grant
copyrighted-anime artwork redistribution rights.

## Actual staging pipeline

New: scripts/bulk_metadata_stage.py. Inputs are locally supplied JSONL,
NDJSON or CSV (including .gz), explicitly named source namespaces.
- 1 million bounded input rows per call, up to 500,000 distinct source IDs;
  streaming reads, temporary SQLite key index, no 100k-entry Python dict.
- Strict namespace/key dedup; identical duplicates merged, **conflicting ID
  records make the batch fail**, cross-provider same name NEVER auto-merged.
- Declared adult flags/ratings excluded; absence of flags is NOT an age/safety
  certification; all input images and file IDs are dropped, even if present.
- All results are **pending review**, JSONL text only, and operator scratch
  SQLite metadata is removed on exit. No DB URL/HTTP/Telegram dependencies.
- Atomic normalized output on success. Do NOT run this on production Render
  or save this raw catalog into Neon.

Example using EXISTING LOCAL approved-to-process metadata files:
python -m scripts.bulk_metadata_stage --source acdb=/tmp/acdb.jsonl \
  --source game=/tmp/game.csv --output /tmp/pending.jsonl \
  --report /tmp/bulk-report.json

The upstream provider's real schema must first be mapped to id,name,series,
category. This pipeline does NOT download ACDB, scrape commercial image hosts
or magically convert 148,604 historical ACDB IDs into usable photo cards.
Upstream metadata licensing/attribution obligations must be researched
independently; ACDB lists ODbL + DbCL for its database, **not generic image
copyright clearance**. See https://www.animecharactersdatabase.com/databasedumps.php.

## Storage priority and next measurable release checks

1. Run separate disposal-PostgreSQL 100k character fixture and 50k ownership
   fixture; real table+index growth separately, without assuming 1GB is enough.
2. Prepare efficient exact source-key to approved image URL joins via an
   auditable creator/source-grant bundle (not a fabricated rights flag).
3. Run PostgreSQL EXPLAIN for search/collection/market and only then consider
   index or schema changes. Do not sacrifice numeric IDs, legacy ownership,
   original catcher attribution or transfer history.
4. Review source terms and genuine artist permissions/credits, including
   official project art. Source-wide licenses can reduce manual repetition
   *only when they genuinely cover each included original image*.
5. Do real owner-approved Telegram test of external direct HTTPS photo
   delivery, cached media fallback and collect/trade before release.

**Observed on production as a READ-ONLY diagnostic, 2026-10-21 Myanmar:**
pg_database_size = 8,462,336 bytes (~8.1 MiB); owned_cards 98,304 total
bytes (1 ownership row; index allocation dominates at this tiny scale);
processed_updates 417,792 bytes. Production characters=1,
owned_cards=1, shared cached media IDs=1. These are baseline observations,
not a speed/load test. No production data mutation occurred.
