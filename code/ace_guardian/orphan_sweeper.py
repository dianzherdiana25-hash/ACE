"""Rencanakan sapuan yatim hanya pada katalog file fixture, dengan umur dan relasi eksplisit."""
from datetime import timedelta

from ._contracts import GuardianError, anchor, cli, integer, items, obj, schema
from ._snapshots import fingerprint, read_fixture, relative
from .snapshot_scheduler import instant

def sweep(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.guardian.orphans.v1", ("now", "age_seconds", "candidates", "references"))
    now = instant(plan["now"])
    minimum = timedelta(seconds=integer(plan["age_seconds"], "Umur yatim", 1, 31_536_000))
    referenced = {relative(value) for value in items(plan["references"], 3000)}
    orphaned = []
    retained = []
    seen = set()
    for row in items(plan["candidates"], 700):
        obj(row, ("path", "created", "hold"))
        key = relative(row["path"])
        created = instant(row["created"])
        if key in seen or type(row["hold"]) is not bool or created > now:
            raise GuardianError("Kandidat sapu ganda atau status/usia tidak sah.")
        seen.add(key)
        try:
            actual = fingerprint(read_fixture(root, row["path"]))
        except FileNotFoundError:
            retained.append({"path": row["path"], "reason": "missing"})
            continue
        reason = "held" if row["hold"] else "referenced" if key in referenced else "young" if now - created < minimum else None
        if reason is None:
            orphaned.append({**row, **actual})
        else:
            retained.append({"path": row["path"], "reason": reason})
    return {"scope": "review_only", "orphaned": sorted(orphaned, key=lambda row: row["path"]),
            "retained": sorted(retained, key=lambda row: row["path"])}

if __name__ == "__main__":
    raise SystemExit(cli(sweep, __doc__, rooted=True))
