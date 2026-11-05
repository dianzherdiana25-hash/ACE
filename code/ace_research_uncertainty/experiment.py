"""Bounded synthetic uncertainty, selective prediction, and active label acquisition.

No network, paid oracles, dynamic code execution, source mutation, or holdout tuning.
The oracle policy is evaluation-only and is NEVER passed to the acquisition code.
This is a public-development synthetic benchmark, not independent OAIE evidence.
Run: PYTHONPATH=code python3 -m ace_research_uncertainty.experiment
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import random
from typing import NamedTuple

SEED = 20261105
GROUPS = 6
TARGET_ACCURACY = 0.80
BUDGETS = (0, 6, 12, 24)
STABLE = (0.18, 0.42, 0.63, 0.78, 0.91, 0.97)
SHIFT = (0.91, 0.19, 0.36, 0.54, 0.33, 0.72)
METHODS = ('fixed', 'random', 'random_lcb', 'active_lcb')


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def rng_for(*parts: object) -> random.Random:
    return random.Random(int(digest(parts), 16))


class Task(NamedTuple):
    uid: str
    family: str
    probabilities: tuple[float, ...]


def make_tasks(split: str, family: str, n: int) -> tuple[Task, ...]:
    if split not in ('train', 'validation', 'test', 'ood'):
        raise ValueError('invalid split')
    if (split == 'ood') != (family == 'shift'):
        raise ValueError('shift must be isolated in ood split')
    if not 1 <= n <= 1000:
        raise ValueError('invalid task count')
    base = SHIFT if family == 'shift' else STABLE
    result = []
    for i in range(n):
        r = rng_for(SEED, 'world', split, family, i)
        p = tuple(min(.99, max(.01, x + r.uniform(-.09, .09))) for x in base)
        result.append(Task(f'{split}:{family}:{i}', family, p))
    return tuple(result)


class Evaluator:
    """Owner of hidden truth; the policy sees only query replies.

    Python object separation is not a security sandbox. Evaluation uses a
    different pseudorandom namespace from acquired labels.
    """
    def __init__(self, task: Task, cap: int):
        self._task = task
        self._cap = cap
        self._counts = [0] * GROUPS
        self.purchases = 0

    def query(self, group: int) -> int:
        if type(group) is not int or not 0 <= group < GROUPS:
            raise ValueError('invalid query')
        if self.purchases >= self._cap:
            raise RuntimeError('label budget exceeded')
        offset = self._counts[group]
        self._counts[group] += 1
        self.purchases += 1
        return int(rng_for(SEED, 'purchase', self._task.uid, group, offset).random()
                   < self._task.probabilities[group])

    def score(self, means: tuple[float, ...], accept: tuple[bool, ...]) -> dict:
        if len(means) != GROUPS or len(accept) != GROUPS:
            raise ValueError('invalid prediction shape')
        if any(not math.isfinite(m) or not 0 <= m <= 1 for m in means):
            raise ValueError('invalid probability')
        y, probs = [], []
        for g in range(GROUPS):
            for k in range(64):
                y.append(int(rng_for(SEED, 'sealed-eval', self._task.uid, g, k).random()
                             < self._task.probabilities[g]))
                probs.append(means[g])
        return {
            'false_accepts': sum(bool(accept[g]) and p < TARGET_ACCURACY
                                 for g, p in enumerate(self._task.probabilities)),
            'true_accepts': sum(bool(accept[g]) and p >= TARGET_ACCURACY
                                for g, p in enumerate(self._task.probabilities)),
            'abstentions': sum(not a for a in accept),
            'purchases': self.purchases,
            'brier_sum': sum((p - t)**2 for p, t in zip(probs, y)),
            'calibration': [(sum(p for p in probs if min(9, int(p * 10)) == b),
                             sum(t for p, t in zip(probs, y) if min(9, int(p * 10)) == b),
                             sum(min(9, int(p * 10)) == b for p in probs)) for b in range(10)],
            'evaluated_labels': len(y),
        }

    def oracle_upper_bound(self) -> dict:
        """Privileged offline bound, never offered to a learner."""
        true = sum(p >= TARGET_ACCURACY for p in self._task.probabilities)
        return {'true_accepts': true, 'false_accepts': 0,
                'abstentions': GROUPS - true, 'purchases': 0}


@dataclass(frozen=True)
class Config:
    strength: int
    z: float

    def __post_init__(self):
        if type(self.strength) is not int or self.strength not in (0, 2, 6, 12):
            raise ValueError('invalid prior strength')
        if type(self.z) is not float or self.z not in (1.0, 1.64, 2.33):
            raise ValueError('invalid uncertainty threshold')


class Belief:
    def __init__(self, prior: tuple[float, ...], config: Config):
        if len(prior) != GROUPS or any(not 0 < p < 1 for p in prior):
            raise ValueError('invalid prior')
        self.a = [1 + config.strength * p for p in prior]
        self.b = [1 + config.strength * (1-p) for p in prior]
        self.counts = [0] * GROUPS

    def observe(self, group: int, label: int):
        if label not in (0, 1) or type(label) is not int:
            raise ValueError('invalid label')
        self.a[group] += label
        self.b[group] += 1 - label
        self.counts[group] += 1

    def mean(self, group: int) -> float:
        return self.a[group] / (self.a[group] + self.b[group])

    def sd(self, group: int) -> float:
        a, b = self.a[group], self.b[group]
        return math.sqrt(a*b / ((a+b)**2 * (a+b+1)))

    def accept(self, g: int, method: str, z: float) -> bool:
        if self.counts[g] < 3:
            return False
        if method in ('fixed', 'random'):
            return self.mean(g) >= TARGET_ACCURACY
        return self.mean(g) - z * self.sd(g) >= TARGET_ACCURACY


def fit_prior(tasks: tuple[Task, ...], labels_per_group: int = 12) -> tuple[tuple[float, ...], int]:
    if any(t.family != 'stable' or not t.uid.startswith('train:') for t in tasks):
        raise ValueError('prior fit must use train tasks only')
    wins = [1] * GROUPS
    count = [2] * GROUPS
    for t in tasks:
        evaluator = Evaluator(t, GROUPS * labels_per_group)
        for g in range(GROUPS):
            for _ in range(labels_per_group):
                wins[g] += evaluator.query(g)
                count[g] += 1
    return tuple(w / n for w, n in zip(wins, count)), len(tasks) * GROUPS * labels_per_group


def choose_group(b: Belief, method: str, step: int, task_id: str) -> int:
    if method == 'fixed':
        return step % GROUPS
    if method in ('random', 'random_lcb'):
        return rng_for(SEED, 'choice', task_id, method.replace('_lcb', ''), step).randrange(GROUPS)
    if method != 'active_lcb':
        raise ValueError('invalid learner method')
    # Fully observation-based uncertainty acquisition. Avoid omniscient labels:
    # score high variance, near-target posterior, and groups not yet visited.
    score = []
    for g in range(GROUPS):
        closeness = max(0, 1 - abs(b.mean(g)-TARGET_ACCURACY) / TARGET_ACCURACY)
        width = b.sd(g)
        score.append((width * (0.4 + 0.6 * closeness) +
                      0.035 / (1 + b.counts[g]), -b.counts[g], -g))
    return max(range(GROUPS), key=lambda g: score[g])


def simulate(task: Task, prior: tuple[float, ...], method: str,
             config: Config, budget: int) -> dict:
    if method not in METHODS or budget not in BUDGETS:
        raise ValueError('invalid method or budget')
    evaluator = Evaluator(task, budget)
    belief = Belief(prior, config)
    for step in range(budget):
        group = choose_group(belief, method, step, task.uid)
        belief.observe(group, evaluator.query(group))
    means = tuple(belief.mean(g) for g in range(GROUPS))
    accept = tuple(belief.accept(g, method, config.z) for g in range(GROUPS))
    return evaluator.score(means, accept)


def aggregate(tasks: tuple[Task, ...], prior: tuple[float, ...],
              method: str, config: Config, budget: int) -> dict:
    rows = [simulate(t, prior, method, config, budget) for t in tasks]
    if not rows:
        raise ValueError('empty eval split')
    bins = [[0., 0., 0] for _ in range(10)]
    for r in rows:
        for j, tup in enumerate(r['calibration']):
            for k in range(3):
                bins[j][k] += tup[k]
    n = sum(r['evaluated_labels'] for r in rows)
    ece = sum(abs(a/c - y/c)*c/n for a, y, c in bins if c)
    total = {k: sum(r[k] for r in rows) for k in ('false_accepts', 'true_accepts',
                                                    'abstentions', 'purchases')}
    total.update({'tasks': len(tasks), 'budget_per_task': budget,
                  'brier': round(sum(r['brier_sum'] for r in rows) / n, 6),
                  'ece': round(ece, 6),
                  'false_acceptance_rate': round(total['false_accepts'] /
                         max(1, total['false_accepts']+total['true_accepts']), 6),
                  'correct_accepts_per_100_labels': round(100*total['true_accepts'] /
                         max(1, total['purchases']), 6)})
    return total


def tune(prior: tuple[float, ...], validation: tuple[Task, ...]) -> tuple[Config, list[dict]]:
    if any(not t.uid.startswith('validation:stable:') for t in validation):
        raise ValueError('validation split required')
    candidates = []
    for strength in (0, 2, 6, 12):
        for z in (1.0, 1.64, 2.33):
            c = Config(strength, z)
            row = aggregate(validation, prior, 'active_lcb', c, 24)
            # Predeclared asymmetric loss; no OOD/test examples used.
            utility = 20*row['true_accepts']-60*row['false_accepts']-2*row['abstentions']
            candidates.append({'config': {'strength': strength, 'z': z},
                               'validation_utility': utility, 'ece': row['ece'],
                               'wrong': row['false_accepts'], 'right': row['true_accepts']})
    best = max(candidates, key=lambda r:(r['validation_utility'], -r['ece'],
                                         -r['config']['strength'], -r['config']['z']))
    return Config(**best['config']), candidates


def run() -> dict:
    train = make_tasks('train', 'stable', 30)
    validation = make_tasks('validation', 'stable', 12)
    test = make_tasks('test', 'stable', 20)
    ood = make_tasks('ood', 'shift', 20)
    ids = [t.uid for split in (train, validation, test, ood) for t in split]
    assert len(ids) == len(set(ids))
    prior, offline_training_labels = fit_prior(train)
    cfg, search = tune(prior, validation)
    locked = {'seed': SEED, 'target': TARGET_ACCURACY, 'budgets': BUDGETS,
              'prior': prior, 'selected': {'strength': cfg.strength, 'z': cfg.z},
              'split_ids_sha256': {name: digest([t.uid for t in ts]) for name, ts in
                                    (('train',train),('validation',validation),('test',test),('ood',ood))}}
    outcome = {}
    for name, split in (('test', test), ('ood', ood)):
        outcome[name] = {}
        for budget in BUDGETS:
            outcome[name][str(budget)] = {
                method: aggregate(split, prior, method,
                                  cfg if method.endswith('_lcb') else Config(0, 1.0), budget)
                for method in METHODS}
        oracle_rows = [Evaluator(t, 0).oracle_upper_bound() for t in split]
        outcome[name]['oracle_upper_bound'] = {k:sum(row[k] for row in oracle_rows)
                         for k in ('true_accepts','false_accepts','abstentions','purchases')}
    return {
        'status':'PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY_NOT_SCIENTIFIC_GO',
        'research_question':'does uncertainty-aware acquisition reduce false capability acceptance?',
        'lock': locked, 'lock_sha256': digest(locked),
        'offline_training_labels': offline_training_labels,
        'validation_tasks': len(validation), 'validation_tuning_evaluations': len(search),
        'validation_search': search, 'results': outcome,
        'oracle_privilege':'evaluation_only_true_probabilities',
        'limitations':['no external evaluator or independent confirmation',
                       'same six observable strata; OOD changes hidden reliabilities',
                       'synthetic label processes not real model outputs',
                       'public seed and in-process evaluator not a secure sealed holdout',
                       'hyperparameter selection only on validation; never on test or OOD',
                       'offline training labels charged separately from online purchases'],
    }


def main() -> None:
    record = run()
    print(json.dumps(record, sort_keys=True, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
