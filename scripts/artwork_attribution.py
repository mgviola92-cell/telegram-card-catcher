"""Public artwork attribution metadata, independently checked per artwork.

No artwork bytes, thumbnails or image URLs on user-owned card rows. These
four shared CREDIT fields are optional for existing legacy catalog entries.
If any is supplied for a new reviewed artwork, ALL must be present in both
the catalog and its exact human-reviewed approval manifest.
"""
import ipaddress
from urllib.parse import urlsplit

CREDIT_FIELDS=(
    "artwork_author",
    "artwork_license_name",
    "artwork_license_url",
    "artwork_page_url",
)
MAX_LEN=(120,90,1500,1500)


def safe_page(url):
    if not isinstance(url,str) or not 12<=len(url)<=1500:
        return False
    try:
        part=urlsplit(url)
        if (part.scheme!="https" or not part.hostname
            or part.username is not None or part.password is not None
            or part.port not in (None,443) or part.fragment
            or part.hostname in ("localhost","localhost.localdomain")
            or part.hostname.endswith(".localhost")):
            return False
        try:
            ipaddress.ip_address(part.hostname)
            return False
        except ValueError:
            return True
    except ValueError:
        return False


def credit_tuple(record):
    if not isinstance(record,dict):
        raise ValueError("Art attribution must be a JSON object")
    values=tuple(record.get(field) for field in CREDIT_FIELDS)
    if all(value is None or value=="" for value in values):
        return (None,)*len(CREDIT_FIELDS)
    for index,value in enumerate(values):
        if (not isinstance(value,str) or not 1<=len(value.strip())<=MAX_LEN[index]):
            raise ValueError(f"Missing/invalid artwork credit {CREDIT_FIELDS[index]}")
        if index>=2 and not safe_page(value):
            raise ValueError("Artwork attribution links must be valid public HTTPS URLs")
    return tuple(str(x).strip() for x in values)


def reviewed_credit(catalog_record, approval_record):
    """Forbid inventing attribution in catalog metadata without matching proof."""
    from_catalog=credit_tuple(catalog_record)
    from_approval=credit_tuple(approval_record)
    if from_catalog!=from_approval:
        raise ValueError("Artwork attribution must exactly match human approval")
    return from_catalog
