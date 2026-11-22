"""Peta prasyarat topik yang merinci rute, tingkat, dan urutan topologis."""
from collections import defaultdict

from ._contracts import ProductionError, anchor, cli, identifier, integer, items, obj, schema, text


def graph(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.teaching.topic-graph-plan.v1", ("topics",))
    nodes = {}
    for row in items(plan["topics"], 400, 1):
        obj(row, ("id", "title", "requires", "minutes", "source_ref"))
        key = identifier(row["id"], "ID topik")
        if key in nodes:
            raise ProductionError("Topik ganda.")
        needs = [identifier(value, "Prasyarat") for value in items(row["requires"], 70)]
        if len(set(needs)) != len(needs) or key in needs:
            raise ProductionError("Prasyarat ganda atau menunjuk diri.")
        nodes[key] = {"title": text(row["title"], "Judul topik"), "required": sorted(needs),
                      "duration_minutes": integer(row["minutes"], "Durasi topik", 1, 1200),
                      "source_ref": text(row["source_ref"], "Sumber topik")}
    for node in nodes.values():
        if not set(node["required"]) <= nodes.keys():
            raise ProductionError("Prasyarat di luar peta topik.")
    remaining = set(nodes)
    placed = {}
    exits = defaultdict(set)
    while remaining:
        ready = sorted(key for key in remaining if not remaining.intersection(nodes[key]["required"]))
        if not ready:
            raise ProductionError("Peta prasyarat membentuk siklus.")
        for key in ready:
            node = nodes[key]
            needed = node["required"]
            parents = {value for before in needed for value in placed[before]["transitive_requires"]}
            path = max((placed[before]["critical_minutes"] for before in needed), default=0)
            levels = [placed[before]["level"] for before in needed]
            placed[key] = {"id": key, **node, "level": max(levels, default=-1) + 1,
                           "critical_minutes": path + node["duration_minutes"],
                           "transitive_requires": sorted(parents | set(needed))}
            for before in needed:
                exits[before].add(key)
            remaining.remove(key)
    return {"schema": "ace.teaching.topic-map.v1", "plan_sha256": expected, "order": list(placed),
            "topics": {key: {**node, "unlocks": sorted(exits[key])} for key, node in placed.items()}}


if __name__ == "__main__":
    raise SystemExit(cli(graph, __doc__))
