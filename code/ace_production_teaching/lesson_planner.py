"""Pilih pelajaran dari celah teramati, rute topik, dan waktu yang tersedia."""
from ._contracts import ProductionError, anchor, cli, identifier, identity, integer, items, obj, schema, text
from .learner_model import posterior
from .topic_map import graph


def plan_lessons(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.lesson-plan.v1", ("topic_graph", "learner_model", "materials", "mastery_floor_bp", "minutes", "targets"))
    profile = posterior(plan["learner_model"], identity(plan["learner_model"]), root)
    subjects = graph(plan["topic_graph"], identity(plan["topic_graph"]))
    threshold = integer(plan["mastery_floor_bp"], "Ambang penguasaan", 1, 10000)
    left = integer(plan["minutes"], "Anggaran pelajaran", 1, 2400)
    known = subjects["topics"]
    targets = [identifier(key, "Target pelajaran") for key in items(plan["targets"], 30, 1)]
    if len(set(targets)) != len(targets) or not set(targets) <= known.keys():
        raise ProductionError("Target ganda atau tidak ada di peta.")
    roles = {}
    content_keys = set()
    for row in items(plan["materials"], 300, 1):
        obj(row, ("id", "topic", "kind", "minutes", "source_ref", "goal"))
        name = identifier(row["id"], "Bahan")
        topic = identifier(row["topic"], "Topik bahan")
        mode = row["kind"]
        if name in content_keys or topic not in known or mode not in ("remedial", "diagnostic", "practice"):
            raise ProductionError("Bahan duplikat, topik tak dikenal atau jenis tidak sesuai.")
        content_keys.add(name)
        roles.setdefault((topic, mode), []).append({"id": name, "minutes": integer(row["minutes"], "Menit bahan", 1, 600),
                        "source_ref": text(row["source_ref"], "Pointer bahan"), "goal": text(row["goal"], "Tujuan latihan")})
    mastered = {key for key, node in profile["topic_posteriors"].items()
                if node["evidence_status"] == "observed" and node["posterior_mean_bp"] >= threshold}
    needed = set(targets) | {before for key in targets for before in known[key]["transitive_requires"]}
    agenda = []
    hold = []
    for key in subjects["order"]:
        if key in mastered or key not in needed:
            continue
        evidence = profile["topic_posteriors"].get(key)
        prereq = sorted(set(known[key]["required"]) - mastered)
        if prereq:
            hold.append({"topic": key, "reason": "prerequisite_unverified", "dependencies": prereq})
            continue
        mode = "diagnostic"
        if evidence and evidence["evidence_status"] == "observed":
            mode = "practice" if evidence["posterior_mean_bp"] * 4 >= threshold * 3 else "remedial"
        available = sorted(roles.get((key, mode), []), key=lambda material: (material["minutes"], material["id"]))
        chosen = next((item for item in available if item["minutes"] <= left), None)
        if chosen is None:
            hold.append({"topic": key, "reason": "material_missing" if not available else "time_budget", "kind": mode})
            continue
        left -= chosen["minutes"]
        agenda.append({"topic": key, "kind": mode, "material": chosen, "topic_source": known[key]["source_ref"],
                       "evidence": None if not evidence else {"attempts": evidence["attempts"],
                                                             "estimate_bp": evidence["posterior_mean_bp"]},
                       "verify_then_unlock": known[key]["unlocks"]})
    return {"schema": "ace.teaching.lesson-draft.v1", "plan_sha256": expected, "learner": profile["learner"],
            "targets": targets, "placed": agenda, "held": hold, "mastered_targets": sorted(set(targets) & mastered),
            "minutes_unused": left, "status": "draft_lesson"}


if __name__ == "__main__":
    raise SystemExit(cli(plan_lessons, __doc__, rooted=True))
