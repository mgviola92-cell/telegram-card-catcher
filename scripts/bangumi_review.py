"""Bounded Bangumi public-v0 metadata-only subject/character REVIEW pilot.

Explicit opt-in --fetch. No private/p1 API, no crawling/pagination, no bulk
harvesting, no image URL output or artwork downloads, no Telegram/Neon writes.
Unknown/NSFW subject eligibility is DENIED (fail closed).
The API's metadata terms/permissions remain a separate review requirement.
"""
import argparse
import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = "https://api.bgm.tv/v0"
MAX_SUBJECTS = 5
MAX_RESPONSE = 500_000
MAX_CHARACTERS_PER_SUBJECT = 100
ID = re.compile(r"[1-9][0-9]{0,8}\Z", re.ASCII)


def safe_subject_id(value):
    if isinstance(value, bool):
        return None
    value = str(value).strip() if isinstance(value,(int,str)) else ""
    if ID.fullmatch(value):
        return int(value)
    return None


def is_eligible_subject(value):
    """Require an *explicit* non-sensitive boolean from the current API."""
    return (isinstance(value,dict)
            and value.get("nsfw") is False
            and isinstance(value.get("name"),str)
            and 1 <= len(value["name"].strip()) <= 150)


def review_characters(subject_id, subject, entries):
    """Output review-only character names; discard provider image objects."""
    if not is_eligible_subject(subject):
        return []
    if not isinstance(entries,list) or len(entries)>MAX_CHARACTERS_PER_SUBJECT:
        raise ValueError("Unexpected Bangumi related-character response size")
    result=[]
    seen=set()
    for row in entries:
        if not isinstance(row,dict):
            continue
        cid = safe_subject_id(row.get("id"))
        name = row.get("name")
        if cid is None or not isinstance(name,str) or not 1 <= len(name.strip()) <= 150:
            continue
        key=f"bangumi:character:{cid}"
        if key in seen:
            continue
        seen.add(key)
        result.append({
            "source_key":key,
            "name":name.strip(),
            "series":subject["name"].strip(),
            "source_subject_id":subject_id,
            "source_metadata_rights_review":"pending",
            "source_character_identity_review":"pending",
            "audience_suitability_review":"pending",
            "image_url":None,
            "telegram_file_id":None,
            "artwork_permission":"unverified",
            "import_ready":False,
        })
    return result


def _get_json(url, user_agent, opener):
    req=Request(url,headers={
        "User-Agent":user_agent,
        "Accept":"application/json",
        "Accept-Encoding":"identity",
    })
    try:
        with opener(req,timeout=12) as res:
            if getattr(res,"status",200)!=200:
                raise RuntimeError("Bangumi returned unexpected HTTP status")
            payload=res.read(MAX_RESPONSE+1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        # Stop on a provider refusal; no retry or quota-bypass attempts.
        raise RuntimeError("Bangumi API unavailable or rate-limited; stop pilot") from exc
    if len(payload)>MAX_RESPONSE:
        raise ValueError("Bangumi response too large for a review pilot")
    return json.loads(payload.decode("utf-8"))


def discover(subject_ids, *, fetch=False, user_agent="", opener=urlopen):
    if not isinstance(subject_ids,list) or not 1 <= len(subject_ids) <= MAX_SUBJECTS:
        raise ValueError("Use 1..5 manually chosen subject IDs")
    ids=[safe_subject_id(value) for value in subject_ids]
    if None in ids or len(set(ids))!=len(ids):
        raise ValueError("Subject IDs must be unique positive integers")
    if fetch and (not isinstance(user_agent,str) or len(user_agent.strip())<20
                  or "@" not in user_agent):
        raise ValueError("Identify responsible API client with contact address")
    results=[]
    for sid in ids:
        if not fetch:
            results.append({"subject_id":sid,"status":"offline_unchecked",
                            "characters":[], "eligible":False})
            continue
        subject=_get_json(f"{BASE}/subjects/{sid}",user_agent,opener)
        if not is_eligible_subject(subject):
            results.append({"subject_id":sid,"status":"not_eligible_or_unverified",
                            "characters":[],"eligible":False})
            continue
        # Only an explicitly non-NSFW subject is allowed to trigger character
        # metadata lookup; age-sensitive source content is not reproduced.
        chars=_get_json(f"{BASE}/subjects/{sid}/characters",user_agent,opener)
        entries=review_characters(sid,subject,chars)
        results.append({"subject_id":sid,"status":"metadata_review_only",
                        "characters":entries,"eligible":True})
    return {"source":"Bangumi public API v0",
            "mode":"small_explicit_network_pilot" if fetch else "offline",
            "subjects_requested":len(ids),
            "eligible_subjects":sum(x["eligible"] for x in results),
            "review_only_character_records":sum(len(x["characters"]) for x in results),
            "subjects":results,
            "artwork_approved":0,"import_ready":0,
            "database_writes":0,"downloaded_image_bytes":0,
            "note":"Neither provider terms nor artwork reuse rights are approved. "
                   "No unscreened subjects, source image URLs, or images are imported."}


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("subject_ids",nargs="+",type=int,help="Known public subject IDs, up to 5")
    cli.add_argument("--fetch",action="store_true")
    cli.add_argument("--output",required=True)
    a=cli.parse_args()
    result=discover(a.subject_ids,fetch=a.fetch,
                    user_agent=os.getenv("BANGUMI_USER_AGENT",""))
    target=Path(a.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"mode":result["mode"],
                      "subjects_requested":result["subjects_requested"],
                      "review_only_character_records":result["review_only_character_records"],
                      "artwork_approved":0,"import_ready":0}))


if __name__=="__main__":
    main()
