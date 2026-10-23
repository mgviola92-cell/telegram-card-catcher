"""Fetch one 100k+ character-URL JSONL dataset from a single trusted HTTPS URL.

This downloads ONLY catalog metadata text (.jsonl/.ndjson/.jsonl.gz), NOT
image files. Files exist only inside an operator-local TemporaryDirectory;
they are removed after processing. Explicit exact host allowlist, no redirects,
no cookies/auth headers and a strict compressed-size budget.
Not for recurring operation or the production Render webhook server.
"""
from contextlib import contextmanager
import ipaddress
from pathlib import Path
import tempfile
import urllib.error
import urllib.request
from urllib.parse import urlsplit

MAX_BYTES=250*1024*1024
CHUNK=1024*1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise ValueError("Dataset URL redirects are disallowed: pin the original source URL")


def validate_dataset_url(url,expected_host):
    if not isinstance(url,str) or not 20<=len(url)<=2048:
        raise ValueError("Require a specific HTTPS JSONL dataset URL")
    if not isinstance(expected_host,str) or not expected_host or expected_host!=expected_host.lower():
        raise ValueError("Expected provider host is required")
    p=urlsplit(url)
    if (p.scheme!="https" or p.hostname!=expected_host or p.username is not None
        or p.password is not None or p.fragment or p.port not in (None,443)
        or p.path.lower().endswith((".jsonl",".ndjson",".jsonl.gz",".ndjson.gz")) is False):
        raise ValueError("Dataset must be JSONL on the EXACT independently trusted HTTPS host")
    if p.hostname in ("localhost","localhost.localdomain") or p.hostname.endswith(".localhost"):
        raise ValueError("Local/private host not allowed")
    try:
        ipaddress.ip_address(expected_host)
        raise ValueError("Raw IP sources are forbidden")
    except ValueError as exc:
        if str(exc)=="Raw IP sources are forbidden":
            raise
    return ".jsonl.gz" if p.path.endswith((".jsonl.gz",".ndjson.gz")) else ".jsonl"


@contextmanager
def acquired_dataset(url,*,expected_host,max_bytes=MAX_BYTES,opener=None):
    """Download ONE metadata dataset, never a binary image, and clean it up."""
    if type(max_bytes) is not int or not 1<=max_bytes<=MAX_BYTES:
        raise ValueError("Invalid download byte cap")
    suffix=validate_dataset_url(url,expected_host)
    request=urllib.request.Request(url,headers={
        "User-Agent":"CardKout-Metadata-OneShot/1.0",
        "Accept":"application/x-ndjson, application/json, application/gzip, */*"
    })
    fetch=opener or urllib.request.build_opener(NoRedirect()).open
    with tempfile.TemporaryDirectory(prefix="cardkout-source-dataset-") as work:
        dest=Path(work)/("official-character-metadata"+suffix)
        count=0
        with fetch(request,timeout=45) as response:
            final_url=response.geturl()
            if final_url!=url:
                raise ValueError("Untrusted redirect or provider URL change")
            status=getattr(response,"status",200)
            if status!=200:
                raise ValueError("Dataset provider returned non-success HTTP")
            declared=response.headers.get("Content-Length")
            if declared is not None:
                try:
                    if int(declared)>max_bytes:
                        raise ValueError("Catalog too large before downloading")
                except (TypeError,ValueError) as exc:
                    if "too large" in str(exc):
                        raise
                    raise ValueError("Malformed provider size header") from exc
            with dest.open("wb") as out:
                while True:
                    chunk=response.read(CHUNK)
                    if not chunk:
                        break
                    count+=len(chunk)
                    if count>max_bytes:
                        raise ValueError("Catalog exceeds maximum downloaded bytes")
                    out.write(chunk)
        yield dest


def main():
    import argparse
    import json
    from scripts.bulk_url_import import run,CONFIRM
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--dataset-url",required=True)
    cli.add_argument("--dataset-host",required=True,
                     help="Exact audited HTTPS provider hostname, not domain wildcard")
    cli.add_argument("--source-grant",required=True)
    cli.add_argument("--apply",action="store_true")
    cli.add_argument("--rights-reviewed",action="store_true")
    cli.add_argument("--enable",action="store_true")
    cli.add_argument("--confirm",default="")
    cli.add_argument("--max-bytes",type=int,default=MAX_BYTES)
    options=cli.parse_args()
    with acquired_dataset(options.dataset_url,expected_host=options.dataset_host,
                          max_bytes=options.max_bytes) as file:
        report=run(file,options.source_grant,allow_write=options.apply,
                   rights_reviewed=options.rights_reviewed,
                   confirm=options.confirm,enable=options.enable)
        print(json.dumps({"dataset_url":options.dataset_url,
                          "dataset_bytes_removed_after_command":True,
                          **report},indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
