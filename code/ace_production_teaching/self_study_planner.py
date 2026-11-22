"""Rencanakan tiga puluh hari studi mandiri dengan verifikasi prasyarat dan jadwal ulang."""
from collections import defaultdict
from datetime import timedelta

from ._contracts import ProductionError, anchor, cli, day, identifier, identity, integer, items, schema
from .topic_map import graph


def plan_study(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.teaching.self-study-plan.v1", ("start", "start_material", "targets", "daily_minutes", "off_days", "review_gap"))
    first = day(plan["start"])
    topics = graph(plan["start_material"], identity(plan["start_material"]))
    cap = integer(plan["daily_minutes"], "Menit per hari", 1, 480)
    off = {integer(value, "Hari bebas", 1, 30) for value in items(plan["off_days"], 30)}
    gap = integer(plan["review_gap"], "Jeda review", 1, 14)
    requested = [identifier(value, "Topik target") for value in items(plan["targets"], 60, 1)]
    if len(set(requested)) != len(requested) or not set(requested) <= topics["topics"].keys():
        raise ProductionError("Target studi ganda atau belum terdaftar.")
    multiple = set(requested) | {item for key in requested for item in topics["topics"][key]["transitive_requires"]}
    ledger = defaultdict(list)
    available = {index: (0 if index in off else cap) for index in range(1, 31)}
    completion = {}
    missed = []
    pending_review = []
    for key in topics["order"]:
        if key not in multiple:
            continue
        record = topics["topics"][key]
        prerequisites = record["required"]
        if any(name not in completion for name in prerequisites):
            missed.append({"topic": key, "reason": "prerequisite_not_scheduled"})
            continue
        start = max([1, *[completion[name] + 1 for name in prerequisites]])
        minutes = record["duration_minutes"]
        if start > 30 or sum(available[number] for number in range(start, 31)) < minutes:
            missed.append({"topic": key, "reason": "not_enough_minutes"})
            continue
        for step in range(start, 31):
            duration = min(minutes, available[step])
            if not duration:
                continue
            available[step] -= duration
            minutes -= duration
            ledger[step].append({"topic": key, "kind": "study", "minutes": duration, "topic_source": record["source_ref"],
                                 "conditional_on_verified": prerequisites, "ends_topic_plan": not minutes})
            if not minutes:
                completion[key] = step
                pending_review.append((step + gap, key))
                break
    for due, key in sorted(pending_review):
        target = next((number for number in range(due, 31) if available[number] >= 5), None)
        if target is None:
            missed.append({"topic": key, "reason": "review_unscheduled", "wanted_day": due})
            continue
        available[target] -= 5
        ledger[target].append({"topic": key, "kind": "review", "minutes": 5, "conditional_on_verified": [key],
                               "topic_source": topics["topics"][key]["source_ref"]})
    return {"schema": "ace.teaching.self-study-draft.v1", "plan_sha256": expected,
            "target_topics": requested, "calendar": [{"day": index, "date": (first + timedelta(days=index - 1)).isoformat(),
                         "minutes_left": available[index], "actions": ledger[index]} for index in range(1, 31)],
            "held": missed, "status": "plan_only"}


if __name__ == "__main__":
    raise SystemExit(cli(plan_study, __doc__))
