"""Choose a diverse, deterministic human artwork-review pilot from staged metadata.

Does not assume discovered images are permitted and does not touch Neon.
Example: python -m scripts.build_pilot_review_queue staged.json pilot-review.json --limit 100
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

def build_queue(items, limit=100, max_per_series=3):
    if not isinstance(items,list):
        raise ValueError("staged catalog must be an array")
    if type(limit) is not int or limit<1 or limit>5000:
        raise ValueError("limit must be 1..5000")
    if type(max_per_series) is not int or not 1<=max_per_series<=50:
        raise ValueError("max_per_series must be 1..50")
    by_series=defaultdict(list)
    seen=set()
    for item in items:
        if not isinstance(item,dict):
            continue
        key=item.get('source_key')
        name=item.get('name')
        series=item.get('series')
        if not all(isinstance(s,str) and s.strip() for s in (key,name,series)) or key in seen:
            continue
        seen.add(key)
        by_series[series.strip()].append(item)
    for series in by_series:
        by_series[series].sort(key=lambda x:(x['name'].casefold(),x['source_key']))
    series_order=sorted(by_series,key=lambda s:(-len(by_series[s]),s.casefold()))
    selected=[]
    for depth in range(max_per_series):
        for series in series_order:
            options=by_series[series]
            if depth<len(options):
                item=options[depth]
                selected.append({
                    'source_key':item['source_key'],
                    'name':item['name'],'series':series,
                    'review_status':'pending_human_artwork_permission_review',
                    'image_url':None,
                    'permission_reference':None,
                    'safety_review':'pending',
                })
                if len(selected)==limit:
                    return selected
    return selected

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('staged_json')
    parser.add_argument('output_json')
    parser.add_argument('--limit',type=int,default=100)
    parser.add_argument('--max-per-series',type=int,default=3)
    args=parser.parse_args()
    data=json.loads(Path(args.staged_json).read_text(encoding='utf-8'))
    rows=build_queue(data,args.limit,args.max_per_series)
    target=Path(args.output_json)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'review_queue':len(rows),'series':len(set(x['series'] for x in rows)),
                      'approved_artwork':0},ensure_ascii=False))

if __name__=='__main__':
    main()
