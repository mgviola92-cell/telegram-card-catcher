"""Enrich a SMALL set of pending Commons file titles using imageinfo metadata.

Strictly OFFLINE by default. The opt-in --fetch mode makes at most FOUR
Commons Action API JSON requests (<=12 distinct File: titles each).
No image is downloaded, no Telegram message is sent, and no character is
approved or imported. Exact file URL, MIME/dimensions, rights metadata and
creator hints still require real manual verification.

This script intentionally DOES NOT recurse categories, auto-apply rights,
or guess Commons image path hashes from filenames.
"""
import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import re
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from scripts.commons_category_discovery import (
    CATEGORY_IDENTITIES, MAX_JSON_BYTES, API,
)
from scripts.commons_media_metadata_audit import (
    plain, same_canonical_url,
)
from scripts.artwork_candidate_checklist import checked_https

MAX_PER_SERIES=12
MAX_ITEMS=48
BATCH=12


def select_titles(report, limit=48, max_per_character=12):
    if (not isinstance(report,dict)
        or report.get("source")!="Wikimedia Commons categorymembers API"
        or not isinstance(report.get("review_titles"),list)
        or len(report["review_titles"])>200
        or type(limit) is not int or not 1<=limit<=MAX_ITEMS
        or type(max_per_character) is not int
        or not 1<=max_per_character<=MAX_PER_SERIES):
        raise ValueError("Expected a bounded explicit Commons discovery report")
    buckets=defaultdict(list)
    candidates=report["review_titles"]
    sources_by_title=defaultdict(set)
    valid_rows=[]
    for row in candidates:
        if (not isinstance(row,dict) or row.get("status")!="pending_human_review"
            or row.get("approved_for_import") is not False
            or row.get("image_url") is not None):
            raise ValueError("Refusing pre-approved or image-enriched discovery data")
        title=row.get("commons_file_title")
        cat=row.get("category")
        if (not isinstance(title,str) or not re.fullmatch(r"File:[^|\r\n]{1,210}",title)
            or cat not in CATEGORY_IDENTITIES):
            raise ValueError("Malformed Commons category/file identity")
        source,name,series=CATEGORY_IDENTITIES[cat]
        if (row.get("claimed_character_source_key")!=source or
            row.get("claimed_character_name")!=name or
            row.get("claimed_series")!=series):
            raise ValueError("Unsafe category-to-character mapping")
        # Commons category membership is many-to-many. The same file can
        # depict several mascots; cross-category hits must be removed FROM
        # BOTH character pools, not assigned to the first category seen.
        sources_by_title[title].add(source)
        valid_rows.append(row)
    ambiguous={title for title,sources in sources_by_title.items()
               if len(sources)>1}
    seen=set()
    for row in valid_rows:
        title=row["commons_file_title"]
        source=row["claimed_character_source_key"]
        if title in ambiguous or (source,title) in seen:
            continue
        seen.add((source,title))
        buckets[source].append(row)
    for group in buckets.values():
        group.sort(key=lambda r:r["commons_file_title"].casefold())
    selected=[]
    # No single very large subcategory starves three smaller character pools.
    for index in range(max_per_character):
        for source in sorted(buckets):
            group=buckets[source]
            if index<len(group):
                selected.append(group[index])
                if len(selected)>=limit:
                    return selected
    return selected


def parse_imageinfo(selected, payload):
    if not isinstance(selected,list) or not 1<=len(selected)<=BATCH:
        raise ValueError("Imageinfo chunk must contain 1..12 file titles")
    if not isinstance(payload,dict) or not isinstance(payload.get("query"),dict):
        raise ValueError("Invalid Commons imageinfo metadata")
    pages=payload["query"].get("pages")
    if not isinstance(pages,list) or len(pages)>BATCH:
        raise ValueError("Unexpected imageinfo page list")
    by_title={}
    for page in pages:
        if not isinstance(page,dict):
            raise ValueError("Invalid Commons page response")
        name=page.get("title")
        if not isinstance(name,str) or name in by_title:
            raise ValueError("Ambiguous duplicate Commons file title")
        by_title[name]=page
    output=[]
    for source in selected:
        title=source["commons_file_title"]
        page=by_title.get(title,{})
        info=page.get("imageinfo") or []
        detail=info[0] if isinstance(info,list) and len(info)==1 else {}
        if not isinstance(detail,dict):
            detail={}
        raw_url=detail.get("url")
        raw_page=detail.get("descriptionurl")
        mime=detail.get("mime")
        size=detail.get("size")
        width=detail.get("width")
        height=detail.get("height")
        ext=detail.get("extmetadata") or {}
        if not isinstance(ext,dict):
            ext={}
        # Do not even surface remote URLs with unfamiliar hosts/protocols.
        valid=(checked_https(raw_url,"upload.wikimedia.org") and
               checked_https(raw_page,"commons.wikimedia.org") and
               isinstance(raw_page,str) and
               same_canonical_url(raw_page,
                   "https://commons.wikimedia.org/wiki/"+
                   quote(title.replace(" ","_"),safe="():")))
        photo_ok=(valid and mime in ("image/png","image/jpeg")
                  and type(size) is int and 0<size<=5_000_000
                  and type(width) is int and type(height) is int
                  and 0<width<=10_000 and 0<height<=10_000)
        hinted_non_free=plain(ext.get("NonFree")).casefold() in ("true","1","yes")
        photo_ok=photo_ok and not hinted_non_free
        output.append({
            **source,
            "candidate_image_url":raw_url if valid else None,
            "file_page_url":raw_page if valid else None,
            "image_url":None, # importer field MUST STAY unset
            "mime":mime if isinstance(mime,str) else None,
            "image_size_bytes":size if type(size) is int else None,
            "width":width if type(width) is int else None,
            "height":height if type(height) is int else None,
            "artist_hint_unverified":plain(ext.get("Artist")),
            "license_hint_unverified":plain(ext.get("LicenseShortName")),
            "license_url_unverified":plain(ext.get("LicenseUrl")),
            "metadata_photo_candidate":bool(photo_ok),
            "metadata_rejection_reason":(
                "awaiting_essential_metadata_or_untrusted_file"
                if not photo_ok else None),
            "status":"pending_human_review",
            "source_identity_verified":False,
            "audience_suitability_verified":False,
            "reuse_rights_verified":False,
            "telegram_photo_verified":False,
            "approved_for_import":False,
        })
    return output


def _get_page(titles, agent, opener):
    params={"action":"query","format":"json","formatversion":"2",
            "prop":"imageinfo","iiprop":"url|size|mime|extmetadata",
            "titles":"|".join(titles),"maxlag":"5"}
    req=Request(API+"?"+urlencode(params),headers={
        "User-Agent":agent,"Accept":"application/json","Accept-Encoding":"identity"})
    try:
        with opener(req,timeout=16) as response:
            if getattr(response,"status",200)!=200:
                raise RuntimeError("Unexpected Commons API status")
            content=response.read(MAX_JSON_BYTES+1)
    except (HTTPError,URLError,TimeoutError,OSError) as exc:
        raise RuntimeError("Commons provider unavailable; abort without retry") from exc
    if len(content)>MAX_JSON_BYTES:
        raise ValueError("Oversized Commons metadata response")
    data=json.loads(content)
    if not isinstance(data,dict) or "error" in data:
        raise ValueError("Commons metadata request rejected")
    return data


def enrich(report,*,fetch=False,user_agent="",limit=48,opener=urlopen):
    selected=select_titles(report,limit=limit)
    identities_by_title=defaultdict(set)
    for item in report["review_titles"]:
        if isinstance(item,dict):
            identities_by_title[item.get("commons_file_title")].add(
                item.get("claimed_character_source_key"))
    collisions=sum(len(sources)>1 for sources in identities_by_title.values())
    if fetch and (not isinstance(user_agent,str) or len(user_agent.strip())<20
                  or ("@" not in user_agent and "https://" not in user_agent)):
        raise ValueError("Need real contact User-Agent for Commons")
    if not fetch:
        return {"mode":"offline","selected_file_titles":len(selected),
                "api_requests":0,"review_rows":selected,
                "ambiguous_cross_character_file_titles_excluded":collisions,
                "artworks_approved":0,"image_bytes_downloaded":0,
                "database_writes":0}
    enriched=[]
    for start in range(0,len(selected),BATCH):
        subset=selected[start:start+BATCH]
        response=_get_page([r["commons_file_title"] for r in subset],user_agent,opener)
        enriched.extend(parse_imageinfo(subset,response))
    return {"mode":"bounded_live_imageinfo_metadata",
            "selected_file_titles":len(selected),
            "api_requests":(len(selected)+BATCH-1)//BATCH,
            "ambiguous_cross_character_file_titles_excluded":collisions,
            "metadata_photo_candidates":sum(r["metadata_photo_candidate"] for r in enriched),
            "review_rows":enriched,
            "artworks_approved":0,"import_ready_characters":0,
            "image_bytes_downloaded":0,"database_writes":0,
            "note":"Candidate filenames, MIME and a CC hint never establish rights, "
                   "subject identity, suitability or Telegram reachability."}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("discovered")
    p.add_argument("output")
    p.add_argument("--limit",type=int,default=48)
    p.add_argument("--fetch",action="store_true")
    args=p.parse_args()
    report=json.loads(Path(args.discovered).read_text(encoding="utf8"))
    result=enrich(report,limit=args.limit,fetch=args.fetch,
                  user_agent=os.getenv("WIKIMEDIA_USER_AGENT",""))
    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({k:v for k,v in result.items() if k!="review_rows"},
                     ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
