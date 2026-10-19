"""Normalize a bounded Bangumi review-pilot result into safe staged metadata.

An identical character may appear in more than one reviewed, non-NSFW subject.
Deduplicate only by Bangumi's own character identifier, never by common name.
Do not turn source images into catalog images or approve text/image rights.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
from scripts.bangumi_review import MAX_SUBJECTS

MAX_OUTPUT=MAX_SUBJECTS*100


def flatten(response):
    if not isinstance(response,dict) or response.get("source")!="Bangumi public API v0":
        raise ValueError("Expected verified Bangumi pilot response")
    groups=response.get("subjects")
    if not isinstance(groups,list) or len(groups)>MAX_SUBJECTS:
        raise ValueError("Unexpected Bangumi pilot subjects")
    found={}
    flags=Counter()
    for group in groups:
        if not isinstance(group,dict):
            raise ValueError("Invalid source group")
        entries=group.get("characters")
        if not isinstance(entries,list) or len(entries)>100:
            raise ValueError("Unexpected source group character list")
        if group.get("eligible") is not True or group.get("status")!="metadata_review_only":
            if entries:
                raise ValueError("Ineligible subject must not carry character metadata")
            continue
        for row in entries:
            if not isinstance(row,dict):
                raise ValueError("Invalid character metadata")
            key,name,series = (row.get(f) for f in ("source_key","name","series"))
            if not all(isinstance(v,str) and 1<=len(v.strip())<=150 for v in
                       (key,name,series)):
                raise ValueError("Missing source identity information")
            if not key.startswith("bangumi:character:"):
                raise ValueError("Not an authorized Bangumi ID namespace")
            if (row.get("image_url") is not None or row.get("telegram_file_id") is not None
                or row.get("import_ready") is not False):
                raise ValueError("Source record unexpectedly contains approved media")
            if key not in found:
                found[key]={
                    "source_key":key,
                    "name":name.strip(),
                    "series":series.strip(),
                    "additional_series":[],
                    "image_url":None,
                    "artwork_status":"awaiting_independent_permission_review",
                    "metadata_status":"pending_upstream_terms_and_identity_review",
                    "audience_suitability_review":"pending",
                    "import_ready":False,
                }
            else:
                previous=found[key]
                if previous["name"].casefold()!=name.strip().casefold():
                    flags["conflicting_names_same_bangumi_id"]+=1
                    raise ValueError("Contradictory names for one Bangumi character ID")
                if series.strip()!=previous["series"] and series.strip() not in previous["additional_series"]:
                    previous["additional_series"].append(series.strip())
                    flags["extra_character_subject_appearances"]+=1
    staged=sorted(found.values(),key=lambda x:x["source_key"])
    if len(staged)>MAX_OUTPUT:
        raise ValueError("Staged metadata exceeds subject cap")
    return {"source":"Bangumi public API v0","metadata_only":True,
            "staged_unique_source_characters":len(staged),
            "extra_subject_links":flags["extra_character_subject_appearances"],
            "staged":staged,"artworks_approved":0,"import_ready":0,
            "note":"Primary series is first reviewed subject, not a canonical fact. "
                   "Multiple shows and identity/source rights still require human review."}


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("pilot_report")
    cli.add_argument("output")
    args=cli.parse_args()
    report=json.loads(Path(args.pilot_report).read_text(encoding="utf8"))
    result=flatten(report)
    path=Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({k:v for k,v in result.items() if k!="staged"}))


if __name__=="__main__":
    main()
