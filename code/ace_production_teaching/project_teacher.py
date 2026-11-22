"""Pandulah proyek mini melalui gate milestone dengan artefak yang benar-benar diperiksa."""
from ._contracts import (ProductionError, anchor, cli, identifier, identity, integer,
                         items, obj, schema, source_bytes, text)
from .artifact_qa import inspect
from .topic_map import graph


def project(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.project-plan.v1", ("graph", "deliverables", "submissions", "minutes"))
    pipeline = graph(plan["graph"], identity(plan["graph"]))
    budget = integer(plan["minutes"], "Menit proyek", 1, 6000)
    paired = {}
    for row in items(plan["deliverables"], 300, 1):
        obj(row, ("id", "format", "minimum", "goal", "source_ref"))
        key = identifier(row["id"], "Milestone")
        if key in paired or key not in pipeline["topics"] or row["format"] not in ("docx", "pdf", "xlsx", "pptx", "svg"):
            raise ProductionError("Milestone ganda, format belum didukung atau topik belum terdaftar.")
        if not isinstance(row["minimum"], dict) or not row["minimum"]:
            raise ProductionError("Milestone memerlukan batas struktur yang terukur.")
        gates = {identifier(name, "Kriteria format"): integer(value, "Batas format", 1, 100000)
                 for name, value in row["minimum"].items()}
        paired[key] = {**row, "minimum": gates, "goal": text(row["goal"], "Target proyek"),
                       "source_ref": text(row["source_ref"], "Pointer target")}
    if paired.keys() != pipeline["topics"].keys():
        raise ProductionError("Setiap milestone peta harus memiliki artefak yang akan diverifikasi.")
    supplied = {}
    for row in items(plan["submissions"], 300):
        obj(row, ("id", "path", "sha256"))
        key = identifier(row["id"], "Milestone kiriman")
        if key in supplied or key not in paired:
            raise ProductionError("Kiriman ganda atau milestone belum dikenal.")
        supplied[key] = row
    completed = set()
    reports = []
    for key in pipeline["order"]:
        context = pipeline["topics"][key]
        request = paired[key]
        dependencies = sorted(set(context["required"]) - completed)
        report = {"id": key, "goal": request["goal"], "source_ref": request["source_ref"],
                  "needs": dependencies, "minutes": context["duration_minutes"]}
        if dependencies:
            reports.append({**report, "status": "blocked_by_unverified_predecessor"})
        elif key in supplied:
            ref = supplied[key]
            raw = source_bytes(root, ref["path"], ref["sha256"], 8_000_000)
            current = inspect(raw, request["format"])
            failed = [name for name, minimum in request["minimum"].items()
                      if type(current.get(name)) is not int or current[name] < minimum]
            if current["active_features"]:
                failed.append("active_features")
            if not failed:
                completed.add(key)
            reports.append({**report, "status": "verified" if not failed else "review_needed",
                            "artifact": ref, "failures": failed})
        elif budget >= context["duration_minutes"]:
            budget -= context["duration_minutes"]
            reports.append({**report, "status": "next_activity"})
        else:
            reports.append({**report, "status": "outside_budget"})
    return {"schema": "ace.teaching.mini-project.v1", "plan_sha256": expected,
            "graph_sha256": identity(pipeline), "milestones": reports, "minutes_left": budget,
            "verified_count": len(completed)}


if __name__ == "__main__":
    raise SystemExit(cli(project, __doc__, rooted=True))
