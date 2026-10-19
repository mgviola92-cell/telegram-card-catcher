"""Bounded, opt-in Wikidata character candidate resolver for human review ONLY.

No Wikimedia images, no database writes, no automatic cross-source identity
merges. One wbsearchentities call per staged review row, capped at 25.
Usage: WIKIDATA_USER_AGENT='CardKout source research (contact: email@example.org)' \
 python -m scripts.wikidata_candidates review_queue.json --fetch --max-items 15

Wikidata CC0 metadata does not grant rights to third-party character artwork.
"""
import argparse
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import unicodedata

ENDPOINT='https://www.wikidata.org/w/api.php'
QID=re.compile(r'^Q[1-9][0-9]{0,15}$')
MAX_ITEMS=25
MAX_CHOICES=5


def normalize(value):
    return ' '.join(unicodedata.normalize('NFKC',value).casefold().split())


def query_params(name,choices=MAX_CHOICES):
    if type(choices) is not int or not 1 <= choices <= MAX_CHOICES:
        raise ValueError('Wikidata choices must be 1..5')
    if not isinstance(name,str) or not 1 <= len(name.strip()) <= 150:
        raise ValueError('Invalid source character name')
    return {'action':'wbsearchentities','format':'json','language':'en',
            'type':'item','search':name.strip(),'limit':str(choices),'maxlag':'5'}


def candidates(item, payload):
    key=item.get('source_key')
    name=item.get('name')
    series=item.get('series')
    if not all(isinstance(x,str) and x.strip() for x in (key,name,series)):
        raise ValueError('Source review row requires source_key,name,series')
    if not isinstance(payload,dict) or not isinstance(payload.get('search'),list):
        return []
    out=[]
    seen=set()
    for entry in payload['search'][:MAX_CHOICES]:
        if not isinstance(entry,dict):
            continue
        qid=entry.get('id')
        if not isinstance(qid,str) or not QID.fullmatch(qid) or qid in seen:
            continue
        seen.add(qid)
        label=entry.get('label') if isinstance(entry.get('label'),str) else ''
        description=entry.get('description') if isinstance(entry.get('description'),str) else ''
        out.append({'source_key':key,'original_name':name,
                    'original_series':series,'wikidata_qid':qid,
                    'wikidata_page':'https://www.wikidata.org/wiki/'+qid,
                    'label_exact_match_hint':normalize(label)==normalize(name),
                    'series_in_description_hint':bool(normalize(series)) and
                       normalize(series) in normalize(description),
                    'verification_status':'unverified_character_identity',
                    'source_mapping_approved':False,
                    'artwork_url':None,'artwork_approved':False,
                    'note':'Textual hints are not proof of character identity or media rights.'})
    return out


def discover(rows, user_agent, max_items=10, choices=MAX_CHOICES, fetch=False,
             opener=urlopen):
    if not isinstance(rows,list):
        raise ValueError('Expected array of staged review character rows')
    if type(max_items) is not int or not 1 <= max_items <= MAX_ITEMS:
        raise ValueError('Max rows must be 1..25')
    if type(choices) is not int or not 1 <= choices <= MAX_CHOICES:
        raise ValueError('Choices must be 1..5')
    if fetch and (not isinstance(user_agent,str) or len(user_agent.strip())<20 or
                  '@' not in user_agent):
        raise ValueError('Explicit descriptive user agent with contact required')
    seen=set()
    out=[]
    for row in rows:
        if len(seen) >= max_items:
            break
        if not isinstance(row,dict):
            continue
        name=row.get('name')
        key=row.get('source_key')
        series=row.get('series')
        if not all(isinstance(x,str) and x.strip() for x in (name,key,series)):
            continue
        if key in seen:
            continue
        seen.add(key)
        params=query_params(name,choices)
        if fetch:
            url=ENDPOINT+'?'+urlencode(params)
            request=Request(url,headers={'User-Agent':user_agent,
                          'Accept':'application/json','Accept-Encoding':'identity'})
            try:
                with opener(request,timeout=15) as response:
                    body=response.read(250_001)
            except HTTPError as exc:
                # Respect Wikimedia 429 and maxlag immediately: no retry floods.
                raise RuntimeError('Wikidata request rejected; stop and review limits') from exc
            if len(body)>250_000:
                raise ValueError('Wikidata response exceeds safety size limit')
            payload=json.loads(body)
        else:
            payload={}
        out.append({'source_key':key,'candidate_count':len(candidates(row,payload)),
                    'candidates':candidates(row,payload),'needs_human_review':True,
                    'import_ready':False})
    return {'source':'Wikidata','mode':'opt_in_lookup' if fetch else 'offline_dry_run',
            'requested_rows':len(out),'review_rows':out,
            'auto_merged_characters':0,'approved_artworks':0,'import_ready':0}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('queue',help='Existing metadata review JSON array')
    p.add_argument('--fetch',action='store_true',help='Opt in to small Wikimedia API requests')
    p.add_argument('--max-items',type=int,default=10)
    p.add_argument('--choices',type=int,default=MAX_CHOICES)
    p.add_argument('--output')
    a=p.parse_args()
    rows=json.loads(Path(a.queue).read_text(encoding='utf-8'))
    result=discover(rows,os.environ.get('WIKIDATA_USER_AGENT',''),
                    max_items=a.max_items,choices=a.choices,fetch=a.fetch)
    raw=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if a.output:
        dest=Path(a.output)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(raw,encoding='utf-8')
    print(raw)


if __name__=='__main__':
    main()
