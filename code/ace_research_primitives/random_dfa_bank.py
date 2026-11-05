"""R1 H2: precommitted fresh task-family test on seeded random target DFAs."""
from __future__ import annotations
import argparse
import json
import random
try:
    from . import primitive_discovery as d
except ImportError:
    import primitive_discovery as d


def run_target(target, word):
    transition, accept = target
    state = 0
    for c in word:
        state = transition[state][0 if c == 'a' else 1]
    return bool(accept[state])


def source_reachable(target):
    transition, _ = target
    seen = {0}
    frontier = [0]
    while frontier:
        i = frontier.pop()
        for j in transition[i]:
            if j not in seen:
                seen.add(j)
                frontier.append(j)
    return len(seen)


def new_tasks():
    train = d.training_words()
    chosen = []
    seen_train = set()
    for n in (2, 3, 4, 5):
        found = 0
        for attempt in range(10000):
            rng = random.Random(d.SEED + 1000 + n * 100 + attempt)
            target = ([tuple(rng.randrange(n) for _ in d.ALPHABET) for _ in range(n)],
                      [rng.randrange(2) for _ in range(n)])
            if source_reachable(target) != n:
                continue
            labels = tuple(run_target(target, word) for word in train)
            if not .2 <= sum(labels) / len(labels) <= .8 or labels in seen_train:
                continue
            seen_train.add(labels)
            chosen.append((n, attempt, target))
            found += 1
            if found == 6:
                break
        if found != 6:
            raise RuntimeError('target bank construction exhausted')
    return chosen


def run_h2():
    cases = []
    preds = d.fixed_predicates()
    train_words = d.training_words()
    val_words = d.validation_words()
    for i, (n, attempt, target) in enumerate(new_tasks()):
        judge = lambda s, target=target: run_target(target, s)
        hold_words = d.heldout_regular(100 + i)
        train = [(s, judge(s)) for s in train_words]
        val = [(s, judge(s)) for s in val_words]
        holdout = [(s, judge(s)) for s in hold_words]
        model, merges = d.infer(train)
        fixed_name, fixed = min(preds, key=lambda item: sum(item[1](s) != y for s, y in train))
        methods = {'induced': model.run,
                   'memorizer': lambda s, lookup=dict(train): lookup.get(s, False),
                   'suffix3': lambda s, examples=train: d.suffix_majority(examples, s),
                   'fixed_library': fixed}
        scores = {k: {'train': d.metric(p, train), 'validation': d.metric(p, val),
                      'holdout': d.metric(p, holdout)} for k, p in methods.items()}
        cases.append({'task_id': i, 'nominal_states': n, 'target_draw_attempt': attempt,
                      'target_transitions': target[0], 'target_accepting': target[1],
                      'train_signature': d.sample_hash([int(y) for _, y in train]),
                      'holdout_sha256': d.sample_hash(hold_words),
                      'inferred_states': model.reachable(), 'merge_attempts': merges,
                      'fixed_predicate': fixed_name, 'scores': scores,
                      'induced_counterexample': next(([s, int(y), int(model.run(s))]
                          for s, y in holdout if model.run(s) != y), None)})
    def avg(model):
        return sum(r['scores'][model]['holdout']['accuracy'] for r in cases) / len(cases)
    induced = avg('induced')
    oracle = sum(max(r['scores'][m]['holdout']['accuracy'] for m in
                      ('memorizer', 'suffix3', 'fixed_library')) for r in cases) / len(cases)
    successes = sum(r['scores']['induced']['holdout']['accuracy'] >= .9 for r in cases)
    return {'schema': 'r1-h2-0.1', 'seed': d.SEED, 'tasks': cases,
            'total_train_labels': 24 * 63, 'total_all_labels': 24 * 511,
            'primary': {'induced_mean': round(induced, 6), 'per_task_oracle_baseline': round(oracle, 6),
                        'gain_vs_oracle': round(induced-oracle, 6), 'tasks_at_90': successes,
                        'h2_passed': induced - oracle >= .05 and successes >= 16},
            'scientific_status': 'NOT_ASSESSED'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output')
    args = parser.parse_args()
    r = run_h2()
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(json.dumps(r, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'primary': r['primary'],
                      'cases': [{'id': t['task_id'], 'states': t['nominal_states'],
                                 'accuracy': t['scores']['induced']['holdout']['accuracy'],
                                 'oracle': max(t['scores'][m]['holdout']['accuracy'] for m in
                                               ('memorizer', 'suffix3', 'fixed_library'))}
                                for t in r['tasks']]}, sort_keys=True))


if __name__ == '__main__':
    main()
