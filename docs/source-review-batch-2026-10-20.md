# Large source-preparation batch — source safety, identity and artwork review

**Scope:** development `feature/large-collection-batch` ONLY. Production
`main`, Render bot and Neon DB must remain unchanged without a separate
explicit approval. The live Telegram bot's original-image + shared Telegram
`file_id` architecture stays unchanged, and **image rendering is off**.

## Current measured source situation
- ACDB official metadata audit: 148,604 distinct declared character IDs;
  14,664 title IDs; 221,411 character-title SQL relations. The relationship
  audit found **five references to one missing character ID**, no missing
  title references, and 148,604 declared characters linked to a valid title.
  These are unique **ACDB IDs**, *not* confirmed unique across catalogs.
- All 148,604 declared character rows had nonblank name and two image-
  pointer **fields**, but the pointer strings are not verified working,
  safe, correctly-matched, legally reusable artworks. No mass import.
- Separate offline source pilot previously staged 4,666 character metadata
  records; its downstream artwork clearance is also pending.
- The source registry has 23 **researched entries**, not 23 approved feeds.
  `enabled_for_import` must stay `false` until evidence review.
- **0 additional artwork rights approved from ACDB or this batch**;
  candidate count never equals spawn-ready character count.

## What this batch implements (read-only review by default)

| Module | Purpose | Guaranteed NON-action |
|---|---|---|
| `scripts/source_identity_review.py` | Build up to 10k deterministic normalized name+series **candidate pairs** across locally staged source arrays (bounded 200k input rows) | Never automatically merges source IDs; never counts collision groups as proven duplicates |
| `scripts/bangumi_review.py` | Optional, at most 5 manually selected public-v0 subject IDs; fetches characters only when a subject explicitly declares `nsfw=false` | No automatic catalog import; no source media URL or image download; no unclassified/mature subject data |
| `scripts/flatten_bangumi_pilot.py` | Deduplicate only within the provider's own character IDs and preserve multiple show relations | Never merges people by display-name coincidence |
| `scripts/artwork_candidate_checklist.py` | From separately found Commons candidates, make a bounded explicit review checklist | License hints, file-page URLs or checkboxes can never auto-grant artwork rights |
| `scripts/source_pipeline_smoke.py` | Offline synthetic subject → character staging → identity candidate → Commons review, checked by CI | Zero network/Telegram/Neon calls and zero imported cards |

### Cross-source identity safety
Different sources can use different IDs for the **same** fictional character,
and different characters can share a name and show title. Therefore:
1. Run the review tool only on *staged, licensed-to-examine* metadata JSON arrays,
   never on raw unapproved bulk dumps.
2. A normalized name+series collision becomes `status=pending`, not a merge.
3. Human decision must be `same` or `different`, with an independently
   reviewed HTTPS evidence reference and a rationale; the program checks the
   **presence** of evidence but cannot establish its authenticity.
4. Three-source transitive conflicts, multiple IDs in the same source merged
   into one character, reused source IDs and ambiguous oversized name buckets
   are rejected or explicitly held for review.
5. Report only **claimed review clusters**, not a global union-unique
   character total. Even accepted identity reviews do not license pictures.
6. No matter what the metadata claims, `artwork_approved` remains zero.

Example (offline with locally staged arrays whose reuse terms were reviewed):

```bash
python -m scripts.source_identity_review \
  mal=/tmp/staged-offline-reviewed.json \
  bangumi=/tmp/bangumi-staged-reviewed.json \
  --output /tmp/identity-review.json
```

The tool accepts a separate `--decisions /tmp/manual-decisions.json` file
of evidence-based pair reviews, but does not write those decisions to the DB.

### New provider pilot — access is **opt-in**
Official provider docs: https://bangumi.github.io/api/ and public v0 OpenAPI.
The code uses exactly these public routes:
`GET /v0/subjects/{id}` and, if explicitly eligible,
`GET /v0/subjects/{id}/characters`. No private API or pagination.
It requires a descriptive `BANGUMI_USER_AGENT` with a maintainer contact
before `--fetch`. **Don't use a fabricated email**; the maintainer must
supply a real appropriate contact first.

Offline dry-run only:

```bash
python -m scripts.bangumi_review 100 --output /tmp/bangumi-dry-run.json
```

Actual opt-in example, **not yet executed**:
```bash
BANGUMI_USER_AGENT='CardKout source review (contact: real-maintainer-address)' \
 python -m scripts.bangumi_review 100 --fetch --output /tmp/bangumi-report.json
python -m scripts.flatten_bangumi_pilot /tmp/bangumi-report.json \
 /tmp/bangumi-review-only.json
```

The example subject ID is illustrative, not a verified eligible character
source. The server's explicit non-sensitive flag is necessary but not enough:
additional audience/content and catalog-rights review remains pending.
Do not bypass account restrictions or provider rate limits.

### Artwork safety
The legacy `scripts/discover_commons_artwork.py` already collects bounded,
unapproved Wikimedia Commons **metadata candidate** rows, not pictures.
Our new `scripts/artwork_candidate_checklist.py` validates the candidate
provenance is genuinely HTTPS from expected Wikimedia hosts, de-duplicates
exact candidate references and writes a per-artwork list of five required
checks (subject/series identity, reuse/derivative rights, attribution,
general-audience suitability, Telegram HTTPS photo compatibility).
Every candidate stays `approved_for_import=false` even with a positive
license hint, because source identifiers alone are not rights evidence.

```bash
python -m scripts.artwork_candidate_checklist \
  /tmp/commons-candidates.json /tmp/artwork-review-queue.json --limit 250
```

No image files are ever written to Neon/Render by any of these source tools.
Even once rights-approved, the intended production model stores *only*
shared HTTPS URL/Telegram `file_id` text and compact per-user ownership IDs.

## Verification / integration
`python -m unittest discover -s tests -v` (regular CI);
`python -m scripts.source_pipeline_smoke` (synthetic integration);
`python -m scripts.benchmark_owned_cards --cards 100000` (localhost
disposable PostgreSQL in Actions). Genuine provider/API/live Telegram
tests are *separate* and must not be described as proven by synthetic tests.

### Important old-branch integration requirement
This development branch predates merged production PR #4, which introduced
numeric `owned_cards.id` references, bold Telegram-native UI and separate
photo/collection handlers. Before merging broad PR #2, resolve conflicts and
retest all numeric card lookups, trading/gifts, ownership, variants and
all existing media send paths against the latest `main`. **Do not merge
an old `main.py` and silently regress the running Telegram UI.**

## Next actual blockers
1. Confirm source metadata and API licensing terms before actual batch imports.
2. Obtain valid provider user agents/credentials if permitted; limit live
   discovery to a tiny reviewed set. No unreviewed mature content.
3. Have a person review each candidate identity and artwork rights; ensure
   images truly depict the intended character with proper credit.
4. Build an import-ready **small verified** catalog only; test against a
   disposable DB and Telegram before expanding. Do not invent 100k approved
   cards from 148k metadata records.
5. Production release only after code integration review and explicit owner
   approval; keep bot actively running on its existing stable release.
