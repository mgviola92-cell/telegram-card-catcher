# Wikidata: bounded source cross-reference candidates

New optional `scripts/wikidata_candidates.py` gathers only **candidate QIDs**
for a small, already staged metadata review queue. It does not make any
automatic identity decisions, download artwork or write to PostgreSQL.
Source status stays `enabled_for_import=false` until rights/data/quality
reviews are separately accepted. Wikimedia's Query Service/API are not bulk
harvesting substitutes.

## Respecting the provider
Wikidata official data-access guidelines require descriptive User-Agent,
limited requests, stopping when rate-limited, and `maxlag` for Action API:
https://www.wikidata.org/wiki/Help:Data_access
The code deliberately uses one `wbsearchentities` search per character,
strictly caps each lookup at five QIDs, and caps an entire opt-in run at 25
staged characters. The default mode is an offline dry run.

## Run with a small existing review queue

```bash
python -m scripts.wikidata_candidates queue.json --max-items 10
WIKIDATA_USER_AGENT='CardKout character metadata audit contact@example.org' \
  python -m scripts.wikidata_candidates queue.json \
    --fetch --max-items 10 --output /tmp/wikidata-review.json
```

The output contains source key, existing staged name/series, candidate QIDs and
two weak text-match hints. **The tool NEVER writes** an importer-compatible
`image_url`, a verified identity mapping, or an artwork approval. Description
text is not exported. Subject suitability and copyright of character
illustrations cannot be inferred from Wikidata's structured metadata license.
An API search result is not proof that two catalogs refer to the same
character; do not merge on name/series alone.

## Verification gates
- Synthetic bounded tests: `tests/test_wikidata_candidates.py`.
- Live API test: **not claimed until an actual opt-in network run succeeds**.
- Real cross-source matches: still **0 human/strong-ID verified**.
- Image rights cleared: **0**.
- Production import: **not permitted** by this proof-of-concept.
