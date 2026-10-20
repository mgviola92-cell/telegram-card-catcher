"""Offline review for two ACTUAL researched artwork lead lists.

These are NOT production catalogs. Fail closed on unknown hosts, duplicate IDs
or premature rights / Telegram assertions. Never access networks or databases.
"""
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
PEPPER=ROOT/"data/peppercarrot_official_portraits.pending.json"
COMMONS=ROOT/"data/commons_six_source_triage.review.json"
FLAGS=("artwork_identity_verified","reuse_rights_verified",
       "content_suitability_verified","upstream_terms_verified",
       "telegram_photo_verified")


def _https_exact(url,host):
    if not isinstance(url,str):
        return False
    try:
        parts=urlsplit(url)
        return (parts.scheme=="https" and parts.hostname==host
                and parts.username is None and parts.password is None
                and parts.port is None and not parts.fragment
                and parts.path.startswith("/"))
    except ValueError:
        return False


def audit(pending,triage):
    if not isinstance(pending,dict) or not isinstance(triage,dict):
        raise ValueError("Expected two explicit research reports")
    rows=pending.get("rows")
    reviews=triage.get("reviews")
    if not isinstance(rows,list) or not isinstance(reviews,list):
        raise ValueError("Missing named character/image review rows")
    source_keys=set()
    urls=set()
    for row in rows:
        if not isinstance(row,dict):
            raise ValueError("Invalid portrait metadata")
        key=row.get("source_key")
        url=row.get("candidate_image_url")
        if (not isinstance(key,str) or not key.startswith("peppercarrot:hereva:")
            or key in source_keys or not row.get("name")
            or row.get("series")!="Pepper&Carrot"
            or row.get("image_url") is not None
            or row.get("telegram_file_id") is not None
            or row.get("approved_for_import") is not False
            or any(row.get(flag) is not False for flag in FLAGS)
            or not _https_exact(url,"www.peppercarrot.com")
            or not url.startswith("https://www.peppercarrot.com/data/wiki/medias/img/chara_")
            or not url.endswith(".jpg") or url in urls
            or not _https_exact(row.get("source_character_page"),"www.peppercarrot.com")
            or not _https_exact(row.get("source_license_page"),"www.peppercarrot.com")):
            raise ValueError("Unreviewed portrait cannot be promoted to approved art")
        source_keys.add(key)
        urls.add(url)
    seen=set()
    blocked=0
    for row in reviews:
        if not isinstance(row,dict):
            raise ValueError("Invalid Commons triage")
        title=row.get("file_title")
        if (not isinstance(title,str) or not title.startswith("File:")
            or title in seen or row.get("approved_for_import") is not False
            or any(row.get(flag) is not False for flag in FLAGS)
            or not _https_exact(row.get("file_page_url"),"commons.wikimedia.org")):
            raise ValueError("Commons triage is not an artwork approval record")
        seen.add(title)
        if row.get("triage_status","").startswith("blocked_"):
            blocked+=1
    if pending.get("identities_with_direct_portrait_urls")!=len(rows):
        raise ValueError("Portrait summary is stale")
    if pending.get("rights_approved")!=0 or pending.get("telegram_confirmed")!=0 or pending.get("db_writes")!=0:
        raise ValueError("Staged file must report no live readiness")
    return {"pending_distinct_official_characters":len(source_keys),
            "pending_official_picture_urls":len(urls),
            "commons_reviewed_file_page_leads":len(seen),
            "commons_on_hold_for_cross_ip_or_other_flags":blocked,
            "rights_approved":0,"telegram_tested":0,
            "import_ready":0,"database_writes":0}


def main():
    pending=json.loads(PEPPER.read_text(encoding="utf-8"))
    commons=json.loads(COMMONS.read_text(encoding="utf-8"))
    print(json.dumps(audit(pending,commons),indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
