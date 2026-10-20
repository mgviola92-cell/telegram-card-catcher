# 2026-10-20 source staging — live-UI-safe feature PR

This branch starts from the exact post-UI-production `main` version so
the running Telegram bot's numeric card IDs, native bold captions, catch,
favorites and shared media delivery are **not** overwritten by older code.
All source tools are offline by default and have **no production DB writes**.

## What is implemented

- `scripts/source_identity_review.py`: review metadata from at most
  200,000 *already staged/licensed-to-review* character records across
  separate sources; deterministic name+series collision pairs **only**.
  Refuses duplicated source IDs, expands at most 10,000 pairs, and skips
  ambiguous crowded buckets. Explicit evidence-based human decisions are
  checked for transitive contradictions and same-source ID conflation.
  No guessed global union-unique count; no approved art or automatic merge.

- `scripts/bangumi_review.py`: opt-in public API v0 source review for at
  most five manually selected subjects, requiring a real project/contact
  user-agent. The subject must explicitly report `nsfw=false` before even
  requesting related character metadata. Unclassified/restricted subjects
  are *not queried further*. No private endpoints, pagination, artwork URLs,
  image downloads, auto-merge or import; source terms remain to be reviewed.

- `scripts/flatten_bangumi_pilot.py`: organize character IDs from an
  eligible and already reviewed pilot response; de-duplicate only by the
  provider's own ID while tracking additional series/subjects. Do not assume
  first series is canonically correct. Reject copied image IDs/URLs.

- `scripts/artwork_candidate_checklist.py`: transform Wikimedia Commons
  research candidates from an existing pipeline into explicit per-file human
  checks: matching subject, reuse/derivative rights, attribution/licensing,
  audience suitability, and Telegram HTTPS delivery. License hints do not
  confer reuse rights, and **all** rows remain unapproved.

- `scripts/source_pipeline_smoke.py`: end-to-end synthetic smoke test of
  source → staged metadata → identity queue → artwork checklist. **0 network
  requests, 0 DB writes, 0 image bytes saved, 0 approved media**.

## Usage (offline only)

```bash
python -m scripts.source_pipeline_smoke
python -m unittest discover -s tests -v
python -m scripts.bangumi_review 100 --output /tmp/bangumi-unchecked.json
```

For an optional source API request after verifying provider rules/terms,
see the adapter's `--help` and use a genuine responsible User-Agent contact.
No default network requests are made. Review data is **not importer-ready**.

Already authorized local metadata arrays can be compared without importing:
```bash
python -m scripts.source_identity_review \
  offline=/tmp/your-allowed-staged-source.json \
  another=/tmp/another-allowed-staged-source.json \
  --output /tmp/identity-candidates.json
```

## Source-to-catalog manual release gate (added next batch)

The existing production `scripts/import_characters.py` CLI used to import
whenever invoked with a catalog file. On this **unmerged development branch**
the importer is now **dry-run-first**: by default it **never connects to
PostgreSQL**. Actual writes demand all four deliberate signals:
`--apply`, `--approval-manifest`, `--rights-reviewed`, and
`--confirm-database-write IMPORT_APPROVED_CARDS`. The internal
`import_batch(items, approvals)` API ALSO rejects absent/inconsistent
per-character permission rows. All upsert batches use one PostgreSQL
transaction, so failure is not a half-imported catalog.

New `scripts/build_reviewed_catalog.py` accepts two **manually prepared**
inputs: staged character metadata and a **separate human decisions file**
keyed by exact `source_key`. Approval records must explicitly include
`status=approved`, a selected `image_url`, a detailed reviewer explanation
and five distinct evidence types:
- `subject_identity` — exact picture/character/series mapping;
- `source_metadata_terms` — dataset access and reuse rights;
- `artwork_public_reuse_rights` — permission or sufficiently public artwork;
- `general_audience_suitability` — image/character safety assessment;
- `telegram_photo_reachability` — delivery compatibility check.

All evidence fields are HTTPS *pointers to review evidence*, not automatic
proof of legality or content suitability; manual independent verification
remains essential. Pending/rejected rows are **not** emitted. Other source
image pointers cannot override human-reviewed URLs. The prepared output
contains one catalog row plus one image approval reference **per approved
character**, and no actual image bytes or individual owner image references.

Example after a human has really completed these reviews:

```bash
python -m scripts.build_reviewed_catalog \
  /tmp/licensed-stage.json /tmp/actual-human-review.json \
  --catalog-out /tmp/manual-approved-catalog.json \
  --approvals-out /tmp/manual-artwork-approvals.json
python -m scripts.import_characters /tmp/manual-approved-catalog.json \
  --approval-manifest /tmp/manual-artwork-approvals.json
```

Both commands above are **offline/dry-run**, no Telegram/Neon activity. A
reviewer would need to authorize and separately run the explicit write
command after ensuring it targets a disposable local DB, then inspect
results before *ever* considering live import. The current owner has **not**
authorized a production source import.

### Local PostgreSQL integration
GitHub Actions now provisions its own disposable PostgreSQL 16 instance
named `cardkout_test_ci`, with `TEST_DATABASE_URL` restricted by test code
to localhost/127.0.0.1/::1 and a `cardkout_test*` name. Integration tests
import a manually-approved synthetic fixture, create a card, verify the
existing numeric card ID and owner remain unchanged, confirm that a second
import with the same URL preserves cached Telegram `file_id`, and that
changing a source URL invalidates the *shared* `file_id` but not ownership.
No test writes to Neon; no test downloads artwork. UI/native captions and
current live Telegram bot stay exactly as they were.

### Turning large staged metadata into a manageable real-review batch

New `scripts/prepare_review_queue.py` selects at most **5,000** candidate
identities from up to 200,000 *existing, permitted-to-review* source
metadata rows. Round-robin sampling gives separate shows opportunities in
the initial review and avoids burning an entire small batch on a single
famous title. Deterministic source/character ordering makes the result
reproducible. All new review records explicitly have
`status="pending"`, `image_url=null` and five `evidence=null` fields;
the script never copies provider picture URLs or blesses a discovered image.

```bash
python -m scripts.prepare_review_queue \
  /tmp/allowed-metadata.json /tmp/pending-character-review.json \
  --limit 200 --max-per-series 5
```

Each record should be independently researched and reviewed before its
fields are edited. A reviewer changes **only genuinely verified** records
to `approved`, provides the correct licensed HTTPS art, five supporting
evidence URLs, and a substantive note. Rejected/unfinished records stay
excluded when `scripts/build_reviewed_catalog.py` produces a candidate
release. The pipeline enforces review consistency, not the truth of
evidence URLs; actual legal review and identity verification remain manual.

## Source status / remaining work

Earlier official metadata audits (in older separate development PR #2)
measured 148,604 distinct **ACDB source character IDs**, 14,664 title IDs,
and 221,411 relationships. The licensed image and cross-source identity
statuses are **not approved**; 148,604 data records do not imply 148,604
available Telegram card images. Another pilot staged 4,666 metadata-only
character entries. There is no claim that those catalogs were imported.

This PR is strictly source-review groundwork and is intentionally separate
from the large older trading/database branch. That older branch's main.py
must never be merged without reconciliation against the current live UI.
Do not enable imported cards or auto-deploy until rights, audience/content
suitability, original image vs character match, and cost are verified.

**User preference maintained:** no card image rendering; one shared approved
artwork URL plus cached Telegram `file_id` per character/variant; `owned_cards`
stores owner/code/id/generation/variant references, not picture bytes or
per-user artwork URLs. No extra images are generated or stored by these tools.
