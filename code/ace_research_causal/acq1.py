"""R5 ACQ1: bounded active direct-intervention purchase, with paid sample accounting.

Public synthetic exploratory development only. Does not identify IV validity or
learn unprovided causal graph structure. Uses the existing R5 IV SCM source.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import random
from . import invalid_iv as iv

ACTION_COST = 0.50
DO_ROW_PRICE = 0.0125
MAX_DO_ROWS = 32
INITIAL_PER_MODE = 80
EVAL_WORLDS = 100
COHORTS = {"valid": 710000, "direct_exclusion": 720000,
           "selected_compliance": 730000, "both_invalid": 740000,
           "weak_first_stage": 750000}
POLICIES = ("no_buy", "always32", "uncertainty32", "disagreement32",
            "staged8_24", "random_matched32")


def initial_rows(w: iv.World, seed: int):
    """Same 160 baseline labels for every policy on this world."""
    r1 = random.Random(seed * 29 + 123)
    r2 = random.Random(seed * 29 + 124)
    z = [-1.0, 1.0] * (INITIAL_PER_MODE // 2)
    r1.shuffle(z)
    r = [iv.one(w, r1, 'encourage', zi) for zi in z]
    o = [iv.one(w, r2, 'observe', 0.0) for _ in range(INITIAL_PER_MODE)]
    return r, o


class DirectOracle:
    """Issues direct interventions *only* when requested, in fixed 8-row batches."""
    def __init__(self, world: iv.World, seed: int):
        self._world = world
        self._rng = random.Random(seed * 29 + 125)
        self.used = 0
        self._issued = []

    def buy(self, n: int):
        if type(n) is not int or n <= 0 or n % 8 or self.used + n > MAX_DO_ROWS:
            raise ValueError('direct-do request outside capped 8-row budget')
        out = []
        for _ in range(n // 8):
            assignments = [-1.0] * 4 + [1.0] * 4
            self._rng.shuffle(assignments)
            out.extend(iv.one(self._world, self._rng, 'do', a)
                       for a in assignments)
        self.used += n
        self._issued.extend(out)
        return out


@dataclass(frozen=True)
class Signal:
    iv_effect: float
    obs_effect: float
    first_stage: float


def signal_from_rows(enc, obs):
    estimate, first = iv.regress(enc, 'iv')
    passive, _ = iv.regress(obs, 'obs')
    return Signal(estimate, passive, first)


def action(est: float):
    if not math.isfinite(est) or abs(est) <= ACTION_COST:
        return 0
    return 1 if est > 0 else -1


def disagreement(s: Signal):
    if not math.isfinite(s.iv_effect) or not math.isfinite(s.obs_effect):
        return True
    return ((s.iv_effect > 0) != (s.obs_effect > 0)
            or abs(s.iv_effect - s.obs_effect) > 0.75
            or abs(s.first_stage) < 0.16)


def uncertainty(s: Signal):
    return (not math.isfinite(s.iv_effect)
            or not math.isfinite(s.first_stage)
            or abs(abs(s.iv_effect) - ACTION_COST) < 0.20
            or abs(s.first_stage) < 0.16)


def direct_estimate(rows):
    if len(rows) < 8 or len(rows) > MAX_DO_ROWS or len(rows) % 8:
        raise ValueError('invalid direct sample count')
    slope, _ = iv.regress(rows, 'direct_do')
    return slope


def choose(policy: str, s: Signal, oracle: DirectOracle, random_flag=False):
    if policy not in POLICIES:
        raise ValueError('unknown acquisition policy')
    if policy == 'no_buy':
        return action(s.iv_effect)
    trigger = {
        'always32': True,
        'uncertainty32': uncertainty(s),
        'disagreement32': disagreement(s),
        'staged8_24': disagreement(s),
        'random_matched32': bool(random_flag)
    }[policy]
    if not trigger:
        return action(s.iv_effect)
    if policy == 'staged8_24':
        rows = oracle.buy(8)
        first = direct_estimate(rows)
        if action(first) != action(s.iv_effect) or abs(abs(first) - ACTION_COST) < 0.30:
            rows += oracle.buy(24)
        return action(direct_estimate(rows))
    return action(direct_estimate(oracle.buy(32)))


def score(w: iv.World, chosen: int, bought: int):
    if chosen not in (-1, 0, 1) or bought < 0 or bought > MAX_DO_ROWS:
        raise ValueError('invalid action or budget')
    optimal = max(0.0, abs(w.tau) - ACTION_COST)
    gain = chosen * w.tau - ACTION_COST if chosen else 0.0
    action_regret = max(0.0, optimal - gain)
    query_cost = DO_ROW_PRICE * bought
    return {
        'net_regret': action_regret + query_cost,
        'action_regret': action_regret,
        'query_cost': query_cost,
        'direct_rows': bought,
        'purchased': int(bought > 0),
        'accepted': int(chosen != 0),
        'wrong_accepted': int(chosen != 0 and chosen * w.tau < 0),
        'optimal_action': int(action_regret < 1e-10),
    }


def run_world(seed: int, cohort: str, match_random=False):
    w = iv.world(seed, cohort)
    encourage, passive = initial_rows(w, seed)
    s = signal_from_rows(encourage, passive)
    out = {}
    for policy in POLICIES:
        oracle = DirectOracle(w, seed)
        decision = choose(policy, s, oracle, match_random)
        out[policy] = score(w, decision, oracle.used)
    return out, disagreement(s)


def mean(items):
    return round(math.fsum(items) / len(items), 6)


def aggregate(results):
    summary = {}
    for policy in POLICIES:
        rs = [r[policy] for r in results]
        one = {k: mean([v[k] for v in rs]) for k in ('net_regret', 'action_regret',
               'query_cost', 'direct_rows', 'purchased', 'accepted', 'optimal_action')}
        one['total_direct_rows'] = sum(v['direct_rows'] for v in rs)
        one['total_purchase_cost'] = round(math.fsum(v['query_cost'] for v in rs), 6)
        one['accepted_count'] = sum(v['accepted'] for v in rs)
        one['wrong_accepted_count'] = sum(v['wrong_accepted'] for v in rs)
        one['conditional_wrong_rate'] = (round(one['wrong_accepted_count'] / one['accepted_count'], 6)
                                         if one['accepted_count'] else None)
        summary[policy] = one
    return summary


def interval(results, lhs, rhs):
    differences = [r[lhs]['net_regret'] - r[rhs]['net_regret'] for r in results]
    n = len(differences)
    rng = random.Random(20261106)
    bs = sorted(math.fsum(differences[rng.randrange(n)] for _ in range(n)) / n
                for _ in range(2000))
    return {'mean': mean(differences), 'ci95_percentile': [round(bs[49], 6), round(bs[1949], 6)]}


def experiment(worlds=EVAL_WORLDS):
    if type(worlds) is not int or worlds < 2 or worlds > 200:
        raise ValueError('world count beyond declared bounds')
    cohort_results = {}
    for cohort, first_seed in COHORTS.items():
        base = [run_world(first_seed + i, cohort, False) for i in range(worlds)]
        trigger_count = sum(trigger for _, trigger in base)
        # An offline matched-budget random control: cohort-level count comes
        # from initial-row triggers, not outcome truth or direct data.
        random_idxs = set(random.Random(9000000 + first_seed).sample(range(worlds), trigger_count))
        # Re-run each world only to compute matched random arm; never share an
        # oracle ledger with other arms. All arm prefixes use same seed.
        rows = []
        for i, (baseline_row, trigger) in enumerate(base):
            selected_row = run_world(first_seed + i, cohort, i in random_idxs)[0]
            merged = dict(baseline_row)
            merged['random_matched32'] = selected_row['random_matched32']
            rows.append(merged)
        data = aggregate(rows)
        assert data['disagreement32']['total_direct_rows'] == data['random_matched32']['total_direct_rows']
        cohort_results[cohort] = {
            'means': data,
            'disagreement_trigger_count': trigger_count,
            'paired_net_regret_differences': {
                'disagreement_minus_no_buy': interval(rows, 'disagreement32', 'no_buy'),
                'disagreement_minus_random_matched': interval(rows, 'disagreement32', 'random_matched32'),
                'staged_minus_disagreement': interval(rows, 'staged8_24', 'disagreement32'),
                'uncertainty_minus_no_buy': interval(rows, 'uncertainty32', 'no_buy'),
                'always_minus_no_buy': interval(rows, 'always32', 'no_buy'),
            }
        }
    return {
        'status': 'EXPLORATORY_AUTHOR_VISIBLE_NOT_INDEPENDENTLY_ACCEPTED',
        'protocol': {
            'worlds_per_cohort': worlds, 'base_rows_per_policy': 160,
            'baseline_encouragement_rows': 80, 'baseline_observational_rows': 80,
            'max_direct_rows': MAX_DO_ROWS, 'direct_row_price': DO_ROW_PRICE,
            'action_cost': ACTION_COST, 'bootstrap_world_resamples': 2000,
            'random_matched_is_offline': True, 'cohort_seeds': {
                k: [v, v + worlds - 1] for k, v in COHORTS.items()}},
        'cohorts': cohort_results}


def gates(result):
    a = result['cohorts']
    def value(c, policy, metric): return a[c]['means'][policy][metric]
    return {
        'F1_exclusion_improvement_ge_point10': (
            value('direct_exclusion', 'no_buy', 'net_regret') -
            value('direct_exclusion', 'disagreement32', 'net_regret') >= .10),
        'F2_better_than_matched_random_in_both_by_point02': all(
            value(c, 'random_matched32', 'net_regret') -
            value(c, 'disagreement32', 'net_regret') >= .02
            for c in ('direct_exclusion', 'both_invalid')),
        'F3_valid_excess_regret_at_most_point10': (
            value('valid', 'disagreement32', 'net_regret') -
            value('valid', 'no_buy', 'net_regret') <= .10),
        'F4_staged_less_data_and_regret_within_point10_both_invalid': (
            value('both_invalid', 'staged8_24', 'total_direct_rows') <
            value('both_invalid', 'disagreement32', 'total_direct_rows') and
            value('both_invalid', 'staged8_24', 'net_regret') -
            value('both_invalid', 'disagreement32', 'net_regret') <= .10),
        'F5_uncertainty_high_regret_exclusion': (
            value('direct_exclusion', 'uncertainty32', 'net_regret') > .20),
        'F6_general_causal_intelligence_claim': 'REJECTED_NOT_IDENTIFIABLE',
        'scientific_acceptance': 'NOT_ASSESSED'
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--worlds', type=int, default=EVAL_WORLDS)
    p.add_argument('--output', type=Path, default=Path('acq1_results.json'))
    args = p.parse_args()
    res = experiment(args.worlds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(res, sort_keys=True, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print('SHA256', hashlib.sha256(args.output.read_bytes()).hexdigest())
    print(json.dumps(gates(res), indent=2, sort_keys=True))

if __name__ == '__main__':
    main()
