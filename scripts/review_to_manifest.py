"""Convert individually reviewed CSV rows to the existing approval manifest format.

Only approved rows with nonempty permission references are emitted.
Unreviewed rows stay excluded. The manifest is checked against catalog on import.
"""
import argparse
import csv
import json


def manifest_from_rows(rows):
    manifest=[]
    seen=set()
    for number,row in enumerate(rows,1):
        key=(row.get('source_key') or '').strip()
        if not key or key in seen:
            raise ValueError(f'Row {number}: missing or duplicate source_key')
        seen.add(key)
        status=(row.get('review_status') or '').strip().lower()
        if status not in ('approved','pending','rejected'):
            raise ValueError(f'Row {number}: review_status must be approved, pending or rejected')
        if status!='approved':
            continue
        url=(row.get('image_url') or '').strip()
        reference=(row.get('permission_reference') or '').strip()
        if len(reference)<8 or not url.startswith('https://'):
            raise ValueError(f'Row {number}: approved artwork needs HTTPS URL and permission reference')
        manifest.append({'source_key':key,'image_url':url,'status':'approved',
                         'permission_reference':reference})
    return manifest


def convert_file(csv_path,json_path):
    with open(csv_path,encoding='utf-8-sig',newline='') as source:
        records=list(csv.DictReader(source))
    result=manifest_from_rows(records)
    with open(json_path,'w',encoding='utf-8') as target:
        json.dump(result,target,ensure_ascii=False,indent=2)
    return len(result)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('review_csv')
    parser.add_argument('approval_json')
    args=parser.parse_args()
    print('Reviewed artwork approvals:',convert_file(args.review_csv,args.approval_json))
