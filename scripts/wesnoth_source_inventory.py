"""Offline validation of real, version-pinned open-source Wesnoth PNG URLs.

The inventory is extracted from OFFICIAL GitHub Git trees, not fabricated
or stock/generated art. The source-wide copyright policy explicitly permits
reuse under GPL v2+ or CC BY-SA 4.0 *subject to those obligations*.
These rows are verified SOURCE FILES, not verified unique characters,
not automatically license-cleared cards, not Telegram-tested photo links.
No binary bytes in our repo, Neon or Render.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

COMMIT="83d4b397f1de466c721e4e393b361c71fc4f5b6c"
RAW_PREFIX=f"https://raw.githubusercontent.com/wesnoth/wesnoth/{COMMIT}/"
PAGE_PREFIX=f"https://github.com/wesnoth/wesnoth/blob/{COMMIT}/"
POLICY="https://wiki.wesnoth.org/Wesnoth:Copyrights"
MAX_INVENTORY=2000


def audit(inventory):
    if (not isinstance(inventory,dict) or inventory.get("pinned_source_commit")!=COMMIT
        or not isinstance(inventory.get("files"),list)
        or not 1<=len(inventory["files"])<=MAX_INVENTORY):
        raise ValueError("Invalid upstream source catalog")
    seen=set()
    counts={"campaign_portraits":0,"unit_type_portraits":0}
    for row in inventory["files"]:
        if not isinstance(row,dict):
            raise ValueError("Non-object artwork file entry")
        path=row.get("source_file")
        collection=row.get("collection")
        if (not isinstance(path,str) or ".." in path or "\\" in path or
            not path.endswith(".png") or len(path)>320 or
            collection not in counts):
            raise ValueError("Unsupported upstream artwork file")
        if collection=="campaign_portraits":
            if not path.startswith("data/campaigns/") or "/images/portraits/" not in path:
                raise ValueError("Campaign portrait path altered")
        else:
            if not path.startswith("data/core/images/portraits/"):
                raise ValueError("Unit type portrait path altered")
        if (path in seen or row.get("source_file_page")!=PAGE_PREFIX+path
            or row.get("candidate_image_url")!=RAW_PREFIX+path
            or row.get("upstream_project_license_page")!=POLICY
            or row.get("pinned_source_commit")!=COMMIT
            or not isinstance(row.get("source_git_blob_sha"),str)
            or len(row.get("source_git_blob_sha"))!=40
            or type(row.get("source_file_bytes")) is not int
            or row["source_file_bytes"]<=0
            or any(row.get(flag) is not False for flag in (
                "approved_for_import","specific_artwork_license_confirmed",
                "artist_credit_verified","character_identity_verified",
                "telegram_send_photo_verified","age_suitability_verified"))):
            raise ValueError("Missing exact pinned source evidence or unreviewed flag")
        seen.add(path)
        counts[collection]+=1
    if (inventory.get("total_actual_source_files")!=len(seen)
        or any(inventory.get("counts",{}).get(k)!=v for k,v in counts.items())):
        raise ValueError("Reported counts do not match files")
    return {"total_source_pngs":len(seen),**counts,
            "live_catalog_characters_added":0,"image_files_downloaded":0,
            "database_writes":0,"legally_approved_specific_artworks":0,
            "note":"Source project permits conditional GPL/CC BY-SA reuse; exact license, identity, attribution and Telegram still pending."}


def export_review_leads(inventory,*,limit=MAX_INVENTORY):
    audit(inventory)
    if type(limit) is not int or not 1<=limit<=MAX_INVENTORY:
        raise ValueError("Invalid review limit")
    return [{
        "source_key":"wesnoth:portrait:"+row["source_file"].removeprefix("data/"),
        "source_file":row["source_file"],
        "campaign_or_family":row["campaign_or_unit_family"],
        "character_filename_hint":row["filename_identity_hint"],
        "candidate_image_url":row["candidate_image_url"],
        "source_file_page":row["source_file_page"],
        "upstream_license_policy":row["upstream_project_license_page"],
        "known_license_family":row["known_license_family"],
        "status":"pending","image_url":None,"approved_for_import":False,
        "character_identity_verified":False,"specific_artwork_license_confirmed":False,
        "artist_credit_verified":False,"telegram_send_photo_verified":False,
        "age_suitability_verified":False
    } for row in inventory["files"][:limit]]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",default="data/wesnoth_1_16_11_official_art_inventory.json")
    p.add_argument("--review-jsonl",help="Write local pending source-art review leads")
    a=p.parse_args()
    with open(a.input,encoding="utf8") as f:
        inventory=json.load(f)
    result=audit(inventory)
    if a.review_jsonl:
        out=Path(a.review_jsonl)
        if out.resolve()==Path(a.input).resolve():
            raise ValueError("Never overwrite inventory")
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text("".join(json.dumps(x,ensure_ascii=False)+"\n"
                               for x in export_review_leads(inventory)),encoding="utf8")
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
