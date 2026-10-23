"""Bulk JSONL/GZIP character+external-art-URL ingestion: ONE source batch.

100,000+ separate named characters in ONE input file; bounded memory.
No pictures, thumbnails, base64, or file IDs are downloaded or saved.
Dry-run NEVER connects to PostgreSQL. Apply requires a separately reviewed,
snapshot-pinned source-wide reuse grant, strict confirmation, and enough
free DB capacity. Grant assertions do not magically confer image rights.

Do NOT run apply on production without explicit owner authorization.
"""
import argparse
import gzip
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from urllib.parse import urlsplit

MAX_ROWS=1_000_000
MAX_LINE=64*1024
MAX_GRANT_BYTES=32768
MAX_ALIASES=20
DATABASE_LIMIT=1_073_741_824
RESERVE_BYTES=268_435_456
PER_NEW_CHARACTER_BUDGET=4096
CONFIRM="IMPORT_REVIEWED_BULK_URLS"
KEY_RE=re.compile(r"^[A-Za-z0-9_.:-]{3,120}$")
CATEGORIES={"anime","manga","manhwa","webtoon","game","other"}
RARITIES={"Common","Uncommon","Rare","Legendary","Mystical","Divine",
          "CrossVerse","Cataphract","Supreme","CNFT"}
UNSUITABLE={"adult","explicit","nsfw","18+","r18","r-18"}
INSERT_COLUMNS=("source_key","name","series","aliases","category","rarity",
                "image_url","weight","artwork_author","artwork_license_name",
                "artwork_license_url","artwork_page_url","enabled")

SQL_COPY="COPY cardkout_bulk_urls ("+",".join(INSERT_COLUMNS)+") FROM STDIN"
SQL_UPSERT="""INSERT INTO characters
    (source_key,name,series,aliases,category,rarity,image_url,weight,
     artwork_author,artwork_license_name,artwork_license_url,
     artwork_page_url,enabled)
  SELECT source_key,name,series,aliases,category,rarity,image_url,weight,
     artwork_author,artwork_license_name,artwork_license_url,
     artwork_page_url,enabled
    FROM cardkout_bulk_urls
  ON CONFLICT (source_key) WHERE source_key IS NOT NULL
  DO UPDATE SET
    name=EXCLUDED.name,series=EXCLUDED.series,aliases=EXCLUDED.aliases,
    category=EXCLUDED.category,rarity=EXCLUDED.rarity,
    weight=EXCLUDED.weight,
    image_url=EXCLUDED.image_url,
    artwork_author=EXCLUDED.artwork_author,
    artwork_license_name=EXCLUDED.artwork_license_name,
    artwork_license_url=EXCLUDED.artwork_license_url,
    artwork_page_url=EXCLUDED.artwork_page_url,
    telegram_file_id=CASE WHEN characters.image_url
                          IS DISTINCT FROM EXCLUDED.image_url
                          THEN NULL ELSE characters.telegram_file_id END,
    enabled=EXCLUDED.enabled"""


def valid_https(url, *, page=False):
    if not isinstance(url,str) or not 12<=len(url)<=2048:
        return False
    try:
        p=urlsplit(url)
        if (p.scheme!="https" or not p.hostname or p.port not in (None,443)
            or p.username is not None or p.password is not None
            or p.fragment or p.hostname=="localhost"
            or p.hostname.endswith(".localhost")):
            return False
        try:
            ipaddress.ip_address(p.hostname)
            return False
        except ValueError:
            pass
        return True if page else p.path.lower().endswith((".jpg",".jpeg",".png"))
    except ValueError:
        return False


def file_sha256(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def validate_grant(grant, input_digest):
    """Human attestation is required, but NEVER independently establishes IP rights."""
    if not isinstance(grant,dict):
        raise ValueError("Grant must be an independently reviewed JSON document")
    if (grant.get("catalog_sha256")!=input_digest
        or grant.get("review_status")!="independently_reviewed"
        or grant.get("scope_includes_every_image") is not True
        or grant.get("redistribution_to_telegram_permitted") is not True):
        raise ValueError("Source-wide grant lacks exact batch scope and explicit reuse review")
    prefix=grant.get("source_key_prefix")
    if (not isinstance(prefix,str) or len(prefix)<3 or len(prefix)>60
        or not KEY_RE.fullmatch(prefix+"test")):
        raise ValueError("Unsafe source key namespace")
    hosts=grant.get("image_hosts")
    if (not isinstance(hosts,list) or not 1<=len(hosts)<=16
        or len(set(hosts))!=len(hosts)
        or any(not valid_https("https://"+x+"/art.jpg") or x!=x.lower()
               for x in hosts if isinstance(x,str))
        or any(not isinstance(x,str) for x in hosts)):
        raise ValueError("Require explicitly audited image hostname allowlist")
    if (not isinstance(grant.get("reviewed_by"),str)
        or len(grant["reviewed_by"].strip())<3
        or not isinstance(grant.get("review_note"),str)
        or len(grant["review_note"].strip())<30):
        raise ValueError("Independent source grant needs reviewer and rationale")
    for key in ("source_terms_url","artwork_license_url","license_scope_evidence_url",
                "credit_policy_url"):
        if not valid_https(grant.get(key),page=True):
            raise ValueError("Missing HTTPS source-wide grant evidence: "+key)
    license_name=grant.get("artwork_license_name")
    if not isinstance(license_name,str) or not 2<=len(license_name)<=90:
        raise ValueError("Specify exact reuse license, not an assumed option")
    return {**grant,"image_hosts":set(hosts)}


def normalize(row,grant, *,enable=False):
    if not isinstance(row,dict):
        raise ValueError("Non-object character record")
    if any(row.get(x) is True for x in ("adult","is_adult","isAdult","nsfw","explicit")):
        raise ValueError("Explicitly unsuitable character record")
    rating=row.get("age_rating") or row.get("rating")
    if isinstance(rating,str) and rating.casefold().strip() in UNSUITABLE:
        raise ValueError("Explicit adult age rating")
    key=row.get("source_key")
    if not isinstance(key,str) or not KEY_RE.fullmatch(key) or not key.startswith(grant["source_key_prefix"]):
        raise ValueError("Character does not belong to granted source namespace")
    name,series=row.get("name"),row.get("series")
    if not all(isinstance(v,str) and 1<=len(v.strip())<=150 for v in (name,series)):
        raise ValueError("Missing named character/series (not unnamed art assets)")
    url=row.get("image_url")
    if not valid_https(url) or urlsplit(url).hostname not in grant["image_hosts"]:
        raise ValueError("Artwork URL not an approved HTTPS source host")
    aliases=row.get("aliases",[])
    if (not isinstance(aliases,list) or len(aliases)>MAX_ALIASES
        or any(not isinstance(a,str) or not 1<=len(a.strip())<=120 for a in aliases)):
        raise ValueError("Invalid aliases")
    category=row.get("category","game")
    rarity=row.get("rarity","Common")
    weight=row.get("weight",100)
    if (category not in CATEGORIES or rarity not in RARITIES
        or type(weight) is not int or not 1<=weight<=10000):
        raise ValueError("Invalid category, rarity or weight")
    author=row.get("artwork_author") or grant.get("uniform_artwork_author")
    if not isinstance(author,str) or not 1<=len(author.strip())<=120:
        raise ValueError("Missing per-file or expressly uniform creator attribution")
    page=row.get("artwork_page_url")
    if not valid_https(page,page=True):
        raise ValueError("Original artwork page required for attribution")
    return (key,name.strip(),series.strip(),[a.strip() for a in aliases],
            category,rarity,url,weight,author.strip(),
            grant["artwork_license_name"],grant["artwork_license_url"],page,
            bool(enable))


def stream_rows(path):
    path=Path(path)
    if path.suffix not in (".jsonl",".gz",".ndjson"):
        raise ValueError("Use .jsonl, .ndjson or compressed .jsonl.gz")
    opener=gzip.open if path.suffix==".gz" else open
    with opener(path,"rt",encoding="utf8") as stream:
        for line in stream:
            if len(line.encode("utf8"))>MAX_LINE:
                raise ValueError("Input line exceeds 64KiB")
            if line.strip():
                yield json.loads(line)


def stage(path, grant_path, *,max_rows=MAX_ROWS,enable=False):
    """Validate 1m lines using a temporary LOCAL SQLite text index.

    Outputs no image files. Error aborts entire source batch. The SQLite DB
    exists only for the current process; no pending records enter Neon.
    """
    if type(max_rows) is not int or not 1<=max_rows<=MAX_ROWS:
        raise ValueError("Invalid maximum number of source records")
    if Path(grant_path).stat().st_size>MAX_GRANT_BYTES:
        raise ValueError("Grant document unexpectedly large")
    digest=file_sha256(path)
    with open(grant_path,encoding="utf8") as f:
        grant=validate_grant(json.load(f),digest)
    if enable and grant.get("telegram_delivery_verified_for_source") is not True:
        raise ValueError("Enabling live characters requires separately verified Telegram photo delivery")
    temp=tempfile.TemporaryDirectory(prefix="cardkout-validated-url-")
    db=sqlite3.connect(str(Path(temp.name)/"catalog.sqlite"))
    db.execute("CREATE TABLE cards (source_key TEXT PRIMARY KEY, row_json TEXT NOT NULL)")
    stats={"source_rows":0,"unique_characters":0,"identical_duplicates":0,
           "source_digest":digest,"artwork_urls_stored_as_text_only":True,
           "image_files_downloaded":0,"database_writes":0,
           "review_attestation_only_not_independent_rights_proof":True}
    try:
        with db:
            for entry in stream_rows(path):
                stats["source_rows"]+=1
                if stats["source_rows"]>max_rows:
                    raise ValueError("Too many URL rows in a single batch")
                values=normalize(entry,grant,enable=enable)
                key=values[0]
                canonical=json.dumps(values,ensure_ascii=False,separators=(",",":"))
                inserted=db.execute("INSERT OR IGNORE INTO cards VALUES (?,?)",(key,canonical))
                if inserted.rowcount==0:
                    found=db.execute("SELECT row_json FROM cards WHERE source_key=?",
                                     (key,)).fetchone()[0]
                    if found!=canonical:
                        raise ValueError("Conflicting source_key; abort rather than silently overwrite")
                    stats["identical_duplicates"]+=1
                else:
                    stats["unique_characters"]+=1
        return temp,db,stats
    except BaseException:
        db.close()
        temp.cleanup()
        raise


def _rows_from(db):
    cursor=db.execute("SELECT row_json FROM cards ORDER BY source_key")
    while True:
        batch=cursor.fetchmany(500)
        if not batch:
            break
        for (serialized,) in batch:
            yield json.loads(serialized)


def apply(db,sqlite_db,stats, *,limit_bytes=DATABASE_LIMIT):
    """One transaction: COPY staging table then one upsert, rollback on error.

    This routine is invoked ONLY by CLI's explicit rights+owner approval gate.
    On success, only shared metadata/text URLs reach characters, never images.
    """
    if type(limit_bytes) is not int or limit_bytes<RESERVE_BYTES:
        raise ValueError("Storage limit too small")
    current=int(db.execute("SELECT pg_database_size(current_database()) AS size").fetchone()["size"])
    projected=current+stats["unique_characters"]*PER_NEW_CHARACTER_BUDGET+RESERVE_BYTES
    if projected>limit_bytes:
        raise ValueError("Storage reserve exceeded; split the source batch or expand DB quota")
    db.execute("""CREATE TEMP TABLE cardkout_bulk_urls
        (source_key TEXT PRIMARY KEY,name TEXT NOT NULL,series TEXT NOT NULL,
         aliases TEXT[],category TEXT,rarity TEXT,image_url TEXT NOT NULL,
         weight INTEGER,artwork_author TEXT,artwork_license_name TEXT,
         artwork_license_url TEXT,artwork_page_url TEXT,enabled BOOLEAN)
         ON COMMIT DROP""")
    with db.cursor() as cursor:
        with cursor.copy(SQL_COPY) as stream:
            for row in _rows_from(sqlite_db):
                stream.write_row(tuple(row))
        new=db.execute("""SELECT count(*) AS n FROM cardkout_bulk_urls s
            WHERE NOT EXISTS(SELECT 1 FROM characters c WHERE c.source_key=s.source_key)""").fetchone()
        new_count=int(new["n"])
        if current+new_count*PER_NEW_CHARACTER_BUDGET+RESERVE_BYTES>limit_bytes:
            raise ValueError("Neon size reserve exceeded before upsert")
        db.execute(SQL_UPSERT)
    return {"mode":"explicit_reviewed_source_metadata_import",
            "rows_processed":stats["unique_characters"],
            "new_characters_count_pre_upsert":new_count,
            "image_files_downloaded":0,
            "shared_external_url_fields_only":True}


def run(path,grant_path,*,allow_write=False,rights_reviewed=False,
        confirm="",enable=False,max_rows=MAX_ROWS,
        connection_factory=None):
    if allow_write and (not rights_reviewed or confirm!=CONFIRM
                        or os.environ.get("CARDKOUT_BULK_IMPORT_AUTHORIZED")!="YES"):
        raise ValueError("Apply blocked: owner authorization and reviewed source grant required")
    temp,local,stats=stage(path,grant_path,max_rows=max_rows,enable=enable)
    try:
        if not allow_write:
            return {"mode":"dry_run","database_connections":0,**stats}
        if not stats["unique_characters"]:
            raise ValueError("Empty character URL batch")
        if connection_factory is None:
            import psycopg
            from psycopg.rows import dict_row
            connection_factory=lambda: psycopg.connect(
                os.environ["DATABASE_URL"],row_factory=dict_row)
        with connection_factory() as db:
            result=apply(db,local,stats)
        return {**result,"input_digest":stats["source_digest"]}
    finally:
        local.close()
        temp.cleanup()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls",help="One character+artwork URL per JSONL line")
    parser.add_argument("--source-grant",required=True,
                        help="Independently reviewed license/coverage attestation for exact SHA256")
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--rights-reviewed",action="store_true")
    parser.add_argument("--enable",action="store_true",
                        help="Enable characters ONLY if source-wide Telegram photo delivery was tested")
    parser.add_argument("--confirm",default="")
    parser.add_argument("--max-rows",type=int,default=MAX_ROWS)
    args=parser.parse_args()
    report=run(args.urls,args.source_grant,allow_write=args.apply,
               rights_reviewed=args.rights_reviewed,confirm=args.confirm,
               enable=args.enable,max_rows=args.max_rows)
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
