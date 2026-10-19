# Image-card rendering: proposed architecture, not enabled in production

**Status:** Design only. Current live bot sends the real image URL to Telegram,
then reuses Telegram `file_id`. The ready-to-review native UI PR improves
captions and navigation; it does **not** generate new picture files.

## What would change?

A "rendered card" means composing a licensed source character illustration
plus frame/border, rarity badge, type-safe title/series labels and possibly
background accents into **one JPEG/PNG image**. This is not AI generation and
does not require permanent image storage on Render or in Neon.

Example display logic (not an actual graphic):

- Catchable spawn: art + rarity/series frame, **no character name**.
- Owned-card detail: art + rarity/name frame and generation/card code
  shown in Telegram caption, not painted into reusable image.
- Per-rarity templates use permitted drawn/vector primitives or separately
  cleared graphic assets.
- Every character/variant shares its framed artwork across all owners.

## Three deployment choices

| Option | Where compositing happens | Cost | Downsides |
| ------ | ------------------------- | ---- | --------- |
| A. Telegram native (current implementation) | No compositing. URL/file_id + HTML caption/buttons | Minimal server CPU/bandwidth | Image is not an ornate physical card |
| B. Shared framed artwork (recommended if users want ornate art) | On first view/spawn, Render fetches source temporarily in RAM, composites once, uploads once to Telegram | One-time network/CPU per artwork/variant *per mode/template revision*, then Telegram file_id reuse | Initial first request latency, need fetch hardening and maintainable renderer |
| C. Per-owned-copy fully personalized image | Composites name, card code, Gen, owner, stickers for every unique owned card | Very high for millions of cards unless a separate cache exists | Repeated downloads/uploads; no good fit for present storage/cost goals |

Preferred for a huge catalog: **A now, B as an opt-in guarded upgrade**.
Avoid C unless absolutely necessary. The card code, owner name, generation
and favorite status can stay in Telegram captions/buttons.

## Image storage contract — must not regress

Neon:
- `characters` / `character_variants` keep an approved original HTTPS
  URL and a Telegram `file_id` **string**. For a framed renderer, at most
  1–2 new cache-ID strings **per shared artwork** or a compact artwork-cache
  table keyed by artwork ID, mode, and renderer version.
- `owned_cards` holds owner, character reference, variant reference,
  unique code, generation and flags. **No JPEG/PNG/image bytes and no per-owned
  framed image URL/file ID.**

Render:
- Briefly downloads an approved original image into bounded **RAM**
  (e.g. BytesIO), composes a PNG/JPEG into a RAM buffer, uploads it to Telegram,
  closes buffers. No permanent file, disk cache, or build asset per card.
- "Never store images in Neon/Render" means never **persist** them there;
  composing a card necessarily holds temporary image bytes in RAM.
- CPU and Render networking are consumed for the **first** conversion;
  further sends reuse Telegram's returned framed-image file ID.

Telegram:
- Stores the uploaded framed image on Telegram's media infrastructure;
  subsequent views reuse its file ID. A lost/invalid ID can be rebuilt from
  the original approved URL if still available and permitted.
- Telegram photo dimensions/size, compression, caption limits and remote
  source availability must be handled; do not assume perpetual access.

## Scaling and safety plan

1. Obtain source image **use/republication rights** before even requesting it
   in the renderer. A working hotlink is not permission.
2. Validate HTTPS target; block loopback, private/link-local DNS results,
   redirects to non-public hosts, oversize responses, unsupported formats,
   decompression bombs, animated frames, corrupt inputs, massive dimensions.
3. Limit image bytes/time and concurrency; apply a single-flight key for
   duplicate first-time render requests for an artwork/mode, avoid load spikes.
4. Style templates for rarity and iconography; fonts must support real character
   names and Burmese where needed, with safe truncation/ellipsis.
5. Separate **spawn template** (identity hidden) and **owned-card template**
   (identity known). Cache IDs separately with `template_version`; invalidating
   artwork rights/URL/version invalidates cache.
6. If render/upload fails, use current original URL/file-ID + caption path.
   Never strand an active invisible spawn, erase existing collections, or send
   an unverified external image as a fallback.
7. Run offline memory-only tests and a **small single-character Telegram pilot**
   with measured latency/bytes/CPU before allowing more than a few artworks.
8. Do not enable mass catalog image rendering, per-owner caching or production
   schema migration until those costs/rights have been confirmed with the user.

## Concrete example at one million ownerships

Suppose one approved art identity appears in 100,000 owners' collections:
- Native route A: one original shared URL + original Telegram file ID.
- Shared frame B: **one** framed media ID for "owned-card" art (and optionally
  one separate "spawn" framed ID), shared across all 100,000 ownerships.
- Unique Gen/code/owner remain as text/caption in `owned_cards`; **100,000
  image renders are NOT necessary**.
- Per-copy route C would potentially render/upload 100,000 personalized
  images — prohibited as the default.

**Current work:** improve Telegram-native UI and existing media-sending
behavior on PR #4. No change to production unless specifically authorized.
