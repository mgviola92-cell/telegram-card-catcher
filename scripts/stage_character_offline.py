"""Stage character metadata from an Anime Character Offline Database JSON snapshot.
Output is deliberately NOT importer-compatible: artwork reuse is unverified.
No image downloads, rights assumptions, or database writes.
"""
import argparse
import json
from pathlib import Path

def stage(snapshot):
    if not isinstance(snapshot,dict) or not isinstance(snapshot.get('data'),list):
        raise ValueError('Expected snapshot object containing a data array')
    found={}
    for item in snapshot['data']:
        if not isinstance(item,dict):
            continue
        ident=item.get('mal_id')
        name=item.get('name')
        appearances=item.get('animeAppearances') or []
        if not isinstance(appearances,list):
            continue
        if type(ident) is not int or ident<1 or not isinstance(name,str) or not name.strip():
            continue
        titles=[]
        for appearance in appearances:
            if not isinstance(appearance,dict):
                continue
            anime=appearance.get('anime')
            title=anime.get('title') if isinstance(anime,dict) else None
            if isinstance(title,str) and title.strip() and title.strip() not in titles:
                titles.append(title.strip())
        if not titles:
            continue
        key=f'mal:character:{ident}'
        nicknames=item.get('nicknames') or []
        if not isinstance(nicknames,list):
            nicknames=[]
        aliases=[x.strip() for x in nicknames
                 if isinstance(x,str) and x.strip() and len(x.strip())<=120][:20]
        found[key]={'source_key':key,'name':name.strip()[:150],
                    'series':titles[0][:150],'additional_series':titles[1:],
                    'aliases':aliases,'metadata_status':'pending_source_rights_review',
                    'image_url':None,'artwork_status':'awaiting_permission_review'}
    return list(found.values())

def coverage_report(snapshot):
    """Measure actual snapshot coverage without treating images as approved."""
    if not isinstance(snapshot,dict) or not isinstance(snapshot.get('data'),list):
        raise ValueError('Expected snapshot object containing a data array')
    staged=stage(snapshot)
    from collections import Counter
    series=Counter(row['series'] for row in staged)
    raw_ids=[item.get('mal_id') for item in snapshot['data'] if isinstance(item,dict) and type(item.get('mal_id')) is int and item['mal_id']>0]
    metadata=snapshot.get('meta') or {}
    return {
        'snapshot_rows':len(snapshot['data']),
        'reported_total':metadata.get('totalCharacters') if isinstance(metadata,dict) else None,
        'staged_unique_characters':len(staged),
        'repeated_source_ids_in_snapshot':len(raw_ids)-len(set(raw_ids)),
        'unique_primary_series':len(series),
        'largest_series':series.most_common(15),
        'eligible_for_live_import':0,
        'reason':'Artwork permissions not reviewed; staged output is metadata only.',
    }


def convert(input_file,output_file):
    with open(input_file,encoding='utf-8') as src:
        result=stage(json.load(src))
    dest=Path(output_file)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return len(result)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('snapshot')
    ap.add_argument('output')
    ap.add_argument('--report',help='Write factual local snapshot coverage report')
    args=ap.parse_args()
    print('Review-only character metadata records:',convert(args.snapshot,args.output))
    if args.report:
        with open(args.snapshot,encoding='utf-8') as source:
            summary=coverage_report(json.load(source))
        Path(args.report).write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\\n',encoding='utf-8')
        print('Coverage report:',args.report)
