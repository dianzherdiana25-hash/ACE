"""Buat pelajaran jembatan yang menyatukan tujuan dua topik dan menahan prasyarat tak terbukti."""
from ._contracts import ProductionError, anchor, cli, identifier, identity, integer, items, obj, schema, text
from .topic_map import graph


def bridge(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.teaching.bridge-lesson-plan.v1", ("graph", "pair", "completed", "activities", "minutes"))
    space = graph(plan["graph"], identity(plan["graph"]))
    left, right = [identifier(value, "Topik jembatan") for value in items(plan["pair"], 2, 2)]
    catalogue = space["topics"]
    if left == right or any(key not in catalogue for key in (left, right)):
        raise ProductionError("Pelajaran jembatan memerlukan dua topik terdaftar.")
    learned = {}
    for row in items(plan["completed"], 400):
        obj(row, ("topic", "ref"))
        key = identifier(row["topic"], "Topik terbukti")
        if key in learned or key not in catalogue:
            raise ProductionError("Bukti topik ganda atau tidak dikenal.")
        learned[key] = text(row["ref"], "Pointer bukti belajar")
    targets = {left, right}
    a, b = [set(catalogue[key]["transitive_requires"]) for key in (left, right)]
    needed = (a | b) - targets
    missing = sorted(needed - learned.keys())
    schedule = []
    seen = set()
    hours = integer(plan["minutes"], "Batas waktu", 1, 400)
    prior_goals = set()
    for row in items(plan["activities"], 50, 2):
        obj(row, ("id", "goal", "topics", "kind", "minutes", "material_ref"))
        key = identifier(row["id"], "Aktivitas")
        topics = {identifier(item, "Topik kegiatan") for item in items(row["topics"], 2, 1)}
        if key in seen or not topics <= targets or row["kind"] not in ("review", "compare", "apply"):
            raise ProductionError("Aktivitas ganda atau bentuk belum didukung.")
        seen.add(key)
        if row["kind"] == "apply" and (topics != targets or not targets <= prior_goals):
            raise ProductionError("Latihan aplikasi perlu dua topik yang telah dikenalkan pada kegiatan.")
        prior_goals.update(topics)
        schedule.append({"id": key, "topics": sorted(topics), "kind": row["kind"],
                         "goal": text(row["goal"], "Tujuan kegiatan"), "minutes": integer(row["minutes"], "Waktu kegiatan", 1, 180),
                         "source_ref": text(row["material_ref"], "Pointer kegiatan")})
    if sum(row["minutes"] for row in schedule) > hours or not any(row["kind"] == "apply" for row in schedule):
        raise ProductionError("Materi perlu latihan aplikasi dan durasi di dalam anggaran.")
    return {"schema": "ace.teaching.bridge-lesson.v1", "plan_sha256": expected, "targets": [left, right],
            "shared_prerequisites": sorted((a & b) - targets), "missing_proof": missing,
            "required_proofs": {name: learned[name] for name in sorted(needed & learned.keys())},
            "activities": [] if missing else schedule, "status": "awaiting_prerequisites" if missing else "draft_ready"}


if __name__ == "__main__":
    raise SystemExit(cli(bridge, __doc__))
