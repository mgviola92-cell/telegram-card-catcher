"""Convert Commons metadata hints into an UNAPPROVED variant review worksheet.

This helper never downloads images, queries Neon, or claims reuse rights.
Only use after a specific subject has been independently identified.
It prepares stable artwork variant keys (SHA256 of original File: title),
not per-player card identifiers. Credit/license fields stay empty.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from scripts.artwork_candidate_checklist import checked_https
from scripts.commons_category_discovery import CATEGORY_IDENTITIES

MAX_REVIEW_ROWS=48


def prepare_queue(report):
    if (not isinstance(report,dict) or
        report.get("mode") not in ("bounded_live_imageinfo_metadata","offline")
        or not isinstance(report.get("review_rows"),list)
        or len(report["review_rows"])>MAX_REVIEW_ROWS):
        raise ValueError("Expected bounded Commons file metadata review output")
    rows=[]
    excluded=0
    seen=set()
    for candidate in report["review_rows"]:
        if not isinstance(candidate,dict):
            raise ValueError("Malformed source review row")
        category=candidate.get("category")
        title=candidate.get("commons_file_title")
        source=candidate.get("claimed_character_source_key")
        if (category not in CATEGORY_IDENTITIES or
            CATEGORY_IDENTITIES[category][0]!=source or
            not isinstance(title,str) or not title.startswith("File:")
            or (source,title) in seen):
            raise ValueError("Ambiguous or duplicate artwork identity")
        seen.add((source,title))
        if candidate.get("approved_for_import") is not False:
            raise ValueError("Incoming file candidate unexpectedly pre-approved")
        url=candidate.get("candidate_image_url")
        page=candidate.get("file_page_url")
        if (candidate.get("metadata_photo_candidate") is not True
            or not checked_https(url,"upload.wikimedia.org")
            or not checked_https(page,"commons.wikimedia.org")):
            excluded+=1
            continue
        key="commons-"+sha256(title.encode("utf8")).hexdigest()[:16]
        rows.append({
            "character_source_key":source,
            "variant_key":key,
            "candidate_file_title":title,
            "candidate_image_url":url,
            "candidate_file_page":page,
            "artwork_name_hint":title.removeprefix("File:")[:100],
            "artist_hint_unverified":candidate.get("artist_hint_unverified"),
            "license_hint_unverified":candidate.get("license_hint_unverified"),
            "status":"pending",
            "image_url":None,
            "label":None,"rarity":"Common","spawn_weight":100,
            "artwork_author":None,"artwork_license_name":None,
            "artwork_license_url":None,"artwork_page_url":None,
            "artwork_identity_verified":False,
            "reuse_rights_verified":False,
            "content_suitability_verified":False,
            "upstream_terms_verified":False,
            "telegram_photo_verified":False,
            "review_note":None,
            "evidence":{
                "subject_identity":None,"source_metadata_terms":None,
                "artwork_public_reuse_rights":None,
                "general_audience_suitability":None,
                "telegram_photo_reachability":None,
            },
            "approved_for_import":False,
        })
    return {"review_queue":rows,"pending_variant_artworks":len(rows),
            "excluded_unsupported_metadata":excluded,
            "approved_artworks":0,"new_characters_created":0,
            "database_writes":0,"image_bytes_downloaded":0}


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("imageinfo_report")
    cli.add_argument("output")
    args=cli.parse_args()
    report=json.loads(Path(args.imageinfo_report).read_text(encoding="utf8"))
    result=prepare_queue(report)
    dest=Path(args.output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result["review_queue"],ensure_ascii=False,indent=2)+"\n",
                    encoding="utf8")
    print(json.dumps({k:v for k,v in result.items() if k!="review_queue"},
                     ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
