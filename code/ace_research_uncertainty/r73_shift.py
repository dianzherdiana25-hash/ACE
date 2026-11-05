"""ACE R7.3 precommitted shift-aware prior selection; public synthetic only.

Never pass latent Bernoulli probability to a decision routine. Test/shift families
are new public-development worlds; source/validation/test/OOD custody is NOT
cryptographically independent. Never use pilot test/OOD to tune.
"""
from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass

from . import experiment as e
from . import r72_certification as prior_work

SEED = 20261107
BUDGETS = (0, 6, 12, 24)
GROUPS = e.GROUPS
CONFIG = e.Config(12, 1.0)
FAMILIES = {
    'stable': (.18, .42, .63, .78, .91, .97),
    'shift_a': (.91, .19, .36, .54, .33, .72),
    'shift_b': (.90, .79, .29, .39, .17, .12),
}
SENTINELS = (4, 5, 4, 5, 4, 5)
THRESHOLD_LBF = 2.0


def new_tasks(split: str, family: str, count: int) -> tuple[e.Task, ...]:
    valid = {'train': 'stable', 'validation': 'stable', 'test': 'stable',
             'ood_a': 'shift_a', 'ood_b': 'shift_b'}
    if valid.get(split) != family or type(count) is not int or not 1 <= count <= 1000:
        raise ValueError('unknown or mismatched split')
    base = FAMILIES[family]
    out = []
    for k in range(count):
        rng = e.rng_for(SEED, 'r73-new-world', split, k)
        probs = tuple(max(.01, min(.99, x + rng.uniform(-.09, .09))) for x in base)
        out.append(e.Task(f'{split}:{family}:r73:{k}', family, probs))
    return tuple(out)


def prior_log_bayes_factor(prior: tuple[float, ...], labels: tuple[tuple[int,int], ...]) -> float:
    """Log likelihood ratio of weak vs source prior, no ground-truth access.

    Integrates future likelihood sequentially via posterior predictive for each
    stratum. Does NOT call an evaluator or know any target family.
    """
    if len(prior) != GROUPS or any(not (0 < p < 1) for p in prior):
        raise ValueError('invalid source prior')
    strong = e.Belief(prior, CONFIG)
    weak = e.Belief(prior, e.Config(0, 1.0))
    lr = 0.
    for g, y in labels:
        if type(g) is not int or g not in (4,5) or type(y) is not int or y not in (0,1):
            raise ValueError('invalid diagnostic observation')
        ps, pw = strong.mean(g), weak.mean(g)
        lr += math.log((pw if y else (1-pw)) / (ps if y else (1-ps)))
        strong.observe(g,y)
        weak.observe(g,y)
    return lr


def prefix(evaluator: e.Evaluator, belief: e.Belief, budget: int) -> list[tuple[int,int]]:
    obs = []
    for g in SENTINELS[:budget]:
        y = evaluator.query(g)
        belief.observe(g,y)
        obs.append((g,y))
    return obs


def source_certificate(evaluator: e.Evaluator, belief: e.Belief, cap: int):
    while evaluator.purchases < cap:
        g = prior_work.next_certificate_group(belief,cap - evaluator.purchases)
        if g is None:
            break
        belief.observe(g,evaluator.query(g))


def weak_explore(evaluator: e.Evaluator, belief: e.Belief,
                 cap: int, task_uid: str):
    # Explicit initial scout of previously unseen strata. All scout labels count.
    for g in range(4):
        if evaluator.purchases >= cap:
            break
        belief.observe(g,evaluator.query(g))
    rng = e.rng_for(SEED,'greedy-tie',task_uid)
    tie_order = list(range(GROUPS))
    rng.shuffle(tie_order)
    priority = {g: -i for i,g in enumerate(tie_order)}
    while evaluator.purchases < cap:
        uncertified = [g for g in range(GROUPS)
                       if not prior_work.certifiable(belief.a[g],belief.b[g],belief.counts[g])]
        if not uncertified:
            break
        # Fully posterior-only exploitation of discovered reliable strata.
        g = max(uncertified, key=lambda k:(belief.mean(k),priority[k]))
        belief.observe(g,evaluator.query(g))


@dataclass(frozen=True)
class Outcome:
    row: dict
    shift_detected: bool
    diagnostic_labels: int
    log_bayes_factor: float | None


def simulate(task: e.Task, prior: tuple[float,...], method: str, cap: int) -> Outcome:
    if method not in ('random_lcb','certificate','sentinel_control','shift_aware'):
        raise ValueError('unknown R7.3 method')
    if cap not in BUDGETS:
        raise ValueError('unexpected cap')
    if method == 'random_lcb':
        return Outcome(e.simulate(task,prior,'random_lcb',CONFIG,cap),False,0,None)
    if method == 'certificate':
        return Outcome(prior_work.simulate_certificate(task,prior,cap),False,0,None)
    evaluator = e.Evaluator(task,cap)
    belief = e.Belief(prior,CONFIG)
    obs = prefix(evaluator,belief,cap)
    detected = False
    bf = None
    if method == 'shift_aware' and len(obs) == 6:
        bf = prior_log_bayes_factor(prior,tuple(obs))
        detected = bf >= THRESHOLD_LBF
    if detected:
        weak = e.Belief(prior,e.Config(0,1.0))
        for g,y in obs:
            weak.observe(g,y)
        belief = weak
        weak_explore(evaluator, belief, cap, task.uid)
    else:
        source_certificate(evaluator,belief,cap)
    means = tuple(belief.mean(g) for g in range(GROUPS))
    accepted = tuple(belief.accept(g,'active_lcb',CONFIG.z) for g in range(GROUPS))
    return Outcome(evaluator.score(means, accepted),detected,len(obs),bf)


def aggregate(tasks: tuple[e.Task,...],prior:tuple[float,...],method:str,cap:int) -> dict:
    results = [simulate(t,prior,method,cap) for t in tasks]
    bins = [[0.,0.,0] for _ in range(10)]
    for o in results:
        for i, row in enumerate(o.row['calibration']):
            for j in range(3):
                bins[i][j] += row[j]
    n = sum(o.row['evaluated_labels'] for o in results)
    row = {k:sum(o.row[k] for o in results) for k in
           ('true_accepts','false_accepts','abstentions','purchases')}
    row['tasks'] = len(tasks)
    row['budget_per_task'] = cap
    row['brier'] = round(sum(o.row['brier_sum'] for o in results)/n,6)
    row['ece'] = round(sum(abs(s-t) for s,t,c in bins if c)/n,6)
    accepted = row['true_accepts'] + row['false_accepts']
    row['false_acceptance_rate'] = round(row['false_accepts']/accepted,6) if accepted else None
    row['correct_accepts_per_100_labels'] = round(100*row['true_accepts']/row['purchases'],6) if row['purchases'] else None
    row['utility'] = 20*row['true_accepts']-60*row['false_accepts']-2*row['abstentions']-row['purchases']
    row['shift_detected_tasks'] = sum(o.shift_detected for o in results)
    row['total_diagnostic_labels'] = sum(o.diagnostic_labels for o in results)
    return row


def assemble_splits():
    return {'test':new_tasks('test','stable',24),
            'ood_a':new_tasks('ood_a','shift_a',24),
            'ood_b':new_tasks('ood_b','shift_b',24)}


def validation_smoke():
    train = new_tasks('train','stable',30)
    valid = new_tasks('validation','stable',12)
    prior, source_cost = e.fit_prior(train)
    return {'status':'VALIDATION_ONLY_PUBLIC', 'prior':prior, 'offline_source_labels':source_cost,
            'validation':{m:aggregate(valid,prior,m,24) for m in
                          ('random_lcb','certificate','sentinel_control','shift_aware')}}


def final_run() -> dict:
    train = new_tasks('train','stable',30)
    prior, source_cost = e.fit_prior(train)
    splits=assemble_splits()
    assert len(set(t.uid for t in train).union(*(set(t.uid for t in x) for x in splits.values()))) == 102
    answer = {}
    for split,tasks in splits.items():
        answer[split]={}
        for cap in BUDGETS:
            answer[split][str(cap)] = {
                method:aggregate(tasks,prior,method,cap)
                for method in ('random_lcb','certificate','sentinel_control','shift_aware')}
        ceilings = [e.Evaluator(t,0).oracle_upper_bound() for t in tasks]
        answer[split]['oracle_ceiling']={k:sum(z[k] for z in ceilings)
                 for k in ('true_accepts','false_accepts','abstentions','purchases')}
    stable_a=answer['test']['24']['shift_aware'];stable_c=answer['test']['24']['certificate']
    cond2=(stable_a['true_accepts'] >= .8*stable_c['true_accepts'] and
           stable_a['false_accepts'] <= stable_c['false_accepts'])
    cond1=all(answer[f]['24']['shift_aware']['false_accepts'] <=
              answer[f]['24']['certificate']['false_accepts'] for f in ('ood_a','ood_b')) and any(
              answer[f]['24']['shift_aware']['false_accepts'] <
              answer[f]['24']['certificate']['false_accepts'] for f in ('ood_a','ood_b'))
    cond3=(any(answer[f]['24']['shift_aware']['true_accepts']>0 for f in ('ood_a','ood_b')) and
           all(answer[f]['24']['shift_aware']['utility'] >
               answer[f]['24']['certificate']['utility'] for f in ('ood_a','ood_b')))
    cond4=all(answer[f][str(cap)][m]['purchases'] <= len(splits[f])*cap
              for f in splits for cap in BUDGETS for m in
              ('random_lcb','certificate','sentinel_control','shift_aware'))
    return {'status':'PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY','protocol':'R73_PROTOCOL.md',
            'seed':SEED,'prior':prior,'offline_training_labels':source_cost,
            'split_ids_sha256':{k:e.digest([t.uid for t in v]) for k,v in splits.items()},
            'results':answer,'gate':{'both_ood_false_accepts_improve':cond1,
                'stable_coverage_80pct_and_no_new_errors':cond2,
                'ood_nontrivial_and_utility_improve':cond3,
                'hard_label_caps':cond4},'gate_passed':bool(cond1 and cond2 and cond3 and cond4),
            'scientific_decision':'HOLD_NO_INDEPENDENT_CONFIRMATION',
            'warnings':['public synthetic development, not sealed independent evaluation',
                        'in-process evaluator is not a security boundary',
                        'no tuning after opening new final test/OOD','OOD mechanism families author-visible']}


def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('--phase',required=True,choices=('validation','final'))
    a=p.parse_args()
    result=validation_smoke() if a.phase=='validation' else final_run()
    print(json.dumps(result,indent=2,sort_keys=True,allow_nan=False))


if __name__=='__main__':
    main()
