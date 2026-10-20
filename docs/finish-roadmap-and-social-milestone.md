# Finishing the Card Kout bot: current blockers and verified social milestone

Status: **this branch is development-only**. It branches from deployed
`main` (`d985d5f`) and does not merge or deploy by itself. The original
Alice pilot, numeric owned-card IDs, Telegram-native HTML typography, and
shared approved artwork URL/`telegram_file_id` must be preserved.

## New opt-in player functionality (this branch)

- **Gift:** reply to a real group member's message with `/gift MY_CARD_ID`.
  Bot creates a 10-minute offer; recipient explicitly accepts or declines.
  No unilateral transfer, no acceptance by third parties, no self-gifting.
- **Trade:** reply to the other person's group message with
  `/trade MY_CARD_ID THEIR_CARD_ID`. The recipient explicitly accepts
  or declines; both card owners are rechecked under PostgreSQL row locks.
  Atomic swap and audit ledger, no double settlement.
- Both commands accept existing numeric `owned_cards.id` or legacy
  alphanumeric code; all user-facing output uses short numeric IDs.
- Pending offers are bounded to 8 per sender per type in a rolling 10-minute
  window. An expired or outdated offer cannot alter ownership; expired and
  stale status are resolved on interaction (no Render interval worker).
- Accepted gifts/trades clear favorite state on transferred cards so a new
  owner doesn't inherit private favorite preferences.
- An append-only `card_transfers` ledger records the old owner, new owner
  and reason but **never images or image URLs**. It can help audit disputed
  ownership changes.
- `/top`: global original catchers; `/gtop`: catches in current group;
  `/today`: catches since midnight **Asia/Yangon**. Gifts/trades don't
  rewrite immutable `catcher_id` or `caught_chat_id`; old legacy cards
  without group data cannot be retroactively attributed to a group.
- Only compact numeric IDs and metadata are in the new tables. No image
  rendering, no image downloads, no image bytes in Neon or Render.

## Data migrations

`database/schema.sql` adds immutable catcher/group columns and three
minimal relation-only tables (`card_transfers`, `gift_offers`,
`trade_offers`). It uses `IF NOT EXISTS` or new-table definitions.
No destructive existing-column or user-card operations. These migrations
will not affect Neon **until a separately approved deployment applies them**.
The app's `storage.initialize()` executes the schema on startup, so a
release must first verify index creation and schema access for the real
database; review quota impact before enabling the feature.

## Verified CI requirements

`.github/workflows/check.yml` provisions an independent disposable
PostgreSQL 16 instance at **localhost**, named `cardkout_test_social`.
Tests refuse any production hostname/db name; they create fixture
characters and owned cards, exercise consent/ownership/expiry/atomic trade,
validate audit events and immutable catch ranks after gift, and remove all
fixture records. No Telegram token or production Neon/Render is accessed by
CI. This is NOT yet a Telegram live test.

## Remaining release blockers / honest status

1. **Most important:** a genuine, sizeable, source-permitted and correctly
   illustrated Anime/Game card catalog does not exist yet. ACDB metadata
   148,604 unique source identifiers does NOT mean 148,604 cleared artworks,
   and the ~4,666 alternate records are metadata-only. This work cannot
   finish by auto-trusting image URLs, AI-generation labels, fan art, or
   another Telegram bot's images.
2. Source/copyright, character identity, content safety, attribution,
   public URL Telegram photo delivery and scale checks must be completed
   for a useful pilot batch, then progressively for larger batches.
3. PR #5 contains the strict review-only source/approved-import tools and
   disposable database tests. Must integrate their importer and art review
   results without overwriting the newer production numeric UI.
4. Advanced card variants and their shared artwork caches, retained
   transfer/offer storage quotas, owner dashboard, housekeeping/idempotent
   update delivery, collection performance for millions of cards, and
   actual real-group user acceptance tests are still open.
5. Re-evaluate risks of indexing, offer growth and global leaderboard
   queries at realistic database sizes. Don't assert Neon Free capacity
   for millions of ownerships before measuring.
6. Do not merge the older PR #2 as-is: it predates the live numeric-ID
   and caption flows and could silently overwrite them.

### Safe validation before any rollout
- Latest CI must be green on the exact PR head SHA.
- Real DB schema additive migration and disk growth should be previewed
  separately before touching live Neon.
- Telegram gift/trade must be tested by two consenting users in a private
  test group before being enabled in large groups.
- UI polish may be deferred; user explicitly requested no image-card rendering.
- User approval is required before merging/deploying/migrating production.
