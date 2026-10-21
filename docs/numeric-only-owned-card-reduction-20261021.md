# Numeric-only new captures — safe metadata storage reduction

**Development PR #7, NOT production deployment.** This modifies
`owned_cards` DDL only in the draft branch. Existing numeric
`owned_cards.id` values, owner relations, old `code` strings,
generation numbers, variant refs and transfer history are preserved.

## Implementation

Previously each new catch allocated a 10-character random legacy code,
performed an extra indexed uniqueness lookup, and still stored the separate
numeric primary key. New catches now leave `owned_cards.code` NULL and
identify the card only by its existing numeric PK. PostgreSQL unique
indexes allow multiple NULLs while preventing repeated non-NULL legacy
codes. The schema migration simply drops `code`'s NOT NULL constraint.
No existing card is rewritten or renumbered. Legacy `/check CODE`,
`/fav CODE`, `/trade CODE` and `/gift CODE` continue to resolve older
stored codes, while new cards use `/check 123` etc.

No image bytes or duplicate artwork references are stored in owner rows.
All shared picture media remains referenced only from character/variant
URL and cached Telegram file_id.

## Separate localhost/PostgreSQL benchmarks

The existing rolled-back 50k ownership fixture now uses NULL text codes
by default, with an opt-in `--legacy-codes` switch for old-row
comparison. Run on a disposable localhost database only:

```bash
python -m scripts.benchmark_owned_cards --run --rows 50000
python -m scripts.benchmark_owned_cards --run --rows 50000 --legacy-codes
```

These are *two separate measurements*, not a proof that Neon fits any
particular volume. There is still a UNIQUE index on legacy `code` to
support old references; index removal is **not** attempted. Audit before
any release: migration locks, stable numeric IDs, old-code lookup,
new-card claim, /check, fav/unfav, gift/trade and backup/rollback.
Do not deploy automatically: startup schema DDL would migrate Neon.
