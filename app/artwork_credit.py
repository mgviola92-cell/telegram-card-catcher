"""Compact, correctly escaped artwork attribution for native Telegram HTML.

Artwork images stay at their one approved remote URL + optional cached
Telegram file_id. This module adds text credit only (no rendered image).
On wild spawns, do not link to the file page: filename may reveal the name.
"""
from html import escape
from urllib.parse import urlsplit


def _short(value, limit):
    if not isinstance(value,str):
        return ""
    value=value.strip()
    if len(value)>limit:
        value=value[:limit-1].rstrip()+"…"
    return escape(value,quote=True)


def _safe_page(value):
    if not isinstance(value,str) or not 12<=len(value)<=1500:
        return None
    try:
        url=urlsplit(value)
        if (url.scheme!="https" or not url.hostname or url.username or url.password
            or url.port not in (None,443) or url.fragment):
            return None
        return escape(value,quote=True)
    except ValueError:
        return None


def credit_line(artwork, *, reveal_source=False):
    """Render credit only when both artist and license identity are present."""
    artist=_short(artwork.get("artwork_author"),60)
    license_name=_short(artwork.get("artwork_license_name"),40)
    if not artist or not license_name:
        return ""
    lic=_safe_page(artwork.get("artwork_license_url"))
    source=_safe_page(artwork.get("artwork_page_url")) if reveal_source else None
    label=(f'<a href="{lic}">{license_name}</a>' if lic else license_name)
    link=(f' · <a href="{source}">Source</a>' if source else "")
    return f"\n🎨 <i>Art: {artist} · {label}{link}</i>"
