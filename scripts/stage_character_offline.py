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
        aliases=[x.strip() for x in (item.get('nicknames') or [])
                 if isinstance(x,str) and x.strip() and len(x.strip())<=120][:20]
        found[key]={'source_key':key,'name':name.strip()[:150],
                    'series':titles[0][:150],'additional_series':titles[1:],
                    'aliases':aliases,'metadata_status':'pending_source_rights_review',
                    'image_url':None,'artwork_status':'awaiting_permission_review'}
    return list(found.values())

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
    args=ap.parse_args()
    print('Review-only character metadata records:',convert(args.snapshot,args.output))
