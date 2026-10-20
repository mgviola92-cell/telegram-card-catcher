"""Deterministic cross-source identity review: suggestions are NEVER automatic merges.

Input: already-staged, locally permitted review metadata (arrays of
source_key/name/series), NOT bulk raw source dumps. No network, DB, images,
or live production writes. Name+series is only a *candidate* match.
An explicit human reviewed decision with independently checked source
evidence is required, and still does not license any character image.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit

MAX_ROWS = 200_000
MAX_CANDIDATE_PAIRS = 10_000
MAX_BUCKET = 8
GENERIC_SERIES = {"", "unknown", "unknown series", "other", "n/a", "untitled"}


def normalize(text):
    if not isinstance(text, str):
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).casefold()).strip()


def pair_key(a, b):
    if not isinstance(a, str) or not isinstance(b, str) or not a or not b or a == b:
        raise ValueError("Identity pair must use two distinct source keys")
    return tuple(sorted((a, b)))


def inspect_sources(named_sources, max_rows=MAX_ROWS, max_bucket=MAX_BUCKET,
                    max_pairs=MAX_CANDIDATE_PAIRS):
    """Find bounded candidate pairs using already curated metadata only."""
    if not isinstance(named_sources, dict) or not 1 <= len(named_sources) <= 16:
        raise ValueError("Use 1..16 named source arrays")
    if type(max_rows) is not int or not 1 <= max_rows <= MAX_ROWS:
        raise ValueError("Invalid metadata row bound")
    if type(max_bucket) is not int or not 2 <= max_bucket <= 32:
        raise ValueError("Invalid ambiguity bucket bound")
    if type(max_pairs) is not int or not 1 <= max_pairs <= MAX_CANDIDATE_PAIRS:
        raise ValueError("Invalid candidate output bound")
    buckets = defaultdict(list)
    keys = {}
    sources = {}
    invalid = 0
    total = 0
    if not all(isinstance(s, str) and s.strip() for s in named_sources):
        raise ValueError("Source labels must be nonempty strings")
    for source, rows in sorted(named_sources.items()):
        if not isinstance(source, str) or not source.strip() or not isinstance(rows, list):
            raise ValueError("Sources must have distinct names and arrays")
        sources[source] = len(rows)
        total += len(rows)
        if total > max_rows:
            raise ValueError("Input exceeds preapproved metadata row limit")
        for row in rows:
            if not isinstance(row, dict):
                invalid += 1
                continue
            key, name, series = (row.get(f) for f in ("source_key", "name", "series"))
            if not all(isinstance(v, str) and 0 < len(v.strip()) <= 200
                       for v in (key, name, series)):
                invalid += 1
                continue
            key = key.strip()
            if key in keys:
                raise ValueError("Duplicated source_key; cannot safely review identity")
            keys[key] = source
            norm_name, norm_series = normalize(name), normalize(series)
            if len(norm_name) < 3 or norm_series in GENERIC_SERIES:
                continue
            buckets[(norm_name, norm_series)].append({
                "source": source, "source_key": key, "name": name.strip(),
                "series": series.strip()
            })
    candidates = []
    crowded = 0
    omitted = 0
    for (name, series), rows in sorted(buckets.items()):
        source_names = {r["source"] for r in rows}
        if len(source_names) < 2:
            continue
        if len(rows) > max_bucket:
            crowded += 1
            omitted += len(rows)
            continue
        for i, left in enumerate(rows):
            for right in rows[i+1:]:
                if left["source"] == right["source"]:
                    continue
                if len(candidates) >= max_pairs:
                    raise ValueError("Too many candidate pairs; split review into smaller batches")
                candidates.append({
                    "left_key": left["source_key"],
                    "right_key": right["source_key"],
                    "left_source": left["source"],
                    "right_source": right["source"],
                    "left_name": left["name"],
                    "right_name": right["name"],
                    "left_series": left["series"],
                    "right_series": right["series"],
                    "status": "pending",
                    "evidence_url": None,
                    "review_note": None,
                })
    candidates.sort(key=lambda c: pair_key(c["left_key"], c["right_key"]))
    return {
        "sources": sources,
        "rows_scanned": total,
        "invalid_rows": invalid,
        "distinct_keys": len(keys),
        "crowded_name_series_buckets_skipped": crowded,
        "rows_in_crowded_buckets_skipped": omitted,
        "candidate_pairs": candidates,
        "note": "Text collisions are ONLY hints; not proven identities or rights-approved artwork.",
    }


def apply_human_decisions(report, decisions):
    """Validate explicit pair decisions, reject contradictory transitive merges."""
    if not isinstance(report, dict) or not isinstance(report.get("candidate_pairs"), list):
        raise ValueError("Expected a candidate-review report")
    if not isinstance(decisions, list) or len(decisions) > MAX_CANDIDATE_PAIRS:
        raise ValueError("Decisions must be a bounded list")
    pairs = {}
    source_by_key = {}
    for candidate in report["candidate_pairs"]:
        key = pair_key(candidate["left_key"], candidate["right_key"])
        if key in pairs:
            raise ValueError("Duplicated candidate pair")
        pairs[key] = candidate
        for field, source in (("left_key", "left_source"), ("right_key", "right_source")):
            k = candidate[field]
            if k in source_by_key and source_by_key[k] != candidate[source]:
                raise ValueError("Ambiguous source for a source_key")
            source_by_key[k] = candidate[source]
    reviewed = {}
    for item in decisions:
        if not isinstance(item, dict):
            raise ValueError("Invalid human decision")
        pair = pair_key(item.get("left_key"), item.get("right_key"))
        if pair not in pairs or pair in reviewed:
            raise ValueError("Duplicate or unrelated identity decision")
        status = item.get("status")
        if status not in ("same", "different"):
            raise ValueError("Decision must be same or different (no auto-approve)")
        evidence = item.get("evidence_url")
        note = item.get("review_note")
        parsed = urlsplit(evidence) if isinstance(evidence, str) else None
        if (not parsed or parsed.scheme != "https" or not parsed.hostname or
            parsed.username or parsed.password or not isinstance(note, str)
            or len(note.strip()) < 15):
            raise ValueError("Human decision needs a public HTTPS evidence link and rationale")
        reviewed[pair] = status

    parent = {key:key for key in source_by_key}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        left, right = find(a), find(b)
        if left != right:
            parent[max(left, right)] = min(left, right)

    for (a, b), status in sorted(reviewed.items()):
        if status == "same":
            union(a, b)
    groups = defaultdict(list)
    for key in parent:
        groups[find(key)].append(key)
    for members in groups.values():
        if len(members) < 2:
            continue
        members_sources = [source_by_key[key] for key in members]
        if len(set(members_sources)) != len(members_sources):
            raise ValueError("Identity merge would collapse two IDs from the same source")
    for (a, b), status in reviewed.items():
        if status == "different" and find(a) == find(b):
            raise ValueError("Conflicting SAME and DIFFERENT decisions in one cluster")

    clusters = [sorted(members) for members in groups.values() if len(members) >= 2]
    clusters.sort()
    return {
        "candidate_pairs":len(pairs),
        "human_reviewed_same_pairs":sum(s == "same" for s in reviewed.values()),
        "human_reviewed_different_pairs":sum(s == "different" for s in reviewed.values()),
        "unreviewed_candidate_pairs":len(pairs)-len(reviewed),
        "human_reviewed_identity_clusters":clusters,
        "claimed_redundant_source_keys_within_reviewed_clusters":
            sum(len(c)-1 for c in clusters),
        "artwork_approved":0,
        "characters_imported":0,
        "globally_verified_unique_characters":None,
        "note":"Manual review claims only; source rights and artwork are NOT approved. "
               "Do not subtract candidate count from catalog totals or auto-import.",
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("sources", nargs="+", metavar="LABEL=staged.json")
    cli.add_argument("--decisions", help="Optional human-evidence decision array")
    cli.add_argument("--output", required=True)
    cli.add_argument("--summary-only", action="store_true")
    a = cli.parse_args()
    named = {}
    for item in a.sources:
        label, sep, filename = item.partition("=")
        if not sep or not label or not filename or label in named:
            cli.error("Provide unique LABEL=staged.json arguments")
        named[label] = json.loads(Path(filename).read_text(encoding="utf8"))
    report = inspect_sources(named)
    if a.decisions:
        report["decisions_summary"] = apply_human_decisions(
            report, json.loads(Path(a.decisions).read_text(encoding="utf8")))
    if a.summary_only:
        report["candidate_pairs_count"] = len(report.pop("candidate_pairs"))
    target = Path(a.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf8")
    print(json.dumps({k:v for k,v in report.items()
                      if k not in ("candidate_pairs","decisions_summary")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
