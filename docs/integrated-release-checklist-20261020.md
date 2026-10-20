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

## Actual controlled storage measurement (GitHub Actions)

Run 39410238385 on 2026-10-20 executed a 50,000-card
image-free synthetic owned-card benchmark against disposable localhost
PostgreSQL 16. It reported 6,299,648 bytes heap growth,
11,116,544 bytes ownership index growth and 17,416,192 bytes total
growth. The observed total is approximately 348.32 bytes **per synthetic
owned-card row including current indexes**, versus the earlier unsupported
512 bytes/row planning placeholder. The benchmark transaction was rolled
back, with 0 production rows written. Test and synthetic ownership
distribution, indexes, page alignment, free space and fill factors differ
from actual Neon workload; **never multiply this number to promise a Neon
plan can fit 1 million cards**. All character metadata, artwork URLs,
transfer logs, user offers, WAL and database overhead are additional.

The most actionable observation is that indexes are more than half the
observed delta. Before millions of cards, use EXPLAIN (ANALYZE, BUFFERS) on
the disposable DB and review redundant indexes against actually used
query patterns. Do NOT drop existing unique or lookup indexes on production
without measuring. A smaller row estimate is not equivalent to a safe
database quota forecast.

## Scalable spawn selection — actual bot optimization

Previous spawn SQL selected **one random character by sorting every enabled
character row** for every spawn. That becomes wasteful with a large catalog.
The development bot now uses `app/weighted_catalog.py`:

- For each bot worker process, a **compact cached** list of numeric
  character IDs and cumulative spawn weights is created **only on an actual
  spawn attempt**. All DB reads run in the already-open spawn transaction.
- The list is built with a PostgreSQL server-side streaming cursor, using two
  packed uint64 arrays. **100,000 weighted character IDs use 1,600,000
  bytes of array payload**, instead of a giant list of full artwork rows.
  Real process overhead and driver buffering are extra.
- `secrets.randbelow(total_weight)` + binary search provides the same
  relative weight distribution as weighted random sampling in a single
  selection, without sorting the full table at every spawn.
- Cache rechecks every **5 minutes of activity-driven use**; if the catalog
  is empty it retries after 30 seconds. NO background polling, timers,
  constant database connections or artificial spawn messages are introduced.
- The chosen ID is rechecked against current `enabled=true` and positive
  weight, with a row share-lock inside the short transaction. If the ID
  became disabled, the snapshot is invalidated and retried (max twice).
  Source changes and newly enabled characters can take up to 5 minutes to
  appear in an otherwise still-valid worker snapshot.
- Both base and alternate-artwork shared URL/file-ID delivery remains
  unchanged. This optimization does not fetch or render images.

Dedicated tests generate **100,000 metadata-only IDs** (synthetic),
verify 1.6MB array storage, randomness boundaries, cache expiry, empty
catalog behavior and stale-character prevention; real disposable PostgreSQL
tests verify the named streaming cursor works and disabled selections are
reloaded correctly. These tests are not proof of a licensed 100k-character
artwork catalog or of throughput under multiple large Telegram groups.

## Webhook reliability: durable claim, success ACK, and retry

Previously the webhook wrote `processed_updates(update_id)` **BEFORE**
calling `bot.process_new_updates`, then returned 200. If a handler raised
or the Render worker crashed, the same Telegram update was blocked forever,
so a catch or button event could be silently lost. The integrated dev branch
now uses a lightweight PostgreSQL inbox state machine:

- `status=processing` when an update is atomically claimed;
- `status=done` only after the synchronous handler returns successfully;
- `status=failed` if handler processing raises, so a repeat delivery can
  be claimed again;
- a three-minute lease for abandoned processing rows after a worker crash,
  and a monotonically increasing attempt counter used as an update fencing
  token;
- completed repeats return HTTP 200 without rerunning the handler;
  already-processing repeats return HTTP 503 (Retry-After: 2) **instead**
  of falsely acknowledging work still in flight;
- wrong webhook secret, invalid JSON, bad update IDs and Telegram parse
  failures are rejected before claiming;
- a broken update-completion DB write also returns HTTP 503 rather than
  giving Telegram a false 200;
- legacy rows created by the previous webhook are assigned status=done
  on additive migration so old updates do not replay unexpectedly.

`tests/test_webhook_guard.py` checks fail/retry/done semantics,
lease-crash reclamation, legacy completed updates, and stale fencing-token
prevention on an actual disposable localhost PostgreSQL. New Flask route
tests cover authenticated success, malformed messages, duplicates, busy
requests, handler exceptions, failure release and completion failures
without Telegram API calls or bot tokens from Render.

**Important limitation:** this is **at-least-once delivery**, not a
transactional outbox. If Telegram's send succeeds but a worker crashes
before recording `done`, retry can repeat the outgoing message. Existing
claim and gift/trade storage operations have transaction-level guards,
but true exactly-once photo/message output needs a separate durable
outbox/operation-ID design. Do not claim complete crash-proof reliability.

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
