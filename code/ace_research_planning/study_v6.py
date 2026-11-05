"""R6-v6 reproducible supervised hazard-to-VOI decision experiment.

Training and validation are public. Transfer task creation is called only after
model serialization/locking in one process. No independent blind holdout.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import random
from statistics import mean

from .planning import World, generate
from .metareason_v6 import (POLICIES, RiskModel, salience, fit_risk, edge_priors,
                            run_policy, utility)
from .study_v2 import independent_optimal_cost
from .study_v4 import _portal_edges, _interior_portals

SEEDS = {
    "train": tuple(range(52100, 52120)),
    "validation": tuple(range(53100, 53114)),
    "iid_transfer": tuple(range(54100, 54116)),
    "shift_transfer": tuple(range(55100, 55116)),
    "no_shock_transfer": tuple(range(56100, 56116)),
}
FAMILIES = {
    "train": ("ordered_grid", "free_grid", "terminal_portal"),
    "validation": ("ordered_grid", "free_grid", "terminal_portal"),
    "iid_transfer": ("ordered_grid", "free_grid", "terminal_portal"),
    "shift_transfer": ("interior_portals", "gated_bypass", "weight_shift"),
    "no_shock_transfer": ("interior_portals", "gated_bypass", "weight_shift"),
}
BUDGETS = (300, 900)


def base_world(seed: int, family: str) -> World:
    if family in ("ordered_grid", "gated_bypass"):
        base = generate(2 * seed + 1, "ood")
        if family == "gated_bypass":
            base = _portal_edges(base, ((base.keys[0], base.keys[-1]),
                                        (0, base.goal), (base.keys[1], base.goal)), needed=1)
    else:
        basic = replace(generate(seed, "ood"), locks=())
        if family == "free_grid":
            base = basic
        elif family == "terminal_portal":
            base = _portal_edges(basic, ((0, basic.keys[-1]), (basic.keys[0], basic.goal),
                                          (basic.keys[-1], basic.goal), (0, basic.keys[0])))
        elif family == "interior_portals":
            base = _interior_portals(basic, seed)
        elif family == "weight_shift":
            base = replace(basic, weights=tuple((u, v, 1 + ((seed + u*3 + v*7 + c) % 13))
                                                      for u, v, c in basic.weights))
        else:
            raise ValueError("unknown family")
    if independent_optimal_cost(base) is None:
        raise AssertionError("no initial solution")
    return replace(base, shock=None)


def sample_world(split: str, seed: int, family: str) -> World:
    if split not in SEEDS or seed not in SEEDS[split] or family not in FAMILIES[split]:
        raise ValueError("unknown split/seed/family")
    base = base_world(seed, family)
    if split == "no_shock_transfer":
        return base
    rng = random.Random((seed << 8) ^ sum(map(ord, family)))
    # 85% chance of precisely one hidden closure, 15% no closure.
    if rng.random() >= .85:
        return base
    top = salience(base)
    # The simulator validates closure solvability. This eligibility oracle is
    # NEVER passed into the learner or runtime controller.
    safe = [(u, v) for u, v, _ in base.weights
            if independent_optimal_cost(base, frozenset(((u, v),))) is not None]
    if not safe:
        return base
    preferred = [e for e in safe if (e in top) == (split != "shift_transfer")]
    other = [e for e in safe if e not in preferred]
    # A deliberate mechanism shift: move the closure mass from public salient
    # edges to ordinary edges. No policy's intended path is consulted.
    if preferred and (rng.random() < .9 or not other):
        candidates = preferred
    else:
        candidates = other or preferred
    return replace(base, shock=rng.choice(candidates))


def worlds(split: str, n: int) -> tuple[tuple[int, str, World], ...]:
    if (split not in SEEDS or isinstance(n, bool) or not isinstance(n, int)
            or n <= 0 or n > len(SEEDS[split])):
        raise ValueError("invalid split or sample size")
    return tuple((seed, family, sample_world(split, seed, family))
                 for seed in SEEDS[split][:n] for family in FAMILIES[split])


def calibration(rows: tuple[tuple[int, str, World], ...], model: RiskModel) -> dict:
    brier = null_brier = 0.0
    labelled_edges = positives = 0
    a = [[0, 0, 0.0] for _ in range(2)]
    for _, _, world in rows:
        priors = edge_priors(model, world)
        top = salience(world)
        null_prob = model.shock_frequency / len(world.weights)
        for edge, p in priors.items():
            y = int(edge == world.shock)
            brier += (p-y)**2
            null_brier += (null_prob-y)**2
            labelled_edges += 1
            positives += y
            group = 0 if edge in top else 1
            a[group][0] += 1
            a[group][1] += y
            a[group][2] += p
    return dict(labelled_edges=labelled_edges, positives=positives,
                brier=round(brier/labelled_edges, 8),
                global_brier=round(null_brier/labelled_edges, 8),
                class_bins={name:dict(edges=z[0], positives=z[1], predicted_mass=round(z[2], 5),
                                      empirical_rate=round(z[1]/z[0], 7), mean_predicted=round(z[2]/z[0], 7))
                            for name, z in zip(('salient','ordinary'), a)})


def evaluate(rows: tuple[tuple[int, str, World], ...], model: RiskModel,
             budget: int) -> tuple[list[dict], dict]:
    results=[]
    for seed, family, world in rows:
        blocked = frozenset((world.shock,)) if world.shock else frozenset()
        ref = independent_optimal_cost(world, blocked)
        if ref is None:
            raise AssertionError("unsolvable benchmark")
        for method in POLICIES:
            r = run_policy(world, method, model, budget)
            results.append(dict(seed=seed, family=family, method=method,
                                success=r['success'], travel_cost=r['travel_cost'],
                                utility=round(utility(r, ref), 6),
                                work=r['work_units'], probes=r['probes'],
                                positive_probes=r['positive_probes'],
                                failures=r['failed_actions'],
                                budget_exhausted=r['status']=='work_budget',
                                shock_present=world.shock is not None,
                                encountered=r['encountered'],
                                decision_calls=r['decision_calls']))
    summaries={}
    for method in POLICIES:
        sel=[r for r in results if r['method']==method]
        summaries[method]=dict(n=len(sel), solved=sum(r['success'] for r in sel),
                               mean_utility=round(mean(r['utility'] for r in sel), 6),
                               mean_work=round(mean(r['work'] for r in sel), 2),
                               probes=sum(r['probes'] for r in sel),
                               positive_probes=sum(r['positive_probes'] for r in sel),
                               failures=sum(r['failures'] for r in sel),
                               work_budget_exits=sum(r['budget_exhausted'] for r in sel))
    return results,summaries


def paired(rows: list[dict], a: str, b: str, draws: int = 1999) -> dict:
    aa={(r['seed'],r['family']):r['utility'] for r in rows if r['method']==a}
    bb={(r['seed'],r['family']):r['utility'] for r in rows if r['method']==b}
    if set(aa)!=set(bb) or not aa:
        raise ValueError("unpaired outcomes")
    diffs=[aa[k]-bb[k] for k in sorted(aa)]
    seed_ids=sorted({s for s,_ in aa})
    # Cluster over seed, NOT separate family rows; intervals are descriptive.
    cluster=[mean(aa[(s,f)]-bb[(s,f)] for t,f in aa if t==s) for s in seed_ids]
    rng=random.Random(6306)
    samples=sorted(mean(cluster[rng.randrange(len(cluster))] for _ in cluster)
                   for _ in range(draws))
    return dict(pairs=len(diffs),seed_clusters=len(seed_ids),
                mean_utility_delta=round(mean(diffs), 6),
                descriptive_cluster_bootstrap_95pct=[round(samples[int(.025*(draws-1))],6),
                                                       round(samples[int(.975*(draws-1))],6)],
                wins=sum(d>1e-6 for d in diffs),losses=sum(d < -1e-6 for d in diffs),
                ties=sum(abs(d) <= 1e-6 for d in diffs))


def equivalent_to_salient(rows: list[dict]) -> dict:
    a={(r['seed'],r['family']):r for r in rows if r['method']=='learned_voi'}
    b={(r['seed'],r['family']):r for r in rows if r['method']=='salient'}
    if set(a)!=set(b):
        raise AssertionError("unpaired salient control")
    fields=('success','travel_cost','probes','positive_probes','failures')
    matched=[k for k in a if all(a[k][name]==b[k][name] for name in fields)]
    return dict(equivalent=len(matched),tested=len(a),
                non_equivalent=[dict(seed=k[0],family=k[1]) for k in sorted(set(a)-set(matched))])

def run(n_train: int = 12, n_validation: int = 8, n_transfer: int = 12,
        budgets: tuple[int,...] = BUDGETS) -> dict:
    if (not budgets or tuple(sorted(set(budgets))) != budgets or
            any(isinstance(x,bool) or not isinstance(x,int) or x<1 or x>10000 for x in budgets)):
        raise ValueError("bad budgets")
    train=worlds("train",n_train)
    validation=worlds("validation",n_validation)
    model=fit_risk(tuple(w for _,_,w in train))
    # Pre-transfer receipt freezes model AND comparators, budgets and generators.
    receipt=dict(model=model.export(),train_seeds=[SEEDS['train'][0],SEEDS['train'][n_train-1]],
                 validation_seeds=[SEEDS['validation'][0],SEEDS['validation'][n_validation-1]],
                 methods=POLICIES,budgets=budgets,protocol='R6-v6-VOI-beta-risk-1',
                 hazard_prob=0.85, salient_probability=0.9)
    validation_calibration=calibration(validation,model)
    summary={}
    selection={}
    train_results={}
    for budget in budgets:
        tr,ts=evaluate(train,model,budget)
        va,vs=evaluate(validation,model,budget)
        baseline_names=('never','always','salient','global_voi','anti_salient')
        fixed=max(baseline_names,key=lambda name:(vs[name]['mean_utility'],-POLICIES.index(name)))
        selection[str(budget)]=dict(validation_selected_fixed=fixed,
                                    train=ts,validation=vs)
        train_results[str(budget)]=dict(train_rollouts=len(tr),validation_rollouts=len(va))
    receipt["validation_selected_controls"] = {b: selection[b]["validation_selected_fixed"] for b in selection}
    frozen=sha256(json.dumps(receipt,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    # Transfer world generation follows model freeze and baseline control selection.
    transfer={split:worlds(split,n_transfer) for split in
              ('iid_transfer','shift_transfer','no_shock_transfer')}
    for split,ws in transfer.items():
        summary[split]=dict(calibration=calibration(ws,model),budgets={})
        for budget in budgets:
            rows,scores=evaluate(ws,model,budget)
            fixed=selection[str(budget)]['validation_selected_fixed']
            summary[split]['budgets'][str(budget)]=dict(scores=scores,
                delta_vs_validation_fixed=paired(rows,'learned_voi',fixed),
                delta_vs_never=paired(rows,'learned_voi','never'),
                delta_vs_salient=paired(rows,'learned_voi','salient'),
                equivalent_to_salient=equivalent_to_salient(rows))
    r=dict(protocol='ACE-R6-v6-public-value-of-information',
           disclosure='Public researcher-defined risk distribution; beta-binomial risk fitted from complete TRAIN labels only. '
                      'In-process freeze ordering, not independently escrowed/blinded. Information acquisition is '
                      'a policy of risk-based probe decisions; no learned new reasoning operator, and no OAIE.',
           counts={'train':len(train),'validation':len(validation),
                   **{k:len(v) for k,v in transfer.items()}},
           seed_ranges={k:[v[0],v[-1]] for k,v in SEEDS.items()},
           model=model.export(),pretransfer_receipt_sha256=frozen,
           validation_calibration=validation_calibration,
           selection=selection,transfer=summary,training_work=train_results)
    r['sha256']=sha256(json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return r


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--n-train',type=int,default=12)
    parser.add_argument('--n-validation',type=int,default=8)
    parser.add_argument('--n-transfer',type=int,default=12)
    parser.add_argument('--output',default='/tmp/r6_v6_summary.json')
    a=parser.parse_args()
    r=run(a.n_train,a.n_validation,a.n_transfer)
    Path(a.output).write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print('sha256',r['sha256'],'world_counts',r['counts'])
    print('risk',r['model'])
    for split,v in r['transfer'].items():
        print(split,'brier',v['calibration']['brier'])
        for b,z in v['budgets'].items():
            print(' budget',b,'learned',z['scores']['learned_voi'],
                  'delta_vs_fixed',z['delta_vs_validation_fixed'])

if __name__=='__main__':
    main()
