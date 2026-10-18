"""Stream a maintained anime-offline-database JSONL release into an offline coverage report.

Read-only: this is series metadata, NOT characters or rights-cleared artwork.
The first line is release metadata, remaining lines are anime series entries.
"""
import argparse
from collections import Counter
import json


def summarize_jsonl(lines):
    total=0
    titles=set()
    providers=Counter()
    malformed=0
    for index,line in enumerate(lines):
        if not line.strip():
            continue
        try:
            row=json.loads(line)
        except json.JSONDecodeError:
            malformed+=1
            continue
        if index==0:
            continue  # release metadata
        if not isinstance(row,dict):
            malformed+=1
            continue
        total+=1
        title=row.get('title')
        if isinstance(title,str) and title.strip():
            titles.add(title.strip().casefold())
        sources=row.get('sources') or []
        if isinstance(sources,list):
            for source in sources:
                if isinstance(source,str) and source.startswith('https://'):
                    from urllib.parse import urlsplit
                    providers[urlsplit(source).hostname or 'unknown']+=1
    return {'series_entries':total,'distinct_primary_titles':len(titles),
            'source_domain_counts':dict(providers.most_common()),
            'invalid_lines':malformed,
            'character_count':None,'artwork_approved':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('jsonl_file')
    args=parser.parse_args()
    with open(args.jsonl_file,encoding='utf-8') as stream:
        print(json.dumps(summarize_jsonl(stream),ensure_ascii=False,indent=2))
