"""Buat peta pertentangan numerik dengan pengelompokan konteks dan penunjuk sumber."""
from collections import defaultdict
from decimal import Decimal
from itertools import combinations

from ._contracts import ResearchError, anchor, cli, fmt, identity, integer, items, obj, schema
from ._evidence import dimension, quantity, reviewed


def map_controversy(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.controversy-plan.v1", ("sources", "scopes", "minimum_sample"))
    registry, observations, held = reviewed(plan["sources"], root)
    n = integer(plan["minimum_sample"], "Sampel minimum", 1, 10**8)
    selected = {}
    for row in items(plan["scopes"], 80, 1):
        obj(row, ("dimensions", "unit", "material_difference"))
        unit, gap = quantity(row["material_difference"], row["unit"])
        descriptor = (dimension(row["dimensions"]), unit)
        if gap <= 0 or descriptor in selected:
            raise ResearchError("Ambang material positif dan cakupan unik diperlukan.")
        selected[descriptor] = (row["dimensions"], gap)
    groups = defaultdict(list)
    for row in observations:
        key = (dimension(row["dimensions"]), row["unit"])
        if key in selected and row["sample_size"] >= n:
            groups[key].append(row)
    result = []
    for (dims, unit), (scope, width) in sorted(selected.items()):
        nodes = sorted(groups[dims, unit], key=lambda row: (row["source_id"], row["id"]))
        if len(nodes) > 160:
            raise ResearchError("Jumlah pengukuran sebanding melampaui anggaran pasangan.")
        edges = []
        joined = defaultdict(set)
        for i, j in combinations(range(len(nodes)), 2):
            left, right = nodes[i], nodes[j]
            if left["source"]["independence_group"] == right["source"]["independence_group"]:
                continue
            delta = abs(Decimal(left["estimate"]) - Decimal(right["estimate"]))
            if delta < width:
                continue
            intervals = [row["interval"] for row in (left, right)]
            overlap = None
            if all(value is not None for value in intervals):
                low = max(Decimal(item["lower"]) for item in intervals)
                high = min(Decimal(item["upper"]) for item in intervals)
                overlap = low <= high
            joined[i].add(j)
            joined[j].add(i)
            edges.append({"a": i, "b": j, "delta": fmt(delta), "intervals_overlap": overlap})
        affected = set(joined)
        clusters = []
        while affected:
            visit = [min(affected)]
            seen = set()
            while visit:
                here = visit.pop()
                if here in seen:
                    continue
                seen.add(here)
                visit.extend(joined[here] - seen)
            affected -= seen
            clusters.append(sorted(seen))
        result.append({"dimensions": scope, "unit": unit, "material_difference": fmt(width), "measurements": nodes,
                       "conflicts": sorted(edges, key=lambda row: (-Decimal(row["delta"]), row["a"], row["b"])),
                       "components": clusters})
    return {"schema": "ace.institute.controversy-map.v1", "plan_sha256": expected,
            "register_sha256": identity(registry), "held_rows": held, "scopes": result}


if __name__ == "__main__":
    raise SystemExit(cli(map_controversy, __doc__, rooted=True))
