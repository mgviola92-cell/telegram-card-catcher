"""Create bounded artwork review checklists from unapproved Commons candidates.

NO rights are granted by metadata, URLs, filenames, or a reviewer checklist.
This adapter does not automatically approve artwork, fetch media or access DB.
Reviewers must independently verify subject identity, public reuse rights,
artwork source/attribution, audience suitability and Telegram reachability.
"""
import argparse
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

MAX_ROWS=5000
GOOD_UPLOAD_HOST="upload.wikimedia.org"
GOOD_PAGE_HOST="commons.wikimedia.org"


def checked_https(value, expected_host):
    if not isinstance(value,str) or not value.strip():
        return False
    try:
        parsed=urlsplit(value.strip())
        return (parsed.scheme=="https" and parsed.hostname==expected_host and
                parsed.username is None and parsed.password is None and
                parsed.port in (None,443) and not parsed.fragment)
    except ValueError:
        return False


def make_checklist(rows, *, limit=500):
    if not isinstance(rows,list) or len(rows)>MAX_ROWS:
        raise ValueError("Bounded Commons candidate array required")
    if type(limit) is not int or not 1<=limit<=MAX_ROWS:
        raise ValueError("Invalid review queue limit")
    seen=set()
    counts=Counter()
    output=[]
    for row in rows:
        if not isinstance(row,dict):
            counts["invalid_source_row"]+=1
            continue
        key=row.get("source_key")
        name=row.get("character_name")
        series=row.get("series")
        image=row.get("candidate_image_url")
        page=row.get("file_page_url")
        if not all(isinstance(v,str) and 1<=len(v.strip())<=500
                   for v in (key,name,series)):
            counts["invalid_identity_metadata"]+=1
            continue
        if (not checked_https(image,GOOD_UPLOAD_HOST) or
                not checked_https(page,GOOD_PAGE_HOST)):
            counts["untrusted_media_provenance"]+=1
            continue
        unique=(key.strip(),image)
        if unique in seen:
            counts["repeated_candidate_image_for_character"]+=1
            continue
        seen.add(unique)
        if len(output)>=limit:
            counts["beyond_output_limit"]+=1
            continue
        license_hint=row.get("license_hint")
        # A hint may help human research but NEVER changes readiness.
        has_license_hint=isinstance(license_hint,str) and bool(license_hint.strip())
        counts["has_license_hint" if has_license_hint else "missing_license_hint"]+=1
        output.append({
            "source_key":key.strip(),
            "character_name":name.strip()[:150],
            "series":series.strip()[:150],
            "candidate_image_url":image,
            "source_file_page":page,
            "license_hint_unverified":str(license_hint or "")[:200],
            "artist_hint_unverified":str(row.get("artist_hint") or "")[:200],
            "required_checks":{
                "exact_character_and_series_match":"pending",
                "public_republication_and_derivative_rights":"pending",
                "correct_license_and_attribution":"pending",
                "safe_for_general_audience":"pending",
                "https_photo_send_compatibility":"pending",
            },
            "approved_for_import":False,
            "image_rights_approved":False,
            "status":"pending_independent_human_review",
        })
    return {"source":"Wikimedia Commons research candidates",
            "review_queue_count":len(output),"counters":dict(sorted(counts.items())),
            "review_queue":output,"approved_artworks":0,
            "import_ready_characters":0,
            "notice":"An image URL and license hint do not prove permission. "
                     "No approved manifest or importer-ready catalog is produced."}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("commons_candidates")
    p.add_argument("output")
    p.add_argument("--limit",type=int,default=500)
    p.add_argument("--summary-only",action="store_true")
    args=p.parse_args()
    records=json.loads(Path(args.commons_candidates).read_text(encoding="utf8"))
    result=make_checklist(records,limit=args.limit)
    if args.summary_only:
        result["review_queue"].clear()
    target=Path(args.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({k:v for k,v in result.items() if k!="review_queue"},ensure_ascii=False))


if __name__=="__main__":
    main()
