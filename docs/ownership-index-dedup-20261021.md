# Duplicate owned-cards index removal — migration review

**Development branch only. No Neon DDL executed.**

Previously `database/schema.sql` defined TWO B-trees with identical
`(character_id, generation)` key order:

- `owned_cards_generation_unique` (UNIQUE)
- `owned_cards_by_character` (NON-UNIQUE duplicate)

The unique index handles all lookups supported by the redundant one,
including `SELECT max(generation)` when catching, equality by
`character_id`, and queries sorting by generation. Every owned card
used to update both independent indexes for no query benefit.

The draft schema no longer creates the redundant index and uses
`DROP INDEX IF EXISTS owned_cards_by_character` to remove that **index
only** on an eventual carefully reviewed migration. This changes
neither `owned_cards` rows, `owned_cards.id`, legacy codes, catches,
generation uniqueness, shared artwork URLs, nor the audit ledger.

**Release risk:** PostgreSQL `DROP INDEX` in the startup migration can
take table locks; rehearse lock time, actual SQL plans and safe rollback
on a disposable copy before owner-approved production deployment.
There is NO `DROP TABLE`, data truncation, ownership rewrite or
index-drop operation on live Neon in this batch.

Combined with the previous change (new numeric-only captures need
`code=NULL` instead of ten redundant characters), this targets the
major source of stored bytes: index replication per user-owned card.

GitHub CI runs a disposable PostgreSQL index/layout test and its
50,000-row rollback benchmark; compare exact HEAD logs for concrete
per-row storage. A synthetic ratio is not a Neon 1GB guarantee.
