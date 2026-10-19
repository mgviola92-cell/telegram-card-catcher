"""Review catalog health before authorizing any import.

Usage: python -m scripts.catalog_audit data/anilist_review.json
No database calls, image downloads or network requests.
"""
import json
import sys
from collections import Counter
from scripts.import_characters import validate

def audit(records):
    parsed=validate(records)
    names=Counter((name.casefold(),series.casefold()) for _,name,series,*_ in parsed)
    duplicates=sum(n-1 for n in names.values() if n>1)
    series_count=len({series.casefold() for _,_,series,*_ in parsed})
    categories=Counter(row[4] for row in parsed)
    rarities=Counter(row[5] for row in parsed)
    return {"total":len(parsed),"unique_series":series_count,
            "same_name_series_duplicates":duplicates,
            "categories":dict(sorted(categories.items())),
            "rarities":dict(sorted(rarities.items()))}

if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("Usage: python -m scripts.catalog_audit FILE.json")
    with open(sys.argv[1],encoding="utf-8") as f:
        print(json.dumps(audit(json.load(f)),indent=2,ensure_ascii=False))
