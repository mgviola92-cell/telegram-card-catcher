# Card Kout — shared images are not ownership records

This is the agreed production-safe design; do not silently replace it.

## Exactly what is and isn't stored
- **Character/spawn artwork:** no image bytes in Neon/PostgreSQL; one approved HTTPS `image_url` and optional Telegram `telegram_file_id` in the shared `characters` row.
- **Alternate artwork:** one URL/file ID per shared `character_variants` row; the same variant art is reused by every owned card that refers to it.
- **User-caught card pictures:** never an image blob, copied URL or separately cached Telegram file ID in `owned_cards`. The existing `get_card` and `get_cards` queries JOIN to the shared artwork record.
- **Ownership:** must still persist **per caught copy** in PostgreSQL: unique card code, `character_id`, `owner_id`, generation, optional `variant_id`, plus necessary favorite/attribution fields. These are small records, not pictures.

**Important distinction:** An HTTPS URL and Telegram media file ID identify **artwork**, not who owns an individual catch. Telegram does not act as our authoritative card ownership ledger. A Telegram message/photo can be unavailable or deleted and cannot safely replace the owner↔card database records.

## How display works
1. Catch stores a compact `owned_cards` row pointing at `characters` and optionally `character_variants`. No media transfer for this step is necessary.
2. Harem/collection/card detail reads the owner’s row and JOINs the correct shared URL and shared Telegram file ID.
3. `app/media_delivery.py` sends the cached Telegram file ID when usable; otherwise asks Telegram to fetch the approved external HTTPS URL. On successful URL send it caches Telegram’s file ID on the **shared art record**, not on the owner’s card.
4. If the cached ID is rejected as stale, clear only that media cache and retry the URL as currently guarded. A missing/deleted Telegram message must not delete ownership.

Example: 100,000 distinct caught copies of the same original Naruto-like character refer to **one** base image URL/file ID, but still require 100,000 small identity/ownership records. Several artwork versions only add a shared URL/file ID *per version*.

## Scale limits and legal rights
- No claim that URL references make PostgreSQL usage zero. A million ownerships still consume indexes/storage. Existing disposable PostgreSQL benchmark: 1,000,000 synthetic cards used **353,796,096 bytes** for the `owned_cards` relation plus its surviving indexes (and **excluded** characters, variants, trade logs, overall database overhead).
- Do not promise a 1 GiB Neon project can always hold a million cards; remeasure realistic rows and workloads in a non-live database.
- Technical access to an external image URL does **not** mean the artwork can be lawfully republished. Require rights evidence, exact character matching, appropriate suitability review, and Telegram reachability before enabling imports.
- Never automatically delete real user ownership, transfer audit, or characters to fit a quota; never migrate or deploy live without explicit permission.

## Protection tests
- `tests/test_shared_artwork_ownership.py` uses disposable PostgreSQL to prove two different owners share one base URL/file ID and a third owned variant resolves a separate shared URL/file ID. Verifies the `owned_cards` table has no image URL/file ID/blob columns. CI outcome should be checked before treating new tests as verified.
- `tests/test_media_delivery.py`, `tests/test_full_flow.py`, and `tests/test_db_integration.py` cover the cached file ID, ownership transfer, variant links and related flows.

This is distinct from source ingestion: ACDB and other registries supply **candidate metadata only**, never default image approvals or ownership records.
