"""Susun peta jalan dua belas bulan dari slot, prioritas, dan prasyarat yang dinyatakan."""
from ._contracts import ResearchError, anchor, cli, day, identifier, integer, items, obj, schema, text


def _month(base, index):
    numeric = base.year * 12 + base.month - 1 + index
    year, month = divmod(numeric, 12)
    if year > 9999:
        raise ResearchError("Peta jalan melebihi rentang kalender.")
    return f"{year:04d}-{month + 1:02d}"


def roadmap(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.institute.roadmap-plan.v1", ("starting_on", "monthly_hours", "projects"))
    start = day(plan["starting_on"])
    capacity = [integer(raw, "Jam satu bulan", 0, 2000) for raw in items(plan["monthly_hours"], 12, 12)]
    months = [_month(start, index) for index in range(12)]
    if start.day != 1:
        raise ResearchError("Peta jalan mulai pada hari pertama bulan.")
    tasks = {}
    for row in items(plan["projects"], 200, 1):
        obj(row, ("id", "question", "priority", "hours", "earliest_month", "deadline_month", "requirements", "evidence_ref"))
        key = identifier(row["id"], "Proyek")
        if key in tasks:
            raise ResearchError("ID proyek ganda.")
        first = integer(row["earliest_month"], "Bulan minimum", 1, 12) - 1
        last = integer(row["deadline_month"], "Tenggat relatif bulan", first + 1, 12) - 1
        deps = [identifier(value, "Prasyarat proyek") for value in items(row["requirements"], 40)]
        if len(set(deps)) != len(deps):
            raise ResearchError("Prasyarat proyek duplikat.")
        tasks[key] = {"id": key, "priority": integer(row["priority"], "Prioritas", 0, 1000),
                      "question": text(row["question"], "Pertanyaan"), "hours": integer(row["hours"], "Jam riset", 1, 16000),
                      "from": first, "to": last, "needs": deps, "evidence_ref": text(row["evidence_ref"], "Pointer rencana")}
    if any(dep not in tasks for row in tasks.values() for dep in row["needs"]):
        raise ResearchError("Prasyarat merujuk proyek tak terdaftar.")
    pending = set(tasks)
    done = {}
    unplaced = []
    emitted = []
    while pending:
        ready = [tasks[name] for name in pending if not pending.intersection(tasks[name]["needs"])]
        if not ready:
            raise ResearchError("Peta jalan memiliki siklus prasyarat.")
        row = min(ready, key=lambda item: (item["to"], -item["priority"], item["id"]))
        key = row["id"]
        pending.remove(key)
        unavailable = sorted(set(row["needs"]) - done.keys())
        if unavailable:
            unplaced.append({"id": key, "reason": "unplaced_dependency", "needs": unavailable})
            continue
        first = max([row["from"], *[done[item] + 1 for item in row["needs"]]])
        positions = range(first, row["to"] + 1)
        if sum(capacity[month] for month in positions) < row["hours"]:
            unplaced.append({"id": key, "reason": "insufficient_hours_before_deadline", "needs": row["needs"]})
            continue
        scheduled = []
        remaining = row["hours"]
        for month in positions:
            hours = min(remaining, capacity[month])
            if not hours:
                continue
            capacity[month] -= hours
            remaining -= hours
            scheduled.append({"month": months[month], "hours": hours})
            if not remaining:
                done[key] = month
                break
        emitted.append({"id": key, "evidence_ref": row["evidence_ref"], "question": row["question"], "work": scheduled})
    return {"schema": "ace.institute.year-roadmap.v1", "plan_sha256": expected,
            "start": start.isoformat(), "allocated": emitted, "unplaced": sorted(unplaced, key=lambda row: row["id"]),
            "remaining_hours": dict(zip(months, capacity, strict=True)), "method": "deadline_then_priority_split_by_month"}


if __name__ == "__main__":
    raise SystemExit(cli(roadmap, __doc__))
