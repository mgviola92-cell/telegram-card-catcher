"""Make a deterministic *pending* human-review worksheet from source metadata.

One source series must not crowd out all others in a tiny trial. This selects
round-robin across series, capped per show; NONE of the produced entries can
satisfy the manual-approved catalog gate without real independent review.
No media fetching, scraping, image URLs, DB access or network calls.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path

from scripts.build_reviewed_catalog import REQUIRED_CHECKS

MAX_ROWS=200_000
MAX_QUEUE=5_000


def make_queue(rows, limit=200, max_per_series=5):
    if not isinstance(rows,list) or len(rows)>MAX_ROWS:
        raise ValueError("Expected a bounded staged metadata array")
    if type(limit) is not int or not 1<=limit<=MAX_QUEUE:
        raise ValueError("Review queue limit must be 1..5000")
    if type(max_per_series) is not int or not 1<=max_per_series<=100:
        raise ValueError("Max per series must be 1..100")
    buckets=defaultdict(list)
    seen=set()
    rejected=0
    for entry in rows:
        if not isinstance(entry,dict):
            rejected+=1
            continue
        key=entry.get("source_key")
        name=entry.get("name")
        series=entry.get("series")
        if not all(isinstance(v,str) and 1<=len(v.strip())<=150
                   for v in (key,name,series)):
            rejected+=1
            continue
        key=key.strip()
        if key in seen:
            raise ValueError("Duplicate source_key in staged source")
        seen.add(key)
        buckets[series.strip()].append((key,name.strip()))
    order=sorted(buckets,key=lambda s:(-len(buckets[s]),s.casefold()))
    for name in buckets:
        buckets[name].sort(key=lambda row:(row[1].casefold(),row[0]))
    queue=[]
    for round_index in range(max_per_series):
        for show in order:
            if round_index>=len(buckets[show]):
                continue
            key,name=buckets[show][round_index]
            queue.append({
                "source_key":key,
                "source_character_name":name,
                "source_series":show,
                "status":"pending",
                "image_url":None,
                "evidence":{field:None for field in REQUIRED_CHECKS},
                "review_note":None,
                "never_autoapprove":True,
            })
            if len(queue)==limit:
                break
        if len(queue)==limit:
            break
    return {
        "source_records":len(rows),
        "valid_source_records":len(seen),
        "invalid_records_skipped":rejected,
        "series_with_valid_metadata":len(buckets),
        "review_queue_count":len(queue),
        "approved_for_import":0,
        "review_queue":queue,
        "note":"Pending worksheet only; no artwork URL or right is approved.",
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("staged")
    p.add_argument("output")
    p.add_argument("--limit",type=int,default=200)
    p.add_argument("--max-per-series",type=int,default=5)
    a=p.parse_args()
    rows=json.loads(Path(a.staged).read_text(encoding="utf8"))
    result=make_queue(rows,limit=a.limit,max_per_series=a.max_per_series)
    dest=Path(a.output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result["review_queue"],ensure_ascii=False,indent=2)+"\n",
                    encoding="utf8")
    print(json.dumps({k:v for k,v in result.items() if k!="review_queue"},indent=2))


if __name__=="__main__":
    main()
