"""Manual, character-specific artwork approval gate (no network or image fetch).

This checks review RECORD consistency, never grants image rights on its own.
Rights, source terms, accurate illustration/character mapping, audience
suitability and required attribution must have been verified by a human.
"""
from urllib.parse import urlsplit


def require_artwork_approval(items, manifest):
    if not isinstance(items,list) or not isinstance(manifest,list):
        raise ValueError("Catalog and image approvals must be JSON arrays")
    if not items:
        raise ValueError("Cannot approve an empty catalog")
    approvals={}
    for index,row in enumerate(manifest,1):
        if not isinstance(row,dict):
            raise ValueError(f"Approval {index} must be an object")
        key=row.get("source_key")
        url=row.get("image_url")
        evidence=row.get("permission_reference")
        if not isinstance(key,str) or not key or key in approvals:
            raise ValueError("Approval has missing/duplicate source key")
        if row.get("status")!="approved" or not isinstance(url,str):
            raise ValueError("Approval must explicitly say approved with matching URL")
        try:
            parsed=urlsplit(url)
            if (parsed.scheme!="https" or not parsed.hostname or parsed.username or
                parsed.password or parsed.port not in (None,443)):
                raise ValueError("Unsafe approved URL")
        except ValueError as exc:
            raise ValueError("Malformed image approval URL") from exc
        if not isinstance(evidence,str) or len(evidence.strip())<12:
            raise ValueError("Artwork approval needs verifiable human permission reference")
        approvals[key]=url
    for row in items:
        if not isinstance(row,dict):
            raise ValueError("Invalid catalog record")
        key=row.get("source_key")
        if key not in approvals or approvals[key]!=row.get("image_url"):
            raise ValueError(f"Missing/exchanged artwork permission for {key}")
    return len(items)
