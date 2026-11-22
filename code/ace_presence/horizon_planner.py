"""Hitung latest finish tiap tonggak dari dependensi dan tenggat akhir yang dinyatakan."""
from collections import defaultdict
from datetime import timedelta

from ._contracts import PresenceError, anchor, cli, identifier, integer, items, obj, schema, text
from ._journal import format_time, instant

def plan_horizon(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.horizon-plan.v1", ("start", "deadline", "milestones"))
    start, deadline = instant(plan["start"]), instant(plan["deadline"])
    if start >= deadline:
        raise PresenceError("Cakrawala harus maju.")
    milestones = {}
    needed_by = defaultdict(set)
    for row in items(plan["milestones"], 300, 1):
        obj(row, ("id", "minutes", "requires", "source"))
        key = identifier(row["id"], "Tonggak")
        dependencies = {identifier(value, "Prasyarat") for value in items(row["requires"], 75)}
        duration = timedelta(minutes=integer(row["minutes"], "Durasi", 1, 50_000))
        text(row["source"], "Pointer")
        if key in milestones or key in dependencies:
            raise PresenceError("ID tonggak salah atau prasyarat diri sendiri.")
        milestones[key] = (duration, dependencies, row["source"])
        for need in dependencies:
            needed_by[need].add(key)
    if needed_by.keys() - milestones.keys():
        raise PresenceError("Tonggak bergantung pada ID yang tidak ditemukan.")
    finish = {}
    remaining = set(milestones)
    while remaining:
        leaves = sorted(key for key in remaining if needed_by[key] <= finish.keys())
        if not leaves:
            raise PresenceError("Prasyarat tonggak melingkar.")
        for key in leaves:
            finish[key] = min((finish[child] - milestones[child][0] for child in needed_by[key]), default=deadline)
        remaining.difference_update(leaves)
    rows = [{"id": key, "latest_start": format_time(finish[key] - milestones[key][0]),
             "latest_finish": format_time(finish[key]), "source": milestones[key][2]} for key in sorted(finish)]
    return {"milestones": rows, "can_fit_parallel": all(instant(row["latest_start"]) >= start for row in rows)}

if __name__ == "__main__":
    raise SystemExit(cli(plan_horizon, __doc__))
