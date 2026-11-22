"""Proyeksikan menit beban dan menandai kelebihan kapasitas dari irisan kalender."""
from fractions import Fraction

from ._contracts import PresenceError, anchor, cli, identifier, integer, items, obj, schema, text
from ._journal import instant

def project(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.workload.v1", ("windows", "jobs"))
    jobs = []
    for row in items(plan["jobs"], 2000):
        obj(row, ("id", "start", "end", "estimated_minutes", "source"))
        key = identifier(row["id"], "Tugas")
        first, last = instant(row["start"]), instant(row["end"])
        cap = integer(row["estimated_minutes"], "Beban tugas", 0, 100_000)
        if first >= last or cap * 60 > (last - first).total_seconds():
            raise PresenceError("Beban tugas melebihi interval.")
        jobs.append((key, first, last, cap, text(row["source"], "Bukti beban")))
    if len({row[0] for row in jobs}) != len(jobs):
        raise PresenceError("ID tugas ganda.")
    results = []
    for row in items(plan["windows"], 500):
        obj(row, ("id", "start", "end", "capacity_minutes"))
        key = identifier(row["id"], "Jendela")
        first, last = instant(row["start"]), instant(row["end"])
        cap = integer(row["capacity_minutes"], "Kapasitas", 0, 100_000)
        if first >= last:
            raise PresenceError("Jendela tidak maju.")
        shares = [
            (Fraction(load * int((min(last, end) - max(first, start)).total_seconds()),
                      int((end - start).total_seconds())), ref)
            for _, start, end, load, ref in jobs if start < last and first < end
        ]
        total = sum((share for share, _ in shares), Fraction())
        results.append({"id": key, "load_minutes": str(total), "overbooked": total > cap,
                        "capacity_minutes": cap, "sources": sorted({ref for _, ref in shares})})
    return {"windows": results}

if __name__ == "__main__":
    raise SystemExit(cli(project, __doc__))
