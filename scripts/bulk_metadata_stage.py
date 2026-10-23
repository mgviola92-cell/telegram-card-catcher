"""Streaming 100k+ character METADATA staging (NOT approved photo cards).

Offline-only. Sources are existing local JSONL/CSV metadata files, provided
explicitly by an operator who has checked their upstream use terms.
Deduplication uses a temporary on-disk SQLite index, not Neon/Render storage.
Input art/image fields are *never copied* to outputs. No network, imports,
Telegram API, production DB or generated images.

Usage:
 python -m scripts.bulk_metadata_stage --source acdb=raw.jsonl \
   --source mygame=names.csv --output /tmp/staged.jsonl --report /tmp/report.json
The source input is normalized: id,name,series,category,aliases.
"""
import argparse
import csv
import gzip
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile

SOURCE_RE = re.compile(r"^[a-z][a-z0-9_-]{0,29}$")
ID_RE = re.compile(r"^[a-zA-Z0-9_.:-]{1,80}$")
CATEGORIES = {"anime","manga","manhwa","webtoon","game","other"}
MAX_INPUT_ROWS = 1_000_000
MAX_DISTINCT_ROWS = 500_000
MAX_LINE_BYTES = 524288
BATCH_FETCH = 1000
UNSAFE_RATINGS = {"adult","mature","18+","r18","r-18","explicit","nsfw"}


def _read_source(path):
    """Stream local rows only; never load the entire source into RAM."""
    filename = str(path).lower()
    gzipped = filename.endswith(".gz")
    base = filename[:-3] if gzipped else filename
    kind = "jsonl" if base.endswith((".jsonl",".ndjson")) else ("csv" if base.endswith(".csv") else None)
    if kind is None:
        raise ValueError("Use .jsonl, .ndjson, .csv or their .gz forms")
    opener = gzip.open if gzipped else open
    with opener(path,"rt",encoding="utf-8-sig",newline="") as stream:
        if kind=="csv":
            reader=csv.DictReader(stream)
            if not reader.fieldnames or not all(k in reader.fieldnames for k in ("id","name","series")):
                raise ValueError("CSV requires id,name,series columns")
            for row in reader:
                yield row
        else:
            for line in stream:
                if len(line.encode("utf-8"))>MAX_LINE_BYTES:
                    raise ValueError("Metadata record exceeds 512 KiB")
                if not line.strip():
                    continue
                yield json.loads(line)


def _normalize(row,source):
    if not isinstance(row,dict):
        return None,"invalid"
    if any(row.get(k) is True for k in ("is_adult","isAdult","nsfw","explicit","adult")):
        return None,"unsafe"
    rating=row.get("rating") or row.get("age_rating")
    if isinstance(rating,str) and rating.strip().casefold() in UNSAFE_RATINGS:
        return None,"unsafe"
    original_id=row.get("id")
    if type(original_id) is int:
        original_id=str(original_id)
    if not isinstance(original_id,str) or not ID_RE.fullmatch(original_id):
        return None,"invalid"
    name,series=row.get("name"),row.get("series")
    if (not isinstance(name,str) or not isinstance(series,str)
        or not 1<=len(name.strip())<=150 or not 1<=len(series.strip())<=150):
        return None,"invalid"
    category=row.get("category","other") or "other"
    if category not in CATEGORIES:
        return None,"invalid"
    aliases=row.get("aliases",[])
    if isinstance(aliases,str):
        try:
            aliases=json.loads(aliases)
        except json.JSONDecodeError:
            aliases=[]
    if not isinstance(aliases,list) or len(aliases)>20 or any(
            not isinstance(a,str) or not 1<=len(a.strip())<=120 for a in aliases):
        return None,"invalid"
    key=f"{source}:character:{original_id}"
    if len(key)>120:
        return None,"invalid"
    # Deliberately omit all provider-image fields, image URLs and media IDs.
    entry={
        "source_key":key,"name":name.strip(),"series":series.strip(),
        "category":category,"aliases":[x.strip() for x in aliases],
        "image_url":None,"metadata_status":"pending_source_terms_and_content_screen",
        "artwork_status":"pending_identity_rights_quality_and_telegram",
        "approved_for_import":False,
    }
    return entry,None


def stage_sources(named_paths,output,*,max_rows=MAX_INPUT_ROWS,report_path=None):
    if (not isinstance(named_paths,dict) or not 1<=len(named_paths)<=16
        or type(max_rows) is not int or not 1<=max_rows<=MAX_INPUT_ROWS):
        raise ValueError("Use 1..16 offline sources and bounded rows")
    names=list(named_paths)
    if not all(isinstance(s,str) and SOURCE_RE.fullmatch(s) for s in names):
        raise ValueError("Source namespace must be unique and safe")
    out=Path(output).resolve()
    inputs=[Path(path).resolve() for path in named_paths.values()]
    if out in inputs or (report_path and Path(report_path).resolve() in [out,*inputs]):
        raise ValueError("Never overwrite a source or use overlapping output paths")
    counts={"input_rows":0,"accepted_distinct_metadata":0,"identical_source_id_repeats":0,
            "invalid_rows_skipped":0,"flagged_unsuitable_rows_skipped":0,
            "image_urls_copied":0,"artwork_approved":0,"production_database_writes":0,
            "telegram_photo_sends":0}
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cardkout-metadata-") as folder:
        scratch=Path(folder)/"dedup.sqlite"
        staged=Path(folder)/"output.jsonl"
        db=sqlite3.connect(str(scratch))
        try:
            db.execute("""CREATE TABLE identity (
                source_key TEXT PRIMARY KEY, payload TEXT NOT NULL)""")
            with db:
                for source,path in sorted(named_paths.items()):
                    for row in _read_source(path):
                        counts["input_rows"]+=1
                        if counts["input_rows"]>max_rows:
                            raise ValueError("Too many raw metadata rows; split source batches")
                        data,reason=_normalize(row,source)
                        if data is None:
                            counts["flagged_unsuitable_rows_skipped" if reason=="unsafe"
                                   else "invalid_rows_skipped"]+=1
                            continue
                        payload=json.dumps(data,ensure_ascii=False,separators=(",",":"),sort_keys=True)
                        result=db.execute("INSERT OR IGNORE INTO identity(source_key,payload) VALUES (?,?)",
                                          (data["source_key"],payload))
                        if result.rowcount==0:
                            old=db.execute("SELECT payload FROM identity WHERE source_key=?",
                                           (data["source_key"],)).fetchone()[0]
                            if old!=payload:
                                raise ValueError("Conflicting records for the same SOURCE ID; reconcile upstream, never auto-merge")
                            counts["identical_source_id_repeats"]+=1
                        else:
                            counts["accepted_distinct_metadata"]+=1
                            if counts["accepted_distinct_metadata"]>MAX_DISTINCT_ROWS:
                                raise ValueError("Too many distinct IDs; split into batches")
            with staged.open("w",encoding="utf-8",newline="\n") as stream:
                cursor=db.execute("SELECT payload FROM identity ORDER BY source_key")
                while True:
                    batch=cursor.fetchmany(BATCH_FETCH)
                    if not batch:
                        break
                    stream.writelines(row[0]+"\n" for row in batch)
            # This runs on a local operator machine or disposable CI runner.
            # Only the normalized text metadata is retained after success.
            os.replace(staged,out)
        finally:
            db.close()
    counts["note"]=(
        "METADATA ONLY. Source licenses, IP, age suitability, external artwork, "
        "rights and Telegram delivery remain unverified; never import directly. "
        "Temporary local SQLite metadata index has been deleted."
    )
    if report_path:
        dest=Path(report_path)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(counts,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return counts


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",action="append",required=True,metavar="LABEL=PATH")
    parser.add_argument("--output",required=True)
    parser.add_argument("--report")
    parser.add_argument("--max-rows",type=int,default=MAX_INPUT_ROWS)
    args=parser.parse_args()
    named={}
    for element in args.source:
        source,sep,path=element.partition("=")
        if not sep or not path or source in named:
            parser.error("Specify distinct source namespaces using LABEL=PATH")
        named[source]=path
    print(json.dumps(stage_sources(named,args.output,max_rows=args.max_rows,
                                   report_path=args.report),indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
