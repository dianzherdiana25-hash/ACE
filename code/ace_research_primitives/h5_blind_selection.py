"""R1 H5: task-blind evidence-based selection of finite DFA vs counter class.

Public deterministic synthetic development. H5_PROTOCOL.md was committed before
this implementation or execution. No generated source code execution or paid calls.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import random
from typing import Callable

try:
    from . import primitive_discovery as d
    from . import h4_counter_induction as h4
    from .random_dfa_bank import run_target, source_reachable
except ImportError:
    import primitive_discovery as d
    import h4_counter_induction as h4
    from random_dfa_bank import run_target, source_reachable

SEED = d.SEED
COUNTER_FAMILIES = h4.H4_PRIMARY
DRIFT_FAMILIES = ('equal_counts', 'a_twice_b', 'dyck', 'a_block_b_block')


def new_finite_targets():
    words = d.training_words()
    signatures = set()
    found = []
    for n in (2, 3, 4, 5):
        accepted = 0
        for attempt in range(50000):
            rng = random.Random(SEED + 24000 + 1000*n + attempt)
            target = (
                [tuple(rng.randrange(n) for _ in d.ALPHABET) for _ in range(n)],
                [rng.randrange(2) for _ in range(n)],
            )
            if source_reachable(target) != n:
                continue
            train_signature = tuple(run_target(target, word) for word in words)
            if train_signature in signatures or not .2 <= sum(train_signature)/63 <= .8:
                continue
            signatures.add(train_signature)
            found.append((n, attempt, target))
            accepted += 1
            if accepted == 3:
                break
        if accepted != 3:
            raise RuntimeError('H5: finite-target generation exhausted')
    return found


def finite_holdout(index):
    rng = random.Random(SEED + 25000 + index)
    chosen = set()
    attempts = 0
    while len(chosen) < 256 and attempts < 100000:
        attempts += 1
        n = rng.randrange(12, 19)
        chosen.add(''.join(d.ALPHABET[rng.randrange(2)] for _ in range(n)))
    if len(chosen) != 256:
        raise RuntimeError('H5: finite holdout generation exhausted')
    return sorted(chosen, key=lambda s: (len(s), s))


def block_holdout(name, index):
    positives = [ ('a'*n+'b'*n) if name == 'a_block_b_block' else ('b'*n+'a'*n)
                  for n in range(28, 52) ]
    rng = random.Random(SEED + 26000 + index)
    occupied = set(positives)
    negatives = []
    for positive in positives:
        for _ in range(250000):
            chars = list(positive)
            rng.shuffle(chars)
            candidate = ''.join(chars)
            if candidate not in occupied and not h4.judge(name, candidate):
                negatives.append(candidate)
                occupied.add(candidate)
                break
        else:
            raise RuntimeError('H5: block negative generation exhausted')
    hold = sorted(positives + negatives, key=lambda s: (len(s), s))
    assert len(hold) == 48 and sum(h4.judge(name, s) for s in hold) == 24
    return hold


def counter_holdout(name, index):
    if name in ('a_block_b_block', 'b_block_a_block'):
        return block_holdout(name, index)
    return h4.sample_holdout(name, 3000 + index)


def tasks():
    result = []
    for i, (n, attempt, target) in enumerate(new_finite_targets()):
        result.append({
            'id': i, 'group': 'finite', 'source': {'states': n, 'attempt': attempt,
                'transitions': target[0], 'acceptance': target[1]},
            'judge': lambda s, target=target: run_target(target, s),
            'holdout': finite_holdout(i),
        })
    for j, name in enumerate(COUNTER_FAMILIES):
        i = 12+j
        result.append({'id': i, 'group': 'counter', 'source': {'family': name},
                       'judge': lambda s, name=name: h4.judge(name, s),
                       'holdout': counter_holdout(name, i)})
    for j, name in enumerate(DRIFT_FAMILIES):
        i = 20+j
        def drift(s, name=name):
            original = h4.judge(name, s)
            return original if len(s) <= 7 else not original
        result.append({'id': i, 'group': 'drift', 'source': {'base_family': name,
                 'rule': 'invert above length 7'}, 'judge': drift,
                 'holdout': counter_holdout(name, i)})
    assert len(result) == 24
    return result


def metrics(predict, examples):
    return d.metric(predict, examples)


def run_h5():
    train_words, val_words = d.training_words(), d.validation_words()
    predicates = d.fixed_predicates()
    records = []
    for task in tasks():
        judge = task['judge']
        hold_words = task['holdout']
        assert len(hold_words) == (256 if task['group'] == 'finite' else 48)
        assert len(set(hold_words)) == len(hold_words)
        assert not (set(hold_words) & (set(train_words) | set(val_words)))
        train = [(s, bool(judge(s))) for s in train_words]
        val = [(s, bool(judge(s))) for s in val_words]
        hold = [(s, bool(judge(s))) for s in hold_words]
        finite, attempts = d.infer(train)
        counter_info = h4.infer_counter(train)
        counter = counter_info['model']
        counter_predict = counter.predict if counter else finite.run
        fitted_name, fitted_pred = min(predicates, key=lambda x: sum(x[1](s)!=y for s,y in train))
        models = {
            'selected': None,
            'finite': finite.run,
            'counter_or_fallback': counter_predict,
            'fixed_library': fitted_pred,
            'suffix3': lambda s, ex=train: d.suffix_majority(ex,s),
            'memorizer': lambda s, known=dict(train): known.get(s,False),
        }
        finite_val_errors = sum(finite.run(s) != y for s, y in val)
        counter_val_errors = sum(counter_predict(s) != y for s, y in val)
        chosen = 'counter_or_fallback' if counter and counter_val_errors < finite_val_errors else 'finite'
        models['selected'] = models[chosen]
        scores = {method: {split: metrics(pred, rows)
                   for split, rows in [('train', train), ('validation', val), ('holdout', hold)]}
                  for method,pred in models.items()}
        failures = [[s, int(y), int(models['selected'](s))] for s, y in hold
                    if bool(models['selected'](s)) != y]
        records.append({
            'id': task['id'], 'group': task['group'], 'source': task['source'],
            'split_hashes': {'train': d.sample_hash([s for s,_ in train]),
                             'validation': d.sample_hash([s for s,_ in val]),
                             'holdout': d.sample_hash(hold_words)},
            'finite': {'states':finite.reachable(), 'merges': attempts,
                       'automaton':finite.signature()},
            'counter': {'status':counter_info['status'], 'reason':counter_info['reason'],
                        'proposals':counter_info['proposal_attempts'],
                        'guards':counter_info['guard_attempts'],
                        'model': asdict(counter) if counter else None},
            'fixed_predicate': fitted_name,
            'selection': {'chosen': chosen, 'finite_validation_errors': finite_val_errors,
                          'counter_validation_errors': counter_val_errors,
                          'validation_margin': finite_val_errors-counter_val_errors,
                          'semantic_abstention': False},
            'scores': scores,
            'counterexamples': failures[:3],
            'holdout_labels': [int(y) for _,y in hold],
        })
    def mean(method, rows):
        return sum(r['scores'][method]['holdout']['accuracy'] for r in rows)/len(rows)
    primary = records[:20]
    best_fixed = max(mean('finite', primary), mean('counter_or_fallback', primary))
    selected = mean('selected', primary)
    high = sum(r['scores']['selected']['holdout']['accuracy'] >= .9 for r in primary)
    bound = all(r['scores']['selected']['holdout']['correct'] >= min(
                r['scores']['finite']['holdout']['correct'],
                r['scores']['counter_or_fallback']['holdout']['correct']) for r in primary)
    drift_abstentions = sum(r['selection']['semantic_abstention'] for r in records[20:])
    h5a = selected-best_fixed >= .05 and high >= 16 and bound
    h5b = drift_abstentions >= 3
    output = {
        'schema': 'r1-h5-1', 'seed': SEED,
        'protocol_commit': 'e53a98a95c1a5e26cebc65f23cdc6fc00086e84a',
        'training_labels': 1512, 'validation_labels': 4608,
        'holdout_labels': 3648, 'total_oracle_labels': 9768,
        'metrics': {'selected_mean':round(selected,6),
                    'finite_mean':round(mean('finite',primary),6),
                    'counter_mean':round(mean('counter_or_fallback',primary),6),
                    'best_fixed_mean':round(best_fixed,6),
                    'improvement_vs_best_fixed':round(selected-best_fixed,6),
                    'selected_tasks_at_90':high, 'drift_semantic_abstentions':drift_abstentions,
                    'h5a_pass':bool(h5a), 'h5b_pass':bool(h5b),
                    'combined_h5_go':bool(h5a and h5b)},
        'tasks':records,
        'scientific_status':'NOT_ASSESSED',
    }
    return output


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output')
    args=ap.parse_args()
    result=run_h5()
    if args.output:
        with open(args.output,'w',encoding='utf-8') as f:
            f.write(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'metrics':result['metrics'], 'selected':{
        'finite':sum(r['selection']['chosen']=='finite' for r in result['tasks']),
        'counter':sum(r['selection']['chosen']=='counter_or_fallback' for r in result['tasks'])},
        'failed':[(r['id'],r['group'],r['scores']['selected']['holdout']['accuracy'])
                  for r in result['tasks'] if r['scores']['selected']['holdout']['accuracy'] < .9]},sort_keys=True))


if __name__=='__main__':
    main()
