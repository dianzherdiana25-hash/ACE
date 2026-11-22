"""Siapkan alokasi eksperimen tertutup yang dapat diulang, dengan blok dan kriteria ukur."""
from collections import defaultdict, Counter
from hashlib import sha256
from random import Random

from ._contracts import ResearchError, anchor, cli, identifier, identity, integer, items, number, obj, schema, text


def _preflight(plan):
    names = {}
    for row in items(plan["arms"], 8, 2):
        obj(row, ("id", "procedure_ref", "is_control"))
        key = identifier(row["id"], "Lengan")
        if key in names or type(row["is_control"]) is not bool:
            raise ResearchError("Lengan ganda atau penanda kontrol tidak sah.")
        names[key] = {"procedure_ref": text(row["procedure_ref"], "Pointer prosedur"), "is_control": row["is_control"]}
    if sum(item["is_control"] for item in names.values()) != 1:
        raise ResearchError("Gunakan satu lengan kontrol.")
    parameters = obj(plan["measurement"], ("outcome", "effect_direction", "minimum_effect", "stop_rule", "evaluator_ref"))
    effect = number(parameters["minimum_effect"], "Efek minimum")
    if effect <= 0 or parameters["effect_direction"] not in ("higher", "lower"):
        raise ResearchError("Efek absolut positif dan arah harus dinyatakan.")
    text(parameters["outcome"], "Hasil yang akan diukur")
    text(parameters["stop_rule"], "Kondisi berhenti")
    text(parameters["evaluator_ref"], "Pointer evaluator")
    return names


def design_experiment(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.institute.experiment-plan.v1", ("question", "seed", "arms", "units", "measurement", "min_per_arm_by_block"))
    question = text(plan["question"], "Pertanyaan eksperimen")
    arms = _preflight(plan)
    minimum = integer(plan["min_per_arm_by_block"], "Observasi minimum per blok", 1, 300)
    random_seed = integer(plan["seed"], "Seed alokasi", 0, 2**63 - 1)
    blocks = defaultdict(list)
    units = set()
    for row in items(plan["units"], 3000, 2):
        obj(row, ("id", "block", "source_ref"))
        key = identifier(row["id"], "Unit")
        block = identifier(row["block"], "Blok")
        if key in units:
            raise ResearchError("Unit ganda pada satu atau beberapa blok.")
        units.add(key)
        blocks[block].append({"unit": key, "source_ref": text(row["source_ref"], "Pointer unit")})
    assignments = []
    deferred = []
    counts = Counter()
    for label, block in sorted(blocks.items()):
        if len(block) < minimum * len(arms):
            deferred.append({"block": label, "reason": "insufficient_units", "units": sorted(row["unit"] for row in block),
                             "available": len(block), "required": minimum * len(arms)})
            continue
        seed = int.from_bytes(sha256(f"{random_seed}:{label}".encode()).digest(), "big")
        random = Random(seed)
        block.sort(key=lambda row: row["unit"])
        random.shuffle(block)
        order = sorted(arms)
        random.shuffle(order)
        local = Counter()
        for index, row in enumerate(block):
            arm = order[index % len(order)]
            assignments.append({**row, "block": label, "arm": arm})
            local[arm] += 1
        counts.update(local)
    return {"schema": "ace.institute.experiment-design.v1", "plan_sha256": expected, "question": question,
            "state": "draft_allocation", "design": "blocked_seeded_balanced_randomization", "arms": arms,
            "measurement": plan["measurement"], "arm_counts": dict(sorted(counts.items())), "deferred_blocks": deferred,
            "assignments": assignments, "assignment_sha256": identity(assignments)}


if __name__ == "__main__":
    raise SystemExit(cli(design_experiment, __doc__))
