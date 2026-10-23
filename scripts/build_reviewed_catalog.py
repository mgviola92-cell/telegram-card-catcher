"""Assemble *manually* reviewed character+artwork rows for importer dry-run.

This code never fetches pictures or writes to a database. A candidate
image URL, provider image pointer or name match alone is NOT permission.
Reviewers need separate evidence of source reuse terms, exact artwork
character identity, rights, audience suitability and Telegram delivery.
Output is still subject to human re-verification before real import.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from scripts.import_characters import MAX_IMPORT_ROWS, validate
from scripts.artwork_approval import require_artwork_approval
from scripts.artwork_attribution import CREDIT_FIELDS, credit_tuple

REQUIRED_CHECKS=(
    "subject_identity",
    "source_metadata_terms",
    "artwork_public_reuse_rights",
    "general_audience_suitability",
    "telegram_photo_reachability",
)


def https_evidence(value):
    if not isinstance(value,str) or not 12<=len(value)<=2048:
        return False
    try:
        uri=urlsplit(value)
        return (uri.scheme=="https" and bool(uri.hostname)
                and uri.username is None and uri.password is None
                and uri.port in (None,443))
    except ValueError:
        return False


def assemble(staged, manual):
    """Return catalog, approval manifest and summary; never mutate inputs."""
    if not isinstance(staged,list) or not isinstance(manual,list):
        raise ValueError("Staged metadata and manual reviews must be arrays")
    if len(staged)>MAX_IMPORT_ROWS or len(manual)>MAX_IMPORT_ROWS:
        raise ValueError("Catalog exceeds review batch limit")
    lookup={}
    for row in staged:
        if not isinstance(row,dict):
            raise ValueError("Malformed staged record")
        key=row.get("source_key")
        if not isinstance(key,str) or not key or key in lookup:
            raise ValueError("Duplicate or missing staged source ID")
        lookup[key]=row
    reviews={}
    for row in manual:
        if not isinstance(row,dict):
            raise ValueError("Malformed manual review")
        key=row.get("source_key")
        if not isinstance(key,str) or key not in lookup or key in reviews:
            raise ValueError("Unknown or repeated manual source ID")
        reviews[key]=row
    catalog=[]
    approvals=[]
    pending=0
    for key,meta in lookup.items():
        review=reviews.get(key)
        if review is None or review.get("status") in ("pending","rejected"):
            pending+=1
            continue
        if review.get("status")!="approved":
            raise ValueError(f"Unexpected review status for {key}")
        proof=review.get("evidence")
        if not isinstance(proof,dict) or not all(
            https_evidence(proof.get(check)) for check in REQUIRED_CHECKS
        ):
            raise ValueError(f"Approved record missing separate HTTPS review evidence: {key}")
        note=review.get("review_note")
        if not isinstance(note,str) or len(note.strip())<20:
            raise ValueError(f"Approved record needs human explanation: {key}")
        image=review.get("image_url")
        # Explicit manual review wins over source-supplied image pointers.
        if not isinstance(image,str):
            raise ValueError(f"Missing manually approved artwork URL: {key}")
        fields=("name","series","aliases","category","rarity","weight")
        item={k:meta[k] for k in fields if k in meta}
        item["source_key"]=key
        item["image_url"]=image
        credits={field:review[field] for field in CREDIT_FIELDS if field in review}
        if credits:
            credit_tuple(credits)  # all fields and two HTTPS evidence pages
            item.update(credits)
        catalog.append(item)
        approval={
            "source_key":key,
            "image_url":image,
            "status":"approved",
            "permission_reference":proof["artwork_public_reuse_rights"],
            "review_note":note.strip(),
            "verification_evidence":dict(proof),
        }
        approval.update(credits)
        approvals.append(approval)
    if catalog:
        validate(catalog)
        require_artwork_approval(catalog,approvals)
    return {"catalog":catalog,
            "approvals":approvals,
            "summary":{
                "metadata_rows":len(staged),
                "human_reviewed_approved":len(catalog),
                "pending_or_rejected":pending,
                "image_files_saved":0,"database_writes":0,
                "note":"Automated validation does not independently establish reuse rights. "
                       "Recheck evidence and sources before live import."
            }}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("staged")
    parser.add_argument("manual_review")
    parser.add_argument("--catalog-out",required=True)
    parser.add_argument("--approvals-out",required=True)
    parser.add_argument("--summary-out")
    args=parser.parse_args()
    with open(args.staged,encoding="utf8") as f:
        staged=json.load(f)
    with open(args.manual_review,encoding="utf8") as f:
        manual=json.load(f)
    result=assemble(staged,manual)
    catalog=Path(args.catalog_out)
    approvals=Path(args.approvals_out)
    if catalog.resolve()==approvals.resolve():
        raise ValueError("Catalog and approvals must have distinct output paths")
    catalog.parent.mkdir(parents=True,exist_ok=True)
    approvals.parent.mkdir(parents=True,exist_ok=True)
    catalog.write_text(json.dumps(result["catalog"],ensure_ascii=False,indent=2)+"\n",
                       encoding="utf8")
    approvals.write_text(json.dumps(result["approvals"],ensure_ascii=False,indent=2)+"\n",
                         encoding="utf8")
    if args.summary_out:
        out=Path(args.summary_out)
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(result["summary"],indent=2)+"\n",encoding="utf8")
    print(json.dumps(result["summary"],indent=2))


if __name__=="__main__":
    main()
