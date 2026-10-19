# Telegram pilot first (no production merge/DB writes yet)

## Current status, not assumptions
- Feature branch: `feature/large-collection-batch`.
- A one-character **public-domain literary artwork** pilot fixture is at
  `data/telegram_pilot_catalog.json` with one matching, explicit
  `data/telegram_pilot_artwork_approvals.json` record.
- Character: Alice from *Alice's Adventures in Wonderland*. This is a visual
  SEND/URL-CACHE/CATCH test, **not** a claim that 148,604 anime characters
  and their copyrighted art are release-ready.
- Original artwork by John Tenniel, 1865, Wikimedia Commons PDM declaration:
  https://commons.wikimedia.org/wiki/File:Alice_in_Wonderland,_Drink_me_by_John_Tenniel.jpg
- Image URL points straight to the Wikimedia original JPEG. No image files
  are stored in PostgreSQL or Render. Reusing this sample in another
  jurisdiction requires obeying applicable laws and source restrictions.

## Automated checks
- `python -m scripts.pilot_preflight --catalog data/telegram_pilot_catalog.json --approvals data/telegram_pilot_artwork_approvals.json` checks the one-character metadata and matching permission-reference manifest. CI runs it.
- `python -m scripts.seed_telegram_pilot` does **not** open the DB.
- `tests/test_telegram_pilot_flow.py` creates a catch, looks up owner
  `image_url` via the shared `characters` table, and verifies Telegram's
  returned `file_id` is cached **once per shared artwork**, not owner.
  This uses disposable PostgreSQL and a mocked Telegram call; it does not
  prove Telegram actually received a photo yet.

## Minimum actual Telegram test prerequisites (before live actions)
**Prefer a separate staging Telegram bot and a separate test Postgres DB.**
The same bot token cannot have a production webhook and staging webhook both
receiving updates. Switching a live bot's webhook is disruptive, so do NOT
do it implicitly.

1. Confirm the Render workspace and service to use for the card bot. Do not
   alter a different user's or project's services.
2. Choose **separate staging BotFather bot token** + dedicated non-live
   database with name beginning `cardkout_test`, or explicitly approve a
   controlled live-bot test with its implications. Keep secrets in Render
   environment variables, never GitHub or chat.
3. Test DB seed (explicitly opt in):
   ```bash
   TEST_DATABASE_URL='postgresql://.../cardkout_test_pilot?...' \
      python -m scripts.seed_telegram_pilot --apply
   ```
   This refuses missing/unsafe `TEST_DATABASE_URL` and equality with
   `DATABASE_URL`. Do **not** do this against production Neon.
4. Configure the staging web service with the staging bot's `BOT_TOKEN`,
   separate test `DATABASE_URL`, `WEBHOOK_SECRET`, `PUBLIC_BASE_URL`,
   `SPAWN_MESSAGES=10`, and deploy **only after confirmation**. Check that
   webhook URL points to this service and token is the intended test bot.
5. Run `python setup_webhook.py` *once* in a trusted configured environment
   with the staging bot token; it changes that bot token's active webhook.
   This must never silently steal the existing live bot's webhook.
6. Add staging bot to a private test group, disable BotFather group privacy
   for that bot, and send ten normal chat messages (commands do not count).
   Expected: a photo appears, no visible character name. Guess `Alice`
   as a text message (or `/catch Alice`). First successful catcher receives
   a code and Gen 1. Test `/harem`, `/check CODE`, `/showcase`, and
   `/fav CODE`; confirm the SAME shared photo is used on repeat sends.
   Test gift/trade with a consenting second user only if desired.
7. Keep user-card ownership records even if a photo URL goes down; do not
   delete real users' cards as cleanup.

## Why this still needs a Render/workspace choice
The user has asked to test on Telegram, but exact Render workspace/service
and whether a separate staging token is available are not yet confirmed.
GitHub tests and a static `/health` reply are not live Telegram end-to-end
evidence. As of this doc, **no active Telegram webhook/photo/catch test was
performed, and no production deployment was triggered**.

## Next plan after live pilot
Only then proceed with sources: ACDB image-pointer reachability/licensing
checks, Wikidata cross-references, justified de-duplication, age-suitable
catalog review, and staged test imports. Database contract is unchanged:
`owned_cards` stores IDs/code/owner/variant; not image bytes or URLs.
