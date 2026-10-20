"""Batch-verify Wikimedia Commons FILE METADATA, never image bytes.

The optional one-request Action API batch retrieves mime, size, dimensions,
file page and license/credit hints for exact File: titles from a bounded
review queue. It NEVER automatically authorizes artwork or writes to Neon.
License fields are metadata claims; source identity and rights still need a
human reviewer. --fetch requires a descriptive Wikimedia User-Agent/contact.
"""
import argparse
from html import unescape
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, unquote, urlsplit
from urllib.request import Request, urlopen

from scripts.artwork_candidate_checklist import checked_https

API="https://commons.wikimedia.org/w/api.php"
MAX_BATCH=12
MAX_JSON_BYTES=1_000_000
PHOTO_MIME={"image/jpeg","image/png"}
MAX_REMOTE_IMAGE_BYTES=5_000_000  # conservative review heuristic, not Telegram SLA


def plain(value):
    """Normalize HTML-like extmetadata into short audit hints, not raw pages."""
    if isinstance(value,dict):
        value=value.get("value","")
    if not isinstance(value,str):
        return ""
    return " ".join(unescape(re.sub(r"<[^>]*>"," ",value)).split())[:300]


def same_canonical_url(first,second):
    """Compare known HTTPS links without treating equivalent %2C vs ',' as edits.

    Only removes percent-encoding ambiguity; never accepts a different domain,
    image path, fragment or query as the 'same file'.
    """
    if not isinstance(first,str) or not isinstance(second,str):
        return False
    try:
        a,b=urlsplit(first),urlsplit(second)
        return (a.scheme==b.scheme=="https" and a.hostname==b.hostname
                and a.username is None and b.username is None
                and a.password is None and b.password is None
                and a.port==b.port
                and unquote(a.path).replace(" ","_")==unquote(b.path).replace(" ","_")
                and a.query==b.query and not a.fragment and not b.fragment)
    except ValueError:
        return False


def inspect_payload(rows,payload):
    if not isinstance(rows,list) or not 1<=len(rows)<=MAX_BATCH:
        raise ValueError("Commons file audit is capped at 1..12 candidates")
    if not isinstance(payload,dict) or not isinstance(payload.get("query"),dict):
        raise ValueError("Missing or malformed Commons imageinfo response")
    pages=payload["query"].get("pages",[])
    if not isinstance(pages,list) or len(pages)>MAX_BATCH:
        raise ValueError("Unexpected Commons API page list")
    mapped={}
    for page in pages:
        if not isinstance(page,dict):
            raise ValueError("Malformed Commons page")
        title=page.get("title")
        if not isinstance(title,str) or title in mapped:
            raise ValueError("Duplicate/invalid Commons API title")
        mapped[title]=page
    seen=set()
    output=[]
    for candidate in rows:
        if not isinstance(candidate,dict):
            raise ValueError("Malformed image review candidate")
        title=candidate.get("commons_file_title")
        key=candidate.get("source_key")
        file_url=candidate.get("candidate_image_url")
        page_url=candidate.get("file_page_url")
        if (not isinstance(title,str) or not title.startswith("File:")
            or len(title)>220 or not isinstance(key,str) or not key.strip()
            or (key,title) in seen):
            raise ValueError("Invalid/repeated Commons candidate key and title")
        seen.add((key,title))
        if not checked_https(file_url,"upload.wikimedia.org") or not checked_https(page_url,"commons.wikimedia.org"):
            raise ValueError("Untrusted candidate file or page host")
        page=mapped.get(title,{})
        details=page.get("imageinfo") or []
        if not isinstance(details,list) or len(details)>1:
            raise ValueError("Unexpected image history length in Commons API")
        info=details[0] if details else {}
        if not isinstance(info,dict):
            raise ValueError("Invalid Commons image info")
        props=info.get("extmetadata") or {}
        if not isinstance(props,dict):
            raise ValueError("Invalid Commons extmetadata")
        filesize=info.get("size")
        width=info.get("width")
        height=info.get("height")
        mime=info.get("mime")
        same_url=same_canonical_url(info.get("url"),file_url)
        same_page=same_canonical_url(info.get("descriptionurl"),page_url)
        mime_ok=mime in PHOTO_MIME
        size_ok=type(filesize) is int and 0<filesize<=MAX_REMOTE_IMAGE_BYTES
        dims_ok=(type(width) is int and type(height) is int and
                 0<width<=10_000 and 0<height<=10_000)
        hints={
            "license_name_unverified":plain(props.get("LicenseShortName")),
            "license_page_unverified":plain(props.get("LicenseUrl")),
            "artist_unverified":plain(props.get("Artist")),
            "credit_unverified":plain(props.get("Credit")),
            "attribution_unverified":plain(props.get("Attribution")),
            "non_free_claim":plain(props.get("NonFree")),
            "restrictions_unverified":plain(props.get("Restrictions")),
        }
        obvious_non_free=hints["non_free_claim"].casefold() in ("1","true","yes")
        # Status is media metadata readiness for HUMAN review, NOT approval.
        checks={"exact_media_url":same_url,"exact_file_page":same_page,
                "jpeg_or_png":mime_ok,"conservative_size_ok":size_ok,
                "dimensions_ok":dims_ok,"no_nonfree_flag":not obvious_non_free}
        output.append({
            "source_key":key,
            "commons_file_title":title,
            "commons_page":page_url,
            "mime":mime if isinstance(mime,str) else None,
            "bytes":filesize if type(filesize) is int else None,
            "width":width if type(width) is int else None,
            "height":height if type(height) is int else None,
            "raw_media_checks":checks,
            "metadata_potentially_usable":all(checks.values()),
            **hints,
            "source_identity_verified":False,
            "artwork_permission_verified":False,
            "telegram_send_verified":False,
            "approved_for_import":False,
            "note":"Metadata hints are not artwork licenses or an actual Telegram send test.",
        })
    return {"source":"Commons Action API imageinfo; review-only",
            "candidate_count":len(output),
            "metadata_potentially_usable_count":sum(x["metadata_potentially_usable"] for x in output),
            "review_rows":output,
            "artworks_approved":0,
            "telegram_uploads":0,
            "image_bytes_downloaded":0,"database_writes":0}


def inspect(rows, *, fetch=False, user_agent="", opener=urlopen):
    if not isinstance(rows,list) or not 1<=len(rows)<=MAX_BATCH:
        raise ValueError("Select 1..12 image review candidates")
    if not fetch:
        return {"mode":"offline","candidate_count":len(rows),
                "requires_live_api_inspection":True,"artworks_approved":0,
                "image_bytes_downloaded":0,"database_writes":0}
    if not isinstance(user_agent,str) or len(user_agent.strip())<20 or (
            "@" not in user_agent and "https://" not in user_agent):
        raise ValueError("Explicit contact-identifying Wikimedia User-Agent required")
    # The API is *not* sent candidate image URLs and does not transfer images.
    titles=[]
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get("commons_file_title"),str):
            raise ValueError("Missing exact Commons File: title")
        title=row["commons_file_title"]
        if not re.fullmatch(r"File:[^|\r\n]{1,210}",title):
            raise ValueError("Unsafe Commons API page title")
        titles.append(title)
    if len(set(titles))!=len(titles):
        raise ValueError("Review exact file titles only once")
    params={"action":"query","format":"json","formatversion":"2",
            "prop":"imageinfo","iiprop":"url|size|mime|extmetadata",
            "titles":"|".join(titles),"maxlag":"5"}
    request=Request(API+"?"+urlencode(params),headers={
        "User-Agent":user_agent.strip(),"Accept":"application/json",
        "Accept-Encoding":"identity"})
    try:
        with opener(request,timeout=20) as response:
            payload=response.read(MAX_JSON_BYTES+1)
    except (HTTPError,URLError,TimeoutError,OSError) as exc:
        raise RuntimeError("Commons metadata lookup failed/rate limited; no retry") from exc
    if len(payload)>MAX_JSON_BYTES:
        raise ValueError("Commons metadata response exceeded 1 MB")
    data=json.loads(payload)
    if "error" in data:
        raise ValueError("Commons API error; do not continue/retry")
    result=inspect_payload(rows,data)
    result["mode"]="one_bounded_live_metadata_request"
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("candidates",help="Up to 12 exact Commons candidate records")
    p.add_argument("output")
    p.add_argument("--fetch",action="store_true",help="Opt in to 1 Wikimedia API metadata-only request")
    a=p.parse_args()
    rows=json.loads(Path(a.candidates).read_text(encoding="utf8"))
    result=inspect(rows,fetch=a.fetch,user_agent=os.getenv("WIKIMEDIA_USER_AGENT",""))
    output=Path(a.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({k:v for k,v in result.items() if k!="review_rows"},indent=2))


if __name__=="__main__":
    main()
