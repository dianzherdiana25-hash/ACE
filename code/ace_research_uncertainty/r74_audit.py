"""Independently verify R7.4 saved JSON results WITHOUT querying an evaluator.

Repro: PYTHONPATH=code python -m ace_research_uncertainty.r74_audit ACE_R74_locked_final_results.json
Never reruns a final evaluation, and cannot establish sealed scoring custody.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

SPLITS = ('test', 'ood_a', 'ood_b', 'ood_c', 'ood_d')
METHODS = ('random_lcb', 'certificate', 'shift_aware', 'diagnostic_abstain', 'paired_lcb', 'e_test')


def audit(source: bytes) -> dict:
    rec = json.loads(source)
    failures = []
    checks = 0
    arms = 0

    def check(condition: bool, description: str):
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(description)

    check(rec.get('seed') == 20261108, 'seed')
    check(rec.get('protocol') == 'R74_PROTOCOL.md', 'protocol')
    check(rec.get('offline_training_labels') == 2160, 'offline cost')
    results = rec['results']
    check(set(results) == set(SPLITS), 'split names')
    for split in SPLITS:
        bank = results[split]
        check(set(bank) == {'0', '6', '12', '24', 'oracle_ceiling'}, 'cap inventory')
        oracle = bank['oracle_ceiling']
        check(oracle['purchases'] == 0 and oracle['false_accepts'] == 0, 'offline oracle ceiling')
        for budget in (0, 6, 12, 24):
            methods = bank[str(budget)]
            check(set(methods) == set(METHODS), 'method inventory')
            for name in METHODS:
                row = methods[name]
                arms += 1
                check(row['tasks'] == 20 and row['budget_per_task'] == budget, 'task/cap')
                check(row['purchases'] <= budget*20, 'budget overspend')
                check(row['true_accepts'] + row['false_accepts'] + row['abstentions'] == 120, 'disjoint outcomes')
                check(row['true_accepts'] <= oracle['true_accepts'], 'oracle coverage ceiling')
                check(row['utility'] == 20*row['true_accepts'] - 60*row['false_accepts'] - 2*row['abstentions'] - row['purchases'], 'utility arithmetic')
                accepted = row['true_accepts'] + row['false_accepts']
                check(row['false_acceptance_rate'] is None if accepted == 0
                      else row['false_acceptance_rate'] == round(row['false_accepts']/accepted, 6), 'undefined FPR handling')
                check(0 <= row['ece'] <= 1 and 0 <= row['brier'] <= 1, 'calibration metrics')
                check(row['diagnostic_labels'] + row['certificate_labels'] <= row['purchases'], 'label accounting')
                if name in ('e_test','paired_lcb'):
                    check(sum(row['selection_histogram'].values()) == (20 if budget >= 6 else 0), 'selected groups')
            paired, chosen = methods['paired_lcb'], methods['e_test']
            check(paired['purchases'] == chosen['purchases'], 'matched buys')
            check(paired['diagnostic_labels'] == chosen['diagnostic_labels'] and paired['certificate_labels'] == chosen['certificate_labels'], 'matched label types')
            check(paired['ece'] == chosen['ece'] and paired['brier'] == chosen['brier'], 'matched calibrated probabilities')
            check(paired['selection_histogram'] == chosen['selection_histogram'], 'matched selected groups')
            check(chosen['true_accepts'] + chosen['false_accepts'] <= 20, 'one candidate per task')
            check(methods['diagnostic_abstain']['true_accepts'] + methods['diagnostic_abstain']['false_accepts'] == 0, 'always abstain control')
            check(methods['diagnostic_abstain']['purchases'] == 20 * min(6, budget), 'diagnostic prefix cost')
            if budget >= 6:
                check(chosen['purchases'] == chosen['diagnostic_labels'] + chosen['certificate_labels'], 'total e-test label conservation')
            if budget == 0:
                check(all(row['purchases'] == 0 and row['true_accepts'] + row['false_accepts'] == 0 for row in methods.values()), 'zero-cap behavior')
    e = lambda name: results[name]['24']['e_test']
    s = lambda name: results[name]['24']['shift_aware']
    ood = SPLITS[1:]
    expected = {
        'stable_coverage_and_safety': e('test')['true_accepts'] >= .25*s('test')['true_accepts'] and e('test')['false_accepts'] <= s('test')['false_accepts'],
        'ood_false_acceptance_nonworse_each': all(e(n)['false_accepts'] <= s(n)['false_accepts'] for n in ood),
        'ood_strict_improvement_at_least_one': any(e(n)['false_accepts'] < s(n)['false_accepts'] for n in ood),
        'ood_coverage_two_families': sum(e(n)['true_accepts'] > 0 for n in ood) >= 2,
        'ood_utility_nondecrease': sum(e(n)['utility'] for n in ood) >= sum(s(n)['utility'] for n in ood),
        'all_purchases_within_caps': all(row['purchases'] <= 20*int(cap) for name in SPLITS for cap,rows in results[name].items() if cap.isdecimal() for row in rows.values()),
    }
    check(expected == rec['gate'], 'rederived gate')
    check(all(expected.values()) == rec['precommitted_gate_pass'], 'final gate status')
    return {'status': 'PASS' if not failures else 'FAIL',
            'arms': arms, 'checks': checks, 'failed': len(failures),
            'errors': failures, 'sha256': hashlib.sha256(source).hexdigest(),
            'bytes': len(source), 'gate': expected,
            'ood_utility_r73': sum(s(name)['utility'] for name in ood),
            'ood_utility_r74': sum(e(name)['utility'] for name in ood),
            'reran_evaluator': False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result_json', type=Path)
    args = parser.parse_args()
    receipt = audit(args.result_json.read_bytes())
    print(json.dumps(receipt, sort_keys=True, indent=2))
    raise SystemExit(0 if receipt['status'] == 'PASS' else 2)


if __name__ == '__main__':
    main()
