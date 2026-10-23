"""Curated Commons *file-title discovery* for manual character-art review.

Wikimedia Action API 'categorymembers' returns metadata (NO image bytes).
Only the FOUR documented single-character categories can be requested.
The category says *topic*, NOT depicted-character identity or image rights.
Discover files at most once per explicitly selected category; do not crawl
subcategories, paginate indefinitely, autoapprove, or populate bot catalog.
Default CLI is offline. Live needs --fetch + a real contact User-Agent.
"""
import argparse
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API="https://commons.wikimedia.org/w/api.php"
MAX_CATEGORIES=4
FILES_PER_CATEGORY=50
MAX_JSON_BYTES=450_000
CATEGORY_IDENTITIES={
    "Category:Wikipe-tan":("commons:wikipe-tan:original","Wikipe-tan","Wikimedia mascots"),
    "Category:Commons-tan":("commons:commons-tan:original","Commons-tan","Wikimedia mascots"),
    "Category:Wikiquote-tan":("commons:wikiquote-tan:original","Wikiquote-tan","Wikimedia mascots"),
    "Category:Kiki the Cyber Squirrel":("commons:kiki:original","Kiki the Cyber Squirrel","Krita"),
}
IMAGE_SUFFIXES=(".jpg",".jpeg",".png")
# Only a preliminary filename filter, NOT content safety verification.
AMBIGUOUS_OR_UNSUITABLE=re.compile(
    r"\b(adult|bikini|nude|nsfw|porn|cosplay|photo|screenshot|real.person|"
    r"animation|meme|poster|banner|logo|icon|comparison|parody|derivative|"
    r"ai.generated)\b",re.IGNORECASE
)


def _validate_categories(categories):
    if (not isinstance(categories,list) or not 1<=len(categories)<=MAX_CATEGORIES
        or any(not isinstance(c,str) or c not in CATEGORY_IDENTITIES for c in categories)
        or len(set(categories))!=len(categories)):
        raise ValueError("Select 1..4 distinct curated character-specific Commons categories")
    return categories


def parse_members(category, payload):
    """Only file names. Never create image URLs by guessing Commons MD5 paths."""
    if category not in CATEGORY_IDENTITIES:
        raise ValueError("Unknown Commons category")
    if (not isinstance(payload,dict) or not isinstance(payload.get("query"),dict)
        or "error" in payload):
        raise ValueError("Malformed Commons category metadata response")
    members=payload["query"].get("categorymembers")
    if not isinstance(members,list) or len(members)>FILES_PER_CATEGORY:
        raise ValueError("Commons returned unexpected file-member count")
    key,name,series=CATEGORY_IDENTITIES[category]
    rows=[]
    seen=set()
    rejected={"duplicate":0,"not_single_jpeg_png_file":0,
              "potentially_unsuitable_title":0}
    for row in members:
        if not isinstance(row,dict) or row.get("ns")!=6:
            rejected["not_single_jpeg_png_file"]+=1
            continue
        title=row.get("title")
        if (not isinstance(title,str) or not title.startswith("File:")
            or len(title)>220 or "|" in title or "\n" in title or "\r" in title
            or not title.casefold().endswith(IMAGE_SUFFIXES)):
            rejected["not_single_jpeg_png_file"]+=1
            continue
        if title in seen:
            rejected["duplicate"]+=1
            continue
        seen.add(title)
        if AMBIGUOUS_OR_UNSUITABLE.search(title.replace("_"," ").replace("-"," ")):
            rejected["potentially_unsuitable_title"]+=1
            continue
        rows.append({
            "commons_file_title":title,
            "claimed_character_source_key":key,
            "claimed_character_name":name,
            "claimed_series":series,
            "category":category,
            "image_url":None,
            "license_name":None,
            "artist":None,
            "source_identity_verified":False,
            "audience_suitability_verified":False,
            "reuse_rights_verified":False,
            "telegram_photo_verified":False,
            "status":"pending_human_review",
            "approved_for_import":False,
        })
    return {"category":category,"reported_file_rows":len(members),
            "review_titles":rows,"rejected":rejected,
            "has_more_pages":bool(payload.get("continue")),
            "approved":0}


def _fetch(category, user_agent, opener):
    params={"action":"query","format":"json","formatversion":"2",
            "list":"categorymembers","cmtitle":category,
            "cmtype":"file","cmlimit":str(FILES_PER_CATEGORY),"maxlag":"5"}
    request=Request(API+"?"+urlencode(params),headers={
        "Accept":"application/json","Accept-Encoding":"identity",
        "User-Agent":user_agent,
    })
    try:
        with opener(request,timeout=15) as response:
            if getattr(response,"status",200)!=200:
                raise RuntimeError("Commons category API returned unexpected status")
            payload=response.read(MAX_JSON_BYTES+1)
    except (HTTPError,URLError,TimeoutError,OSError) as exc:
        raise RuntimeError("Commons category request failed/rate limited: STOP") from exc
    if len(payload)>MAX_JSON_BYTES:
        raise ValueError("Oversized Commons metadata response")
    return json.loads(payload)


def discover(categories, *,fetch=False,user_agent="",opener=urlopen):
    _validate_categories(categories)
    if fetch and (not isinstance(user_agent,str) or len(user_agent.strip())<20
                  or ("@" not in user_agent and "https://" not in user_agent)):
        raise ValueError("Live Commons discovery needs a genuine contact User-Agent")
    audits=[]
    for category in categories:
        if not fetch:
            audits.append({"category":category,"reported_file_rows":0,
                           "review_titles":[],"has_more_pages":False,
                           "not_fetched":True,"approved":0})
            continue
        audits.append(parse_members(category,_fetch(category,user_agent,opener)))
    rows=[r for x in audits for r in x["review_titles"]]
    # Never claim this is a COMPLETE category crawl. No continuation request.
    return {"source":"Wikimedia Commons categorymembers API",
            "mode":"one_page_per_explicit_category" if fetch else "offline",
            "categories_requested":len(categories),
            "api_requests":len(categories) if fetch else 0,
            "file_titles_for_review":len(rows),
            "review_titles":rows,
            "category_summaries":[{k:v for k,v in a.items() if k!="review_titles"}
                                  for a in audits],
            "approved_artworks":0,"import_ready_characters":0,
            "image_bytes_downloaded":0,"database_writes":0,
            "note":"Category membership and filenames do not prove character identity, "
                   "safety, a free license or Telegram photo compatibility."}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("output")
    p.add_argument("--category",action="append",dest="categories",
                   required=True,help="One of the four curated Category: names")
    p.add_argument("--fetch",action="store_true",
                   help="Opt-in metadata lookup; maximum four HTTPS API requests")
    args=p.parse_args()
    result=discover(args.categories,fetch=args.fetch,
                    user_agent=os.getenv("WIKIMEDIA_USER_AGENT",""))
    target=Path(args.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",
                      encoding="utf8")
    print(json.dumps({k:v for k,v in result.items() if k!="review_titles"},
                     ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
