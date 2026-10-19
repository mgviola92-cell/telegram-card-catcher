# ACDB official metadata SQL source: measured preflight

## Source and observed receipt (2026-10-19)
Verified with the official ACDB data-dump page:
https://www.animecharactersdatabase.com/databasedumps.php
Source data licensing is described as ODbL + DbCL; the artwork on
character pages is **not independently licensed for redistribution**.
Do not copy/hotlink that artwork based on data licensing alone.
Assess attribution, database sharing obligations, and upstream provenance before
publishing derivative bulk data.

One-time bounded metadata-only GitHub Action audit:
https://github.com/mgviola92-cell/telegram-card-catcher/actions/runs/39277429129

| Archive | Compressed bytes | Uncompressed bytes | SQL INSERT statements |
| --- | ---: | ---: | ---: |
| characters.sql.gz | 9,062,776 | 36,862,965 | 36 |
| publishers.sql.gz | 2,301,609 | 8,260,415 | 8 |
| assignments.sql.gz | 594,684 | 3,302,968 | 4 |

The above figures are SQL INSERT **statements**, not character records.
A newer successful full-source audit counted SQL inserted tuples in the real
archives, with a bounded stream parser:

| Archive / table | Raw inserted SQL tuples | Verified unique records | Approved/spawnable |
| --- | ---: | --- | ---: |
| characters | **148,604** | Not yet established | 0 |
| publishers (titles) | **14,664** | Not yet established | 0 |
| assignments (character-title relations) | **221,411** | Not yet established | 0 |

Evidence: https://github.com/mgviola92-cell/telegram-card-catcher/actions/runs/39277834977
The inserted-tuple totals are *real measured aggregates*, not mock counts.
They do NOT establish distinct character IDs, allowed general-audience
records, rights to names/data, character-to-title matching, image coverage,
or a live import. **The 148,604 must not be added to the separate 4,666
metadata count** until cross-source duplicates are actually measured.

### Verified table/relationship fields (from actual SQL DDL)
- `characters`: `id`, `romji`, `japanese`, `publisher`,
  `pid2`, `image`, `thumb`, and other trait/census fields.
- `publishers` (titles): `id`, `english`, `japanese`,
  `mt`, `eechi`, and other metadata fields.
- `assignments`: `cid`, `pid` (candidate character-to-title mapping).

The `publisher` and `pid2` fields in characters are **not yet assumed**
to mean a validated series mapping. Relationship correctness, status flags
and content safety must be tested against actual rows on an isolated runner.

### Safety / licensing / import controls
- SQL data is used to measure aggregate schemas/volume only.
- Dump fields cannot be assumed to define a reliable general-audience
  content filter. Unclassified titles are excluded from any future live import
  until verified suitable for the bot's audience.
- Full raw dumps and images are **not** committed or uploaded as artifacts.
- No development or live DB rows were imported; user collections unaffected.
- Permission-checked, character-specific artwork and matching remain a blocker.
- Baseline separate real anime-character snapshot stays at
  4,666 review-only unique characters / 1,521 primary series (no approved art).
- Future source dedup must report *union counts*, not add all source sizes.

## Next exact sequence
1. Verify inserted tuples report and GitHub head CI.
2. Confirm ACDB key/relationship mapping and discover safe public content
   filtering using documented provenance; reject unknown classification.
3. Stage reviewed metadata, preserve per-source attribution, and measure
   cross-source duplicates against existing 4,666 baseline.
4. Find image URLs with per-file permission and exact character matching;
   do not claim any image approved without evidence.
5. Test only with a disposable/non-live database, then request explicit
   permission for production merge/deployment.
