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

## Research-backed anime-style art and public attribution

This batch now includes **one real anime-style character source identity**
(Wikimedia project mascot **Wikipe-tan**) with **two distinct actual Commons
PNG artworks** (base and alternate) in
`data/commons_anime_style_pilot_candidates.review.json`. The corresponding
staged catalog has exactly one character metadata row, without an approved
image link. Copyright/artist attribution is researched from the actual file
description pages and **no new art has been imported**. The illustrator's
name (Kasuga) and the original file licensing alternatives (CC BY-SA 3.0 and
older; full-length sailor art also 4.0) are recorded as **review hints**,
not automatic human approval. Additional creator-controlled source leads
(Kiki from Krita / Pepper from Pepper&Carrot) contain no approved images.

The shared image tables now optionally include author, license name,
license URL and original file-page link as **metadata only**. The
`owned_cards` table still never stores image URLs, source URLs, author
names or picture bytes. `app/artwork_credit.py` renders author/license
under original Telegram photo captions, hides spoiler-containing source
filename links during wild spawns, and displays a Source link on
`/check` after the card is collected. HTML is escaped; Telegram renders
the unchanged remote original PNG, **no PIL/photo collage**.

Source and variant importers now preserve four-field attribution, and
approval manifests must match any supplied credit fields **exactly**. The
manual review-to-catalog assembler carries verified credit fields to both
sides of that check. Existing uncredited test/legacy entries remain
backwards-compatible; newly introduced CC works should not be published
without an independently reviewed author/license/source reference. CI
includes source/manifest and HTML escaping/spoiler tests and actual
**disposable Postgres** original-to-variant credit lookup tests. Source
research details and outstanding permission/delivery checks:
`docs/open-anime-art-pilot-20261020.md`.

**Honest status:** Two real illustrated files and a licensed-page claim
have been researched, not validated by actual Telegram photo sends, and
not added to production. This is an infrastructure proof, not evidence that
the 148,604 ACDB character IDs have reusable artwork. Popular copyrighted
franchise art and AI-generated fan art still require source-specific rights
checks.

## New collector tools and consent-only group trade board

- **`/duplicates`:** group owned copies by exact character identity and
  count generations/alternate art as duplicates, showing up to 10 names.
  Never expose per-user image URLs or list other collectors' private cards.
- **`/missing EXACT SERIES NAME`:** list up to 12 enabled-catalog character
  identities this specific player has not yet caught. This can reveal
  characters but not other players' owned-card IDs, and only runs on demand.
- **`/listcard OWNED_ID`:** opt-in to an expiring **24-hour virtual swap
  advertisement** in the current group; 5 active cards per seller maximum,
  enforced by a per-seller PostgreSQL transaction lock and current ownership
  check. Updating one's own listing is permitted without bypassing quota.
- **`/market`:** browse up to 8 active offers only in the same group, showing
  numeric owned-card ID, character and owner mention. Expired listings and
  cards that changed owners are automatically hidden from browsing and
  excluded from quota.
- **`/unlist OWNED_ID`:** current owner and original advertiser only can
  withdraw a listing. Only the owner can list a card; nobody can list a
  different user's card. Existing legacy codes resolve to the same numeric
  owned-card ID.
- A listing never transfers or charges for a card. Two players must still
  negotiate via reply-to-member `/trade MY_ID THEIR_ID`, where the receiver
  explicitly accepts and ownership is verified under row locks. Successful
  `/gift` and `/trade` settlement deletes any listing for transferred
  cards **in the same database transaction**. No real-money marketplace,
  cryptocurrency, currency ledger, purchases or gambling are implemented.
- `market_listings` stores only `card_id`, `seller_id`, `chat_id`, listing
  and expiry timestamps (NO pictures, URL copies, file IDs or art credits).
  Indexes support by-group lookups and per-seller quota counts.
- Manual database maintenance also supports old expired listing cleanup
  after at least **7 days past expiry**; default **14 days**, bounded to
  2,000 rows/table per invocation. It never deletes cards, transfers or
  still-processing webhook inbox records. No scheduled background job.

Real disposable PostgreSQL tests cover ownership, legacy/numeric ID refs,
duplicate listing refresh, 5-card quota, group isolation, stale/expired
invisibility, seller revocation, atomic gift/trade delisting, copy-aware
collection queries and cleanup with preserved active listings. The native
Telegram HTML formatting is tested, but actual two-member Telegram group
acceptance remains a separate release requirement. These features are on
the **unmerged** integrated development PR, not on the deployed Alice pilot.

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
