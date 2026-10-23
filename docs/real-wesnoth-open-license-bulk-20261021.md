# FIRST REAL bulk open-source artwork inventory (2026-10-21)

This is not another "find some images" plan. The actual checked-in
`data/wesnoth_1_16_11_official_art_inventory.json` contains **442 existing
real PNG source image references** discovered directly from Battle for
Wesnoth's official upstream git tree at tag **1.16.11**, pinned to commit
`83d4b397f1de466c721e4e393b361c71fc4f5b6c`. Exactly **204 campaign portrait PNG files** and **238
generic unit-type portraits**. These are ***442 actual asset files***, NOT
442 independently verified named characters or 442 Telegram-tested cards.

The source is `wesnoth/wesnoth` (not a search-engine scraper, AI-generated
art, or unlicensed anime franchise illustrations); official public licensing:
https://wiki.wesnoth.org/Wesnoth:Copyrights
and artist credit directory:
https://wiki.wesnoth.org/Credits
The project states **visual/audio assets are under GPL-2.0-or-later OR
CC-BY-SA-4.0**. That is a real upstream open-reuse license family, NOT a
claim that every file is under one particular one of the two licenses.
Redistribution must satisfy the applicable attribution, notices, GPL source
or sharealike conditions; creator and special file exceptions must be
resolved before approval. No creator endorsement implied.

For every source PNG we have: Git blob SHA, byte size, exact relative path,
version-pinned raw HTTPS artwork URL, exact GitHub source page, license policy
and credits page. Assets are **not downloaded or embedded** in this bot repo.
The result file is a referenced SOURCE ASSET catalog, not a legal approval
manifest. It intentionally keeps per-file approvals FALSE: individual image
identity, content suitability, credit and Telegram sendPhoto have not yet
been checked. This prevents accidental promotion to live character cards.

Generate a *real* nonimportable review queue offline:

```bash
python -m scripts.wesnoth_source_inventory \
 --review-jsonl /tmp/wesnoth-official-art-pending.jsonl
```

User priority: automated content batches not human uploading one image at a
time. The 204 campaign portraits already include named Wesnoth character
art variants (e.g. Konrad, Li'sar, Delfador, Asheviere), but expression PNGs
and generic unit types must be clustered and verified against in-game
character assignments before computing **distinct character count**.
Never count the 238 class portraits as 238 independently named people.

`raw.githubusercontent.com` is a source URL, not proof that Telegram can
send it as a photo. Do not push into Neon or enable character spawning until
the source grant obligations and Telegram API compatibility are confirmed.
No data-migration/deploy done on live main.
