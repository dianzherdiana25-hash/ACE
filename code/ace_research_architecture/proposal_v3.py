"""R3-V3 exploratory cost-aware proposal mechanism and rejection accounting.

Public synthetic exploratory experiment; no code generation/execution, no live ACE change.
Requires only the immutable R3-v1 typed graph interpreter in study.py.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import random
import statistics
from . import study as v1

WORK_CAP = 9000
MAX_SCORED = 240
MAX_PROPOSALS = 750
BEAM = 16
SHORTLIST = 12
PER_DEPTH = 4
PENALTY = 0.015
CONFIRM_TASKS = (
    'v2_chain_xor', 'v2_fanout', 'v2_branch_and', 'v2_deep_mixed',
    'v2_five_xor', 'v2_nested_or',
)
DEV_TASKS = v1.DEV_TASKS
ARMS = ('config', 'random', 'greedy', 'neutral', 'neutral_coverage', 'cost_aware', 'cost_aware_compact')


def truth(task, x):
    a, b, c, d, e = x
    if task in v1.DEV_TASKS:
        return v1.target(task, x)
    targets = {
        'v2_chain_xor': ((a ^ e) & (b ^ c)) | d,
        'v2_fanout': ((a & b) | (b & c)) ^ (d & e),
        'v2_branch_and': ((a | b) ^ c) & (d ^ e),
        'v2_deep_mixed': (a | (b & c)) & (d ^ e),
        'v2_five_xor': a ^ b ^ c ^ d ^ e,
        'v2_nested_or': ((a & b) ^ (c | d)) & e,
    }
    return int(targets[task])


def keyed_rng(arm, task, seed):
    digest = sha256(f'R3-V2:{arm}:{task}:{seed}'.encode()).digest()
    return random.Random(int.from_bytes(digest[:8], 'big'))


def mutate_tether(graph, rng):
    # Grow from the currently selected output to compose partial programs.
    if len(graph.gates) < v1.MAX_GATES and rng.random() < 0.65:
        i = v1.N_INPUTS + len(graph.gates)
        second = rng.randrange(i)
        left, right = (graph.output, second) if rng.randrange(2) else (second, graph.output)
        return v1.Graph(graph.gates + (v1.Gate(rng.choice(v1.OPS), left, right),), i)
    return v1.mutate(graph, rng)


def score(graph, loss):
    return (loss + PENALTY * len(graph.gates), len(graph.gates), graph.canonical())


def make_shortlist(measured, coverage):
    ranked = sorted(measured, key=lambda g: score(g, measured[g]))
    if not coverage:
        return ranked[:SHORTLIST]
    # Explicitly represent neutral/deeper candidates at validation, while
    # never consulting test outcomes or allowing more validation evaluations.
    by_depth = defaultdict(list)
    for graph in ranked:
        by_depth[len(graph.gates)].append(graph)
    selected = []
    for depth in range(v1.MAX_GATES + 1):
        selected.extend(by_depth[depth][:PER_DEPTH])
    selected = sorted(selected, key=lambda g: score(g, measured[g]))
    if len(selected) > SHORTLIST:
        # Depth-aware round robin, not global truncation.
        selected = []
        for j in range(PER_DEPTH):
            for depth in range(v1.MAX_GATES + 1):
                if len(by_depth[depth]) > j and len(selected) < SHORTLIST:
                    selected.append(by_depth[depth][j])
    return selected


def output_live_normal_form(graph):
    """Prune unreachable gates and sort operands of commutative Boolean ops."""
    graph.validate()
    live = set()
    worklist = [graph.output]
    while worklist:
        ref = worklist.pop()
        if ref >= v1.N_INPUTS:
            idx = ref - v1.N_INPUTS
            if idx not in live:
                live.add(idx)
                g = graph.gates[idx]
                worklist.extend((g.a, g.b))
    mapping = {v1.N_INPUTS + i: v1.N_INPUTS + j for j, i in enumerate(sorted(live))}
    remap = lambda ref: mapping.get(ref, ref)
    gates = []
    for i in sorted(live):
        g = graph.gates[i]
        a, b = sorted((remap(g.a), remap(g.b)))
        gates.append(v1.Gate(g.op, a, b))
    out = v1.Graph(tuple(gates), remap(graph.output))
    out.validate()
    return out


def affordable_random_graph(rng, affordable):
    """Draw one valid bounded graph with output depending on its last gate."""
    if affordable == 0:
        return v1.Graph((), rng.randrange(v1.N_INPUTS))
    n = rng.randrange(1, min(affordable, v1.MAX_GATES) + 1)
    gs = tuple(v1.Gate(rng.choice(v1.OPS), rng.randrange(v1.N_INPUTS + i), rng.randrange(v1.N_INPUTS + i)) for i in range(n))
    return v1.Graph(gs, v1.N_INPUTS + n - 1)


def run_case(arm, task, seed):
    if arm not in ARMS or seed < 0:
        raise ValueError('bad arm or seed')
    train, valid, holdout = v1.samples(task, seed)
    rng = keyed_rng(arm, task, seed)
    measured, signatures = {}, {}
    work, proposals = 0, 0
    rejection = {"duplicate": 0, "candidate_cap": 0, "work_cap": 0}
    eligible_gates = 0
    observed_work_rejection_gates = 0
    # Fixed reserve protects validation and test no matter which graph wins.
    reserve = (SHORTLIST * len(valid) + len(holdout)) * v1.MAX_GATES
    if WORK_CAP <= reserve:
        raise ValueError('invalid resource cap')

    def eval_split(graph, xs):
        nonlocal work
        graph.validate()
        cost = len(graph.gates) * len(xs)
        if work + cost > WORK_CAP:
            raise RuntimeError('work budget violated')
        ys = tuple(graph.predict(x)[0] for x in xs)
        work += cost
        return sum(y != truth(task, x) for y, x in zip(ys, xs)) / len(xs), ys

    def admit(graph):
        nonlocal proposals, eligible_gates, observed_work_rejection_gates
        proposals += 1
        graph.validate()
        if arm == "cost_aware_compact":
            graph = output_live_normal_form(graph)
        if graph in measured:
            rejection["duplicate"] += 1
            return False
        if len(measured) >= MAX_SCORED:
            rejection["candidate_cap"] += 1
            return False
        if work + len(graph.gates) * len(train) + reserve > WORK_CAP:
            rejection["work_cap"] += 1
            observed_work_rejection_gates += len(graph.gates)
            return False
        measured[graph], signatures[graph] = eval_split(graph, train)
        eligible_gates += len(graph.gates)
        return True

    if arm == 'config':
        for graph in v1.config_catalog():
            admit(graph)
    elif arm == 'random':
        while len(measured) < MAX_SCORED and proposals < MAX_PROPOSALS:
            admit(v1.draw_graph(rng))
    else:
        for graph in v1.first_stage():
            admit(graph)
        while len(measured) < MAX_SCORED and proposals < MAX_PROPOSALS:
            if arm == 'greedy':
                parents = []
                seen = set()
                for graph in sorted(measured, key=lambda g: score(g, measured[g])):
                    sig = signatures[graph]
                    if sig not in seen:
                        parents.append(graph)
                        seen.add(sig)
                    if len(parents) >= BEAM:
                        break
                parent = rng.choice(parents)
                mutant = v1.mutate(parent, rng)
            else:
                # Keep intermediate depth-specific parents, even without
                # immediate accuracy improvement (neutral stepping stones).
                by_depth = defaultdict(list)
                for graph in sorted(measured, key=lambda g: score(g, measured[g])):
                    items = by_depth[len(graph.gates)]
                    if len(items) < BEAM and signatures[graph] not in {signatures[v] for v in items}:
                        items.append(graph)
                available = sorted(by_depth)
                requested = (proposals // 2) % (v1.MAX_GATES + 1)
                depth = min(available, key=lambda d: (abs(d - requested), d))
                parent = rng.choice(by_depth[depth])
                mutant = mutate_tether(parent, rng)
                if arm in ('cost_aware', 'cost_aware_compact'):
                    affordable = min(v1.MAX_GATES, (WORK_CAP - work - reserve) // len(train))
                    if affordable <= 0:
                        break  # No new nonzero-gate candidate can be scored.
                    # Deterministic bounded candidate generation rather than
                    # repeatedly proposing graphs too costly to score.
                    if proposals % 4 == 0:
                        mutant = affordable_random_graph(rng, affordable)
                    elif len(mutant.gates) > affordable:
                        # Truncate the proposal into the admissible depth range.
                        gs = mutant.gates[:affordable]
                        mutant = v1.Graph(tuple(gs), v1.N_INPUTS + len(gs) - 1)
            admit(mutant)

    shortlist = make_shortlist(measured, arm in ('neutral_coverage','cost_aware','cost_aware_compact'))
    validation = []
    for g in shortlist:
        valerr, _ = eval_split(g, valid)
        validation.append((valerr + PENALTY * len(g.gates), valerr, len(g.gates), g.canonical(), g))
    validation.sort(key=lambda t: t[:-1])
    winner = validation[0][-1]
    testerr, _ = eval_split(winner, holdout)
    return {
        'task': task, 'seed': seed, 'arm': arm,
        'test_accuracy': round(1 - testerr, 12),
        'train_accuracy': round(1 - measured[winner], 12),
        'validation_accuracy': round(1 - validation[0][1], 12),
        'selected': winner.as_json(),
        'candidate_count': len(measured), 'proposals': proposals,
        'rejection': rejection, 'admitted_gate_total': eligible_gates,
        'work_rejected_gate_total': observed_work_rejection_gates,
        'validation_count': len(shortlist), 'gate_work': work,
        'pool_sha256': sha256(json.dumps([g.as_json() for g in sorted(measured, key=lambda g:g.canonical())],sort_keys=True).encode()).hexdigest(),
    }


def summarize(records):
    summary = {}
    for arm in ARMS:
        rows = [r for r in records if r['arm'] == arm]
        summary[arm] = {
            'n': len(rows),
            'mean_test_accuracy': round(statistics.mean(r['test_accuracy'] for r in rows), 6),
            'exact_solutions': sum(r['test_accuracy'] == 1.0 for r in rows),
            'gate_work': sum(r['gate_work'] for r in rows),
            'candidates': sum(r['candidate_count'] for r in rows),
            'mean_selected_gates': round(statistics.mean(len(r['selected']['gates']) for r in rows), 4),
        }
    return summary


def run_bank(tasks, seeds=range(4)):
    records = []
    for task in tasks:
        for seed in seeds:
            for arm in ARMS:
                records.append(run_case(arm, task, seed))
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--seeds', default=3, type=int)
    parser.add_argument('--bank', required=True, choices=['development', 'new_public_tasks'])
    args = parser.parse_args()
    if not 1 <= args.seeds <= 12:
        parser.error('seeds outside 1..12')
    tasks = DEV_TASKS if args.bank == 'development' else CONFIRM_TASKS
    rows = run_bank(tasks, range(args.seeds))
    bank = {'summary': summarize(rows), 'records': rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bank, indent=2, sort_keys=True) + '\n')
    print(json.dumps(bank['summary'], indent=2))


if __name__ == '__main__':
    main()
