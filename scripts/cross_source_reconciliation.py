"""Conservative multi-source metadata coverage; no automatic merging.

Inputs are review-only staged arrays from independent source pipelines.
Neither a shared name nor a shared series proves character identity.
No media, database writes, or external requests are performed.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import unicodedata


def norm(value):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', value).casefold()).strip()


def report(named_sources):
    if not isinstance(named_sources, dict):
        raise ValueError('Sources must map names to arrays')
    raw = invalid = 0
    unique_keys = {}
    repeated_keys = 0
    inconsistent_keys = 0
    source_counts = {}
    series = set()
    matches = defaultdict(set)
    for label, rows in named_sources.items():
        if not isinstance(label,str) or not label.strip() or not isinstance(rows,list):
            raise ValueError('Each source must have a name and an array')
        source_counts[label] = {'raw':len(rows),'valid':0}
        for row in rows:
            raw += 1
            if not isinstance(row,dict):
                invalid+=1
                continue
            k,n,s = (row.get(x) for x in ('source_key','name','series'))
            if not all(isinstance(v,str) and v.strip() for v in (k,n,s)):
                invalid+=1
                continue
            source_counts[label]['valid'] += 1
            key = k.strip()
            pair = norm(n),norm(s)
            if key in unique_keys:
                repeated_keys+=1
                if unique_keys[key] != pair:
                    inconsistent_keys+=1
            else:
                unique_keys[key]=pair
            series.add(pair[1])
            matches[pair].add(key)
    multi_source_candidates = sum(1 for keys in matches.values() if len(keys)>1)
    possible_duplicate_extra_keys = sum(len(keys)-1 for keys in matches.values() if len(keys)>1)
    return {
        'sources':source_counts,
        'raw_rows':raw,
        'valid_metadata_rows':raw-invalid,
        'invalid_rows':invalid,
        'repeated_source_keys':repeated_keys,
        'conflicting_source_keys':inconsistent_keys,
        'distinct_source_keys':len(unique_keys),
        'distinct_normalized_primary_series':len(series),
        'potential_name_plus_series_collision_groups':multi_source_candidates,
        'potential_duplicate_additional_keys':possible_duplicate_extra_keys,
        'verified_cross_source_matches':0,
        'union_unique_characters':None,
        'import_ready':0,
        'artwork_rights_approved':0,
        'note':'Do NOT add per-source counts as unique characters. Name+series matches are only candidates; no automatic merges or imports.',
    }


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('sources',nargs='+',metavar='LABEL=review.json')
    cli.add_argument('--output')
    args=cli.parse_args()
    catalogs={}
    for entry in args.sources:
        label,sep,file=entry.partition('=')
        if not sep or not label or not file or label in catalogs:
            cli.error('Each source must be a distinct LABEL=review.json')
        catalogs[label]=json.loads(Path(file).read_text(encoding='utf-8'))
    result=report(catalogs)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if args.output:
        target=Path(args.output)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
