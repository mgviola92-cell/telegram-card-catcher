"""Optional public HTTPS artwork link audit. No image bytes saved to disk.

Use only for catalogs with permission to check their image hosts.
"""
import argparse
import ipaddress
import json
import socket
import ssl
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from scripts.import_characters import validate

MAX_IMAGE_BYTES=10*1024*1024  # conservative Telegram photo audit threshold
PHOTO_TYPES={'image/jpeg','image/png','image/webp'}

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def public_url(url):
    parsed=urlsplit(url)
    host=parsed.hostname
    if parsed.scheme!='https' or not host or parsed.username or parsed.password:
        return False
    try:
        if parsed.port not in (None,443): return False
        infos=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
        return bool(infos) and all(ipaddress.ip_address(info[4][0]).is_global for info in infos)
    except (ValueError,OSError):
        return False

def check_one(url, opener=None):
    if not public_url(url):
        return {'status':'unsafe_or_dns_failure'}
    opener=opener or build_opener(NoRedirect(), HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(Request(url,method='HEAD',headers={'User-Agent':'CardKoutArtAudit/1.0'}),timeout=8) as response:
            kind=response.headers.get('Content-Type','').split(';')[0].strip().lower()
            if response.status!=200: return {'status':'http_error','http_status':response.status}
            if kind not in PHOTO_TYPES: return {'status':'unsupported_image_type','content_type':kind}
            length=response.headers.get('Content-Length')
            if length is not None:
                try: size=int(length)
                except (ValueError,TypeError): return {'status':'invalid_content_length'}
                if size<0: return {'status':'invalid_content_length'}
                if size>MAX_IMAGE_BYTES: return {'status':'image_too_large','bytes':size}
            return {'status':'ok','content_type':kind,'bytes':int(length) if length is not None else None}
    except HTTPError as exc:
        return {'status':'http_error','http_status':exc.code}
    except (URLError,TimeoutError,OSError):
        return {'status':'network_error'}

def audit(items, limit=20, checker=check_one):
    rows=validate(items)
    if not 1<=limit<=100: raise ValueError('limit must be 1..100')
    results=[]
    for row in rows[:limit]:
        results.append({'source_key':row[0],'image_url':row[6],**checker(row[6])})
    return {'checked':len(results),'remaining':max(0,len(rows)-len(results)),
            'results':results}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('catalog')
    parser.add_argument('--limit',type=int,default=20)
    args=parser.parse_args()
    with open(args.catalog,encoding='utf-8') as f:
        print(json.dumps(audit(json.load(f),args.limit),indent=2))
