"""Shared approved-artwork variant importer: offline by default.

Use only with independently verified permissions and character/artwork match.
A URL or an AI-generated label is NOT a license. No image is downloaded;
each variant saves one HTTPS URL + nullable Telegram file_id shared by owners.
"""
import argparse
import ipaddress
import json
import re
from urllib.parse import urlsplit

from app.storage import connect, RARITIES
from scripts.artwork_attribution import credit_tuple, reviewed_credit

MAX_VARIANTS=1000
KEY=re.compile(r"[a-zA-Z0-9_.:-]{3,120}\Z")
CONFIRM="IMPORT_REVIEWED_VARIANTS"


def safe_url(text):
    if not isinstance(text,str) or not 12<=len(text)<=2048:
        return False
    try:
        parsed=urlsplit(text)
        if (parsed.scheme!="https" or not parsed.hostname
            or parsed.port not in (None,443) or parsed.username or parsed.password
            or parsed.fragment or parsed.hostname.endswith(".localhost")
            or parsed.hostname=="localhost"):
            return False
        try:
            ipaddress.ip_address(parsed.hostname)
            return False
        except ValueError:
            return True
    except ValueError:
        return False


def validate(rows, approvals):
    if (not isinstance(rows,list) or not isinstance(approvals,list)
        or len(rows)>MAX_VARIANTS or len(approvals)>MAX_VARIANTS):
        raise ValueError("Provide bounded variant rows and approval manifests")
    checked={}
    for review in approvals:
        if not isinstance(review,dict):
            raise ValueError("Invalid artwork permission review")
        identity=(review.get("character_source_key"),review.get("variant_key"))
        if identity in checked or not all(isinstance(v,str) for v in identity):
            raise ValueError("Repeated/invalid artwork permission identity")
        for flag in ("artwork_identity_verified","reuse_rights_verified",
                     "content_suitability_verified","upstream_terms_verified"):
            if review.get(flag) is not True:
                raise ValueError("Independent reviewer has not completed every check")
        if (review.get("status")!="approved" or
            not safe_url(review.get("image_url")) or
            not safe_url(review.get("permission_reference")) or
            not isinstance(review.get("review_note"),str) or
            len(review["review_note"].strip())<20):
            raise ValueError("Approved variants require exact image and permission proof")
        checked[identity]=review
    accepted=[]
    seen=set()
    for entry in rows:
        if not isinstance(entry,dict):
            raise ValueError("Variant must be an object")
        source,key,label=(entry.get(x) for x in
                          ("character_source_key","variant_key","label"))
        ident=(source,key)
        if ident in seen or not all(isinstance(v,str) and
            KEY.fullmatch(v) for v in (source,key)):
            raise ValueError("Missing/repeated variant source identity")
        seen.add(ident)
        if (not isinstance(label,str) or not 1<=len(label.strip())<=100
            or entry.get("rarity","Common") not in RARITIES
            or type(entry.get("spawn_weight",100)) is not int
            or not 0<=entry.get("spawn_weight",100)<=10000):
            raise ValueError("Invalid artwork label, rarity or spawn weight")
        url=entry.get("image_url")
        if not safe_url(url):
            raise ValueError("Unsafe or absent artwork HTTPS URL")
        review=checked.get(ident)
        if review is None or review["image_url"]!=url:
            raise ValueError("Variant cannot be enabled without exact-image review")
        accepted.append((source,key,label.strip(),url,
                         entry.get("rarity","Common"),entry.get("spawn_weight",100),
                         *reviewed_credit(entry,review)))
    if len(checked)!=len(accepted):
        raise ValueError("Unused approval rows indicate source identity mismatch")
    return accepted


def apply(rows, approvals):
    values=validate(rows,approvals)
    if not values:
        raise ValueError("Empty variant import is not an approved operation")
    with connect() as db:
        # Single atomic transaction. Missing characters abort everything.
        for source,key,label,url,rarity,weight,author,license_name,license_url,page_url in values:
            found=db.execute("SELECT id FROM characters WHERE source_key=%s",
                             (source,)).fetchone()
            if not found:
                raise ValueError("Unknown character source_key: "+source)
            db.execute("""INSERT INTO character_variants
                (character_id,variant_key,label,image_url,rarity,spawn_weight,
                 enabled,artwork_author,artwork_license_name,
                 artwork_license_url,artwork_page_url)
                VALUES (%s,%s,%s,%s,%s,%s,true,%s,%s,%s,%s)
                ON CONFLICT(character_id,variant_key) DO UPDATE SET
                    label=EXCLUDED.label,image_url=EXCLUDED.image_url,
                    rarity=EXCLUDED.rarity,spawn_weight=EXCLUDED.spawn_weight,
                    artwork_author=EXCLUDED.artwork_author,
                    artwork_license_name=EXCLUDED.artwork_license_name,
                    artwork_license_url=EXCLUDED.artwork_license_url,
                    artwork_page_url=EXCLUDED.artwork_page_url,
                    enabled=true,
                    telegram_file_id=CASE WHEN
                      character_variants.image_url IS DISTINCT FROM EXCLUDED.image_url
                      THEN NULL ELSE character_variants.telegram_file_id END""",
                (found["id"],key,label,url,rarity,weight,
                 author,license_name,license_url,page_url))
    return len(values)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("variants",help="Explicit human-review variants JSON")
    parser.add_argument("--approval-manifest",required=True)
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--rights-reviewed",action="store_true")
    parser.add_argument("--confirm",default="")
    args=parser.parse_args()
    with open(args.variants,encoding="utf8") as f:
        rows=json.load(f)
    with open(args.approval_manifest,encoding="utf8") as f:
        proofs=json.load(f)
    verified=validate(rows,proofs)
    if not args.apply:
        print(json.dumps({"mode":"dry_run","reviewed_variants":len(verified),
                          "production_writes":0,"images_downloaded":0}))
        return 0
    if not args.rights_reviewed or args.confirm!=CONFIRM:
        parser.error("--apply requires --rights-reviewed --confirm IMPORT_REVIEWED_VARIANTS")
    written=apply(rows,proofs)
    print(json.dumps({"mode":"explicit_approved_write","variant_upserts":written,
                      "images_downloaded":0}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
