# Real anime-style mascot source batch — four identities and bounded review pipeline

**Development only, 2026-10-20. NO character/image imports and NO live bot
deployment in this batch.** The reason for this work is to move from
synthetic source code toward substantial, human-verifiable artwork supply
without trusting filenames, AI-generated labels or commercial Anime/ACDB
image pointers as reproduction permission.

## Verified source category entry points (category != cleared media)

Four existing Wikimedia Commons topic categories have been mapped to FOUR
distinct *candidate character identities* in
`data/commons_curated_mascot_metadata.stage.json`. Each staged character
has `image_url: null` and remains explicitly pending.

| Candidate character | Category source page | Context | Image approval |
| --- | --- | --- | --- |
| Wikipe-tan | [Wikipe-tan category](https://commons.wikimedia.org/wiki/Category:Wikipe-tan) | Wikimedia anime-style personification | NONE |
| Commons-tan | [Commons-tan category](https://commons.wikimedia.org/wiki/Category:Commons-tan) | Wikimedia anime-style personification | NONE |
| Wikiquote-tan | [Wikiquote-tan category](https://commons.wikimedia.org/wiki/Category:Wikiquote-tan) | Wikimedia original mascot / Quote-tan | NONE |
| Kiki the Cyber Squirrel | [Kiki category](https://commons.wikimedia.org/wiki/Category:Kiki_the_Cyber_Squirrel) | Original Krita mascot | NONE |

These category pages respectively list approximately 28, 27, 13 and 49
direct file entries when researched (total 117 **category entries**, NOT
117 usable illustrations or distinct cards). Categories can include
logos, files with several characters, edits, screenshots, not-photos, or
material unsuitable for a general-audience group. No image or card count
may be inferred from these numbers without file-by-file review.

All four identities are separate from a licensed commercial anime
franchise. No One Piece/Naruto etc. fan art has been auto-imported.
Copyright metadata, derivative restrictions, attribution, the identity
of the illustrator and suitability MUST be checked per individual file
even when Commons lists a file in an anime-style character category.

## Three more individually researched, illustrated single-character files

Beyond the Wikipe-tan two-artwork pilot, the following **real Wikimedia
Commons file descriptions** have now been researched separately, and
recorded as evidence-only rows in
`data/commons_three_new_character_file_leads.review.json`:

| Single-character source | Exact Commons file-page lead | Author/edits as claimed on page | Source-page license claims | Photo URL/rights status |
| --- | --- | --- | --- | --- |
| Commons-tan | [Commons-tan.png](https://commons.wikimedia.org/wiki/File:Commons-tan.png) | Kasuga; cropped from Wiki-sisters art | CC BY-SA alternatives and GFDL | Raw direct PNG URL NOT confirmed; review pending |
| Wikiquote-tan | [Wikiquote-tan child-single.png](https://commons.wikimedia.org/wiki/File:Wikiquote-tan_child-single.png) | Kasuga; with Zscout370 logo removal | CC BY-SA 3.0 and other options | Raw direct PNG URL NOT confirmed; review pending |
| Kiki | [Kiki version 5.0 splash (cropped).png](https://commons.wikimedia.org/wiki/File:Kiki_the_Cyber_Squirrel_mascot_of_Krita_version_5.0_splash_(cropped).png) | Tyson Tan | CC BY-SA 4.0 / GPL v3 | Raw direct PNG URL NOT confirmed; review pending |

**Important visual identity correction:** `File:Quote-tan.png`, although
listed under Wikiquote-tan, is described on its file page as a
**quotation-mark hair accessory**, not a portrait of the full
character. It is NOT appropriate as a full Wikiquote-tan Card image.
The researched `Wikiquote-tan child-single.png` is a more meaningful
*candidate* but remains unapproved. Source page text/credit hints are
not proof of current image permission, suitability or Telegram
reachability. Shared image URL hashes were intentionally **not invented**:
the category/individual-file API must return the actual direct URL.

Combined with the previous Wikipe-tan base+head pictures, this is now
**five specific original-art file-page candidates across four source
character identities**, with still **zero** new production imports.
Distinct appearance/variant counts are not extra unique character IDs.
The legal/media verification pipeline is still needed before real cards.

## Implemented source→artwork pipeline, offline by default

The pipeline now has FOUR separate, independent checkpoints:

**1. Limited category filename discovery.**
`scripts/commons_category_discovery.py` only allows the above FOUR exact
hand-curated character categories. No recursion through Wiki-sisters,
adult outfits, pictures of cosplayers or general Internet categories;
no pagination loop. A request uses `list=categorymembers`,
`cmtype=file`, at most 50 File: title results per category, four HTTPS
metadata-only requests total, a small size/time cap, and a basic
filename-safety filter. The filter only excludes some obvious *names*;
it cannot inspect or certify image content. Everything stays PENDING and
has NO image URL attached to importer-ready `image_url` field.

**2. Bounded imageinfo evidence enrichment.**
`scripts/commons_file_enrichment.py` selects at most 48 titles fairly
across the four character identities (12 max per character), and requests
imageinfo in batches of at most 12 file names (FOUR API requests maximum).
Source identity and licensed permission are NOT inferred. Actual API URL,
file-page source, MIME, pixel dimensions, byte size and raw artist/license
hints may be attached as **unverified review evidence** only. No picture
content, thumbnail, OAuth/private data, file_id, stored card image, or
database calls.

**3. Unapproved artwork worksheet.**
`scripts/prepare_variant_review_queue.py` produces stable
`commons-<sha256 file title prefix>` variant keys and five EMPTY
evidence fields. The image for actual importer input stays NULL;
rights/identity/audience/Telegram compatibility checks are ALL FALSE.
The same character's multiple images are *variants*, never additional
unique character count.

**4. Human-to-import bridge.**
`scripts/assemble_reviewed_variants.py` requires exact original
Commons file and media URLs and five individual HTTPS evidence pointers:
subject identity, metadata source terms, public artwork rights,
general-audience suitability and actual Telegram photo compatibility,
plus genuine artist/license/source attribution, substantive notes and
all independent approval flags. Only explicitly reviewed entries can
produce the two files understood by the **existing** reviewed variant
importer. This is an audit trail/consistency gate, **not automated legal
clearance**: an individual must independently verify that each piece of
evidence actually supports the claims. Missing, pending or rejected
records never become importable.

`scripts/import_variants.py` still defaults to dry-run; real DB writes
need an explicit approval manifest, --apply, --rights-reviewed and exact
manual confirmation phrase, and should be tested against a disposable
database long before production.

### Commands (all offline, no database or API calls)

```bash
python -m scripts.commons_category_discovery \
  /tmp/commons-categories.json \
  --category 'Category:Wikipe-tan' \
  --category 'Category:Commons-tan' \
  --category 'Category:Wikiquote-tan' \
  --category 'Category:Kiki the Cyber Squirrel'

python -m scripts.commons_file_enrichment \
  /tmp/commons-categories.json /tmp/commons-imageinfo.json

python -m scripts.prepare_variant_review_queue \
  /tmp/commons-imageinfo.json /tmp/pending-artwork-variants.json
```

Optional real Commons **metadata-only** fetch: re-run each of the first
two commands with `--fetch`. It requires a correctly identifying
`WIKIMEDIA_USER_AGENT` with a genuine contact URL or email. Never invent
a fake contact, bypass API rate limits, recursively crawl categories,
request image bytes or infer rights from a license string. Human decisions
are prepared separately from machine-supplied metadata.

Final conversion **after actual human verification**, never with made-up
approval records:

```bash
python -m scripts.assemble_reviewed_variants \
  /tmp/pending-artwork-variants.json /tmp/real-human-decisions.json \
  --variants-out /tmp/reviewed-variants.json \
  --approvals-out /tmp/reviewed-variant-proofs.json

# Validation only; NO database write:
python -m scripts.import_variants /tmp/reviewed-variants.json \
  --approval-manifest /tmp/reviewed-variant-proofs.json
```

In the **current repository there is NO human-approved batch of these
artwork variants**. This pipeline is ready to accept such a batch, but
**does not produce one from API queries alone**.

## Tests / next real operational blocker

The full repo GitHub Actions CI runs mocked API regressions that prove:
- strict category whitelist, explicit opt-in, bounded requests and 429
  response failure with no retry;
- fair per-character candidate title queue, title identity conflicts,
  MIME/dimension/size filtering, untrusted origin rejection, empty/offline
  operation and no auto-approval;
- stable variant keys, blank independent rights checks and artifact/
  character reference consistency;
- review-only records produce zero importable characters/variants;
- synthetic *human-review fixtures* check exact image/credit/evidence
  manifests and protect the guarded importer (not actual legal approval).

**Actual live Wikimedia imageinfo enrichment and real Telegram send tests
have NOT yet been performed.** This is the next external-data gate, and it
should start with a very small, definitely reusable and safe picture
selection before expanding. Never equate category entries to usable Cards.

The storage architecture remains unchanged: one shared original artwork
URL and optional Telegram file_id on `characters` /
`character_variants`; only numeric ownership/variant IDs on
`owned_cards`. No image bytes in Neon/Render and no compositing.
