"""Read-only go/no-go preflight for a pilot character catalog.

This never touches Neon. It refuses import readiness without item-specific,
human-reviewed artwork permission references.
Usage:
 python -m scripts.pilot_preflight --catalog data/characters.example.json --approvals data/artwork_approvals.example.json
"""
import argparse
import json
from pathlib import Path
from scripts.import_characters import validate
from scripts.catalog_readiness import readiness

def check(catalog,approvals):
    result={'catalog_count':len(catalog) if isinstance(catalog,list) else 0,
            'metadata_valid':False,'artwork_ready':False,'can_pilot':False,'issues':[]}
    try:
        validate(catalog)
        result['metadata_valid']=True
    except (ValueError,TypeError,KeyError) as exc:
        result['issues'].append('Metadata validation: '+str(exc))
        return result
    try:
        state=readiness(catalog,approvals)
        result['artwork_ready']=state['ready_to_import']
        result['awaiting_artwork_review_count']=len(state['awaiting_artwork_review'])
        result['quality_issues']=state['quality_issues']
        result['can_pilot']=bool(state['ready_to_import'])
    except (ValueError,TypeError,KeyError) as exc:
        result['issues'].append('Artwork review: '+str(exc))
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog',required=True)
    parser.add_argument('--approvals',required=True)
    parser.add_argument('--output',help='Optional JSON report path')
    args=parser.parse_args()
    catalog=json.loads(Path(args.catalog).read_text(encoding='utf-8'))
    approvals=json.loads(Path(args.approvals).read_text(encoding='utf-8'))
    result=check(catalog,approvals)
    rendered=json.dumps(result,ensure_ascii=False,indent=2)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered+'\n',encoding='utf-8')
    return 0 if result['can_pilot'] else 2

if __name__=='__main__':
    raise SystemExit(main())
