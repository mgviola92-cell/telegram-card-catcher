"""Offline pre-import quality gates. Review rights separately; this is not a license check."""
from collections import Counter
from scripts.import_characters import validate

def report(items):
    rows=validate(items)
    duplicates=Counter((r[1].casefold(),r[2].casefold()) for r in rows)
    repeated={f"{name} / {series}":count for (name,series),count in duplicates.items() if count>1}
    # Normalize whitespace and case: imported spellings must not split one series.
    series_spellings={}
    for row in rows:
        series_spellings.setdefault(' '.join(row[2].casefold().split()),set()).add(row[2])
    inconsistent_series={key:sorted(names) for key,names in series_spellings.items() if len(names)>1}
    image_duplicates=Counter(r[6] for r in rows)
    shared_images=sum(n-1 for n in image_duplicates.values() if n>1)
    weights=Counter()
    for row in rows:
        weights[row[5]]+=row[7]
    total=sum(weights.values())
    probabilities={key:round(100*value/total,4) for key,value in sorted(weights.items())} if total else {}
    issues=[]
    if repeated:
        issues.append(f"{len(repeated)} duplicated name+series pairs")
    if inconsistent_series:
        issues.append(f"{len(inconsistent_series)} inconsistent series spellings")
    if shared_images:
        issues.append(f"{shared_images} reused artwork URLs")
    if any(r[2]=='Unknown Series' for r in rows):
        issues.append("Unknown Series records require review")
    return {"valid_records":len(rows),"duplicate_name_series":repeated,
            "reused_image_urls":shared_images,"inconsistent_series":inconsistent_series,"spawn_weight_by_rarity":dict(weights),
            "estimated_rarity_percent":probabilities,"issues":issues,"passed":not issues}

def require_approval(items,allow_warnings=False):
    result=report(items)
    if not result["passed"] and not allow_warnings:
        raise ValueError("Catalog quality gate failed: "+"; ".join(result["issues"]))
    return result
