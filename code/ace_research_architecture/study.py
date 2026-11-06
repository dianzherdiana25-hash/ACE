"""R3 research-only binary dataflow architecture evolution.

Candidate graphs are immutable typed data. No candidate source code is executed.
All randomness is seeded and all search limits explicit. Standard library only.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
from itertools import product
import json
import random
import statistics
import time
from pathlib import Path

N_INPUTS = 5
OPS = ("AND", "OR", "XOR")
MAX_GATES = 5
BUDGET = 240
BEAM = 16
SHORTLIST = 12
LAMBDA = 0.015
TRAIN_N, VALID_N = 18, 7  # remaining 7 samples form a sealed-in-run test set


@dataclass(frozen=True)
class Gate:
    op: str
    a: int
    b: int


@dataclass(frozen=True)
class Graph:
    gates: tuple[Gate, ...]
    output: int

    def validate(self) -> None:
        if len(self.gates) > MAX_GATES or type(self.output) is not int or not (0 <= self.output < N_INPUTS + len(self.gates)):
            raise ValueError("invalid graph size or output")
        for i, g in enumerate(self.gates):
            if g.op not in OPS or type(g.a) is not int or type(g.b) is not int or not (0 <= g.a < N_INPUTS + i) or not (0 <= g.b < N_INPUTS + i):
                raise ValueError("illegal gate or non-causal edge")

    def predict(self, x: tuple[int, ...]) -> tuple[int, int]:
        self.validate()
        if len(x) != N_INPUTS or any(type(v) is not int or v not in (0, 1) for v in x):
            raise ValueError("invalid binary input")
        values = list(x)
        for gate in self.gates:
            a, b = values[gate.a], values[gate.b]
            values.append((a & b) if gate.op == "AND" else ((a | b) if gate.op == "OR" else (a ^ b)))
        return values[self.output], len(self.gates)

    def canonical(self) -> tuple:
        return (tuple((g.op, g.a, g.b) for g in self.gates), self.output)

    def as_json(self):
        return {"gates": [{"op": g.op, "a": g.a, "b": g.b} for g in self.gates], "output": self.output}


def samples(task: str, seed: int):
    all_inputs = list(product((0, 1), repeat=N_INPUTS))
    rng = random.Random(int.from_bytes(sha256(f"R3-split:{task}:{seed}".encode()).digest()[:8], "big"))
    rng.shuffle(all_inputs)
    return all_inputs[:TRAIN_N], all_inputs[TRAIN_N:TRAIN_N + VALID_N], all_inputs[TRAIN_N + VALID_N:]


def target(task: str, x: tuple[int, ...]) -> int:
    a, b, c, d, e = x
    tasks = {
        # Development bank: named only to identify public synthetic mechanisms.
        "dev_masked_xor": lambda: (a ^ b) & c,
        "dev_double_or": lambda: (a | b) & (c | d),
        "dev_pair_xors": lambda: (a ^ b) & (c ^ d),
        "dev_xor3": lambda: a ^ b ^ c,
        "dev_majority": lambda: (a & b) | (a & c) | (b & c),
        "dev_conditional": lambda: (a & b) | (c & d),
        # Held-out *task structures*; they are never used to tune the algorithm here.
        "confirm_cross_or": lambda: (a ^ c) | (b ^ d),
        "confirm_mixed_xor": lambda: (a | d) ^ (b & c),
        "confirm_xor4": lambda: a ^ b ^ c ^ d,
        "confirm_nested": lambda: ((a & b) ^ c) & d,
        "confirm_nuisance": lambda: ((a & e) | b) ^ d,
        "confirm_masked_or": lambda: (a & (b | c)) | (d & e),
    }
    return int(tasks[task]())


DEV_TASKS = ("dev_masked_xor", "dev_double_or", "dev_pair_xors", "dev_xor3", "dev_majority", "dev_conditional")
CONFIRM_TASKS = ("confirm_cross_or", "confirm_mixed_xor", "confirm_xor4", "confirm_nested", "confirm_nuisance", "confirm_masked_or")


class Meter:
    def __init__(self):
        self.gate_evaluations = 0
        self.candidate_evaluations = 0
        self.proposal_attempts = 0

    def error(self, graph: Graph, points, task: str, with_signature=False):
        mismatches = 0
        signature = []
        for x in points:
            pred, gates = graph.predict(x)
            self.gate_evaluations += gates
            signature.append(pred)
            mismatches += (pred != target(task, x))
        error = mismatches / len(points)
        return (error, tuple(signature)) if with_signature else error


def draw_graph(rng: random.Random) -> Graph:
    size = rng.randint(0, MAX_GATES)
    gs = []
    for i in range(size):
        gs.append(Gate(rng.choice(OPS), rng.randrange(N_INPUTS + i), rng.randrange(N_INPUTS + i)))
    return Graph(tuple(gs), rng.randrange(N_INPUTS + size))


def mutate(graph: Graph, rng: random.Random) -> Graph:
    gs = list(graph.gates)
    possible = ["output"]
    if gs:
        possible += ["rewire", "operator", "delete"]
    if len(gs) < MAX_GATES:
        possible += ["add", "add", "add"]
    move = rng.choice(possible)
    if move == "add":
        ix = N_INPUTS + len(gs)
        gs.append(Gate(rng.choice(OPS), rng.randrange(ix), rng.randrange(ix)))
        return Graph(tuple(gs), ix)
    if move == "delete":
        gs.pop()
        return Graph(tuple(gs), N_INPUTS + len(gs) - 1 if gs else rng.randrange(N_INPUTS))
    if move == "output":
        return Graph(tuple(gs), rng.randrange(N_INPUTS + len(gs)))
    i = rng.randrange(len(gs))
    old = gs[i]
    if move == "operator":
        gs[i] = Gate(rng.choice([op for op in OPS if op != old.op]), old.a, old.b)
    else:
        if rng.randrange(2):
            gs[i] = Gate(old.op, rng.randrange(N_INPUTS + i), old.b)
        else:
            gs[i] = Gate(old.op, old.a, rng.randrange(N_INPUTS + i))
    return Graph(tuple(gs), graph.output)


def fixed_graph():
    return Graph((Gate("XOR", 0, 1), Gate("XOR", 2, 3), Gate("AND", 5, 6)), 7)


def config_catalog():
    # Fixed dataflow edges. Only gate operation labels may change.
    for first, second, third in product(OPS, repeat=3):
        yield Graph((Gate(first, 0, 1), Gate(second, 2, 3), Gate(third, 5, 6)), 7)


def first_stage():
    for i in range(N_INPUTS):
        yield Graph((), i)
    for a in range(N_INPUTS):
        for b in range(a, N_INPUTS):
            for op in OPS:
                yield Graph((Gate(op, a, b),), N_INPUTS)


def score_key(g: Graph, measured):
    return (measured[g] + LAMBDA * len(g.gates), len(g.gates), g.canonical())


def propose_arm(arm: str, task: str, seed: int, meter: Meter):
    rng = random.Random(int.from_bytes(sha256(f"R3-search:{arm}:{task}:{seed}".encode()).digest()[:8], "big"))
    train, valid, test = samples(task, seed)
    results = {}
    signatures = {}

    def admit(graph):
        meter.proposal_attempts += 1
        if graph in results or len(results) >= BUDGET:
            return
        graph.validate()
        results[graph], signatures[graph] = meter.error(graph, train, task, with_signature=True)
        meter.candidate_evaluations += 1

    if arm == "fixed":
        admit(fixed_graph())
    elif arm == "config":
        for graph in config_catalog():
            admit(graph)
    elif arm == "random":
        while len(results) < BUDGET and meter.proposal_attempts < BUDGET * 100:
            admit(draw_graph(rng))
    elif arm == "evolve":
        for graph in first_stage():
            admit(graph)
        while len(results) < BUDGET and meter.proposal_attempts < BUDGET * 100:
            # Evidence-guided graph mutation, phenotype-diverse finite beam.
            beam = []
            seen_signatures = set()
            for graph in sorted(results, key=lambda g: score_key(g, results)):
                signature = signatures[graph]
                if signature not in seen_signatures:
                    seen_signatures.add(signature)
                    beam.append(graph)
                    if len(beam) >= BEAM:
                        break
            parent = rng.choice(beam)
            admit(mutate(parent, rng))
    else:
        raise ValueError("unknown arm")

    # Freeze shortlist using training only; validation chooses final graph;
    # test is evaluated exactly once on the frozen selected graph.
    shortlist = sorted(results, key=lambda g: score_key(g, results))[:SHORTLIST]
    ranked = []
    for g in shortlist:
        v_error = meter.error(g, valid, task)
        ranked.append((v_error + LAMBDA * len(g.gates), v_error, len(g.gates), g.canonical(), g))
    ranked.sort(key=lambda t: t[:4])
    selected = ranked[0][-1]
    train_error = results[selected]
    valid_error = ranked[0][1]
    test_error = meter.error(selected, test, task)
    return {
        "arm": arm, "task": task, "seed": seed, "train_error": train_error,
        "validation_error": valid_error, "test_error": test_error,
        "test_correct": int(test_error == 0), "selected": selected.as_json(),
        "candidate_evaluations": meter.candidate_evaluations,
        "proposal_attempts": meter.proposal_attempts,
        "gate_evaluations": meter.gate_evaluations,
        "train_points": len(train), "validation_points": len(valid), "test_points": len(test),
        "candidate_pool_sha256": sha256(json.dumps([g.as_json() for g in sorted(results, key=lambda g: g.canonical())], sort_keys=True).encode()).hexdigest()
    }


def run_bank(tasks, seeds=tuple(range(6))):
    records = []
    for task in tasks:
        for seed in seeds:
            for arm in ("fixed", "config", "random", "evolve"):
                meter = Meter()
                records.append(propose_arm(arm, task, seed, meter))
    return records


def summarize(records):
    byarm = {}
    for arm in ("fixed", "config", "random", "evolve"):
        items = [r for r in records if r["arm"] == arm]
        byarm[arm] = {
            "n_cases": len(items),
            "mean_test_accuracy": round(1 - statistics.mean(r["test_error"] for r in items), 6),
            "exact_test_solutions": sum(r["test_correct"] for r in items),
            "candidate_evaluations": sum(r["candidate_evaluations"] for r in items),
            "gate_evaluations": sum(r["gate_evaluations"] for r in items),
            "mean_gates_selected": round(statistics.mean(len(r["selected"]["gates"]) for r in items), 4),
        }
    # Paired by task and split, descriptive only: no population generality claim.
    a = {(r["task"], r["seed"]): r for r in records if r["arm"] == "evolve"}
    b = {(r["task"], r["seed"]): r for r in records if r["arm"] == "random"}
    diffs = [b[k]["test_error"] - a[k]["test_error"] for k in sorted(a)]
    return {"arms": byarm, "evolve_minus_random_paired_accuracy": round(statistics.mean(diffs), 6), "evolve_wins": sum(d > 0 for d in diffs), "ties": sum(d == 0 for d in diffs), "evolve_losses": sum(d < 0 for d in diffs)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seeds", type=int, default=6)
    args = parser.parse_args()
    if not 1 <= args.seeds <= 32:
        parser.error("--seeds must be in 1..32")
    start = time.perf_counter()
    development = run_bank(DEV_TASKS, range(args.seeds))
    # Confirmatory bank is evaluated only after the algorithm is fixed. Its
    # structure is nevertheless public and not independently concealed.
    confirmation = run_bank(CONFIRM_TASKS, range(args.seeds))
    artifact = {
        "protocol": {"version": "R3-V1", "inputs": N_INPUTS, "max_gates": MAX_GATES,
                     "max_training_candidates_per_case": BUDGET, "max_proposals_per_case": BUDGET * 100,
                     "beam": BEAM, "validation_shortlist": SHORTLIST, "complexity_penalty": LAMBDA,
                     "split": [TRAIN_N, VALID_N, 2 ** N_INPUTS - TRAIN_N - VALID_N],
                     "seeds": args.seeds,
                     "closed_operators": OPS,
                     "selection": "training shortlist => validation winner => final input holdout"},
        "development": {"summary": summarize(development), "records": development},
        "confirmation": {"summary": summarize(confirmation), "records": confirmation},
        "wall_seconds": round(time.perf_counter() - start, 3),
        "limitations": "Public author-visible synthetic tasks, 7 holdout inputs per case, no independent sealed evaluator, no OS sandbox, no statistical generality claim",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"development": artifact["development"]["summary"],
                      "confirmation": artifact["confirmation"]["summary"],
                      "wall_seconds": artifact["wall_seconds"]}, indent=2))


if __name__ == "__main__":
    main()
