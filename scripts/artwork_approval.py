"""Human-reviewed artwork manifest gate. Metadata discovery is NOT artwork permission.

Manifest entries explicitly bind each approval to a source key and exact image URL.
A changed URL must be reviewed again; no network calls or implicit approvals.
"""
from urllib.parse import urlsplit


def require_artwork_approval(items, manifest):
    if not isinstance(items,list) or not isinstance(manifest,list):
        raise ValueError('Catalog and artwork approvals must be arrays')
    approvals={}
    for entry in manifest:
        if not isinstance(entry,dict):
            raise ValueError('Invalid approval entry')
        key=entry.get('source_key')
        url=entry.get('image_url')
        proof=entry.get('permission_reference')
        if not isinstance(key,str) or not key or key in approvals:
            raise ValueError('Missing or duplicated approval source key')
        if (entry.get('status')!='approved' or not isinstance(url,str)
                or urlsplit(url).scheme!='https'
                or not isinstance(proof,str) or len(proof.strip())<8):
            raise ValueError('Approval needs exact HTTPS artwork, status and permission reference')
        approvals[key]=(url,proof)
    for item in items:
        if not isinstance(item,dict):
            raise ValueError('Invalid catalog entry')
        key=item.get('source_key')
        approval=approvals.get(key)
        if not approval or approval[0]!=item.get('image_url'):
            raise ValueError(f'Artwork permission approval missing or changed: {key}')
    return len(items)
