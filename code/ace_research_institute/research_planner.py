"""Ubah pertanyaan menjadi rencana falsifiable dengan prasyarat, biaya, dan kondisi berhenti."""
from collections import defaultdict

from ._contracts import ResearchError, anchor, cli, identifier, integer, items, obj, schema, text, words


METHODS = {
    "literature": {"fields": ("population", "outcome", "independent_groups"), "artefact": "evidence_grid"},
    "measurement": {"fields": ("population", "outcome", "comparator", "minimum_n"), "artefact": "measurement_table"},
    "survey": {"fields": ("population", "minimum_n", "sampling_rule"), "artefact": "response_matrix"},
    "replication": {"fields": ("outcome", "comparator", "minimum_n", "protocol_ref"), "artefact": "replication_receipt"},
}


def _method(row, name):
    info = METHODS[name]
    obj(row, info["fields"])
    return {key: integer(value, key, 1, 10**7) if key in ("minimum_n", "independent_groups")
            else text(value, key) for key, value in row.items()}


def _load(tasks, focus):
    planned = {}
    for row in items(tasks, 120, 1):
        obj(row, ("id", "question", "method", "specification", "evidence", "falsifier", "after",
                  "person_hours", "priority", "covers"))
        name = identifier(row["id"], "Pekerjaan riset")
        if name in planned or row["method"] not in METHODS:
            raise ResearchError("ID pekerjaan ganda atau metode belum didukung.")
        specified = _method(row["specification"], row["method"])
        evidence = [text(item, "Bukti minimal") for item in items(row["evidence"], 20, 1)]
        falsifier = text(row["falsifier"], "Kondisi yang menyangkal")
        depends = [identifier(item, "Prasyarat") for item in items(row["after"], 40)]
        covers = set()
        for phrase in items(row["covers"], 30, 1):
            covers.update(words(text(phrase, "Slot relevansi", 80)))
        if len(set(depends)) != len(depends) or not covers & focus:
            raise ResearchError("Prasyarat ganda atau tugas tidak bersinggungan dengan fokus.")
        planned[name] = {"id": name, "question": text(row["question"], "Pertanyaan tugas"),
                         "method": row["method"], "specification": specified, "evidence_required": evidence,
                         "falsifier": falsifier, "after": depends, "hours": integer(row["person_hours"], "Jam", 1, 200),
                         "priority": integer(row["priority"], "Prioritas", 0, 100),
                         "focus_terms": sorted(covers & focus), "artefact": METHODS[row["method"]]["artefact"]}
    return planned


def _schedule(tasks, limit):
    remaining = set(tasks)
    placed = {}
    paused = {}
    assigned = 0
    while remaining:
        candidates = [tasks[name] for name in remaining if not remaining.intersection(tasks[name]["after"])]
        if not candidates:
            raise ResearchError("Dependensi pekerjaan membentuk siklus.")
        row = min(candidates, key=lambda item: (-item["priority"], -len(item["focus_terms"]), item["hours"], item["id"]))
        name = row["id"]
        remaining.remove(name)
        absent = sorted(set(row["after"]) - placed.keys())
        if absent:
            paused[name] = {"id": name, "reason": "prerequisite_unplanned", "prerequisites": absent}
        elif assigned + row["hours"] > limit:
            paused[name] = {"id": name, "reason": "hours_exhausted", "needed": row["hours"]}
        else:
            placed[name] = {**row, "from_hour": assigned, "to_hour": assigned + row["hours"]}
            assigned += row["hours"]
    return placed, paused, assigned


def build_plan(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.institute.research-plan.v1", ("question", "focus", "max_hours", "tasks", "exclusions"))
    question = text(plan["question"], "Pertanyaan riset")
    focus = set()
    for query in items(plan["focus"], 30, 1):
        focus.update(words(text(query, "Cakupan riset", 110)))
    if not focus:
        raise ResearchError("Cakupan tidak mengandung kata.")
    limit = integer(plan["max_hours"], "Anggaran jam", 1, 10000)
    tasks = _load(plan["tasks"], focus)
    if any(dep not in tasks for row in tasks.values() for dep in row["after"]):
        raise ResearchError("Prasyarat pekerjaan belum terdaftar.")
    placed, excluded, used = _schedule(tasks, limit)
    mapping = defaultdict(list)
    for row in placed.values():
        for term in row["focus_terms"]:
            mapping[term].append(row["id"])
    return {"schema": "ace.institute.research-schedule.v1", "plan_sha256": expected, "question": question,
            "max_hours": limit, "allocated_hours": used, "schedule": list(placed.values()),
            "unplanned": [excluded[name] for name in sorted(excluded)], "focus_coverage": dict(sorted(mapping.items())),
            "uncovered_focus": sorted(focus - mapping.keys()),
            "scope_exclusions": [text(item, "Batas lingkup") for item in items(plan["exclusions"], 20)],
            "status": "plan_only"}


if __name__ == "__main__":
    raise SystemExit(cli(build_plan, __doc__))
