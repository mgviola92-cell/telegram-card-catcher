# Four real Wikimedia illustration candidates: a small, verifiable media research batch

**This is NOT the anime source catalog.** It tests the actual Wikimedia image
evidence/review workflow before touching ACDB's 148,604 metadata IDs or
claiming the many thousands of anime pictures may be reused.

## Source file-page research (2026-10-20)

The repository now contains **four actually named image candidates**, unlike
the old fully synthetic source smoke tests. These links are review evidence,
not blanket permission to import.

| Character | Work | Commons file page | Page claims | Remaining verification |
| --- | --- | --- | --- | --- |
| Alice | Alice's Adventures in Wonderland | [Tenniel, Drink Me](https://commons.wikimedia.org/wiki/File:Alice_in_Wonderland,_Drink_me_by_John_Tenniel.jpg) | John Tenniel, 1865 illustration; faithful reproduction of PD two-dimensional art; original reported 181×250 JPG, 18 KB | Existing live demo only; check country-specific public-domain status and media metadata |
| Tin Woodman | The Wonderful Wizard of Oz | [Tin Woodman](https://commons.wikimedia.org/wiki/File:Tin_Woodman.png) | W. W. Denslow, 1900, page carries Public Domain Mark, original reported 1,283×2,937 PNG, ~212 KB | Recheck edits and exact rights; Telegram upload not attempted |
| Scarecrow | The Wonderful Wizard of Oz | [Scarecrow detail](https://commons.wikimedia.org/wiki/File:Wizard_of_Oz_scarecrow_detail.png) | Denslow illustration with digital restoration; Commons page carries CC0, original reported 882×1,461 PNG, ~1.03 MB | Verify derivative/author details; Telegram upload not attempted |
| Dorothy Gale and Toto | The Wonderful Wizard of Oz | [Dorothy and Toto](https://commons.wikimedia.org/wiki/File:Dorothy_and_Toto,_1900.png) | Denslow, 1900, page carries Public Domain Mark; original reported 245×238 PNG, 15 KB | The image includes TWO subjects; check whether appropriate as one card |

These were checked against the **file description and licensing pages**, not
by downloading their original image bytes. Metadata/license markings are
subject to updates and local reuse law. Raw API extmetadata also may contain
HTML, incomplete author credits, or bad rights claims, so no program can
replace an independent evidence/suitability review.

All four candidate metadata rows are in
`data/commons_literary_pilot_candidates.review.json` and corresponding
source-name/series-only rows are in
`data/commons_literary_pilot_metadata.stage.json`. No new image files were
checked in; the staged character records intentionally carry no `image_url`.

## Repeatable safe pipeline

1. Run the existing pure offline review queue builder:

```bash
python -m scripts.prepare_review_queue \
  data/commons_literary_pilot_metadata.stage.json \
  /tmp/commons-pending-human-reviews.json --limit 4
```

2. Run the candidate checklist without any network/image fetch:

```bash
python -m scripts.artwork_candidate_checklist \
  data/commons_literary_pilot_candidates.review.json \
  /tmp/commons-artwork-checklist.json --limit 4
```

3. New `scripts/commons_media_metadata_audit.py` defaults to a **NO NETWORK**
dry-run; optionally it makes one bounded Commons Action API request, looking
up up to 12 exact files using `prop=imageinfo` and
`iiprop=url|size|mime|extmetadata` (official docs:
https://www.mediawiki.org/wiki/API:Imageinfo). This retrieves
**ONLY JSON metadata** — not the picture content. Exact HTTPS host and
canonical file URL/page must match. Reports:
MIME, byte size, dimensions, author/credit/attribution/license hints,
an explicit nonfree hint, conservative photo-size/format eligibility, and
any mismatches. **All per-file flags remain**
`artwork_permission_verified=false`,
`telegram_send_verified=false`, and `approved_for_import=false`
even if MIME and license metadata look fine.

```bash
python -m scripts.commons_media_metadata_audit \
  data/commons_literary_pilot_candidates.review.json \
  /tmp/commons-media-dry-run.json

# Only when approved to use the Commons API with a REAL contact identity:
WIKIMEDIA_USER_AGENT='CardKout source audit contact: REAL_ADDRESS' \
  python -m scripts.commons_media_metadata_audit \
  data/commons_literary_pilot_candidates.review.json \
  /tmp/commons-media-metadata-review.json --fetch
```

**Never add a fictional contact address or bypass a provider rate limit.**
A successful API response is not an end-to-end Telegram photo send. The
same media URL may later fail with Telegram because of image compression
limits, source fetch restrictions or URL changes.

4. Only after a separate **genuine human review** for every approved
character (correct art/series identity, source metadata terms, public reuse
rights, general audience suitability, Telegram compatibility) may
`scripts/build_reviewed_catalog.py` emit an import candidate. Actual
production changes remain blocked, requiring express owner approval.
The sample **does not** provide an approved manifest for new characters.

## Scope and next real blocker

The verified four candidate pages are evidence that real source URLs can be
assembled into a review pipeline. They are **NOT** four more cards in the
Telegram bot. The one Alice artwork previously deployed is still the
single live production sample. Scarecrow/Tin Woodman/Dorothy need review,
and the anime/game mass catalog needs separately licensed, correctly
matched artwork. For ACDB and similar commercial character databases,
populated `image` metadata alone is insufficient for image reuse.

No image-card rendering, no Render disk download, no Neon image blobs, and
no image URL per owned card. One shared original URL/file ID per artwork
identity remains the architecture.
