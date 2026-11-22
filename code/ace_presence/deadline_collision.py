"""Temukan tabrakan tenggat dari demand yang melebihi menit kerja dalam jendela mana pun."""
from bisect import bisect_right
from itertools import accumulate

from ._contracts import PresenceError, anchor, cli, identifier, integer, items, obj, schema, text
from ._journal import format_time, instant
from ._timeline import minute_slots, minutes

def collide(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.deadline-collisions.v1", ("working", "tasks"))
    shifts = minute_slots(plan["working"])
    tasks = []
    seen = set()
    for row in items(plan["tasks"], 120):
        obj(row, ("id", "available_at", "due_at", "minutes", "source"))
        key = identifier(row["id"], "Tugas")
        start, end = instant(row["available_at"]), instant(row["due_at"])
        if start >= end or start.second or end.second or key in seen:
            raise PresenceError("Jendela tugas harus maju dan unik, pada batas menit.")
        seen.add(key)
        tasks.append((start, end, integer(row["minutes"], "Demand", 1, 100_000),
                      key, text(row["source"], "Bukti tenggat")))
    shift_ends = [end for _, end in shifts]
    cumulative = list(accumulate((minutes(start, end) for start, end in shifts), initial=0))
    def capacity_through(point):
        bound = bisect_right(shift_ends, point)
        complete = cumulative[bound]
        if bound < len(shifts):
            partial = max(0, minutes(shifts[bound][0], point))
            return complete + partial
        return complete
    conflicts = []
    starts = sorted({row[0] for row in tasks})
    ends = sorted({row[1] for row in tasks})
    for first in starts:
        for last in ends:
            if first >= last:
                continue
            required = [entry for entry in tasks if first <= entry[0] and entry[1] <= last]
            demand = sum(entry[2] for entry in required)
            capacity = capacity_through(last) - capacity_through(first)
            if demand > capacity:
                detail = {"start": format_time(first), "end": format_time(last),
                          "demand_minutes": demand, "capacity_minutes": capacity, "deficit_minutes": demand - capacity,
                          "tasks": [{"id": row[3], "source": row[4]} for row in sorted(required, key=lambda row: row[3])]}
                conflicts.append(detail)
    return {"can_fit_preemptive": not conflicts,
            "collisions": sorted(conflicts, key=lambda row: (-row["deficit_minutes"], row["start"], row["end"]))}

if __name__ == "__main__":
    raise SystemExit(cli(collide, __doc__))
