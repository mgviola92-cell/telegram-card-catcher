# Stream a real anime-character JSON snapshot into the bulk pipeline

The old stand-alone `scripts/stage_character_offline.py` from superseded PR #2
would parse the entire upstream JSON snapshot in memory. The current
development branch now offers `scripts/anime_offline_stream.py` supporting
the actual Anime Character Offline Database snapshot structure:
`{"meta": {...}, "data": [...]}`, including `animeAppearances`.

The parser loads ONE character at a time, with a bounded input buffer
(2 MiB) and an explicit hard 300k-record cap. It emits intermediate
metadata-only JSONL and refuses to transfer upstream `images` fields or
other photo URLs. It skips explicit adult flags and entries missing
a named series; absent age flags are **not** proof that the source is suitable.
Source licensing and all artwork rights remain unverified. No internet
download, no Telegram, no production DB, no on-Render cache.

From an operator-provided, legally usable, local JSON snapshot:

```bash
python -m scripts.anime_offline_stream /tmp/characters.min.json \
 /tmp/anime-mapped.jsonl
python -m scripts.bulk_metadata_stage \
 --source mal=/tmp/anime-mapped.jsonl \
 --output /tmp/characters-pending.jsonl \
 --report /tmp/bulk-review-metrics.json
```

The historical snapshot audit was 5,129 source rows -> 4,666 distinct
character IDs across 1,521 primary series. Those are **old observed**
counts and not a claim that this new workflow fetched the latest snapshot
or licensed its images. The matching provider's real data license and
source terms must be checked before running on any external data.

The new 50k-row test generates synthetic snapshots to test streaming.
Production still contains only the previously owned public-domain
Alice sample; draft changes have not been deployed.
