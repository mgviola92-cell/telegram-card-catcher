# Owned-card storage: shared artwork and disposable PostgreSQL measurements

## Agreed data model (do not regress)
- Neither spawn art nor individually caught-card art is stored as image bytes in PostgreSQL or Render.
- `characters` and `character_variants` hold one HTTPS image URL and optional Telegram `file_id` per **shared artwork identity**.
- `owned_cards` stores the ownership link and individual card identity: owner, character, optional variant, code, generation, timestamps, favorites and attribution. It **does not store image URLs or blobs**.
- The collection and card detail queries join to shared art; `app/media_delivery.py` tries Telegram's cached file_id first and falls back to the approved HTTPS URL.
- Hundreds of thousands of card copies increase **ownership and index records**, not per-card image storage.

## Why index storage matters
`owned_cards_generation_unique` is a unique btree on `(character_id, generation)`.
The former plain `owned_cards_by_character` btree had the same columns and
ordering; it was a redundant second copy of the same lookup path.
The *fresh* development schema no longer creates this redundant btree.
No existing database is automatically migrated or touched by this change.
Do not drop any other index without real query-plan and storage verification.

## Verifiable, safe footprint experiment

`scripts/benchmark_owned_cards.py` creates an isolated disposable schema
using the exact repo schema, inserts a mix of 100 synthetic characters and
card ownerships, runs generation/owner lookup probes, and deletes its schema.
For parity, it temporarily re-creates the **legacy duplicate index inside the
isolated test schema only**, measures the difference, and drops it there.
It requires `TEST_DATABASE_URL` pointing to **localhost** and a database whose
name starts with `cardkout_test`; it refuses production fallback.

Run locally against a disposable PostgreSQL instance:

```bash
TEST_DATABASE_URL=postgresql://test_runner:password@localhost:5432/cardkout_test_ci \
    python -m scripts.benchmark_owned_cards --cards 100000
```

### Recorded measurements (GitHub Actions disposable PostgreSQL 16)

| Simulated workload | With duplicate index | Without duplicate | Index savings | Without duplicate / card |
| --- | ---: | ---: | ---: | ---: |
| 100,000 owned cards; 100 shared characters | 38,551,552 bytes | 33,816,576 bytes | 4,734,976 bytes | 338.17 bytes |

Source: GitHub Actions 39274470832 (CI run executing the opt-in 100k experiment).

These are **real PostgreSQL relation/index sizes for synthetic test rows**,
not actual production Neon measured row sizes. They omit character/variant
storage, all other tables, Postgres overall DB overhead, bloat and actual user
distribution. Do **not** extrapolate a guaranteed 1 GiB capacity or change
a live instance based on this synthetic benchmark alone.

## Production safety
- No user collections, codes, generations, transfers or ledger entries are
  ever automatically deleted to save storage.
- No index removal, schema migration, bulk import, or cleanup is executed
  against Neon production without explicit user approval.
- Existing deployed databases may still have the redundant index. Removing
  it would require a separate reviewed migration and checks that it exactly
  duplicates the unique index, plus suitable operational timing.
- No polling/scheduled Neon usage was added.
