# Card Kout unified development handoff — 2026-10-20

Status: DEVELOPMENT DRAFT. This branch starts from the latest working social
feature branch (PR #6) and incorporates all rights-guarded source staging
modules and tests from source PR #5. Production GitHub main, Render bot and
Neon data are unchanged; no new characters or rights-approved photos
have been imported. Do not merge old pre-numeric-UI PR #2 without review.

## Systems now combined

- Working existing Telegram spawn/catch + numeric /check, /harem, /fav,
  /unfav, /search UI. Native Telegram text/HTML formatting. NO image rendering.
- Opt-in reply-to /gift and /trade offers, recipient-only approval, 10-minute
  expiry, transactionally atomic ownership and append-only transfer audit.
- /top, /gtop, /today rank original catchers; /stats, /progress, /series
  count distinct characters rather than counting copies/generations twice.
- Optional approved shared-artwork variants. Newly created variant rows are
  disabled by default, and a caught card retains a numeric variant_id even
  after gifts and trades.
- Source staging for at most 200,000 metadata rows, identity review, limited
  public Bangumi API metadata adapter, four actual Commons example file
  candidates (NOT automatically approved), human-only character/artwork
  rights/evidence review queues, and exact approval manifests.
- Character importer and artwork variant importer both default to NO DATABASE
  WRITE and require per-image human-reviewed provenance plus explicit apply
  confirmation before touching any database.

## No image bytes in the database

Characters and shared artwork variants only store HTTPS URL text and an
optional reusable Telegram file_id string. Owned cards store numeric IDs,
character/variant/owner/generation references and other small metadata. User
card copies never store URLs, photo bytes, copies, blobs or separate file_ids.
All artwork is original remote URL/Telegram-hosted file ID, not a rendered
card/photo made on Render.

## Storage conservation and performance

A new operator-only script, scripts/database_maintenance.py, audits the
database and table/index footprint without deleting anything. Its manual
apply mode is confirmed separately and removes ONLY stale processed update
dedup rows (at least 14 days old) and ephemeral offer records (at least
90 days old), at most 2,000 per table per call. It explicitly does NOT
remove owned cards, catalog entries, artwork or card_transfers history.
MAINTENANCE_DATABASE_URL must be deliberately configured, rather than
silently reusing the production bot connection. No automatic idle polling.

A separate scripts/benchmark_owned_cards.py measures heap/index growth
using 50,000 rolled-back image-free fixture cards on a disposable localhost
PostgreSQL named cardkout_test*. This reports actual observed bytes-per-row
under ONE synthetic distribution, not Neon Free quota promises; the
test database is disposable because rollback does not necessarily shrink
relation page allocations. The other integration tests use the same local
PostgreSQL service and never production Neon.

## How to verify locally

  python -m unittest discover -s tests -v
  python -m scripts.source_pipeline_smoke
  python -m scripts.import_characters /tmp/catalog.json --approval-manifest /tmp/proofs.json
  python -m scripts.import_variants /tmp/variants.json --approval-manifest /tmp/variant-proofs.json

The last two commands are dry runs; they require real human evidence-reviewed
JSON inputs and are not launch instructions. Do not set --apply without
explicit owner approval and validating target database.

## Before a real release

1. Confirm the green GitHub Actions result on the exact unified branch head.
2. Verify character identities, metadata source terms, image reuse/credit
   rights, audience suitability, and real Telegram HTTPS delivery. A
   provider URL, AI-generated label or image filename is NOT artwork license.
3. Run migrations against a disposable DB; test spawn -> catch -> numeric
   /check -> gift/trade two consenting users -> variant and progress in a
   separate test group. Check ownership remains correct across variants.
4. Get explicit approval before real Neon schema migration, catalog import,
   branch merge and Render deployment. Do not modify the live Alice pilot
   silently. Review actual Neon relation/index bytes before large releases.
5. Monitor bot logs and storage after a small approved release; expand
   gradually once verified.

## Critical remaining blocker

The 148,604 ACDB source character identifiers and ~4,666 staged metadata
records are not a cleared anime/game photo collection. Large-scale useful
cards require a lawful, reliable artwork review/import supply and matching
Telegram playback/delivery checks. The source adapter and synthetic tests
are infrastructure, NOT proof that huge catalogs have real permission to
republish character images. The existing two-group-trading test is on
disposable Postgres, not a real Telegram live-group test. Production remains
on the previous UI pilot until separately authorized.
