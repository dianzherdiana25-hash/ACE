"""Public order-sensitive counterexamples to E1.3's counter transition basis."""

import json
from pathlib import Path

from ..contract import canonical_json, input_value
from ..dsl import Fuel, graph_costs, symbol_event
from ..extension import _definitions
from ..public_bank import Probe
from ..patterns import pattern_ast
from .bank import Episode, _chain
from .locked_runner import (
    StudyEpisode, bank_digest, digest, evaluator_digest, make_plan, run_locked,
)
from .selection_budget import CPU_US, WALL_US

MODE = "public_dry_run"
PROTOCOL = b"ACE E1.3 public order challenge v1; four balanced pairs per family; nine policies"


def _symbols(events, start, step):
    values = [start]
    for event in events:
        values.append(values[-1] + (step, 0, -step)[event])
    return values


def _graph(events, label, cost):
    labels = [label]
    for event in events:
        labels.append(labels[-1] if event == 1 else (labels[-1] + 1) % 4)
    return _chain(labels, [cost] * len(labels))


def _answer(family, events, value, target):
    hits = [int(events[i + 1 - len(target):i + 1] == target) if i + 1 >= len(target) else 0
            for i in range(len(events))]
    if family == "S":
        return tuple(hits)
    return sum(edge[3] for edge in value["edges"]) if any(hits) else None


def _fixture(family):
    if family == "S":
        target, rival, neutral, encode = (0, 1, 2), (1, 0, 2), 1, _symbols
        demo_settings = ((4, 1), (6, 2))
        probe_settings = ((8, 1), (9, 2), (10, 1), (11, 2))
    else:
        target, rival, neutral, encode = (1, 1, 2), (1, 2, 1), 2, _graph
        demo_settings = ((0, 1), (1, 2))
        probe_settings = ((0, 3), (1, 4), (2, 3), (3, 4))
    demos = [{"input": (value := encode(word, *setting)),
              "output": _answer(family, word, value, target)}
             for word, setting in zip((target, rival), demo_settings, strict=True)]
    probes = []
    for index, setting in enumerate(probe_settings):
        prefix = () if index < 2 else (neutral,) * (index + 2)
        for word in (target, rival):
            events = prefix + word
            value = encode(events, *setting)
            probes.append(Probe(canonical_json(value), _answer(family, events, value, target)))
    fit = canonical_json({"version": 1, "task_id": "1" * 32 if family == "S" else "2" * 32,
                          "family": family, "seed": 0, "fuel": 75_000,
                          "source": demos, "target": demos})
    episode = Episode(family, "related", f"{family}-public-source", f"{family}-public-order",
                      fit, tuple(probes[:4]), tuple(probes[4:]))
    return StudyEpisode(f"{family}-public-block", f"{family}-episode", episode,
                        (pattern_ast(family, target), pattern_ast(family, rival)))


def _readout_key(family, table, value):
    parsed = input_value(family, value)
    if family == "G":
        return tuple(graph_costs(parsed, table, Fuel(10_000)))
    events = [symbol_event(left, right) for left, right in zip(parsed, parsed[1:])]
    state = 0
    for event in events[:-1]:
        state = table[state][event]
    return state, events[-1]


def order_certificate(item):
    """Check every C_EXTEND transition and all possible readouts on paired probes."""
    fixture = item.fixture
    family = fixture.family
    options = _definitions(family, 8)
    probes = fixture.in_distribution + fixture.extrapolation
    pairs = list(zip(probes[::2], probes[1::2], strict=True))
    counts = []
    for left, right in pairs:
        if family == "S":
            assert left.expected[-1] != right.expected[-1]
        else:
            assert left.expected != right.expected
        a, b = json.loads(left.input), json.loads(right.input)
        counts.append(sum(_readout_key(family, option.table, a) != _readout_key(family, option.table, b)
                          for option in options))
    return {"family": family, "transition_definitions": len(options),
            "paired_witnesses": len(pairs), "distinguishing_definitions_per_pair": counts,
            "max_correct_on_balanced_pairs": len(pairs) if not any(counts) else None}


def public_run(path):
    episodes = tuple(_fixture(family) for family in ("S", "G"))
    oracle_path = Path(__file__).resolve()
    plan = make_plan(episodes, oracle_path.read_bytes(), PROTOCOL, mode=MODE)
    audit = canonical_json({
        "mode": MODE, "bank_sha256": bank_digest(episodes), "oracle_sha256": plan.oracle_sha256,
        **dict.fromkeys(("integrity", "novelty", "ambiguity", "independence", "custody"), "pass"),
    })
    lock = canonical_json({
        "version": 1, "mode": MODE, "plan_sha256": plan.sha256,
        "evaluator_sha256": evaluator_digest(), "audit_sha256": digest(audit),
        "cpu_us": len(plan.arms) * CPU_US + CPU_US, "wall_us": len(plan.arms) * WALL_US + WALL_US,
        "overhead_cpu_us": CPU_US, "overhead_wall_us": WALL_US,
    })
    rows = run_locked(path, episodes, oracle_path, PROTOCOL, audit, lock, digest(lock), mode=MODE)
    return {"mode": MODE, "scope": "public stress cases; source repeats target demos to isolate expressivity",
            "plan_sha256": plan.sha256, "lock_sha256": digest(lock),
            "candidate_sha256": plan.candidate_sha256, "bank_sha256": plan.bank_sha256,
            "certificates": [order_certificate(item) for item in episodes], "arms": len(rows),
            "by_policy": {
                policy: {family: {
                    "correct": sum(r["correct"] for r in rows if r["policy"] == policy and r["family"] == family),
                    "total": sum(r["total"] for r in rows if r["policy"] == policy and r["family"] == family),
                } for family in ("S", "G")} for policy in sorted({r["policy"] for r in rows})
            },
            "max_observed_cpu_us": max(r["total_cpu_us"] for r in rows if r["status"] == "scored"),
            "max_observed_wall_us": max(r["wall_us"] for r in rows if r["status"] == "scored"),
            "reference_profile": {
                "arms": sum(r["policy"] == "structured_oracle" for r in rows),
                "max_cpu_us": max(r["total_cpu_us"] for r in rows
                                  if r["policy"] == "structured_oracle" and r["status"] == "scored"),
                "max_wall_us": max(r["wall_us"] for r in rows
                                   if r["policy"] == "structured_oracle" and r["status"] == "scored"),
            },
            "score_caps": sum(r.get("cap_reached", False) for r in rows),
            "candidate_failures": sum(r["status"] == "candidate_failure" for r in rows)}
