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
CREATE INDEX IF NOT EXISTS owned_cards_by_owner ON owned_cards (owner_id, obtained_at DESC);
CREATE INDEX IF NOT EXISTS owned_cards_by_character ON owned_cards (character_id, generation);
CREATE TABLE IF NOT EXISTS processed_updates (update_id BIGINT PRIMARY KEY, processed_at TIMESTAMPTZ NOT NULL DEFAULT now());
