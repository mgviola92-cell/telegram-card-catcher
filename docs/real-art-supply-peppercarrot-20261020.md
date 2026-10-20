# Real original-webcomic character-art research batch — 2026-10-20

**Development-only evidence, not a release or a licensed import.** Exact GitHub
source: Draft PR #7 `feature/integrated-catalog-core-20261020`.
No photo image bytes downloaded, no character or owner inserted, no Telegram send
claimed, no Render/Neon changes.

## Most useful new discovery: 15 DISTINCT official named character portraits

The **official** [Pepper&Carrot Hereva character index](https://www.peppercarrot.com/en/wiki/Characters.html)
lists named story characters, rather than unnamed AI portraits. Its image links
resolved to 15 **separate actual JPEG portrait URLs** on the first-party
`www.peppercarrot.com` domain (visually fetched in public browsing). The
official [about/license page](https://www.peppercarrot.com/en/about/index.html) says comic art and translations are
CC BY 4.0 unless otherwise noted (e.g. fan art), and **also announces an AI
derivation prohibition**; do not generate AI variants from this source.
The [wiki landing page](https://www.peppercarrot.com/en/wiki/) also says
wiki resources are CC BY 4.0, with author credits in the wiki footer.

15 **distinct identity leads** (not fifteen approved or spawn-ready cards):

| Character identities | Original image evidence |
| --- | --- |
| Pepper, Carrot, Thyme, Cayenne, Cumin | official `chara_*.jpg` portraits |
| Saffron, Truffel, Shichimi, Yuzu, Torreya | official `chara_*.jpg` portraits |
| Coriander, Mango, Spirulina, Durian, Camomile | official `chara_*.jpg` portraits |

Exact individually observed HTTPS links, stable source keys and **explicitly
UNAPPROVED status** are in `data/peppercarrot_official_portraits.pending.json`.
Use the single official Hereva character page as source context for names.
This increases **prospective distinct characters** beyond the FOUR Wikimedia
mascots, with named character portraits in a repeatable first-party
creator-owned source family. It does **not** prove a comprehensive 100k corpus.

### Why the 15 are still PENDING

1. These wiki portraits are small low-resolution JPEG thumbnails: confirm
   per-image original artist, source image/credit, embedded third-party works,
   edit rights and any attribution details. Try to locate the separately
   creator-published **higher-resolution original** for each portrait, not
   invent URLs or copy thumbnails into a local/Neon image cache.
2. Confirm audience suitability and character identity from the actual art.
   Names, displayed portraits and wiki summary alone are *leads*, not approvals.
3. Verify CC BY 4.0 compliance plus the current creator-published policy and
   note whether the selected image itself has different terms. Fan-art files
   must not inherit the blanket license.
4. Test real Telegram Bot API `sendPhoto` and URL/reuse behavior in an
   explicit owner-approved disposable test group (none performed).
5. Only after those independent checks, author exact human-reviewed input
   for the existing safe importer; no automatic `--apply` or Neon migration.

The `candidate_image_url` is intentionally **not** `image_url`; every
`image_url`/credit field stays null and five sign-off flags are false.
An official image response is not a Telegram file_id.

## Revised triage of the SIX Commons imageinfo leads

Exact title-by-title statuses and reasons:
`data/commons_six_source_triage.review.json`.

- **Abstract Wikipe-tan.png**: HOLD. Its Commons file page also categorizes it
  under **The Amazing Digital Circus**, raising a clear mixed-IP/crossover
  provenance question. The uploader's CC BY-SA claim does not alone resolve
  other franchise/artwork rights; do not auto-import.
- **Commons-tan cropped.png**: HOLD for crop lineage and source page, which was
  not independently accessible in the latest browsing pass.
- **Commons-tan.png**: Commons identifies original material as a cut-out of
  Wiki-sisters; Kasuga credit/derivation must be checked.
- **Wikiquote-tan child-single.png**: file page identifies the single portrait
  derived from Wiki-sisters and credits Kasuga / Zscout370 alterations; confirm
  the exact attribution and image.
- **Kiki the cyber squirrel mascot of krita 3.png** and **Kiki ... cropped
  square profile.png**: stronger traceability than mixed-IP files. Wikimedia
  pages cite Tyson Tan and CC BY-SA 4.0, and the
  [Krita official mascot page](https://krita.org/en/about/mascot/) confirms
  Kiki's original author/role and CC BY-SA/GPL statements. These two exact
  images still need license attribution and real Telegram send confirmation.

Commons artwork file pages (not download mirroring):
- https://commons.wikimedia.org/wiki/File:Abstract_Wikipe-tan.png
- https://commons.wikimedia.org/wiki/File:Commons-tan_cropped.png
- https://commons.wikimedia.org/wiki/File:Commons-tan.png
- https://commons.wikimedia.org/wiki/File:Wikiquote-tan_child-single.png
- https://commons.wikimedia.org/wiki/File:Kiki_the_cyber_squirrel_mascot_of_krita_3.png
- https://commons.wikimedia.org/wiki/File:Kiki_the_Cyber_Squirrel_mascot_of_Krita_cropped_square_profile.png

## A larger lawful catalog means negotiating image availability, not counting APIs

Another potentially large **game-character artwork** family is the
[Battle for Wesnoth](https://github.com/wesnoth/wesnoth) open game;
its official README notes mixed **GPL v2+** and newer **CC BY-SA 4.0** art,
so do not bulk-assign a single license or import anonymous unit portraits.
Source character-name mapping and creator/art-per-file audits are needed.
Other commercial anime-franchise character databases are metadata leads,
not licenses to republish their image URLs. **No automatic harvesting**.

### Reproducible, network-free review
```bash
python -m scripts.audit_official_art_leads
python -m unittest tests.test_official_art_leads -v
```
Expected report: **15 official named-character portrait leads**, **6 Commons
files individually triaged**, one marked cross-IP HOLD, **0 approved**,
**0 Telegram-tested**, **0 imported**. These tests do not simulate actual
rights review or prove live delivery.

The existing large-scale architecture is unchanged: original HTTPS pictures
only, shared URL+one cached Telegram file_id on character or variant, numeric
owned IDs only, no Pillow renderer, no Neon/Render binary art.
