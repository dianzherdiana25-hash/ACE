"""Usulkan karantina langkah dari kegagalan beruntun dan hormati fungsi yang wajib dipertahankan."""
from collections import defaultdict

from ._contracts import GuardianError, anchor, cli, identifier, integer, items, obj, schema, text
from .snapshot_scheduler import instant

def suggest(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.step-quarantine.v1", ("outcomes", "threshold", "protected"))
    minimum = integer(plan["threshold"], "Kegagalan beruntun", 1, 1000)
    protected = {identifier(key, "Langkah wajib") for key in items(plan["protected"], 200)}
    groups = defaultdict(list)
    points = set()
    for row in items(plan["outcomes"], 7000):
        obj(row, ("step", "at", "ok", "source"))
        key = identifier(row["step"], "Langkah")
        stamp = instant(row["at"])
        if type(row["ok"]) is not bool or (key, stamp) in points:
            raise GuardianError("Hasil karantina ganda atau flag tidak valid.")
        points.add((key, stamp))
        groups[key].append((stamp, row["ok"], text(row["source"], "Bukti status")))
    report = []
    for key, rows in sorted(groups.items()):
        streak = []
        for _, ok, source in sorted(rows, reverse=True):
            if ok:
                break
            streak.append(source)
        if len(streak) >= minimum:
            report.append({"step": key, "streak": len(streak), "sources": streak,
                           "suggestion": "operator_review_protected" if key in protected else "draft_quarantine"})
    return {"findings": report, "mutations": 0}

if __name__ == "__main__":
    raise SystemExit(cli(suggest, __doc__))
