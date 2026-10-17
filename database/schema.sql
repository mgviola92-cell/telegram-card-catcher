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
CREATE UNIQUE INDEX IF NOT EXISTS owned_cards_generation_unique ON owned_cards(character_id, generation);
CREATE INDEX IF NOT EXISTS owned_cards_by_owner ON owned_cards (owner_id, obtained_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS owned_cards_by_character ON owned_cards (character_id, generation);
CREATE TABLE IF NOT EXISTS processed_updates (
  update_id BIGINT PRIMARY KEY,
  processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS processed_updates_age ON processed_updates(processed_at);

CREATE TABLE IF NOT EXISTS trade_offers (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sender_id BIGINT NOT NULL,
  receiver_id BIGINT NOT NULL,
  sender_code TEXT NOT NULL,
  receiver_code TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS pending_trades_receiver ON trade_offers(receiver_id,created_at DESC)
  WHERE status='pending';
