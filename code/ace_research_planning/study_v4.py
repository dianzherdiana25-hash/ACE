"""R6-v4 public, bounded strategy-selection study with a one-way transfer gate.

This is NOT an independent holdout. Train/validation are fully evaluated before
freezing the chosen decision stump, then OOD transfer is evaluated once.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
import random
from statistics import mean

from .planning import (World, forced_key_order_certificate,
                       generate, geometric_lower_bound_certificate, simulate)
from .study_v2 import independent_optimal_cost, neutral_surprise

METHODS = ('hier_replan', 'astar', 'astar_metric', 'dijkstra', 'robust')
WORK_BUDGETS = (250, 2200)
CONDITIONS = ('static', 'neutral_closure')
SEEDS = {
    'train': tuple(range(22100, 22124)),
    'validation': tuple(range(23100, 23124)),
    'transfer': tuple(range(24100, 24124)),
}
FAMILIES = {
    'train': ('ordered_grid', 'free_grid', 'terminal_portal'),
    'validation': ('ordered_grid', 'free_grid', 'terminal_portal'),
    'transfer': ('interior_portals', 'gated_bypass', 'weight_shift'),
}
FEATURES = ('ordered', 'geometric', 'four_keys', 'large', 'dense')


def _portal_edges(base: World, pairs: tuple[tuple[int, int], ...], cost: int = 1,
                  needed: int = 1) -> World:
    used = {(u, v) for u, v, _ in base.weights}
    adj = [set(neighbors) for neighbors in base.adjacency]
    weights = list(base.weights)
    added = 0
    for u, v in pairs:
        a, b = sorted((u, v))
        if a == b or (a, b) in used:
            continue
        dist = abs(a % base.width - b % base.width) + abs(a // base.width - b // base.width)
        if dist < 4:
            continue
        used.add((a, b))
        adj[a].add(b)
        adj[b].add(a)
        weights.append((a, b, cost))
        added += 1
        if added >= 3:
            break
    if added < needed:
        raise AssertionError('generator failed to add nonlocal portal')
    return replace(base, adjacency=tuple(tuple(sorted(n)) for n in adj), weights=tuple(sorted(weights)))


def _interior_portals(base: World, seed: int) -> World:
    avoid = set(base.keys) | {0, base.goal}
    interior = [i for i in range(base.width * base.height) if i not in avoid]
    rng = random.Random(seed ^ 0xD190)
    rng.shuffle(interior)
    candidates = tuple((u, v) for u in interior[:15] for v in interior[-15:])
    return _portal_edges(base, candidates, needed=2)


def make_world(split: str, family: str, seed: int, condition: str) -> World:
    if (split not in SEEDS or seed not in SEEDS[split]
            or family not in FAMILIES[split] or condition not in CONDITIONS):
        raise ValueError('unregistered split/family/seed/condition')
    if family == 'ordered_grid':
        world = generate(2 * seed + 1, 'ood')  # odd -> locks and key-order task
        if not forced_key_order_certificate(world):
            raise AssertionError('ordered grid must be certified')
    elif family == 'gated_bypass':
        base = generate(2 * seed + 1, 'ood')
        pairs = ((base.keys[0], base.keys[-1]), (0, base.goal),
                 (base.keys[1], base.goal))
        world = _portal_edges(base, pairs, needed=1)
        if forced_key_order_certificate(world):
            raise AssertionError('bypass world cannot have order proof')
    else:
        base = replace(generate(seed, 'ood'), locks=())
        if family in ('free_grid',):
            world = base
        elif family == 'terminal_portal':
            world = _portal_edges(base, ((0, base.keys[-1]), (base.keys[0], base.goal),
                                         (base.keys[-1], base.goal), (0, base.keys[0])))
        elif family == 'interior_portals':
            world = _interior_portals(base, seed)
        elif family == 'weight_shift':
            # Mechanism shift: a different edge-weight regime, same geometry.
            world = replace(base, weights=tuple((u, v, 1 + ((seed + u * 3 + v * 7 + cost) % 13))
                                                  for u, v, cost in base.weights))
        else:
            raise AssertionError(family)
    if independent_optimal_cost(world) is None:
        raise AssertionError('base world unsolvable')
    if condition == 'neutral_closure':
        world = neutral_surprise(world, seed + 900000)
    return world


def features(world: World) -> dict[str, bool]:
    """Never consults World.shock or future action outcomes."""
    n = world.width * world.height
    return {
        'ordered': forced_key_order_certificate(world),
        'geometric': geometric_lower_bound_certificate(world),
        'four_keys': len(world.keys) >= 4,
        'large': n >= 42,
        'dense': len(world.weights) * 10 >= 14 * n,
    }


@dataclass(frozen=True)
class Selector:
    feature: str | None
    false_method: str
    true_method: str

    def choose(self, observed: dict[str, bool]) -> str:
        if self.feature is None:
            return self.false_method
        if self.feature not in FEATURES:
            raise ValueError('unregistered feature')
        return self.true_method if observed[self.feature] else self.false_method

    def export(self) -> dict:
        return {'feature': self.feature, 'false': self.false_method, 'true': self.true_method}


def candidates() -> tuple[Selector, ...]:
    constants = [Selector(None, m, m) for m in METHODS]
    stumps = [Selector(f, a, b) for f in FEATURES for a in METHODS for b in METHODS if a != b]
    return tuple(constants + stumps)


def score(row: dict) -> float:
    """Predeclared utility: first prioritize solving, then quality and metered work."""
    # Every solved task gives a large advantage over any timeout (max work 2201).
    if not row['success']:
        return -50.0 - row['work_units'] / 50.0
    return 1000.0 - 200.0 * (row['cost'] / row['reference'] - 1.0) - row['work_units'] / 50.0


def evaluate_worlds(split: str, n: int, work_budget: int) -> list[dict]:
    rows = []
    for seed in SEEDS[split][:n]:
        for family in FAMILIES[split]:
            for condition in CONDITIONS:
                world = make_world(split, family, seed, condition)
                reference = independent_optimal_cost(world, frozenset((world.shock,)) if world.shock else frozenset())
                if reference is None:
                    raise AssertionError('post-closure reference unsolvable')
                feature_map = features(world)
                for method in METHODS:
                    outcome = simulate(world, method, 1800, work_limit=work_budget)
                    rows.append(dict(split=split, seed=seed, family=family, condition=condition,
                                     method=method, features=feature_map,
                                     reference=reference,
                                     **{k: v for k, v in outcome.items() if k not in ('budget', 'work_limit')}))
    return rows


def selected_rows(rows: list[dict], policy: Selector) -> list[dict]:
    groups: dict[tuple, dict[str, dict]] = {}
    for row in rows:
        key = (row['seed'], row['family'], row['condition'])
        groups.setdefault(key, {})[row['method']] = row
    return [group[policy.choose(next(iter(group.values()))['features'])] for _, group in sorted(groups.items())]


def assess(rows: list[dict], policy: Selector) -> dict:
    chosen = selected_rows(rows, policy)
    solved = [r for r in chosen if r['success']]
    return dict(n=len(chosen), success=len(solved),
                utility=round(mean(score(r) for r in chosen), 6),
                mean_work=round(mean(r['work_units'] for r in chosen), 2),
                ratio_success_only=round(mean(r['cost']/r['reference'] for r in solved), 4) if solved else None,
                shock_encounters=sum(r['shock_encountered'] for r in chosen),
                recovered=sum(r['shock_encountered'] and r['success'] for r in chosen),
                action_counts={m: sum(r['method']==m for r in chosen) for m in METHODS},
                failures=[dict(seed=r['seed'], family=r['family'], condition=r['condition'],
                               method=r['method'], status=r['status']) for r in chosen if not r['success']][:12])


def fit(train: list[dict], validation: list[dict]) -> tuple[Selector, list[dict]]:
    """Freeze policy using train and validation only; no transfer argument."""
    scored = [(assess(train, p)['utility'], i, p) for i, p in enumerate(candidates())]
    # Select top 12 training candidates; use validation only for final choice.
    scored.sort(key=lambda x: (-x[0], x[1]))
    shortlist = scored[:12]
    ranked = [(assess(validation, p)['utility'], train_score, i, p)
              for train_score, i, p in shortlist]
    ranked.sort(key=lambda x: (-x[0], -x[1], x[2]))
    chosen = ranked[0][3]
    audit = [dict(policy=p.export(), validation_utility=v,
                  train_utility=t) for v, t, _, p in ranked]
    return chosen, audit


def paired_seed_delta(rows: list[dict], chosen: Selector, control: Selector,
                      draws: int = 999, seed: int = 6783) -> dict:
    """Cluster bootstrap with entire seed (all correlated family/condition rows)."""
    selected = selected_rows(rows, chosen)
    baseline = selected_rows(rows, control)
    def group(xs):
        bucket={}
        for r in xs:
            bucket.setdefault(r['seed'],[]).append(score(r))
        return {k:mean(v) for k,v in bucket.items()}
    a, b = group(selected), group(baseline)
    if set(a)!=set(b):
        raise AssertionError('nonpaired cluster data')
    ids=sorted(a)
    diffs=[a[k]-b[k] for k in ids]
    rng=random.Random(seed)
    draws_values=[]
    for _ in range(draws):
        draws_values.append(mean(diffs[rng.randrange(len(diffs))] for _ in ids))
    draws_values.sort()
    return dict(seeds=len(ids), observations=len(selected),
                mean_utility_delta=round(mean(diffs),6),
                cluster_bootstrap_95pct=[round(draws_values[int(0.025*(draws-1))],6),
                                         round(draws_values[int(0.975*(draws-1))],6)],
                bootstrap_draws=draws,
                caveat='Descriptive cluster bootstrap on author-visible synthetic seeds; not blind inference')


def support(rows: list[dict], selector: Selector) -> dict:
    selected=selected_rows(rows,selector)
    return dict(n=len(selected), true_feature=sum(r['features'][selector.feature]
                for r in selected) if selector.feature else None,
                selected_methods={m:sum(selector.choose(r['features'])==m for r in selected)
                                  for m in METHODS})


def run(ntrain: int = 24, nval: int = 24, ntransfer: int = 24,
        budgets: tuple[int, ...] = WORK_BUDGETS) -> dict:
    if any(isinstance(n, bool) or not isinstance(n, int) or n < 1 or n > 24
           for n in (ntrain, nval, ntransfer)):
        raise ValueError('split sample counts must be 1..24')
    if (not budgets or tuple(sorted(set(budgets))) != budgets or
            any(isinstance(x, bool) or not isinstance(x, int) or x < 1 or x > 30000 for x in budgets)):
        raise ValueError('invalid metered work ceilings')
    summaries = {}
    policy_receipts = {}
    all_rows = []
    for budget in budgets:
        # IMPORTANT: transfer data not generated or scored until selector frozen.
        train = evaluate_worlds('train', ntrain, budget)
        val = evaluate_worlds('validation', nval, budget)
        winner, shortlist = fit(train, val)
        best_fixed = max((Selector(None,m,m) for m in METHODS),
                         key=lambda p: (assess(val,p)['utility'], -METHODS.index(p.false_method)))
        frozen_bytes = json.dumps({'selector':winner.export(),'shortlist':shortlist, 'best_fixed':best_fixed.export(), 'budget':budget},
                                  sort_keys=True,separators=(',', ':')).encode()
        freeze_sha = sha256(frozen_bytes).hexdigest()
        policy_receipts[str(budget)] = dict(selector=winner.export(), best_fixed=best_fixed.export(), freeze_sha256=freeze_sha,
                                             trained_on=ntrain*len(FAMILIES['train'])*len(CONDITIONS),
                                             selected_on=nval*len(FAMILIES['validation'])*len(CONDITIONS),
                                             shortlist=shortlist)
        # Only AFTER the selection receipt is frozen: new mechanism transfer.
        transfer = evaluate_worlds('transfer', ntransfer, budget)
        policy_receipts[str(budget)]['support'] = {
            'train':support(train,winner), 'validation':support(val,winner),
            'transfer':support(transfer,winner)}
        policy_receipts[str(budget)]['paired_delta_vs_val_selected_fixed'] = paired_seed_delta(
            transfer,winner,best_fixed,seed=6783+budget)
        all_rows.extend(transfer)
        for split, rows in (('train',train), ('validation',val), ('transfer',transfer)):
            for label, p in [('learned',winner), ('best_fixed_validation',best_fixed), ('robust_v3', Selector(None,'robust','robust'))] + [
                    (m,Selector(None,m,m)) for m in METHODS if m != 'robust']:
                summaries[f'{budget}/{split}/{label}'] = assess(rows, p)
        # Hindsight upper bound, only an evaluation comparator, NEVER an executable policy.
        grouped: dict[tuple, list[dict]] = {}
        for r in transfer:
            grouped.setdefault((r['seed'],r['family'],r['condition']),[]).append(r)
        best = [max(g, key=score) for g in grouped.values()]
        summaries[f'{budget}/transfer/hindsight_oracle'] = dict(n=len(best), success=sum(r['success'] for r in best),
               utility=round(mean(score(r) for r in best),6),
               mean_work=round(mean(r['work_units'] for r in best),2),
               warning='NONDEPLOYABLE: uses per-case terminal outcomes')
    report = dict(protocol='ACE-R6-v4-public-decision-stump-transfer',
        disclosure='Author-generated PUBLIC transfer, not blind. Selector is a finite decision stump, '
                   'not new primitive or autonomous reasoning. Work units count instrumented events '
                   '(expanded states, heuristic calls, graph scans, heap pops) and are NOT FLOPs/CPU. '
                   'Reference for surprises is hindsight lower bound; shock selection is route independent.',
        split_seed_ranges={s:[SEEDS[s][0],SEEDS[s][min(len(SEEDS[s]),n)-1]] for s,n in
                           [('train',ntrain),('validation',nval),('transfer',ntransfer)]},
        families=FAMILIES, budgets=budgets, methods=METHODS,
        candidate_count=len(candidates()), policies=policy_receipts, summary=summaries,
        transfer_rows=all_rows)
    report['sha256'] = sha256(json.dumps(report,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return report


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument('--output',default='/tmp/ace_r6_v4.json')
    p.add_argument('--n',type=int,default=24)
    a=p.parse_args()
    report=run(a.n,a.n,a.n)
    Path(a.output).write_text(json.dumps(report,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print('R6 v4 transfer runs',len(report['transfer_rows']), 'digest',report['sha256'])
    for budget in report['budgets']:
        print('budget',budget, 'frozen selector', report['policies'][str(budget)]['selector'])
        for method in ('learned','robust_v3','hier_replan','astar','astar_metric','dijkstra','hindsight_oracle'):
            print(method,report['summary'][f'{budget}/transfer/{method}'])

if __name__ == '__main__':
    main()
