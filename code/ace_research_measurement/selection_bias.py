"""R8: public deterministic test of multiple-testing and holdout reuse effects.

All candidates are independent Bernoulli(0.5) noise, so the known true
population performance is identical for every arm. No ACE agent is evaluated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path


def experiment(*, seed: int = 14005, repetitions: int = 512,
               arms: int = 48, validation_cases: int = 24,
               evaluation_cases: int = 24, threshold: float = 0.10) -> dict:
    if type(seed) is not int or type(repetitions) is not int or type(arms) is not int:
        raise ValueError('invalid integer experiment configuration')
    if type(validation_cases) is not int or type(evaluation_cases) is not int:
        raise ValueError('invalid integer case counts')
    if not (1 <= repetitions <= 2000 and 2 <= arms <= 100 and
            4 <= validation_cases <= 1000 and 4 <= evaluation_cases <= 1000):
        raise ValueError('invalid bounded study design')
    if type(threshold) is not float or not 0 < threshold < 1:
        raise ValueError('invalid success threshold')
    rng = random.Random(seed)
    selected_validation = []
    selected_evaluation = []
    fixed_validation = []
    fixed_evaluation = []
    selected_ids = []
    naive_win = 0
    confirmation_win = 0
    false_progress = 0
    bad_on_holdout = 0
    for _ in range(repetitions):
        # Precommitted: draw all public validation scores, choose champion;
        # never use evaluation to select candidate in this experiment.
        val = [sum(rng.getrandbits(1) for __ in range(validation_cases)) / validation_cases
               for __ in range(arms)]
        chosen = min(range(arms), key=lambda j: (-val[j], j))
        # Purchase a shared test set for baseline and the FROZEN selected arm
        # only. If chosen == baseline, reuse the same evaluation receipt.
        h0 = sum(rng.getrandbits(1) for __ in range(evaluation_cases)) / evaluation_cases
        h = (h0 if chosen == 0 else
             sum(rng.getrandbits(1) for __ in range(evaluation_cases)) / evaluation_cases)
        v, v0 = val[chosen], val[0]
        selected_validation.append(v)
        selected_evaluation.append(h)
        fixed_validation.append(v0)
        fixed_evaluation.append(h0)
        selected_ids.append(chosen)
        va = v - v0 >= threshold
        ea = h - h0 >= threshold
        naive_win += int(va)
        confirmation_win += int(ea)
        false_progress += int(va and h - h0 <= 0)
        bad_on_holdout += int(h < h0)
    avg = lambda x: sum(x) / len(x)
    return {
        'schema': 'ace.r8.selection-bias-public.v1',
        'design': {'seed': seed, 'repetitions': repetitions, 'arms': arms,
                   'validation_cases': validation_cases, 'evaluation_cases': evaluation_cases,
                   'promotion_threshold': threshold,
                   'ground_truth_candidate_accuracy': 0.5},
        'means': {
            'selected_validation': avg(selected_validation),
            'selected_evaluation': avg(selected_evaluation),
            'fixed_validation': avg(fixed_validation),
            'fixed_evaluation': avg(fixed_evaluation),
            'validation_selection_optimism': avg(selected_validation) - avg(selected_evaluation),
            'selected_evaluation_minus_fixed_evaluation': avg(selected_evaluation) - avg(fixed_evaluation),
        },
        'rates': {
            'naive_validation_gain_at_least_threshold': naive_win / repetitions,
            'independent_evaluation_gain_at_least_threshold': confirmation_win / repetitions,
            'naive_wins_but_evaluation_no_gain': false_progress / repetitions,
            'selected_worse_than_fixed_on_evaluation': bad_on_holdout / repetitions,
        },
        'counts': {'naive_validation_wins': naive_win,
                   'independent_evaluation_wins': confirmation_win,
                   'naive_false_progress': false_progress,
                   'selected_worse_on_evaluation': bad_on_holdout},
        'selected_indices_sha256': hashlib.sha256(json.dumps(selected_ids, separators=(',', ':')).encode()).hexdigest(),
        'interpretation': ('Post-selection validation is optimistic under a pure null. '
                           'Public simulated evaluation is not independent external confirmation.'),
        'claim_gate': 'NOT_ASSESSED',
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    result = experiment()
    encoded = json.dumps(result, sort_keys=True, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding='utf-8')
    else:
        print(encoded, end='')


if __name__ == '__main__':
    main()
