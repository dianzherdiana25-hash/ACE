"""Bandingkan median langkah pada dua jendela berurutan, dengan cakupan sampel tiap sisi."""
from collections import defaultdict
from fractions import Fraction
from statistics import median

from ._contracts import GuardianError, anchor, cli, identifier, integer, items, obj, schema, text
from .snapshot_scheduler import instant

def trend(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.slow-trend.v1", ("from", "split", "until", "rows", "minimum", "slowdown_bp"))
    early, middle, late = (instant(plan[key]) for key in ("from", "split", "until"))
    if not early < middle < late:
        raise GuardianError("Jendela tren perlu dua interval maju.")
    minimum = integer(plan["minimum"], "Minimum sampel tiap jendela", 1, 1000)
    limit = integer(plan["slowdown_bp"], "Ambang basis point", 0, 100_000)
    groups = defaultdict(lambda: [[], []])
    seen = set()
    for row in items(plan["rows"], 6000):
        obj(row, ("step", "at", "ms", "source"))
        key = identifier(row["step"], "Langkah")
        when = instant(row["at"])
        duration = integer(row["ms"], "Durasi", 0, 10_000_000)
        if (key, when) in seen:
            raise GuardianError("Langkah dan waktu ganda.")
        seen.add((key, when))
        source = text(row["source"], "Sumber durasi")
        if early <= when < late:
            groups[key][int(when >= middle)].append((Fraction(duration), source))
    report = {}
    for key, (before, after) in sorted(groups.items()):
        left, right = (median([row[0] for row in values]) if values else None for values in (before, after))
        valid = min(len(before), len(after)) >= minimum
        relative = (right - left) / left if valid and left else None
        report[key] = {"baseline_n": len(before), "recent_n": len(after),
                       "baseline_ms": None if left is None else str(left), "recent_ms": None if right is None else str(right),
                       "slower": valid and (relative > Fraction(limit, 10_000) if relative is not None else right > 0),
                       "relative": str(relative) if relative is not None else None,
                       "sources": sorted({row[1] for row in before + after})}
    return {"steps": report}

if __name__ == "__main__":
    raise SystemExit(cli(trend, __doc__))
