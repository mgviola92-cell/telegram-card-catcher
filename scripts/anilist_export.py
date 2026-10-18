"""AniList public character metadata batch exporter, offline-first and resumable.

This tool is for small, manual metadata review only; bulk harvesting is disabled.\nDoes NOT import into the database and
does NOT download image bytes. Always check source terms and image permissions
before running the generated catalog in a public bot.

Usage: python -m scripts.anilist_export --pages 1 --out data/anilist_review.json
"""
import argparse
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ENDPOINT = "https://graphql.anilist.co"
QUERY = """query ($page: Int!, $perPage: Int!) {
  Page(page: $page, perPage: $perPage) {
    pageInfo { hasNextPage }
    characters(sort: FAVOURITES_DESC) {
      id name { full alternative }
      image { large }
      media(perPage: 1, sort: POPULARITY_DESC) {
        nodes { title { romaji english } type }
      }
    }
  }
}"""


def parse_character(obj):
    if not isinstance(obj, dict):
        return None
    ident = obj.get("id")
    name = (obj.get("name") or {}).get("full")
    image = (obj.get("image") or {}).get("large")
    media = ((obj.get("media") or {}).get("nodes") or [])
    if not isinstance(ident, int) or not name or not isinstance(image, str):
        return None
    if not image.startswith("https://"):
        return None
    series = "Unknown Series"
    category = "anime"
    if media:
        node = media[0]
        title = node.get("title") or {}
        series = title.get("english") or title.get("romaji") or series
        if node.get("type") == "MANGA":
            category = "manga"
    aliases = [v.strip() for v in (obj.get("name") or {}).get("alternative") or []
               if isinstance(v, str) and v.strip() and len(v) <= 120]
    return {
        "source_key": f"anilist:character:{ident}",
        "name": name[:150],
        "series": series[:150],
        "aliases": list(dict.fromkeys(aliases))[:20],
        "category": category,
        "rarity": "Common",
        "weight": 100,
        "image_url": image,
    }


def request_page(page, per_page=10, attempts=3):
    payload = json.dumps({"query": QUERY, "variables": {
        "page": page, "perPage": per_page}}).encode()
    for attempt in range(attempts):
        try:
            request = Request(ENDPOINT, payload, {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "CardKoutMetadataImporter/0.1",
            })
            with urlopen(request, timeout=25) as response:
                result = json.load(response)
            if result.get("errors"):
                raise RuntimeError(str(result["errors"])[:300])
            return result["data"]["Page"]
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == attempts - 1:
                raise
            time.sleep(min(30, 3 * (attempt + 1)))
        except (URLError, TimeoutError):
            if attempt == attempts - 1:
                raise
            time.sleep(3 * (attempt + 1))


def export(pages, output, delay=2.0, start_page=1):
    if pages != 1 or not 1 <= start_page <= 10000:
        raise ValueError("Bulk export is disabled. Review one page (10 records) at a time.")
    destination = Path(output)
    existing = []
    if destination.exists():
        existing = json.loads(destination.read_text(encoding="utf-8"))
        if not isinstance(existing,list):
            raise ValueError("Existing export must be a JSON array")
    catalog = {item["source_key"]: item for item in existing if isinstance(item,dict) and "source_key" in item}
    for page in range(start_page, start_page + pages):
        result = request_page(page)
        for character in result.get("characters") or []:
            parsed = parse_character(character)
            if parsed:
                catalog[parsed["source_key"]] = parsed
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Validate the generated output before replacing the last good file.
        from scripts.import_characters import validate
        records=list(catalog.values())
        validate(records)
        staging=destination.with_suffix(destination.suffix + ".tmp")
        staging.write_text(json.dumps(records, ensure_ascii=False, indent=2),encoding="utf-8")
        staging.replace(destination)
        if not result.get("pageInfo", {}).get("hasNextPage"):
            break
        if page < start_page + pages - 1:
            time.sleep(max(1.5, delay))
    return len(catalog)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--out", default="data/anilist_review.json")
    parser.add_argument("--start-page", type=int, default=1)
    args = parser.parse_args()
    print("Metadata records exported for review:", export(args.pages, args.out, start_page=args.start_page))
