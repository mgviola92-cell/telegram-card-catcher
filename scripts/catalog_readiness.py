"""Read-only catalog readiness summary. Does not fetch or import images."""
import argparse
import json
from collections import Counter
from scripts.catalog_quality import report
from scripts.artwork_approval import require_artwork_approval


def readiness(items, approvals):
    quality=report(items)
    approved=0
    missing=[]
    # Index approvals once: 10k-character reviews must not scan the manifest 10k times.
    approvals_by_key={}
    for entry in approvals:
        if isinstance(entry,dict) and isinstance(entry.get('source_key'),str):
            approvals_by_key.setdefault(entry['source_key'],[]).append(entry)
    for item in items:
        try:
            require_artwork_approval([item], approvals_by_key.get(item['source_key'],[]))
            approved+=1
        except ValueError:
            missing.append(item['source_key'])
    return {
        'characters':len(items),
        'series':len({c['series'] for c in items}),
        'category_counts':dict(sorted(Counter(c.get('category','anime') for c in items).items())),
        'approved_artwork':approved,
        'awaiting_artwork_review':missing,
        'quality_passed':quality['passed'],
        'quality_issues':quality['issues'],
        'ready_to_import':quality['passed'] and approved==len(items) and bool(items),
    }


if __name__=='__main__':
    cli=argparse.ArgumentParser()
    cli.add_argument('catalog')
    cli.add_argument('approval_manifest')
    args=cli.parse_args()
    with open(args.catalog,encoding='utf-8') as f: items=json.load(f)
    with open(args.approval_manifest,encoding='utf-8') as f: approvals=json.load(f)
    print(json.dumps(readiness(items,approvals),ensure_ascii=False,indent=2))
