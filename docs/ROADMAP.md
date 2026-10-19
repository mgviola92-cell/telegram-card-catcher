# Card Kout — full project scope
The following are designs, **not all implemented**.

## Core
Character Catcher style message-based hidden-name drops, first correct guess, global harem, /hmode, /fav, /mfav, /unfav, /search, /check, /trade, /gift, /top, /gtop, /todaygtop, /changetime. Sofi-inspired card codes, collection filters, three-card drops, wishlist, inventory, frames, cosmetics, packs.

## Content
Anime/manga/manhwa/webtoon/game/waifu/husbando and original AI characters. Thousands to tens of thousands of catalog records with provenance, rate limits, deduplication, image rights review, URL checking, alternate artwork and generation per card. Use general-audience appropriate artwork.

## Economy / later
Silver, gems, virtual shop and marketplace with no cash-out, cards trade/gift, audit ledger, quests, achievements, raid/guilds, albums, collection completion, badges, event rotation, crafting and evolution. Do not implement gambling or real-money/NFT exchanges.

## Image/hosting
URL send first, file_id caching on Telegram, Pillow-generated cards on demand, cache hashes for variants. Database remains on Neon, never store image catalogs on Render free ephemeral disk. Respect platform rate limits. Render free sleeps and has limited bandwidth.

## Release gate
All changes on feature branches; Python unit and DB integration checks; no merge into main until review. Live Telegram test needed for concurrency, admin permissions and callback UX. Never assume a successful CI unit test proves full bot operation.

## Implemented on development branch only (not live)
- Rate-limited AniList JSON metadata exporter with manual review gate; no live import or mass image scraping.
- Catalog variant schema and variant metadata importer.
- Optional variant artwork selection on group spawn; captured card retains its exact variant_id.
- /showcase sends recent/featured artwork through Telegram URL or cached file_id.
- Atomic gift/trade, transfer audit, group and global rankings.
- Unit tests and Python syntax CI. Real database schema migration and network/API testing are still required.

## Known release blockers
- Validate full migration on a Neon test database before main merge.
- Verify Telegram API photo behavior for alternate art (variant-specific file_id caching pending).
- Avoid mass imports unless source image use is permitted.
- Verify webhook retry/idempotency semantics (an update recorded before handling can be lost on crash).
- Confirm rarity/spawn probability balancing; 25% artwork-variant selection is provisional.
