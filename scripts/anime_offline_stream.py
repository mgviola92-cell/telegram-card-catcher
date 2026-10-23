"""Stream a REAL Anime Character Offline Database JSON snapshot to JSONL.

A single top-level {"meta":..., "data":[...]} snapshot can be large. This
parser never loads its whole array, never transfers picture URLs, never
contacts providers and never writes to Neon. Result is OFFLINE metadata only.
Source data/provider terms must be separately checked by the operator.
Original reference: https://github.com/arda-/anime-character-offline-database

Next stage via: python -m scripts.bulk_metadata_stage --source mal=...
NOTE: Terms in an upstream *database* never license third-party images.
"""
import argparse
from collections import Counter
import gzip
import json
import os
from pathlib import Path
import tempfile

CHUNK = 65536
MAX_TOKEN = 2 * 1024 * 1024
MAX_RECORDS = 300_000


class _JSONSource:
    def __init__(self,stream):
        self.stream=stream
        self.buffer=""
        self.offset=0
        self.eof=False
        self.decoder=json.JSONDecoder()

    def _fill(self):
        if self.offset:
            self.buffer=self.buffer[self.offset:]
            self.offset=0
        additional=self.stream.read(CHUNK)
        if additional:
            self.buffer+=additional
        else:
            self.eof=True
        if len(self.buffer)>MAX_TOKEN:
            raise ValueError("Source record or metadata exceeds bounded parser memory")

    def _space(self):
        while True:
            while self.offset<len(self.buffer) and self.buffer[self.offset].isspace():
                self.offset+=1
            if self.offset<len(self.buffer) or self.eof:
                return
            self._fill()

    def next_is(self,char):
        self._space()
        return self.offset<len(self.buffer) and self.buffer[self.offset]==char

    def consume(self,char):
        self._space()
        while self.offset>=len(self.buffer) and not self.eof:
            self._fill()
        if self.offset>=len(self.buffer) or self.buffer[self.offset]!=char:
            raise ValueError(f"Malformed JSON: expected {char!r}")
        self.offset+=1

    def value(self):
        self._space()
        while True:
            if self.offset>=len(self.buffer):
                if self.eof:
                    raise ValueError("Unexpected end of source JSON")
                self._fill()
                continue
            try:
                # Objects/strings are returned only when completely decoded.
                value,end=self.decoder.raw_decode(self.buffer,self.offset)
            except json.JSONDecodeError as exc:
                if self.eof:
                    raise ValueError("Incomplete or invalid source JSON") from exc
                self._fill()
                continue
            self.offset=end
            return value

    def end(self):
        self._space()
        if self.offset<len(self.buffer):
            raise ValueError("Unexpected trailing content after source JSON")
        if not self.eof:
            self._fill()
            self._space()
            if self.offset<len(self.buffer):
                raise ValueError("Trailing content after source JSON")


def snapshot_records(stream,*,max_records=MAX_RECORDS):
    if type(max_records) is not int or not 1<=max_records<=MAX_RECORDS:
        raise ValueError("Invalid record cap")
    parser=_JSONSource(stream)
    parser.consume("{")
    seen_data=False
    count=0
    while True:
        if parser.next_is("}"):
            parser.consume("}")
            break
        key=parser.value()
        if not isinstance(key,str):
            raise ValueError("Invalid object key")
        parser.consume(":")
        if key=="data":
            if seen_data:
                raise ValueError("Duplicate data array")
            seen_data=True
            parser.consume("[")
            while not parser.next_is("]"):
                count+=1
                if count>max_records:
                    raise ValueError("Source row limit exceeded")
                yield parser.value()
                if parser.next_is("]"):
                    break
                parser.consume(",")
            parser.consume("]")
        else:
            if key not in ("meta",):
                raise ValueError("Unexpected top-level source key")
            meta=parser.value()
            if not isinstance(meta,dict):
                raise ValueError("Source meta must be an object")
        if parser.next_is("}"):
            parser.consume("}")
            break
        parser.consume(",")
    if not seen_data:
        raise ValueError("Source is missing data array")
    parser.end()


def normalize(row):
    if not isinstance(row,dict):
        return None,"invalid"
    if row.get("isAdult") is True or row.get("adult") is True:
        return None,"flagged_adult"
    ident=row.get("mal_id")
    name=row.get("name")
    shows=row.get("animeAppearances")
    if (type(ident) is not int or ident<1 or
        not isinstance(name,str) or not 1<=len(name.strip())<=150 or
        not isinstance(shows,list)):
        return None,"invalid"
    titles=[]
    for group in shows:
        if not isinstance(group,dict):
            continue
        if group.get("isAdult") is True:
            return None,"flagged_adult"
        anime=group.get("anime")
        name_of_show=anime.get("title") if isinstance(anime,dict) else None
        if isinstance(name_of_show,str) and 1<=len(name_of_show.strip())<=150:
            label=name_of_show.strip()
            if label not in titles:
                titles.append(label)
    if not titles:
        return None,"without_series"
    names=row.get("nicknames") or []
    if not isinstance(names,list):
        names=[]
    aliases=[n.strip() for n in names
             if isinstance(n,str) and 1<=len(n.strip())<=120][:20]
    return {"id":ident,"name":name.strip(),"series":titles[0],
            "category":"anime","aliases":aliases,
            "metadata_age_status":"unverified",
            "source_image_pointer_dropped":True},None


def stage_snapshot(source,output,*,max_records=MAX_RECORDS):
    incoming=Path(source).resolve()
    target=Path(output).resolve()
    if incoming==target or target.is_dir():
        raise ValueError("Source and output paths must differ")
    counts=Counter({"source_rows":0,"normalized_rows":0,"invalid_rows":0,
                    "without_series":0,"flagged_adult":0,
                    "image_urls_preserved":0,"database_writes":0,
                    "photo_files_downloaded":0})
    target.parent.mkdir(parents=True,exist_ok=True)
    opener=gzip.open if incoming.name.endswith(".gz") else open
    with tempfile.TemporaryDirectory(prefix="cardkout-real-snapshot-") as temp:
        staged=Path(temp)/"metadata.jsonl"
        with opener(incoming,"rt",encoding="utf-8-sig") as stream, staged.open(
            "w",encoding="utf8",newline="\n") as dest:
            for item in snapshot_records(stream,max_records=max_records):
                counts["source_rows"]+=1
                row,reason=normalize(item)
                if row is None:
                    counts[reason]+=1
                    continue
                dest.write(json.dumps(row,ensure_ascii=False,separators=(",",":"))+"\n")
                counts["normalized_rows"]+=1
        os.replace(staged,target)
    counts=dict(counts)
    counts["note"]="Metadata only. All image pointers dropped; stage with bulk_metadata_stage. Exact age suitability, dataset reuse rights and artwork permissions remain unverified."
    return counts


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("snapshot",help="Existing locally obtained source .json or .json.gz")
    p.add_argument("output",help="Intermediate normalized .jsonl")
    p.add_argument("--max-records",type=int,default=MAX_RECORDS)
    a=p.parse_args()
    print(json.dumps(stage_snapshot(a.snapshot,a.output,max_records=a.max_records),
                     indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
