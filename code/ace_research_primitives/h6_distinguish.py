"""R1 H6: one-label query experiments to distinguish two supplied representations.

Public synthetic experiment only. These candidate classes are authored, not discovered.
No execution of arbitrary generated source and no external paid evaluator.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
from pathlib import Path

SEED = 20261106
TRIGGERS = ('aaaaa', 'aaabb', 'ababa', 'bbbaa', 'bbbbb')
BASES = ('equal_counts', 'a_mod3', 'contains_ab', 'dyck', 'ends_ba',
         'avoids_bb', 'odd_length', 'first_equals_last')


def binary_words(start: int, stop: int) -> list[str]:
    return [''.join(p) for n in range(start, stop + 1)
            for p in itertools.product('ab', repeat=n)]


def truth_base(name: str, word: str) -> bool:
    if name == 'equal_counts':
        return word.count('a') == word.count('b')
    if name == 'a_mod3':
        return word.count('a') % 3 == 0
    if name == 'contains_ab':
        return 'ab' in word
    if name == 'dyck':
        depth = 0
        for c in word:
            depth += 1 if c == 'a' else -1
            if depth < 0:
                return False
        return depth == 0
    if name == 'ends_ba':
        return word.endswith('ba')
    if name == 'avoids_bb':
        return 'bb' not in word
    if name == 'odd_length':
        return len(word) % 2 == 1
    if name == 'first_equals_last':
        return bool(word) and word[0] == word[-1]
    raise ValueError('unknown base predicate')


def mechanism(name: str, word: str, trigger: str | None, start_len: int = 6) -> bool:
    base = truth_base(name, word)
    return base ^ bool(trigger is not None and len(word) >= start_len and trigger in word)


def digest(items) -> str:
    return hashlib.sha256(json.dumps(items, separators=(',', ':'), sort_keys=True).encode()).hexdigest()


def query_pool() -> list[str]:
    pool = binary_words(6, 10)
    if len(pool) != 1984:
        raise AssertionError('query pool size changed')
    return pool


def select_query(pool: list[str], base: str, trigger: str, strategy: str, index: int,
                 start_len: int = 6):
    """Only candidate predictions, not world truth, enter query selection."""
    disagreements = [i for i, s in enumerate(pool)
                     if truth_base(base, s) != mechanism(base, s, trigger, start_len)]
    if strategy == 'active':
        return disagreements[0] if disagreements else 0, len(disagreements)
    rng = random.Random(SEED + index)
    if strategy == 'uniform':
        return rng.randrange(len(pool)), len(disagreements)
    if strategy == 'random_disagreement':
        return disagreements[rng.randrange(len(disagreements))] if disagreements else 0, len(disagreements)
    raise ValueError('unknown strategy')


def infer_from_one_label(h0: bool, h1: bool, observed: bool) -> str | None:
    if h0 == h1:
        return None
    if observed == h0:
        return 'H0'
    if observed == h1:
        return 'H1'
    raise AssertionError('Boolean label matches neither candidate')


def sampled_holdout(index: int, start=11, stop=13, size=256) -> list[str]:
    pool = binary_words(start, stop)
    result = random.Random(SEED + 100000 + index).sample(pool, size)
    return sorted(result, key=lambda s: (len(s), s))


def execute_world(index: int, base: str, trigger: str, true_hypothesis: str, pool: list[str]):
    train = binary_words(0, 5)
    assert len(train) == 63
    assert all(mechanism(base, s, trigger) == truth_base(base, s) for s in train)
    hold = sampled_holdout(index)
    actual_trigger = trigger if true_hypothesis == 'H1' else None
    trials = {}
    for strategy in ('active', 'uniform', 'random_disagreement'):
        qidx, disagreements = select_query(pool, base, trigger, strategy, index)
        word = pool[qidx]
        h0 = mechanism(base, word, None)
        h1 = mechanism(base, word, trigger)
        oracle = mechanism(base, word, actual_trigger)
        decision = infer_from_one_label(h0, h1, oracle)
        correct = (decision == true_hypothesis)
        terminal = None
        if decision is not None:
            pred = lambda s, d=decision: mechanism(base, s, trigger if d == 'H1' else None)
            terminal = sum(pred(s) == mechanism(base, s, actual_trigger) for s in hold)
        trials[strategy] = {
            'query_index': qidx, 'query': word, 'h0_label': int(h0),
            'h1_label': int(h1), 'oracle_label': int(oracle),
            'candidate_disagreements': disagreements, 'decision': decision,
            'correct_identification': correct, 'abstained': decision is None,
            'holdout_correct_if_decided': terminal,
        }
    return {'task_index': index, 'base': base, 'trigger': trigger,
            'true_hypothesis': true_hypothesis,
            'training_sha256': digest([int(truth_base(base, s)) for s in train]),
            'holdout_sha256': digest(hold), 'trials': trials}


def execute_controls(pool: list[str]):
    controls = {'late_indistinguishable': [], 'misspecified_open_world': []}
    for index, base in enumerate(BASES):
        qidx, disagreements = select_query(pool, base, 'aaaaa', 'active', index, 14)
        word = pool[qidx]
        h0 = mechanism(base, word, None)
        h1 = mechanism(base, word, 'aaaaa', 14)
        oracle = h1
        dec = infer_from_one_label(h0, h1, oracle)
        controls['late_indistinguishable'].append({
            'base': base, 'query': word, 'candidate_disagreements': disagreements,
            'oracle_label': int(oracle), 'decision': dec, 'abstained': dec is None})
        qidx, disagreements = select_query(pool, base, 'aaaaa', 'active', index)
        word = pool[qidx]
        h0, h1 = truth_base(base, word), mechanism(base, word, 'aaaaa')
        oracle = mechanism(base, word, 'bbbbb')
        dec = infer_from_one_label(h0, h1, oracle)
        controls['misspecified_open_world'].append({
            'base': base, 'query': word, 'candidate_disagreements': disagreements,
            'oracle_label': int(oracle), 'decision': dec,
            'false_acceptance': dec is not None,
            'abstained': dec is None})
    return controls


def run():
    pool = query_pool()
    rows = []
    for base in BASES:
        for trigger in TRIGGERS:
            for actual in ('H0', 'H1'):
                rows.append(execute_world(len(rows), base, trigger, actual, pool))
    assert len(rows) == 80
    controls = execute_controls(pool)
    scores = {}
    for strategy in ('active', 'uniform', 'random_disagreement'):
        sub = [r['trials'][strategy] for r in rows]
        scores[strategy] = {
            'correct_identification': sum(t['correct_identification'] for t in sub),
            'abstentions': sum(t['abstained'] for t in sub),
            'oracle_queries': len(sub),
            'decided_holdout_correct': sum(t['holdout_correct_if_decided'] or 0 for t in sub),
            'decided_holdout_total': 256 * sum(not t['abstained'] for t in sub),
        }
    late_abstentions = sum(x['abstained'] for x in controls['late_indistinguishable'])
    missed_abstentions = sum(x['abstained'] for x in controls['misspecified_open_world'])
    h6a = (scores['active']['correct_identification'] / 80 >= .95 and
           (scores['active']['correct_identification'] - scores['uniform']['correct_identification']) / 80 >= .40)
    h6b = late_abstentions == 8
    h6c = missed_abstentions >= 6
    return {'schema': 'r1-h6-1', 'protocol_seed': SEED, 'query_pool_sha256': digest(pool),
            'query_pool_size': len(pool), 'training_labels_per_world': 63,
            'holdout_labels_per_in_class_world': 256, 'additional_query_oracle_labels': 256,
            'worlds': rows, 'controls': controls, 'scores': scores,
            'gates': {'H6a_identification': h6a, 'H6b_late_abstention': h6b,
                      'H6c_open_world_abstention': h6c, 'overall_go': h6a and h6b and h6c},
            'scientific_status': 'NOT_ASSESSED'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = run()
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'scores': result['scores'], 'gates': result['gates'],
                      'late_abstentions': sum(x['abstained'] for x in result['controls']['late_indistinguishable']),
                      'open_world_abstentions': sum(x['abstained'] for x in result['controls']['misspecified_open_world'])},
                     sort_keys=True))


if __name__ == '__main__':
    main()
