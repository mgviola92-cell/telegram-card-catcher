"""Bounded Wikimedia Commons *candidate* discovery for human review only.

No artwork is downloaded, no image is approved, and no database is touched.
The exported JSON deliberately isn't a character import catalog or approval manifest.

Example (opt-in external requests):
  WIKIMEDIA_USER_AGENT='MyProject/1.0 (contact: maintainer@example.org)' \
    python -m scripts.discover_commons_artwork pilot-review.json commons-candidates.json --fetch --limit 10

Review the subject match, file page, derivative rights, exact license, author,
required attribution, source permissions, content safety and Telegram reachability
before separately preparing a *manual* character catalog and approval manifest.
"""
import argparse
import json
import os
import re
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

API = 'https://commons.wikimedia.org/w/api.php'
MIME_TYPES = {'image/jpeg', 'image/png'}
BLOCKED_WORDS = re.compile(r'(?i)(?:\b(?:nsfw|hentai|porn|explicit|erotic|nude|nudity)\b)')


def _metadata_value(info, key):
    field = info.get('extmetadata', {}).get(key, {})
    return str(field.get('value', ''))[:500] if isinstance(field, dict) else ''


def _safe_commons_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value)
    try:
        return (parsed.scheme == 'https' and parsed.hostname in
                {'upload.wikimedia.org', 'commons.wikimedia.org'}
                and parsed.username is None and parsed.password is None
                and parsed.port in (None, 443))
    except ValueError:
        return False


def build_candidates(character, payload, max_results=3):
    """Turn one Commons API response into unapproved, provenance-rich candidates."""
    if not isinstance(payload, dict) or 'error' in payload:
        raise ValueError('Invalid Commons API response')
    if 'query' not in payload:
        return []  # Commons may omit query entirely when there are zero matches.
    if not isinstance(payload['query'], dict):
        raise ValueError('Invalid Commons query response')
    if type(max_results) is not int or not 1 <= max_results <= 10:
        raise ValueError('max_results must be 1..10')
    key, name, series = (character.get(x) for x in ('source_key', 'name', 'series'))
    if not all(isinstance(x, str) and x.strip() for x in (key, name, series)):
        raise ValueError('Review queue character needs source_key, name, series')
    output = []
    pages = payload['query'].get('pages', [])
    if not isinstance(pages, list):
        raise ValueError('Invalid Commons pages')
    for page in pages:
        if not isinstance(page, dict) or page.get('ns') != 6:
            continue
        title = page.get('title', '')
        info = (page.get('imageinfo') or [None])[0]
        if not isinstance(info, dict) or not isinstance(title, str):
            continue
        url = info.get('url')
        file_page = info.get('descriptionurl')
        if (info.get('mime') not in MIME_TYPES or not _safe_commons_url(url)
                or not _safe_commons_url(file_page) or BLOCKED_WORDS.search(title)):
            continue
        if _metadata_value(info, 'NonFree').strip().lower() in ('true', '1'):
            continue
        output.append({
            'source_key': key,
            'character_name': name,
            'series': series,
            'commons_file_title': title,
            'file_page_url': file_page,
            'candidate_image_url': url,
            'license_hint': _metadata_value(info, 'LicenseShortName'),
            'license_url_hint': _metadata_value(info, 'LicenseUrl'),
            'artist_hint': _metadata_value(info, 'Artist'),
            'attribution_hint': _metadata_value(info, 'Attribution'),
            'restrictions_hint': _metadata_value(info, 'Restrictions'),
            'review_status': 'pending_human_license_subject_and_safety_review',
            'permission_reference': None,
            'approved_for_import': False,
        })
        if len(output) >= max_results:
            break
    return output


def search_character(character, user_agent, per_character=3, timeout=12):
    """Make exactly one bounded metadata API request, not a file/image download."""
    if not isinstance(user_agent, str) or len(user_agent.strip()) < 15:
        raise ValueError('Set a descriptive WIKIMEDIA_USER_AGENT with contact info')
    if type(per_character) is not int or not 1 <= per_character <= 10:
        raise ValueError('per_character must be 1..10')
    name = character.get('name')
    series = character.get('series')
    if not all(isinstance(x, str) and x.strip() for x in (name, series)):
        raise ValueError('Character needs a name and series')
    params = {
        'action': 'query', 'format': 'json', 'formatversion': '2',
        'generator': 'search', 'gsrnamespace': 6,
        'gsrsearch': f'"{name.strip()}" "{series.strip()}"',
        'gsrlimit': per_character,
        'prop': 'imageinfo', 'iiprop': 'url|mime|extmetadata',
    }
    request = Request(API + '?' + urlencode(params),
                      headers={'User-Agent': user_agent.strip(), 'Accept': 'application/json'})
    with urlopen(request, timeout=timeout) as response:
        raw = response.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ValueError('Commons response exceeds 1 MB limit')
    return build_candidates(character, json.loads(raw), max_results=per_character)


def discover(rows, fetcher, limit=10, per_character=3):
    if not isinstance(rows, list) or type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError('Pilot review queue must be an array and limit 1..50')
    if type(per_character) is not int or not 1 <= per_character <= 10:
        raise ValueError('per_character must be 1..10')
    results = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = row.get('source_key')
        if not isinstance(key, str) or key in seen:
            continue
        seen.add(key)
        if len(seen) > limit:
            break
        results.extend(fetcher(row, per_character))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('review_queue_json')
    parser.add_argument('output_json')
    parser.add_argument('--fetch', action='store_true', help='Explicitly allow bounded Commons API calls')
    parser.add_argument('--limit', type=int, default=10, help='Max characters (1..50)')
    parser.add_argument('--per-character', type=int, default=3, help='Max files per character (1..10)')
    args = parser.parse_args()
    if not args.fetch:
        parser.error('No network calls by default; --fetch is required')
    agent = os.environ.get('WIKIMEDIA_USER_AGENT', '')
    if len(agent.strip()) < 15 or '@' not in agent and 'http' not in agent.lower():
        parser.error('Set WIKIMEDIA_USER_AGENT with project name and contact')
    rows = json.loads(Path(args.review_queue_json).read_text(encoding='utf-8'))
    result = discover(rows, lambda row, n: search_character(row, agent, n),
                      limit=args.limit, per_character=args.per_character)
    out = Path(args.output_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'unapproved_candidates': len(result),
                      'characters_with_candidates': len({x['source_key'] for x in result}),
                      'approved_for_import': 0}))


if __name__ == '__main__':
    main()
