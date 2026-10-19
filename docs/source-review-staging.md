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
