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
