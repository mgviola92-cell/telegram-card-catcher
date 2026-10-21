CREATE TABLE IF NOT EXISTS characters (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name TEXT NOT NULL,
  series TEXT NOT NULL,
  aliases TEXT[] NOT NULL DEFAULT '{}',
  category TEXT NOT NULL DEFAULT 'anime',
  rarity TEXT NOT NULL DEFAULT 'Common',
  image_url TEXT NOT NULL,
  telegram_file_id TEXT,
  enabled BOOLEAN NOT NULL DEFAULT TRUE
);
ALTER TABLE characters ADD COLUMN IF NOT EXISTS source_key TEXT;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS weight INTEGER NOT NULL DEFAULT 100;
CREATE UNIQUE INDEX IF NOT EXISTS characters_source_key_unique ON characters(source_key) WHERE source_key IS NOT NULL;
CREATE TABLE IF NOT EXISTS group_settings (
  chat_id BIGINT PRIMARY KEY,
  message_count INTEGER NOT NULL DEFAULT 0,
  spawn_every INTEGER NOT NULL DEFAULT 35,
  active_character_id BIGINT REFERENCES characters(id),
  last_spawn TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS owned_cards (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  character_id BIGINT NOT NULL REFERENCES characters(id),
  owner_id BIGINT NOT NULL,
  generation INTEGER NOT NULL,
  obtained_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  favorite BOOLEAN NOT NULL DEFAULT FALSE
);
-- The visible card reference is owned_cards.id. Existing legacy text codes
-- stay searchable, but newly caught cards use NULL to avoid duplicating
-- random per-copy identifiers. Non-NULL codes remain protected by the
-- existing UNIQUE constraint; this is an additive metadata-only migration.
ALTER TABLE owned_cards ALTER COLUMN code DROP NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS owned_cards_generation_unique ON owned_cards(character_id, generation);
CREATE INDEX IF NOT EXISTS owned_cards_by_owner ON owned_cards (owner_id, obtained_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS owned_cards_by_character ON owned_cards (character_id, generation);
CREATE TABLE IF NOT EXISTS processed_updates (
  update_id BIGINT PRIMARY KEY,
  processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS processed_updates_age ON processed_updates(processed_at);
-- Retry-safe webhook inbox state. Existing processed update rows stay 'done':
-- do not accidentally replay past Telegram actions after the migration.
ALTER TABLE processed_updates ADD COLUMN IF NOT EXISTS status TEXT NOT NULL
  DEFAULT 'done' CHECK (status IN ('processing','done','failed'));
ALTER TABLE processed_updates ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ;
ALTER TABLE processed_updates ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0;



-- Immutable catcher attribution for leaderboards, including after transfers.
-- Existing legacy cards have NULL attribution; their original catcher can be
-- recovered from the oldest transfer ledger entry if such a record exists.
ALTER TABLE owned_cards ADD COLUMN IF NOT EXISTS catcher_id BIGINT;
ALTER TABLE owned_cards ADD COLUMN IF NOT EXISTS caught_chat_id BIGINT;
CREATE INDEX IF NOT EXISTS owned_cards_group_catches
  ON owned_cards(caught_chat_id, obtained_at DESC)
  WHERE caught_chat_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS owned_cards_catcher_id
  ON owned_cards(catcher_id) WHERE catcher_id IS NOT NULL;

-- All collectible copies remain in owned_cards. No image bytes, file IDs or
-- artwork URLs are duplicated per owner for gifts, swaps or rankings.
CREATE TABLE IF NOT EXISTS card_transfers (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  card_id BIGINT NOT NULL REFERENCES owned_cards(id),
  from_user_id BIGINT NOT NULL,
  to_user_id BIGINT NOT NULL,
  reason TEXT NOT NULL CHECK(reason IN ('gift','trade')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS card_transfers_card_order
  ON card_transfers(card_id,id);

CREATE TABLE IF NOT EXISTS gift_offers (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sender_id BIGINT NOT NULL,
  receiver_id BIGINT NOT NULL,
  card_id BIGINT NOT NULL REFERENCES owned_cards(id),
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK(status IN ('pending','accepted','declined','expired','invalid')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK(sender_id <> receiver_id)
);
CREATE INDEX IF NOT EXISTS gift_pending_sender
  ON gift_offers(sender_id,created_at DESC) WHERE status='pending';

CREATE TABLE IF NOT EXISTS trade_offers (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sender_id BIGINT NOT NULL,
  receiver_id BIGINT NOT NULL,
  sender_card_id BIGINT NOT NULL REFERENCES owned_cards(id),
  receiver_card_id BIGINT NOT NULL REFERENCES owned_cards(id),
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK(status IN ('pending','accepted','declined','expired','invalid')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK(sender_id <> receiver_id),
  CHECK(sender_card_id <> receiver_card_id)
);
CREATE INDEX IF NOT EXISTS trade_pending_sender
  ON trade_offers(sender_id,created_at DESC) WHERE status='pending';


-- Multiple approved original illustrations for ONE character; all owners of
-- the same artwork share one URL/file_id. NEVER store artwork on owned_cards.
CREATE TABLE IF NOT EXISTS character_variants (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  character_id BIGINT NOT NULL REFERENCES characters(id),
  variant_key TEXT NOT NULL,
  label TEXT NOT NULL,
  image_url TEXT NOT NULL,
  telegram_file_id TEXT,
  rarity TEXT NOT NULL DEFAULT 'Common',
  spawn_weight INTEGER NOT NULL DEFAULT 100
    CHECK(spawn_weight BETWEEN 0 AND 10000),
  enabled BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE(character_id,variant_key)
);
ALTER TABLE owned_cards ADD COLUMN IF NOT EXISTS variant_id
  BIGINT REFERENCES character_variants(id);
ALTER TABLE group_settings ADD COLUMN IF NOT EXISTS active_variant_id
  BIGINT REFERENCES character_variants(id);
CREATE INDEX IF NOT EXISTS character_variants_by_character
  ON character_variants(character_id,enabled);
-- Index on owned_cards.variant_id is postponed until real EXPLAIN / telemetry;
-- main ownership queries filter by owner and use its existing owner index.

-- Fast exact-title collection progress without scanning the full catalog.
CREATE INDEX IF NOT EXISTS characters_by_series_enabled
  ON characters(series,id) WHERE enabled=true;


-- Shared ARTWORK ATTRIBUTION, not picture storage: license/source links are
-- informational HTTPS page URLs, distinct from the one original image_url.
-- Card copies do not duplicate image URLs, art credit, or Telegram file_id.
ALTER TABLE characters ADD COLUMN IF NOT EXISTS artwork_author TEXT;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS artwork_license_name TEXT;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS artwork_license_url TEXT;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS artwork_page_url TEXT;
ALTER TABLE character_variants ADD COLUMN IF NOT EXISTS artwork_author TEXT;
ALTER TABLE character_variants ADD COLUMN IF NOT EXISTS artwork_license_name TEXT;
ALTER TABLE character_variants ADD COLUMN IF NOT EXISTS artwork_license_url TEXT;
ALTER TABLE character_variants ADD COLUMN IF NOT EXISTS artwork_page_url TEXT;

-- The community trade board is an advertisement ONLY. Transfers remain
-- controlled by /trade with an explicit consenting recipient; no currency
-- or real-money exchange is supported. No artwork bytes/URLs are duplicated.
CREATE TABLE IF NOT EXISTS market_listings (
  card_id BIGINT PRIMARY KEY REFERENCES owned_cards(id),
  seller_id BIGINT NOT NULL CHECK(seller_id > 0),
  chat_id BIGINT NOT NULL,
  listed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '24 hours')
);
CREATE INDEX IF NOT EXISTS market_listings_by_group
  ON market_listings(chat_id, expires_at DESC);
CREATE INDEX IF NOT EXISTS market_listings_by_seller
  ON market_listings(seller_id,expires_at DESC);
