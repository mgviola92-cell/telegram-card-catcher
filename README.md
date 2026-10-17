# Telegram Card Catcher — Phase 1 Starter

Telegram collectible-character bot, inspired by Character Catcher and Sofi gameplay. **Development starter, not production-ready.**

## Implemented
- Group activity-count spawns with first correct name claim.
- Global per-user collection with `/harem`, `/collection`, `/recent`.
- `/check CODE` / `/view CODE` inspect a card.
- `/changetime COUNT` group-admin spawn setting (10–500).
- Individual unique card codes; per-character generation; PostgreSQL locking to avoid concurrent duplicate claims.
- Image URL via Telegram with subsequent `file_id` cache and text fallback.
- Flask Telegram webhook, Render Free blueprint, Neon PostgreSQL schema.

## Still needed before live usage
- Populate `characters` database: there are **no supplied characters or images yet**.
- Configure Telegram BotFather privacy setting off for normal group text guesses.
- Create a new Neon database and a Telegram bot token; supply environment variables to Render.
- Deploy only when explicitly requested. Register webhook once with `setup_webhook.py` from a trusted environment.
- End-to-end and database integration testing; idempotent webhook update handling, active spawn expiration, retry controls.
- Daily caps, collection UI, full rarity weighting, trading, gifting, Sofi multi-card drop, variants, marketplace, image rendering, quests and events.

## Environment
Copy the names from `.env.example` into Render Secrets:
- `BOT_TOKEN` — Telegram bot token, **never commit**
- `DATABASE_URL` — private Neon PostgreSQL connection URL
- `WEBHOOK_SECRET` — strong random secret accepted as Telegram secret header
- `PUBLIC_BASE_URL` — actual deployed https service base
- `SPAWN_MESSAGES` — default group messages between spawns (default 35)

Render start: `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 main:app`.
The app initializes schema at startup. The Telegram webhook needs separate registration after service deploy.

**Important:** The starter's `characters` table is initially empty, so spawns will not produce art until data is imported. Free Render may sleep, and local files are ephemeral. Database and Telegram media caching are the intended persistent paths.

## Design roadmap
Maintain existing plans for 10 reference rarity categories, anime/manga/manhwa/webtoon/game/original character pools, unique code/variant support, profile art, cards, favorites, search, trade, gift, market, economy, crafting, evolution, guilds, raid, achievements, events, and optimized URL / file_id / Pillow delivery. These are roadmap features, **not yet implemented**.
