"""R3-v4: controlled structural-edit credit assignment, research-only.

No generated source is executed. All candidate graphs are typed, bounded data.
The same public train/validation/test points are used across search arms;
holdout is consulted *only after* a validation winner is frozen.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from functools import lru_cache
from hashlib import sha256
from itertools import product
import json
import math
from pathlib import Path
import random
import statistics
from unittest.mock import patch

from . import study as core
from . import proposal_v3 as v3

ARMS = ('config', 'greedy', 'cost_aware', 'uniform_edits', 'credit_edits', 'credit_novelty')
DEVELOPMENT = v3.DEV_TASKS
# Fresh, procedurally generated circuit descriptions; independent seeds from the search RNG.
# Author-visible synthetic tasks, not independently concealed benchmarks.
NEW_TASKS = tuple(f'new_fork_{i}' for i in range(6))
# New family generated after freezing the original v4 results; no v4b tuning on its results.
CHAIN_TASKS = tuple(f'new_chain_{i}' for i in range(6))
ALL_NEW_TASKS = NEW_TASKS + CHAIN_TASKS
CANDIDATE_CAP, PROPOSAL_CAP, WORK_CAP = 240, 750, 9000
BEAM, SHORTLIST, PENALTY = 16, 12, 0.015
MOVES = ('add', 'delete', 'operator', 'rewire', 'output')


def _seed(s: str) -> int:
    return int.from_bytes(sha256(s.encode()).digest()[:8], 'big')


@lru_cache(maxsize=64)
def new_task_graph(task: str) -> core.Graph:
    if task not in ALL_NEW_TASKS:
        raise ValueError('unknown fresh task')
    rng = random.Random(_seed('R3-v4-target-graph:' + task))
    # Fork and chain families have distinct information-flow topologies.
    inputs = list(range(core.N_INPUTS))
    rng.shuffle(inputs)
    a, b, c, d, e = inputs
    ops = [rng.choice(core.OPS) for _ in range(4)]
    if task in CHAIN_TASKS:
        # Four dependent stages; all five inputs participate.
        gates = (core.Gate(ops[0], a, b),
                 core.Gate(ops[1], core.N_INPUTS, c),
                 core.Gate(ops[2], core.N_INPUTS + 1, d),
                 core.Gate(ops[3], core.N_INPUTS + 2, e))
    else:
        gates = (core.Gate(ops[0], a, b),
                 core.Gate(ops[1], c, d),
                 core.Gate(ops[2], core.N_INPUTS, core.N_INPUTS + 1),
                 core.Gate(ops[3], core.N_INPUTS + 2, e))
    graph = core.Graph(gates, core.N_INPUTS + 3)
    graph.validate()
    return graph


_ORIGINAL_TRUTH = v3.truth


def truth(task: str, x: tuple[int, ...]) -> int:
    if task in ALL_NEW_TASKS:
        return new_task_graph(task).predict(x)[0]
    return _ORIGINAL_TRUTH(task, x)


def seeded_rng(task: str, seed: int) -> random.Random:
    # Common RNG seed across the two edit-selection arms.
    return random.Random(_seed(f'R3-v4-policy:{task}:{seed}'))


def proposed_edit(parent: core.Graph, move: str, rng: random.Random) -> core.Graph:
    if move not in MOVES:
        raise ValueError('invalid mutation')
    gs = list(parent.gates)
    out = parent.output
    n = len(gs)
    if move == 'add':
        if n >= core.MAX_GATES:
            raise ValueError('gate cap')
        # Tether growth to the current output, creating useful compositional paths.
        limit = core.N_INPUTS + n
        other = rng.randrange(limit)
        a, b = (out, other) if rng.randrange(2) else (other, out)
        gs.append(core.Gate(rng.choice(core.OPS), a, b))
        out = limit
    elif move == 'delete':
        if not n:
            raise ValueError('no gate to delete')
        gs.pop()
        out = core.N_INPUTS + n - 2 if n > 1 else rng.randrange(core.N_INPUTS)
    elif move == 'operator':
        if not n:
            raise ValueError('no gate to relabel')
        i = rng.randrange(n)
        old = gs[i]
        gs[i] = core.Gate(rng.choice([op for op in core.OPS if op != old.op]), old.a, old.b)
    elif move == 'rewire':
        if not n:
            raise ValueError('no edge to rewire')
        i = rng.randrange(n)
        old = gs[i]
        a, b = (rng.randrange(core.N_INPUTS + i), old.b) if rng.randrange(2) else (old.a, rng.randrange(core.N_INPUTS + i))
        gs[i] = core.Gate(old.op, a, b)
    else:
        out = rng.randrange(core.N_INPUTS + n)
    graph = core.Graph(tuple(gs), out)
    graph.validate()
    return graph


def eligible_moves(parent: core.Graph, affordable_gates: int):
    moves = ['output']
    if parent.gates:
        moves.extend(('operator', 'rewire', 'delete'))
    if len(parent.gates) < min(core.MAX_GATES, affordable_gates):
        moves.append('add')
    return moves


def choose_move(arm, moves, counts, reward_sum, rng):
    if arm == 'uniform_edits':
        return rng.choice(moves)
    # Bandit credit = observed *counterfactual train-score improvement*
    # attributable to the structural edit, measured against its parent.
    # The UCB bonus prevents a single lucky mutation locking the policy.
    total = sum(counts.values())
    def ucb(op):
        if counts[op] == 0:
            return 2.0
        return reward_sum[op] / counts[op] + 0.12 * math.sqrt(math.log(total + 2) / counts[op])
    best = max(ucb(op) for op in moves)
    return rng.choice([op for op in moves if abs(ucb(op) - best) < 1e-12])


def _select_shortlist(measured):
    ordered = sorted(measured, key=lambda g: (measured[g] + PENALTY * len(g.gates), len(g.gates), g.canonical()))
    return ordered[:SHORTLIST]


def run_case(arm: str, task: str, seed: int, flip_holdout: bool = False):
    if arm not in ARMS or type(seed) is not int or seed < 0:
        raise ValueError('invalid arm/seed')
    if task not in DEVELOPMENT and task not in ALL_NEW_TASKS:
        raise ValueError('invalid task')
    if arm in ('config', 'greedy', 'cost_aware'):
        # Existing controls remain *unchanged*; a held-out label flip affects only
        # the result of the final test. This preserves their published behavior.
        train, valid, holdout = core.samples(task, seed)
        hset = set(holdout)
        def flipped_truth(t,x):
            y=truth(t,x)
            return 1-y if flip_holdout and t==task and x in hset else y
        with patch.object(v3, 'truth', side_effect=flipped_truth):
            base = v3.run_case(arm, task, seed)
        return {**base, 'credit': None, 'selected': base['selected'],
                'test_accuracy': base['test_accuracy']}

    train, valid, holdout = core.samples(task, seed)
    rng = seeded_rng(task, seed)
    measured, signature = {}, {}
    work = 0
    proposals = 0
    rejection = dict(duplicate=0, work_cap=0, candidate_cap=0)
    move_counts, reward_sum = defaultdict(int), defaultdict(float)
    move_admitted = defaultdict(int)
    reserve = (SHORTLIST * len(valid) + len(holdout)) * core.MAX_GATES

    def evaluate(g, xs, flip=False):
        nonlocal work
        cost = len(g.gates)*len(xs)
        if work + cost > WORK_CAP:
            raise RuntimeError('gate work exceeded')
        ys = tuple(g.predict(x)[0] for x in xs)
        work += cost
        return sum(y != (truth(task,x) ^ (int(flip))) for y,x in zip(ys,xs))/len(xs), ys

    def admit(graph):
        nonlocal proposals
        proposals += 1
        graph.validate()
        if graph in measured:
            rejection['duplicate'] += 1
            return False
        if len(measured) >= CANDIDATE_CAP:
            rejection['candidate_cap'] += 1
            return False
        if work + len(graph.gates)*len(train) + reserve > WORK_CAP:
            rejection['work_cap'] += 1
            return False
        measured[graph], signature[graph] = evaluate(graph, train)
        return True

    for g in core.first_stage():
        admit(g)
    while len(measured) < CANDIDATE_CAP and proposals < PROPOSAL_CAP:
        affordable = min(core.MAX_GATES, (WORK_CAP - work - reserve)//len(train))
        if affordable <= 0:
            break
        parents = []
        seen_sig = set()
        for g in sorted(measured, key=lambda g:(measured[g] + PENALTY*len(g.gates),len(g.gates),g.canonical())):
            if len(g.gates)>affordable:
                continue
            if signature[g] not in seen_sig:
                parents.append(g)
                seen_sig.add(signature[g])
                if len(parents)==BEAM:
                    break
        parent = rng.choice(parents)
        moves = eligible_moves(parent, affordable)
        move = choose_move(arm, moves, move_counts, reward_sum, rng)
        candidate = proposed_edit(parent, move, rng)
        successful = admit(candidate)
        move_counts[move] += 1
        if successful:
            move_admitted[move] += 1
            # Parent-vs-child loss delta on *exactly the same training points*.
            improvement = measured[parent] - measured[candidate]
            cost_regularizer = PENALTY * (len(candidate.gates) - len(parent.gates))
            reward_sum[move] += max(-1.0,min(1.0,improvement-cost_regularizer))
            if arm == 'credit_novelty':
                reward_sum[move] += 0.15  # Reward novel admitted structure.
        elif arm == 'credit_novelty':
            reward_sum[move] -= 0.15  # Penalize unproductive duplicate attempts.

    shortlist = _select_shortlist(measured)
    validation = []
    for g in shortlist:
        val_error, _ = evaluate(g,valid)
        validation.append((val_error+PENALTY*len(g.gates),val_error,len(g.gates),g.canonical(),g))
    validation.sort(key=lambda x:x[:-1])
    winner = validation[0][-1]
    test_error, _ = evaluate(winner,holdout,flip_holdout)
    return dict(task=task,seed=seed,arm=arm,test_accuracy=round(1-test_error,12),
                train_accuracy=round(1-measured[winner],12),validation_accuracy=round(1-validation[0][1],12),
                selected=winner.as_json(),candidate_count=len(measured),proposals=proposals,
                rejection=rejection,gate_work=work,validation_count=len(shortlist),
                pool_sha256=sha256(json.dumps([g.as_json() for g in sorted(measured,key=lambda g:g.canonical())],sort_keys=True).encode()).hexdigest(),
                credit={op:{'attempts':move_counts[op],'accepted':move_admitted[op],
                            'net_train_reward':round(reward_sum[op],6)} for op in MOVES})


def summarize(rows):
    out={}
    for arm in ARMS:
        records=[r for r in rows if r['arm']==arm]
        out[arm]=dict(cases=len(records),accuracy=round(statistics.mean(r['test_accuracy'] for r in records),6),
                      exact=sum(r['test_accuracy']==1 for r in records),
                      candidates=sum(r['candidate_count'] for r in records),
                      gate_work=sum(r['gate_work'] for r in records),
                      mean_gates=round(statistics.mean(len(r['selected']['gates']) for r in records),4))
    return out


def run_bank(tasks,seeds=range(2)):
    rows=[]
    for task in tasks:
        for seed in seeds:
            for arm in ARMS:
                rows.append(run_case(arm,task,seed))
    return {'summary':summarize(rows),'records':rows}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--bank',required=True,choices=['development','fresh','chain'])
    parser.add_argument('--seeds',type=int,default=2)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    if not 1<=args.seeds<=8:parser.error('seed limit 1..8')
    bank=run_bank(DEVELOPMENT if args.bank=='development' else (NEW_TASKS if args.bank=='fresh' else CHAIN_TASKS),range(args.seeds))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({'protocol':{
         'id':'ACE-R3-v4-CREDIT-PILOT','author_visible':True,'fresh_task_graphs':{t:new_task_graph(t).as_json() for t in ALL_NEW_TASKS},
         'budget':{'candidates':CANDIDATE_CAP,'proposals':PROPOSAL_CAP,'gate_work':WORK_CAP},
         'train_valid_test':[18,7,7],'seeds':args.seeds},
         args.bank:bank},indent=2,sort_keys=True)+'\n')
    print(json.dumps(bank['summary'],indent=2))

if __name__=='__main__':main()
