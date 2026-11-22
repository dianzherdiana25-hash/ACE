"""Cari solusi tanpa tabrakan untuk jendela yang diberikan dan minimalkan biaya memindah jadwal."""
from datetime import timedelta

from ._contracts import PresenceError, anchor, cli, identifier, integer, items, obj, schema
from ._journal import instant
from ._timeline import minute_slots, minutes

def optimize(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.optimize-plan.v1", ("busy", "missions"))
    busy = minute_slots(plan["busy"])
    jobs = []
    seen = set()
    for row in items(plan["missions"], 8, 1):
        obj(row, ("id", "duration", "preferred", "starts", "weight"))
        key = identifier(row["id"], "Misi")
        if key in seen:
            raise PresenceError("Misi ganda.")
        seen.add(key)
        preferred = instant(row["preferred"])
        length = integer(row["duration"], "Menit", 1, 10080)
        weight = integer(row["weight"], "Bobot pindah", 1, 100)
        options = []
        for value in sorted(set(items(row["starts"], 5, 1))):
            start = instant(value)
            end = start + timedelta(minutes=length)
            if start.second == 0 and not any(start < last and first < end for first, last in busy):
                options.append((abs(minutes(preferred.replace(second=0), start)) * weight, start, end, value))
        jobs.append((key, options))
    jobs.sort(key=lambda item: (len(item[1]), item[0]))
    best = None
    def visit(index, chosen, cost):
        nonlocal best
        if best is not None and cost > best[0]:
            return
        if index == len(jobs):
            placements = tuple(sorted((key, value) for key, _, _, value in chosen))
            candidate = (cost, placements)
            if best is None or candidate < best:
                best = candidate
            return
        key, options = jobs[index]
        for penalty, start, end, value in options:
            if not any(start < last and first < end for _, first, last, _ in chosen):
                visit(index + 1, [*chosen, (key, start, end, value)], cost + penalty)
    visit(0, [], 0)
    return {"feasible": best is not None, "cost": best[0] if best else None,
            "starts": dict(best[1]) if best else {}}

if __name__ == "__main__":
    raise SystemExit(cli(optimize, __doc__))
