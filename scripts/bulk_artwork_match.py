"""Offline 500k-row exact-source-ID to original-art candidate join.

NEVER imports photos, approves rights, contacts Telegram or writes PostgreSQL.
All source/media evidence is UNVERIFIED; temp SQLite holds TEXT metadata only.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from urllib.parse import urlsplit
from scripts.import_characters import safe_image_url

LIMIT=500_000
VARIANT_LIMIT=12


def lines(path):
    with open(path,encoding="utf8") as f:
        for line in f:
            if len(line.encode("utf8"))>524288:
                raise ValueError("Oversized review row")
            if line.strip():
                data=json.loads(line)
                if not isinstance(data,dict):
                    raise ValueError("Expected JSON objects")
                yield data


def join(stage,art,out,*,allowed_hosts,report_path=None,max_rows=LIMIT):
    if (not isinstance(allowed_hosts,(list,set,tuple)) or not allowed_hosts
        or any(not isinstance(h,str) or h.lower()!=h or ":" in h
               or "/" in h or "." not in h for h in allowed_hosts)):
        raise ValueError("Specify reviewed exact HTTPS image hostnames")
    if type(max_rows) is not int or not 1<=max_rows<=LIMIT:
        raise ValueError("Invalid row limit")
    hosts=set(allowed_hosts)
    dest=Path(out).resolve()
    ins=[Path(stage).resolve(),Path(art).resolve()]
    if dest in ins or (report_path and Path(report_path).resolve() in [dest,*ins]):
        raise ValueError("Input and output paths must differ")
    report=Counter({"metadata_read":0,"artwork_seen":0,"matched_pending":0,
                    "unmatched_source_key":0,"rejected_art":0,
                    "duplicate_art":0,"artwork_approved":0,
                    "database_writes":0,"image_files_downloaded":0})
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cardkout-art-index-") as temp:
        db=sqlite3.connect(str(Path(temp)/"metadata.sqlite"))
        generated=Path(temp)/"candidate.jsonl"
        try:
            db.execute("CREATE TABLE chars(key TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            db.execute("CREATE TABLE art(key TEXT, url TEXT, PRIMARY KEY(key,url))")
            with db:
                for meta in lines(stage):
                    report["metadata_read"]+=1
                    if report["metadata_read"]>max_rows:
                        raise ValueError("Too many source rows")
                    if (meta.get("approved_for_import") is not False
                        or meta.get("image_url") is not None
                        or not isinstance(meta.get("source_key"),str)
                        or not isinstance(meta.get("name"),str)
                        or not isinstance(meta.get("series"),str)):
                        raise ValueError("Staged source must be unapproved metadata")
                    try:
                        db.execute("INSERT INTO chars VALUES (?,?)",
                                   (meta["source_key"],json.dumps({
                                    "source_key":meta["source_key"],"name":meta["name"],
                                    "series":meta["series"]},ensure_ascii=False)))
                    except sqlite3.IntegrityError as exc:
                        raise ValueError("Duplicate staged identity key") from exc
                with generated.open("w",encoding="utf8") as f:
                    for candidate in lines(art):
                        report["artwork_seen"]+=1
                        if report["artwork_seen"]>max_rows:
                            raise ValueError("Too many artwork rows")
                        key=candidate.get("source_key")
                        url=candidate.get("candidate_image_url")
                        if (not isinstance(key,str) or not safe_image_url(url)
                            or candidate.get("approved_for_import") is not False
                            or candidate.get("is_adult") is True
                            or candidate.get("rights_approved") is True
                            or candidate.get("telegram_photo_verified") is True):
                            report["rejected_art"]+=1
                            continue
                        parsed=urlsplit(url)
                        if (parsed.hostname not in hosts or not
                            parsed.path.lower().endswith((".png",".jpg",".jpeg"))):
                            report["rejected_art"]+=1
                            continue
                        src=db.execute("SELECT payload FROM chars WHERE key=?",(key,)).fetchone()
                        if src is None:
                            report["unmatched_source_key"]+=1
                            continue
                        count=db.execute("SELECT count(*) FROM art WHERE key=?",(key,)).fetchone()[0]
                        if count>=VARIANT_LIMIT:
                            report["rejected_art"]+=1
                            continue
                        inserted=db.execute("INSERT OR IGNORE INTO art VALUES (?,?)",(key,url))
                        if inserted.rowcount==0:
                            report["duplicate_art"]+=1
                            continue
                        result=json.loads(src[0])
                        result.update({
                            "candidate_image_url":url,
                            "claimed_source_file_page":candidate.get("file_page_url"),
                            "claimed_author":candidate.get("author"),
                            "claimed_license":candidate.get("license"),
                            "image_url":None,
                            "identity_verified":False,"reuse_rights_verified":False,
                            "upstream_terms_verified":False,
                            "content_suitability_verified":False,
                            "telegram_photo_verified":False,
                            "approved_for_import":False,
                            "status":"pending_independent_review"
                        })
                        f.write(json.dumps(result,ensure_ascii=False)+"\n")
                        report["matched_pending"]+=1
            os.replace(generated,dest)
        finally:
            db.close()
    report=dict(report)
    report["note"]="Exact ID matches are only image leads; source claims never license pictures."
    if report_path:
        target=Path(report_path)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(report,indent=2)+"\n",encoding="utf8")
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage")
    p.add_argument("art")
    p.add_argument("out")
    p.add_argument("--allowed-host",action="append",required=True)
    p.add_argument("--report")
    a=p.parse_args()
    print(json.dumps(join(a.stage,a.art,a.out,allowed_hosts=a.allowed_host,
                          report_path=a.report),indent=2))


if __name__=="__main__":
    main()
