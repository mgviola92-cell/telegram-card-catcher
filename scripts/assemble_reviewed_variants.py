"""Strict reviewed Commons variant worksheet -> importer-ready *offline* files.

No rights are inferred from API metadata. This emits 0 approved artworks
unless a separate human supplies all five relevant evidence links, matching
file/character keys, license credits, and explicit real Telegram send review.

Even emitted records still need independent owner review before any
disposable DB import; no DB, no network, no original photo bytes.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from scripts.artwork_attribution import credit_tuple, CREDIT_FIELDS
from scripts.artwork_candidate_checklist import checked_https
from scripts.build_reviewed_catalog import REQUIRED_CHECKS, https_evidence
from scripts.import_variants import validate as validate_variants


CHECKS=("artwork_identity_verified","reuse_rights_verified",
        "content_suitability_verified","upstream_terms_verified",
        "telegram_photo_verified")
MAX_ROWS=48


def assemble(queue,decisions):
    if (not isinstance(queue,list) or not isinstance(decisions,list)
        or len(queue)>MAX_ROWS or len(decisions)>MAX_ROWS):
        raise ValueError("Expected <=48 pending file worksheets and human decisions")
    mapping={}
    for q in queue:
        if not isinstance(q,dict) or q.get("status")!="pending" or q.get("approved_for_import") is not False:
            raise ValueError("Input artwork queue is not pending review")
        key=(q.get("character_source_key"),q.get("variant_key"))
        if not all(isinstance(x,str) and x for x in key) or key in mapping:
            raise ValueError("Duplicate or missing variant identity")
        if not checked_https(q.get("candidate_image_url"),"upload.wikimedia.org") or not checked_https(q.get("candidate_file_page"),"commons.wikimedia.org"):
            raise ValueError("Missing original Commons image/file page")
        mapping[key]=q
    reviewed={}
    for item in decisions:
        if not isinstance(item,dict):
            raise ValueError("Human review must be a JSON object")
        key=(item.get("character_source_key"),item.get("variant_key"))
        if key not in mapping or key in reviewed:
            raise ValueError("Unknown/duplicate manual variant identity")
        reviewed[key]=item

    out=[]
    manifest=[]
    for key,q in sorted(mapping.items()):
        review=reviewed.get(key)
        if review is None or review.get("status") in ("pending","rejected"):
            continue
        if review.get("status")!="approved":
            raise ValueError("Manual decision must be pending, rejected or approved")
        if (review.get("candidate_file_title")!=q.get("candidate_file_title")
            or review.get("image_url")!=q["candidate_image_url"]
            or review.get("artwork_page_url")!=q["candidate_file_page"]):
            raise ValueError("Artwork approval must match exact original file and URL")
        if not all(review.get(field) is True for field in CHECKS):
            raise ValueError("Artwork needs identity, reuse, terms, safety AND Telegram checks")
        proof=review.get("evidence")
        if not isinstance(proof,dict) or not all(
             https_evidence(proof.get(field)) for field in REQUIRED_CHECKS):
            raise ValueError("Human review missing HTTPS evidence categories")
        notes=review.get("review_note")
        if not isinstance(notes,str) or len(notes.strip())<20:
            raise ValueError("Independent review must contain a substantive explanation")
        credits=credit_tuple(review)
        if not all(credits):
            raise ValueError("CC art requires artist/license/source attribution")
        if not checked_https(credits[3],"commons.wikimedia.org"):
            raise ValueError("Art source page must match Commons")
        variant={
            "character_source_key":key[0],
            "variant_key":key[1],
            "label":review.get("label"),
            "image_url":review["image_url"],
            "rarity":review.get("rarity","Common"),
            "spawn_weight":review.get("spawn_weight",100),
        }
        variant.update({field:value for field,value in zip(CREDIT_FIELDS,credits)})
        out.append(variant)
        entry={
            "character_source_key":key[0],"variant_key":key[1],
            "status":"approved","image_url":variant["image_url"],
            "artwork_identity_verified":True,
            "reuse_rights_verified":True,
            "content_suitability_verified":True,
            "upstream_terms_verified":True,
            "permission_reference":proof["artwork_public_reuse_rights"],
            "review_note":notes.strip(),
            "review_evidence":dict(proof),
        }
        entry.update({field:value for field,value in zip(CREDIT_FIELDS,credits)})
        manifest.append(entry)
    if out:
        validate_variants(out,manifest)
    return {
        "variants":out,"approvals":manifest,
        "summary":{"pending_worksheet_rows":len(mapping),
                   "human_approved_variant_records":len(out),
                   "pending_or_rejected":len(mapping)-len(out),
                   "database_writes":0,"images_downloaded":0,
                   "note":"Review references require verification; no automatic permissions."},
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("pending_worksheet")
    p.add_argument("human_decisions")
    p.add_argument("--variants-out",required=True)
    p.add_argument("--approvals-out",required=True)
    args=p.parse_args()
    queue=json.loads(Path(args.pending_worksheet).read_text(encoding="utf8"))
    decisions=json.loads(Path(args.human_decisions).read_text(encoding="utf8"))
    result=assemble(queue,decisions)
    first=Path(args.variants_out)
    second=Path(args.approvals_out)
    if first.resolve()==second.resolve():
        raise ValueError("Outputs must be separate files")
    first.parent.mkdir(parents=True,exist_ok=True)
    second.parent.mkdir(parents=True,exist_ok=True)
    first.write_text(json.dumps(result["variants"],ensure_ascii=False,indent=2)+"\n",
                     encoding="utf8")
    second.write_text(json.dumps(result["approvals"],ensure_ascii=False,indent=2)+"\n",
                      encoding="utf8")
    print(json.dumps(result["summary"],ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
