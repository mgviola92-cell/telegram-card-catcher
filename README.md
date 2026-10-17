# Telegram Card Catcher

Character collection bot for Telegram, influenced by Character Catcher (name-guess spawns and global harem) and Sofi (planned collection customization). **Development only — not deployed or live-tested.**

## Implemented now
- Auto character spawn by group message count (admin configurable with `/changetime 10..500`).
- First correct free-text character name or alias wins; 15-minute spawn expiration, DB row locking for one winner.
- 10-character unique alphanumeric card code and serialized per-character generation.
- `/harem` / `/collection` / `/recent`: global collection, eight entries/page, inline next/previous.
- `/check CODE` / `/view CODE`; `/start`, `/help`.
- Telegram direct HTTPS URL and cached `file_id` fallback; failed image sends cancel the spawn.
- Rarity metadata for Common, Uncommon, Rare, Legendary, Mystical, Divine, CrossVerse, Cataphract, Supreme, CNFT; configurable per-character spawn weights.
- Validated JSON character importer, CI workflow with offline validation unit tests.

## Character data import
No real artwork/characters are supplied. `data/characters.example.json` is illustrative only — **example.com URL will not work**. Use *licensed/permitted* publicly reachable HTTPS image URLs and unique `source_key` values. Edit or create a JSON array and run:

```bash
python -m scripts.import_characters data/your_characters.json
```

Required fields: `source_key`, `name`, `series`, `image_url`.
Optional: `aliases`, `category`, `rarity`, `weight` (1..10000).
Importer upserts in one DB transaction. Changes to an existing image URL do not automatically invalidate a cached Telegram `file_id`; clear it if replacing art.

## Render + Neon setup (not performed)
1. Create independent Neon Postgres database.
2. Create Telegram bot with BotFather; set privacy **disabled** to receive ordinary group guesses.
3. Set Render environment variables from `.env.example`: `BOT_TOKEN`, `DATABASE_URL`, `WEBHOOK_SECRET`, `PUBLIC_BASE_URL`, `SPAWN_MESSAGES`.
4. Deploy web service from `render.yaml` **only after approval**. Database schema is initialized on app startup.
5. Register Telegram webhook once after deployment from a trusted environment: `python setup_webhook.py`. Never commit secrets.

## Caveats before production
- Webhook update deduplication, retry-safe delivery, daily claim caps, and monitoring remain incomplete.
- Live PostgreSQL integration and Telegram API testing have NOT been performed. GitHub Actions is only syntax and isolated unit checks.
- Free Render instances sleep; no background timers will reliably run while sleeping.
- High-volume random weighted character selection should later be optimized for large catalogs.
- Marketplace/trades, 3-card Sofi drop, visual cards, AI original art, cosmetic frames, favorites, rarity balances, quests, raids, guilds, and other agreed features remain on roadmap.
- No real-money/crypto/NFT commerce is implemented.
