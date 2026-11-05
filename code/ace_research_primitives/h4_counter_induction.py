"""ACE R1 H4: observation-conditioned synthesis of a one-register representation.

Synthetic public development only. The counter *class and refinement guards* are
researcher-authored; signed weights and guard instances are inferred from train.
No eval/exec/generated source/external oracle. Terminal holdout is not model input.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
from math import gcd
import json
import random
from typing import Callable

try:
    from . import primitive_discovery as d
except ImportError:
    import primitive_discovery as d

ALPHABET = 'ab'
TARGET_NAMES = ('equal_counts', 'a_twice_b', 'b_twice_a', 'a_three_b',
                'dyck', 'reverse_dyck', 'a_block_b_block', 'b_block_a_block',
                'a_odd', 'avoids_aba', 'palindrome', 'late_flip_equal')
H4_PRIMARY = TARGET_NAMES[:8]
H4_SPECIFICITY = TARGET_NAMES[8:11]
MAX_DRAW = 250_000


def judge(name: str, word: str) -> bool:
    a, b = word.count('a'), word.count('b')
    if name == 'equal_counts':
        return a == b
    if name == 'a_twice_b':
        return a == 2*b
    if name == 'b_twice_a':
        return b == 2*a
    if name == 'a_three_b':
        return a == 3*b
    if name == 'dyck':
        return d.dyck(word)
    if name == 'reverse_dyck':
        depth = 0
        for symbol in word:
            depth += 1 if symbol == 'b' else -1
            if depth < 0:
                return False
        return depth == 0
    if name == 'a_block_b_block':
        return word == 'a'*a + 'b'*b and a == b
    if name == 'b_block_a_block':
        return word == 'b'*b + 'a'*a and a == b
    if name == 'a_odd':
        return a % 2 == 1
    if name == 'avoids_aba':
        return 'aba' not in word
    if name == 'palindrome':
        return word == word[::-1]
    if name == 'late_flip_equal':
        return (a == b) if len(word) <= 5 else (a != b)
    raise ValueError('unknown synthetic family')


def evaluate_finite(pred: Callable[[str], bool], examples):
    correct = sum(bool(pred(s)) == y for s, y in examples)
    return {'n': len(examples), 'correct': correct,
            'accuracy': round(correct / len(examples), 6)}


def numeric_path(w: tuple[int,int], word: str):
    cur = 0
    low = high = 0
    for c in word:
        cur += w[0] if c == 'a' else w[1]
        low = min(low, cur)
        high = max(high, cur)
    return cur, low, high


@dataclass(frozen=True)
class CounterModel:
    w_a: int
    w_b: int
    target: int
    guard_kind: str = 'none'
    guard_parameter: int | str | None = None

    def predict(self, word: str) -> bool:
        final, low, high = numeric_path((self.w_a, self.w_b), word)
        if final != self.target:
            return False
        if self.guard_kind == 'none':
            return True
        if self.guard_kind == 'min':
            return low >= self.guard_parameter
        if self.guard_kind == 'max':
            return high <= self.guard_parameter
        if self.guard_kind == 'forbid':
            return self.guard_parameter not in word
        raise ValueError('unexpected guard')


def infer_counter(examples):
    """Build a 1-counter feature from positive equivalence observations only.

    No target name, target oracle, validation, or holdout data are accepted.
    False positives and guard selection are scored only on train.
    """
    if not examples or len(examples) > 63:
        raise ValueError('R1 H4 train cap')
    if any(type(word) is not str or set(word)-set(ALPHABET) or type(y) is not bool
           for word, y in examples):
        raise ValueError('invalid binary observations')
    observations = dict(examples)
    if len(observations) != len(examples):
        raise ValueError('duplicate train keys')
    positives = [s for s, y in examples if y]
    negatives = [s for s, y in examples if not y]
    vectors = sorted(set((s.count('a'), s.count('b')) for s in positives))
    hypotheses = {}
    attempts = 0
    for i, va in enumerate(vectors):
        for vb in vectors[i+1:]:
            attempts += 1
            if attempts > 1000:
                raise RuntimeError('register proposal budget')
            delta_a, delta_b = vb[0]-va[0], vb[1]-va[1]
            if not delta_a or not delta_b:
                continue
            common = gcd(abs(delta_a), abs(delta_b))
            wa, wb = delta_b//common, -delta_a//common
            if wa < 0:
                wa, wb = -wa, -wb
            if wa <= 0 or wb >= 0:
                continue
            target = wa*va[0] + wb*va[1]
            candidate = CounterModel(wa, wb, target)
            if all(candidate.predict(s) for s in positives):
                hypotheses[(wa, wb, target)] = candidate
    if not hypotheses:
        return {'status': 'abstain', 'reason': 'no_positive_supported_register',
                'proposal_attempts': attempts, 'guard_attempts': 0,
                'model': None, 'raw_model': None, 'guarded_model': None}
    best = min(hypotheses.values(), key=lambda m: (
        sum(m.predict(s) for s in negatives), abs(m.w_a)+abs(m.w_b),
        m.w_a, m.w_b, m.target))
    false_positives = [s for s in negatives if best.predict(s)]
    if not false_positives:
        return {'status': 'constructed', 'reason': 'counter_train_consistent',
                'proposal_attempts': attempts, 'guard_attempts': 0,
                'model': best, 'raw_model': best, 'guarded_model': best}

    # Context residuals: guards are fixed *classes*, instances are train-derived.
    positive_paths = [numeric_path((best.w_a, best.w_b), s) for s in positives]
    min_threshold = min(x[1] for x in positive_paths)
    max_threshold = max(x[2] for x in positive_paths)
    guards = [CounterModel(best.w_a, best.w_b, best.target, 'min', min_threshold),
              CounterModel(best.w_a, best.w_b, best.target, 'max', max_threshold)]
    for first in ALPHABET:
        for second in ALPHABET:
            bigram = first + second
            if all(bigram not in s for s in positives):
                guards.append(CounterModel(best.w_a, best.w_b, best.target, 'forbid', bigram))
    if len(guards) > 1000:
        raise RuntimeError('guard budget')
    # All guards must retain positives; take maximal eliminated training false positives.
    viable = [g for g in guards if all(g.predict(s) for s in positives)]
    guarded = min(viable, key=lambda m: (
        sum(m.predict(s) for s in negatives),
        0 if m.guard_kind in ('min', 'max') else 1,
        m.guard_kind, str(m.guard_parameter))) if viable else None
    improvements = sum(best.predict(s) for s in negatives) - (
        sum(guarded.predict(s) for s in negatives) if guarded else 0)
    if not guarded or improvements <= 0:
        return {'status': 'abstain', 'reason': 'no_valid_residual_guard',
                'proposal_attempts': attempts, 'guard_attempts': len(guards),
                'model': None, 'raw_model': best, 'guarded_model': guarded}
    residual = [s for s in negatives if guarded.predict(s)]
    if residual:
        return {'status': 'abstain', 'reason': 'unresolved_train_false_positives',
                'proposal_attempts': attempts, 'guard_attempts': len(guards),
                'model': None, 'raw_model': best, 'guarded_model': guarded}
    return {'status': 'constructed', 'reason': 'guard_train_consistent',
            'proposal_attempts': attempts, 'guard_attempts': len(guards),
            'model': guarded, 'raw_model': best, 'guarded_model': guarded}


def sample_holdout(name: str, index: int):
    rng = random.Random(d.SEED + 14000 + index)
    if name in ('a_block_b_block', 'b_block_a_block'):
        positives = [('a'*n+'b'*n) if name.startswith('a_') else ('b'*n+'a'*n)
                     for n in range(4, 28)]
    else:
        positives = []
        used = set()
        for attempt in range(MAX_DRAW):
            if len(positives) == 24:
                break
            length = rng.randrange(8, 21)
            candidate = ''.join(ALPHABET[rng.randrange(2)] for _ in range(length))
            if name == 'late_flip_equal' and length % 2 != 0:
                continue  # matched-length opposite class requires even length
            if candidate not in used and judge(name, candidate):
                positives.append(candidate)
                used.add(candidate)
        if len(positives) != 24:
            raise RuntimeError(f'positive bank exhausted for {name}')
    seen = set(positives)
    negatives = []
    for positive in positives:
        result = None
        for attempt in range(MAX_DRAW):
            if name in ('a_block_b_block', 'b_block_a_block', 'dyck', 'reverse_dyck'):
                shuffled = list(positive)
                rng.shuffle(shuffled)
                candidate = ''.join(shuffled)
            elif name in ('equal_counts', 'a_twice_b', 'b_twice_a', 'a_three_b'):
                at = rng.randrange(len(positive))
                replacement = 'b' if positive[at] == 'a' else 'a'
                candidate = positive[:at] + replacement + positive[at+1:]
            else:
                candidate = ''.join(ALPHABET[rng.randrange(2)] for _ in range(len(positive)))
            if candidate not in seen and not judge(name, candidate):
                result = candidate
                break
        if result is None:
            raise RuntimeError(f'negative bank exhausted for {name}')
        seen.add(result)
        negatives.append(result)
    holdout = sorted(positives + negatives, key=lambda s: (len(s), s))
    assert len(set(holdout)) == 48
    assert sum(judge(name, s) for s in holdout) == 24
    assert all(len(s) >= 8 for s in holdout)
    if name in ('dyck', 'reverse_dyck', 'a_block_b_block', 'b_block_a_block'):
        assert all(pos.count('a') == neg.count('a') and pos.count('b') == neg.count('b')
                   for pos, neg in zip(positives, negatives))
    return holdout


def run_h4():
    train_words = d.training_words()
    val_words = d.validation_words()
    predicates = d.fixed_predicates()
    report = {'schema': 'r1-h4-v1', 'protocol_commit': '85515f6c91c18b898c8e51d1d2ed75b3df755ef0',
              'seed': d.SEED, 'tasks': [], 'train_labels_per_task': 63,
              'validation_labels_per_task': 192, 'holdout_labels_per_task': 48,
              'status': 'NOT_ASSESSED'}
    for index, name in enumerate(TARGET_NAMES):
        oracle = lambda s, name=name: judge(name, s)
        train = [(s, oracle(s)) for s in train_words]
        val = [(s, oracle(s)) for s in val_words]
        hold_strings = sample_holdout(name, index)
        hold = [(s, oracle(s)) for s in hold_strings]
        assert not set(hold_strings) & (set(train_words)|set(val_words))
        inferred = infer_counter(train)
        finite, merges = d.infer(train)
        best_fixed_name, fixed = min(predicates, key=lambda item: sum(item[1](s) != y for s, y in train))
        chosen = inferred['model']
        classifiers = {
            'constructed_or_fallback': chosen.predict if chosen else finite.run,
            'raw_counter': inferred['raw_model'].predict if inferred['raw_model'] else (lambda s: False),
            'guarded_counter': inferred['guarded_model'].predict if inferred['guarded_model'] else (lambda s: False),
            'rpni': finite.run,
            'prefix_memorizer': lambda s, t=dict(train): t.get(s, False),
            'suffix3': lambda s, tr=train: d.suffix_majority(tr, s),
            'fixed_library': fixed,
        }
        scores = {model: {split: evaluate_finite(predict, examples)
                          for split, examples in (('train', train), ('validation', val), ('holdout', hold))}
                  for model, predict in classifiers.items()}
        errors = [[s, int(y), int(classifiers['constructed_or_fallback'](s))]
                  for s,y in hold if classifiers['constructed_or_fallback'](s) != y]
        report['tasks'].append({'task': name, 'kind': ('primary' if index < 8 else
                                ('specificity' if index < 11 else 'adversarial')),
                                'data_hash': {'train': d.sample_hash(train_words),
                                              'validation': d.sample_hash(val_words),
                                              'holdout': d.sample_hash(hold_strings)},
                                'constructed': inferred['status']=='constructed',
                                'reason': inferred['reason'],
                                'feature': (asdict(inferred['model']) if inferred['model'] else None),
                                'raw_feature': (asdict(inferred['raw_model']) if inferred['raw_model'] else None),
                                'guarded_feature': (asdict(inferred['guarded_model']) if inferred['guarded_model'] else None),
                                'proposal_attempts': inferred['proposal_attempts'],
                                'guard_attempts': inferred['guard_attempts'],
                                'rpni_states': finite.reachable(), 'rpni_automaton': finite.signature(),
                                'rpni_merge_attempts': merges,
                                'fixed_predicate': best_fixed_name,
                                'scores': scores, 'counterexamples': errors[:4]})
    primary = report['tasks'][:8]
    def avg(method):
        return sum(x['scores'][method]['holdout']['correct'] for x in primary) / (8*48)
    mean_method = avg('constructed_or_fallback')
    oracle_mean = sum(max(t['scores'][method]['holdout']['correct'] for method in
                          ('rpni','prefix_memorizer','suffix3','fixed_library'))
                      for t in primary) / (8*48)
    reaches_90 = sum(t['scores']['constructed_or_fallback']['holdout']['correct'] >= 44
                     for t in primary)
    abs_target = sum(t['constructed'] for t in report['tasks'][8:11])
    report['primary'] = {'mean_induced': round(mean_method,6),
                         'best_per_task_oracle_control':round(oracle_mean,6),
                         'gain':round(mean_method-oracle_mean,6),
                         'primary_at_least_90_percent': reaches_90,
                         'h4a_pass': bool(mean_method >= .85 and mean_method-oracle_mean >= .10 and reaches_90>=6),
                         'specificity_counter_proposals': abs_target,
                         'h4b_pass': abs_target<=1,
                         'adversarial_correct': report['tasks'][-1]['scores']['constructed_or_fallback']['holdout']['correct']}
    report['synthetic_label_evaluations'] = len(TARGET_NAMES)*(63+192+48)
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output')
    args=p.parse_args()
    result=run_h4()
    if args.output:
        with open(args.output,'w',encoding='utf-8') as file:
            json.dump(result,file,sort_keys=True,indent=2)
            file.write('\n')
    print(json.dumps({'primary':result['primary'],
                      'tasks':[{'name':t['task'],'constructed':t['constructed'],
                                'guard': t['feature']['guard_kind'] if t['feature'] else None,
                                'accuracy': t['scores']['constructed_or_fallback']['holdout']['accuracy'],
                                'rpni': t['scores']['rpni']['holdout']['accuracy']}
                               for t in result['tasks']]},sort_keys=True))


if __name__ == '__main__':
    main()
