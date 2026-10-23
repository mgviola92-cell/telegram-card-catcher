# ONE-command 100,000+ original-art URL batch (developer workflow)

This is a source-wide **catalog import**, not individual hand approval for
each image. The command reads one JSONL or JSONL.GZ file containing 100,000+
\`source_key,name,series,image_url,artwork_author,artwork_page_url\`
records. It streams rows to temporary operator-local SQLite; duplicates
are detected by exact source key, while all image bytes are NEVER fetched,
decoded, stored in Neon, or written onto Render. It can bulk upsert into
\`characters\` using PostgreSQL COPY + one ON CONFLICT merge in a single
transaction. No image columns on \`owned_cards\`; legacy IDs and ownership
are unchanged. This script must run from an **operator workstation** or
approved one-shot job, NOT the live Render webhook service.

A source-wide *licensed batch* needs one separately, independently
reviewed grant JSON describing the scope of reuse for ALL included art,
not a fabricated auto approval on rows. The exact file must be pinned to
its SHA256. Each art must have the correct creator/credit and artwork page,
and all URL hosts must be covered by the grant. Copyrighted franchise
metadata/ACDB ODbL rights do NOT license copyrighted anime pictures.
See https://www.animecharactersdatabase.com/about.php for ACDB's image
copyright position. An operator's self-assertion in JSON does not create
image rights. SOURCE licences can simplify review only when they clearly
cover every included original visual asset; otherwise split into independently
licensed batches. Artwork license identity, false-positive matches, safety
and Telegram file access need real verification. Do not invent a grant.

Generate a 100k+ JSONL from an appropriately licensed, named-character
source; single line per source character, e.g.:

{"source_key":"my-open-game:character:1","name":"Named Hero","series":"My Open Game","image_url":"https://creator.example/hero.png","artwork_author":"Artist","artwork_page_url":"https://creator.example/art/hero"}

Source grant schema: \`catalog_sha256\`, \`review_status\` set to
\`independently_reviewed\`, \`source_key_prefix\`, \`image_hosts\` exact list,
\`artwork_license_name\`, \`artwork_license_url\`, \`source_terms_url\`,
\`license_scope_evidence_url\`, \`credit_policy_url\`, \`reviewed_by\`,
\`review_note\`, explicit booleans
\`scope_includes_every_image=true\`,
\`redistribution_to_telegram_permitted=true\`. These fields mean an
operator CONFIRMS a separately checked claim; the program only validates
their presence/consistency and cannot independently verify the license.

Usage (NO DB access):
python -m scripts.bulk_url_import /tmp/100k_urls.jsonl \
  --source-grant /tmp/reviewed_source_grant.json

After independent source license, age suitability, original photo identity
and operator-approved release checks:

CARDKOUT_BULK_IMPORT_AUTHORIZED=YES python -m scripts.bulk_url_import \
  /tmp/100k_urls.jsonl --source-grant /tmp/reviewed_source_grant.json \
  --apply --rights-reviewed --confirm IMPORT_REVIEWED_BULK_URLS

**New URLs default DISABLED** to avoid bots spawning art before source-wide
Telegram photo delivery is checked. \`--enable\` is allowed only if the
separate source grant expressly confirms such testing. Existing rows
retain the same IDs but importer can update their URL and reset shared
Telegram file-id when artwork changes. A production import MUST have
owner approval; writing the code here is not that approval.

**Neon 1GB guard:** before the transaction, reserve 256MiB and conservatively
budget ~4KiB per new metadata character plus existing DB size. These are
heuristics, NOT real quota guarantees (indexes, journal/WAL,
PostgreSQL bloat, branching, other tables). 100k new rows budget roughly
390.6MiB plus reserve; real footprint needs separate benchmarking.
If not enough space, abort BEFORE any upsert. No new background polling.

**Current status:** implementation and CI synthetic 100k tests only.
Zero new real anime artwork license grants, zero new production URL imports.
