"""Pilih panel sumber ahli yang mencakup topik dan memisahkan kelompok serta konflik."""
from ._contracts import ResearchError, anchor, cli, decode, identifier, integer, items, obj, schema, source_bytes, text


def form_panel(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.expert-panel-plan.v1", ("registry", "topics", "capacity", "minimum_credibility"))
    target = {}
    for row in items(plan["topics"], 30, 1):
        obj(row, ("id", "weight", "minimum_members"))
        key = identifier(row["id"], "Topik panel")
        if key in target:
            raise ResearchError("Topik panel ganda.")
        target[key] = (integer(row["weight"], "Bobot topik", 1, 1000),
                       integer(row["minimum_members"], "Pakar minimum", 1, 15))
    cap = integer(plan["capacity"], "Kapasitas panel", 1, 30)
    credibility = integer(plan["minimum_credibility"], "Kredibilitas minimum", 0, 100)
    ref = obj(plan["registry"], ("path", "sha256"))
    census = decode(source_bytes(root, ref["path"], ref["sha256"], 1000000))
    schema(census, "ace.institute.expert-registry.v1", ("entries",))
    candidate = {}
    known = set()
    holds = []
    for row in items(census["entries"], 160, 1):
        obj(row, ("id", "group", "topics", "credential_ref", "disclosure", "credibility"))
        key = identifier(row["id"], "Pakar")
        if key in known:
            raise ResearchError("ID pakar ganda.")
        known.add(key)
        category = identifier(row["group"], "Grup afiliasi")
        topics = {identifier(name, "Keahlian") for name in items(row["topics"], 45, 1)} & target.keys()
        support = text(row["credential_ref"], "Pointer keahlian")
        score = integer(row["credibility"], "Skor kredibilitas", 0, 100)
        status = row["disclosure"]
        if status not in ("none_declared", "conflict_declared", "unknown"):
            raise ResearchError("Status disclosure belum didukung.")
        reasons = (["conflict_or_unknown"] if status != "none_declared" else []) + (
            ["below_credibility"] if score < credibility else []) + (["no_relevant_topic"] if not topics else [])
        if reasons:
            holds.append({"id": key, "reasons": reasons})
        else:
            candidate[key] = {"id": key, "group": category, "topics": sorted(topics),
                              "credential_ref": support, "credibility": score}
    selected = []
    groups = set()
    filled = dict.fromkeys(target, 0)
    while len(selected) < cap:
        best = []
        for key, value in candidate.items():
            if value["group"] in groups:
                continue
            additional = sum(target[topic][0] for topic in value["topics"] if filled[topic] < target[topic][1])
            if additional:
                best.append((-additional, -value["credibility"], key))
        if not best:
            break
        _, _, key = min(best)
        added = candidate.pop(key)
        selected.append(added)
        groups.add(added["group"])
        for topic in added["topics"]:
            filled[topic] += 1
    unmet = [{"topic": key, "required": target[key][1], "selected_members": value}
             for key, value in sorted(filled.items()) if value < target[key][1]]
    return {"schema": "ace.institute.expert-panel.v1", "plan_sha256": expected, "source": ref,
            "method": "greedy_weighted_coverage_distinct_affiliations",
            "selected": selected, "hold": sorted(holds, key=lambda row: row["id"]),
            "coverage": filled, "unmet_topics": unmet}


if __name__ == "__main__":
    raise SystemExit(cli(form_panel, __doc__, rooted=True))
