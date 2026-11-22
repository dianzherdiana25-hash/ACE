"""Tandai miskonsepsi berulang hanya dari receipt yang cocok dan tugas berbeda."""
from collections import defaultdict

from ._contracts import (ProductionError, anchor, cli, day, decode, identifier,
                         integer, items, obj, schema, source_bytes, text)


def track(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.misconception-plan.v1", ("as_of", "window_days", "minimum_unique_tasks", "map", "grades"))
    date = day(plan["as_of"])
    window = integer(plan["window_days"], "Jendela pola", 1, 365)
    minimum = integer(plan["minimum_unique_tasks"], "Tugas berbeda", 2, 25)
    rules = {}
    for value in items(plan["map"], 160, 1):
        obj(value, ("criterion", "id", "topic", "source_ref"))
        criterion = identifier(value["criterion"], "Kriteria")
        if criterion in rules:
            raise ProductionError("Kriteria pemicu miskonsepsi ganda.")
        rules[criterion] = {"id": identifier(value["id"], "Miskonsepsi"),
                            "topic": identifier(value["topic"], "Topik"),
                            "source_ref": text(value["source_ref"], "Pointer miskonsepsi")}
    observations = defaultdict(list)
    ignored = []
    used = set()
    for row in items(plan["grades"], 250):
        obj(row, ("date", "path", "sha256"))
        stamp = day(row["date"])
        if row["sha256"] in used or stamp > date:
            raise ProductionError("Receipt berulang atau bertanggal masa depan.")
        used.add(row["sha256"])
        if (date - stamp).days > window:
            ignored.append(row["sha256"])
            continue
        receipt = decode(source_bytes(root, row["path"], row["sha256"], 200000))
        schema(receipt, "ace.teaching.open-grade.v1", ("plan_sha256", "exercise", "response_source", "method",
                                                      "score_bp", "criteria", "status"))
        for record in items(receipt["criteria"], 65):
            label = identifier(record["id"], "Kriteria grade")
            if label in rules and record["status"] == "contradiction" and record["opposed_by"]:
                rule = rules[label]
                observations[rule["id"], rule["topic"]].append({
                    "exercise": identifier(receipt["exercise"], "Latihan"),
                    "criterion": label, "reference": row, "rule_source_ref": rule["source_ref"],
                    "response_source": receipt["response_source"]})
    categories = []
    for (name, topic), evidence in sorted(observations.items()):
        tasks = sorted({item["exercise"] for item in evidence})
        categories.append({"id": name, "topic": topic, "distinct_tasks": tasks,
                           "state": "recurring" if len(tasks) >= minimum else "insufficient_repetition", "evidence": evidence})
    return {"schema": "ace.teaching.misconceptions.v1", "plan_sha256": expected,
            "window_days": window, "patterns": categories, "old_receipts": ignored}


if __name__ == "__main__":
    raise SystemExit(cli(track, __doc__, rooted=True))
