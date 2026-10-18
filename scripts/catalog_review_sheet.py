"""Prepare a compact human-review worksheet from a validated metadata export.

This does not approve rights, fetch images, or import to PostgreSQL.
"""
import argparse
import csv
import json
from scripts.import_characters import validate


COLUMNS=('source_key','name','series','category','image_url','review_status',
         'permission_reference','notes')


def review_rows(items):
    rows=validate(items)
    return [dict(zip(COLUMNS,(key,name,series,category,image_url,'pending','','')))
            for key,name,series,aliases,category,rarity,image_url,weight in rows]


def write_csv(items,output):
    rows=review_rows(items)
    with open(output,'w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('catalog')
    parser.add_argument('output')
    args=parser.parse_args()
    with open(args.catalog,encoding='utf-8') as source:
        items=json.load(source)
    print('Pending review rows:',write_csv(items,args.output))
