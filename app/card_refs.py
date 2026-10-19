"""Public card references: short numeric DB IDs, legacy codes still accepted.

The owned_cards.id BIGINT primary key already uniquely identifies every copy.
Do not generate a separate stored image, URL, or numeric code column.
"""
import re

MAX_BIGINT = 9223372036854775807
LEGACY_CODE = re.compile(r"[A-Za-z0-9]{1,32}\Z", re.ASCII)


def parse_card_ref(value):
    """Return ('id', bigint) or ('legacy_code', uppercase text), else None."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    token = str(value).strip()
    if not 1 <= len(token) <= 32:
        return None
    if re.fullmatch(r"[0-9]+", token, re.ASCII):
        n = int(token)
        return ("id", n) if 1 <= n <= MAX_BIGINT else None
    if LEGACY_CODE.fullmatch(token):
        return ("legacy_code", token.upper())
    return None


def public_card_id(card):
    """Use the primary key as player-visible ID, retaining old-code fallback."""
    raw = card.get("card_id")
    if raw is not None and isinstance(raw, int) and not isinstance(raw, bool) and raw > 0:
        return str(raw)
    return str(card.get("code") or "")
