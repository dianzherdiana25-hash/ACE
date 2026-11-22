"""Jawab pertanyaan terstruktur dari indeks topik yang merekam setiap sumber numerik."""
from collections import defaultdict
from decimal import Decimal

from ._contracts import ResearchError, anchor, cli, identifier, identity, integer, items, obj, schema, text, words
from ._evidence import dimension, reviewed


def query_topics(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.topic-query.v1", ("source_plan", "aliases", "query", "limit"))
    query = text(plan["query"], "Pertanyaan indeks")
    cap = integer(plan["limit"], "Ukuran hasil", 1, 50)
    registry, measurements, held = reviewed(plan["source_plan"], root)
    requested = words(query)
    lookups = defaultdict(set)
    for row in items(plan["aliases"], 300):
        obj(row, ("field", "value", "phrases", "source_ref"))
        field = row["field"]
        if field not in ("population", "outcome", "context"):
            raise ResearchError("Alias perlu field klaim yang dikenal.")
        key = identifier(row["value"], "Nilai indeks")
        pointer = text(row["source_ref"], "Pointer istilah")
        for phrase in items(row["phrases"], 20, 1):
            tokens = words(text(phrase, "Alias topik", 80))
            if tokens and tokens <= requested:
                lookups[field].add((key, pointer))
    indexes = {}
    for item in measurements:
        matched = []
        annotations = []
        for name, goal in item["dimensions"].items():
            tokens = words(goal.replace("_", " "))
            if tokens and tokens <= requested:
                matched.append(name)
            else:
                sources = sorted(pointer for key, pointer in lookups[name] if goal == key)
                if sources:
                    matched.append(name)
                    annotations.extend({"dimension": name, "source_ref": pointer} for pointer in sources)
        if "outcome" not in matched:
            continue
        key = (dimension(item["dimensions"]), item["unit"])
        group = indexes.setdefault(key, {"dimensions": item["dimensions"], "unit": item["unit"],
                                         "match_fields": sorted(matched), "alias_provenance": annotations, "evidence": []})
        group["evidence"].append({"value": item["estimate"], "interval": item["interval"], "sample_size": item["sample_size"],
                                  "source": item["source"], "score": item["source_score"]})
    ranked = sorted(indexes.values(), key=lambda item: (-len(item["match_fields"]), -len(item["evidence"]),
                                                        dimension(item["dimensions"]), item["unit"]))
    for item in ranked:
        item["evidence"].sort(key=lambda row: (-row["score"], row["source"]["path"], row["source"]["line"]))
        item["distinct_values"] = sorted({row["value"] for row in item["evidence"]}, key=Decimal)
    return {"schema": "ace.institute.topic-answer.v1", "plan_sha256": expected, "query_terms": sorted(requested),
            "source_register_sha256": identity(registry), "held_tables": held, "matching_contexts": len(ranked),
            "results": ranked[:cap], "status": "measurements_found" if ranked else "unknown"}


if __name__ == "__main__":
    raise SystemExit(cli(query_topics, __doc__, rooted=True))
