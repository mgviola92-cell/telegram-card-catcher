"""Explicit offline-character snapshot fetch for manual bulk-metadata review.

Only fetches the pinned official HTTPS JSON endpoint, limits bytes, and verifies
JSON shape before atomically writing locally. Does not touch DB or download art.
Check source terms before use; never schedule scraping.
"""
import argparse
import json
import os
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

URL="https://raw.githubusercontent.com/arda-/anime-character-offline-database/prod/latest/characters.min.json"
MAX_BYTES=80*1024*1024
CHUNK_SIZE=1024*1024

def download_snapshot(output, opener=urlopen, max_bytes=MAX_BYTES):
    if max_bytes<1:
        raise ValueError("max_bytes must be positive")
    request=Request(URL,headers={"User-Agent":"CardKoutManualMetadataReview/1.0","Accept":"application/json"})
    with opener(request,timeout=45) as response:
        if getattr(response,"status",200)!=200:
            raise ValueError("Snapshot HTTP request failed")
        length=response.headers.get("Content-Length")
        if length and int(length)>max_bytes:
            raise ValueError("Snapshot exceeds download limit")
        chunks=[]
        size=0
        while True:
            chunk=response.read(min(CHUNK_SIZE,max_bytes-size+1))
            if not chunk:
                break
            size+=len(chunk)
            if size>max_bytes:
                raise ValueError("Snapshot exceeds download limit")
            chunks.append(chunk)
        content=b"".join(chunks)
    snapshot=json.loads(content.decode("utf-8"))
    if not isinstance(snapshot,dict) or not isinstance(snapshot.get("data"),list):
        raise ValueError("Unexpected character snapshot shape")
    destination=Path(output)
    destination.parent.mkdir(parents=True,exist_ok=True)
    fd,temporary=tempfile.mkstemp(prefix=".snapshot-",suffix=".tmp",dir=str(destination.parent))
    try:
        with os.fdopen(fd,"wb") as stream:
            stream.write(content)
        os.replace(temporary,destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return len(snapshot["data"])

if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output",required=True)
    cli.add_argument("--fetch",action="store_true",help="Explicit consent to manually fetch one official metadata snapshot")
    cli.add_argument("--report",help="Write measured snapshot metadata and character coverage report")
    cli.add_argument("--stage",help="Write review-only characters (not approved for bot import)")
    args=cli.parse_args()
    if not args.fetch:
        cli.error("Add --fetch after checking the source usage terms.")
    print("Snapshot rows:",download_snapshot(args.output))
    if args.report or args.stage:
        from scripts.stage_character_offline import coverage_report, convert
        if args.report:
            source=json.loads(Path(args.output).read_text(encoding="utf-8"))
            Path(args.report).write_text(json.dumps(coverage_report(source),ensure_ascii=False,indent=2)+chr(10),encoding="utf-8")
            print("Measured coverage report:",args.report)
        if args.stage:
            print("Review-only records:",convert(args.output,args.stage))
