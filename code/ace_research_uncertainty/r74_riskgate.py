"""ACE R7.4: precommitted single-candidate e-process certification.

Public synthetic research only. The selector sees only acquired label replies.
Diagnostic labels choose one group but are disjoint from the e-test sequence.
The e-test has a conditional, per-task Bernoulli null risk bound under its
assumptions; this is NOT a calibration or OAIE claim across task families.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math

from . import experiment as e
from . import r72_certification as r72
from . import r73_shift as r73

SEED = 20261108
BUDGETS = (0, 6, 12, 24)
P0 = 0.80
P1 = 0.96
ALPHA = 0.10
E_THRESHOLD = 1.0 / ALPHA
DIAGNOSTICS = (0, 4, 5, 0, 4, 5)
METHODS = ('random_lcb', 'certificate', 'shift_aware',
           'diagnostic_abstain', 'paired_lcb', 'e_test')
FAMILIES = {
    'stable': (.18, .42, .63, .78, .91, .97),
    'ood_a': (.91, .19, .36, .54, .33, .72),
    'ood_b': (.90, .79, .29, .39, .17, .12),
    'ood_c': (.86, .94, .22, .68, .14, .24),
    'ood_d': (.21, .34, .96, .91, .27, .11),
}


def new_tasks(split: str, count: int) -> tuple[e.Task, ...]:
    if split not in ('train', 'validation', 'test', 'ood_a', 'ood_b', 'ood_c', 'ood_d'):
        raise ValueError('unknown split')
    if type(count) is not int or not 1 <= count <= 1000:
        raise ValueError('invalid task count')
    family = 'stable' if split in ('train', 'validation', 'test') else split
    base = FAMILIES[family]
    tasks = []
    for i in range(count):
        rng = e.rng_for(SEED, 'r74-new-world', split, i)
        probs = tuple(min(.99, max(.01, v + rng.uniform(-.09, .09))) for v in base)
        tasks.append(e.Task(f'{split}:{family}:r74:{i}',
                            'stable' if family == 'stable' else family, probs))
    return tuple(tasks)


def likelihood_multiplier(label: int) -> float:
    if type(label) is not int or label not in (0, 1):
        raise ValueError('invalid certificate label')
    return P1 / P0 if label else (1.0 - P1) / (1.0 - P0)


def null_expected_multiplier(true_success_probability: float) -> float:
    """Analytic supermartingale check at any Bernoulli null p <= P0."""
    if not 0 <= true_success_probability <= 1:
        raise ValueError('invalid hypothetical success probability')
    return (true_success_probability * likelihood_multiplier(1) +
            (1 - true_success_probability) * likelihood_multiplier(0))


def choose_one(diagnostic_labels: tuple[tuple[int, int], ...],
               source_prior: tuple[float, ...]) -> int:
    """No Task, oracle, evaluator, or hidden probabilities in this routine."""
    if len(source_prior) != e.GROUPS or any(not 0 < p < 1 for p in source_prior):
        raise ValueError('invalid source prior')
    if len(diagnostic_labels) != len(DIAGNOSTICS):
        raise ValueError('incomplete diagnostics')
    successes = {0: 0, 4: 0, 5: 0}
    for (g, y), expected_group in zip(diagnostic_labels, DIAGNOSTICS):
        if type(g) is not int or g != expected_group or type(y) is not int or y not in (0, 1):
            raise ValueError('invalid diagnostic evidence')
        successes[g] += y
    return max(successes, key=lambda g: (successes[g], source_prior[g], -g))


@dataclass(frozen=True)
class RunRecord:
    scored: dict
    chosen_group: int | None
    diagnostic_count: int
    certificate_count: int
    e_value: float
    certified: bool


def one(task: e.Task, source_prior: tuple[float, ...], method: str,
        budget: int) -> RunRecord:
    if method not in METHODS or budget not in BUDGETS:
        raise ValueError('invalid method or budget')
    if method in ('random_lcb', 'certificate', 'shift_aware'):
        if method == 'random_lcb':
            row = e.simulate(task, source_prior, 'random_lcb', r73.CONFIG, budget)
        elif method == 'certificate':
            row = r72.simulate_certificate(task, source_prior, budget)
        else:
            row = r73.simulate(task, source_prior, 'shift_aware', budget).row
        return RunRecord(row, None, 0, 0, 1.0, False)

    oracle = e.Evaluator(task, budget)
    # Weak probability calibration is not used in choosing a certificate.
    posterior = e.Belief(source_prior, e.Config(0, 1.0))
    diag = []
    for group in DIAGNOSTICS[:budget]:
        reply = oracle.query(group)
        posterior.observe(group, reply)
        diag.append((group, reply))

    chosen = choose_one(tuple(diag), source_prior) if len(diag) == 6 else None
    evidence = 1.0
    cert_labels = 0
    certified = False
    if chosen is not None and method != 'diagnostic_abstain':
        while oracle.purchases < budget:
            label = oracle.query(chosen)
            posterior.observe(chosen, label)
            cert_labels += 1
            evidence *= likelihood_multiplier(label)
            if cert_labels >= 3 and evidence >= E_THRESHOLD:
                certified = True
                break

    decisions = [False] * e.GROUPS
    if chosen is not None and method == 'e_test':
        decisions[chosen] = certified
    elif chosen is not None and method == 'paired_lcb':
        # Same samples and same optional-stopping time as e_test, but the
        # Bayesian LCB does re-use diagnostic samples (a deliberate control).
        decisions[chosen] = posterior.accept(chosen, 'active_lcb', 1.0)

    means = tuple(posterior.mean(g) for g in range(e.GROUPS))
    return RunRecord(oracle.score(means, tuple(decisions)), chosen,
                     len(diag), cert_labels, round(evidence, 12), certified)


def aggregate(tasks: tuple[e.Task, ...], source_prior: tuple[float, ...],
              method: str, budget: int) -> dict:
    if not tasks:
        raise ValueError('no evaluation tasks')
    records = [one(t, source_prior, method, budget) for t in tasks]
    bins = [[0.0, 0.0, 0] for _ in range(10)]
    for rec in records:
        for i, stats in enumerate(rec.scored['calibration']):
            for k in range(3):
                bins[i][k] += stats[k]
    n = sum(rec.scored['evaluated_labels'] for rec in records)
    total = {key: sum(rec.scored[key] for rec in records)
             for key in ('true_accepts', 'false_accepts', 'abstentions', 'purchases')}
    accepts = total['true_accepts'] + total['false_accepts']
    total.update({
        'tasks': len(tasks), 'budget_per_task': budget,
        'ece': round(sum(abs(s - y) for s, y, count in bins if count) / n, 6),
        'brier': round(sum(rec.scored['brier_sum'] for rec in records) / n, 6),
        'false_acceptance_rate': round(total['false_accepts'] / accepts, 6) if accepts else None,
        'correct_accepts_per_100_labels':
            round(100 * total['true_accepts'] / total['purchases'], 6) if total['purchases'] else None,
        'certified_task_count': sum(rec.certified for rec in records),
        'diagnostic_labels': sum(rec.diagnostic_count for rec in records),
        'certificate_labels': sum(rec.certificate_count for rec in records),
        'selection_histogram': {str(g): sum(rec.chosen_group == g for rec in records)
                                for g in (0, 4, 5)},
    })
    total['utility'] = 20 * total['true_accepts'] - 60 * total['false_accepts'] - 2 * total['abstentions'] - total['purchases']
    total['utility_per_100_labels'] = (
        round(100 * total['utility'] / total['purchases'], 6) if total['purchases'] else None)
    return total


def source_prior() -> tuple[tuple[float, ...], int]:
    return e.fit_prior(new_tasks('train', 30))


def validation_only() -> dict:
    prior, offline = source_prior()
    tasks = new_tasks('validation', 12)
    return {'phase': 'validation', 'seed': SEED, 'offline_training_labels': offline,
            'results': {method: aggregate(tasks, prior, method, 24)
                        for method in METHODS}}


def final_once() -> dict:
    prior, offline = source_prior()
    splits = {'test': new_tasks('test', 20),
              **{name: new_tasks(name, 20) for name in ('ood_a', 'ood_b', 'ood_c', 'ood_d')}}
    ids = [t.uid for group in [new_tasks('train', 30), new_tasks('validation', 12),
                                *splits.values()] for t in group]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate split ID')
    results = {}
    for name, tasks in splits.items():
        rows = {}
        for cap in BUDGETS:
            rows[str(cap)] = {method: aggregate(tasks, prior, method, cap) for method in METHODS}
        oracle_ceiling = [e.Evaluator(t, 0).oracle_upper_bound() for t in tasks]
        rows['oracle_ceiling'] = {
            k: sum(o[k] for o in oracle_ceiling)
            for k in ('true_accepts', 'false_accepts', 'abstentions', 'purchases')}
        results[name] = rows
    stable_a = results['test']['24']['e_test']
    stable_r = results['test']['24']['shift_aware']
    stable = (stable_a['true_accepts'] >= .25 * stable_r['true_accepts'] and
              stable_a['false_accepts'] <= stable_r['false_accepts'])
    ood = ('ood_a', 'ood_b', 'ood_c', 'ood_d')
    nonworse = all(results[f]['24']['e_test']['false_accepts'] <=
                   results[f]['24']['shift_aware']['false_accepts'] for f in ood)
    strictly_better = any(results[f]['24']['e_test']['false_accepts'] <
                          results[f]['24']['shift_aware']['false_accepts'] for f in ood)
    coverage = sum(results[f]['24']['e_test']['true_accepts'] > 0 for f in ood) >= 2
    utility = sum(results[f]['24']['e_test']['utility'] for f in ood) >= sum(
        results[f]['24']['shift_aware']['utility'] for f in ood)
    budgets = all(results[s][str(b)][m]['purchases'] <= b * len(splits[s])
                  for s in splits for b in BUDGETS for m in METHODS)
    gate = {'stable_coverage_and_safety': stable,
            'ood_false_acceptance_nonworse_each': nonworse,
            'ood_strict_improvement_at_least_one': strictly_better,
            'ood_coverage_two_families': coverage,
            'ood_utility_nondecrease': utility,
            'all_purchases_within_caps': budgets}
    return {'status': 'PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY',
            'scientific_decision': 'HOLD_PENDING_INDEPENDENT_CONFIRMATION',
            'protocol': 'R74_PROTOCOL.md', 'seed': SEED,
            'offline_training_labels': offline,
            'source_prior': prior,
            'split_id_hashes': {name: e.digest([t.uid for t in tasks]) for name, tasks in splits.items()},
            'one_sided_alpha_per_task_under_stationary_bernoulli_null': ALPHA,
            'results': results, 'gate': gate, 'precommitted_gate_pass': all(gate.values()),
            'limitations': ['public synthetic worlds and author-visible OOD families',
                            'one-seed development result is not independent confirmation',
                            'e-process only controls per-task false acceptance under conditional i.i.d. Bernoulli null',
                            'per-task control is not global family-wise or long-run deployment safety',
                            'same in-process evaluator for policies and scoring (non-secure boundary)']}


def main() -> None:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--phase', choices=('validation', 'final'), required=True)
    options = p.parse_args()
    result = validation_only() if options.phase == 'validation' else final_once()
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
