"""ACE R7.5 standalone, bounded, deterministic public synthetic experiment.

All candidate-selection policies consume only evaluator-purchased labels, never
latent probabilities or evaluator-only scoring probes. The sequential likelihood
ratio supports per-selected-candidate null control only under IID Bernoulli.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from functools import lru_cache

SEED_TRAIN = 20261108
FINAL_SEEDS = (20261109, 20261110, 20261111)
P0 = 0.80
ALPHA = 0.10
THRESHOLD = 1 / ALPHA
GROUPS = 6
BUDGETS = (0, 6, 12, 18, 24)
FAMILIES = {
    "stable": (.18, .42, .63, .78, .91, .97),
    "swap": (.91, .19, .36, .54, .33, .72),
    "reverse": (.90, .79, .29, .39, .17, .12),
    "new01": (.86, .94, .22, .68, .14, .24),
    "new23": (.21, .34, .96, .91, .27, .11),
    "all_null": (.55, .62, .70, .73, .75, .77),
    "correlated": (.18, .42, .63, .78, .91, .97),
}
METHODS = (
    "full099", "narrow099", "narrow096", "full096",
    "random099", "diag_abstain",
)
FULL_SEQUENCE = tuple(range(GROUPS)) * 2
NARROW_SEQUENCE = (0, 4, 5, 0, 4, 5)


def checksum(x: object) -> str:
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def rand_for(*parts: object) -> random.Random:
    return random.Random(int(checksum(parts), 16))


@dataclass(frozen=True)
class World:
    uid: str
    family: str
    p: tuple[float, ...]  # private to evaluator and offline audit only


def worlds(split: str, family: str, seed: int, count: int) -> tuple[World, ...]:
    if family not in FAMILIES or split not in ("train", "validation", "test"):
        raise ValueError("invalid split/family")
    if split in ("train", "validation") and (family != "stable" or seed != SEED_TRAIN):
        raise ValueError("source world split is fixed")
    if split == "test" and seed not in FINAL_SEEDS:
        raise ValueError("unknown final seed")
    if type(count) is not int or not 1 <= count <= 1000:
        raise ValueError("invalid task count")
    out = []
    for i in range(count):
        rng = rand_for("r75-new-world", split, family, seed, i)
        p = tuple(max(.01, min(.99, x + rng.uniform(-.09, .09))) for x in FAMILIES[family])
        if family == "all_null":
            p = tuple(min(.799, x) for x in p)
        out.append(World(f"r75:{split}:{family}:{seed}:{i}", family, p))
    return tuple(out)


@lru_cache(maxsize=1024)
def _scored_truth(uid: str, probabilities: tuple[float, ...]) -> tuple[int, ...]:
    """Cache evaluator-only probe outcomes; byte-identical to uncached draws.

    This pure cache changes runtime cost, NOT split, policy, scoring, or labels.
    """
    return tuple(int(rand_for("r75-score", uid, g, j).random() < probabilities[g])
                 for g in range(GROUPS) for j in range(64))


class Evaluator:
    def __init__(self, world: World, max_labels: int):
        self._world = world
        self._cap = max_labels
        self._groups = [0] * GROUPS
        self.purchases = 0

    def buy(self, g: int) -> int:
        if type(g) is not int or not 0 <= g < GROUPS:
            raise ValueError("invalid group")
        if self.purchases >= self._cap:
            raise RuntimeError("label cap exhausted")
        index = self._groups[g]
        self._groups[g] += 1
        self.purchases += 1
        if self._world.family == "correlated":
            index //= 2  # correlated repeated observations violate iid
        r = rand_for("r75-purchase", self._world.uid, g, index).random()
        return int(r < self._world.p[g])

    def oracle_ceiling(self) -> int:
        """Privileged scoring only; decision makers NEVER call this."""
        return sum(p >= P0 for p in self._world.p)

    def grade(self, accepted_group: int | None, estimates: tuple[float, ...]) -> dict:
        if accepted_group is not None and (type(accepted_group) is not int or
                                           not 0 <= accepted_group < GROUPS):
            raise ValueError("invalid decision")
        if len(estimates) != GROUPS or any(not 0 <= p <= 1 for p in estimates):
            raise ValueError("invalid estimates")
        y = _scored_truth(self._world.uid, self._world.p)
        q = [estimates[g] for g in range(GROUPS) for _ in range(64)]
        bins = [[0., 0., 0] for _ in range(10)]
        brier = 0.
        for p, label in zip(q, y):
            k = min(9, int(p * 10))
            bins[k][0] += p
            bins[k][1] += label
            bins[k][2] += 1
            brier += (p-label)**2
        correct = int(accepted_group is not None and self._world.p[accepted_group] >= P0)
        false = int(accepted_group is not None and self._world.p[accepted_group] < P0)
        return dict(true_accepts=correct, false_accepts=false,
                    abstained=GROUPS - correct-false, purchases=self.purchases,
                    brier_sum=brier, bins=bins, scored_probes=len(y))


def fit_source_prior() -> tuple[tuple[float, ...], int]:
    success = [1] * GROUPS
    count = [2] * GROUPS
    paid = 0
    for w in worlds("train", "stable", SEED_TRAIN, 18):
        evalr = Evaluator(w, 72)
        for g in range(GROUPS):
            for _ in range(12):
                success[g] += evalr.buy(g)
                count[g] += 1
                paid += 1
    return tuple(s/n for s, n in zip(success, count)), paid


def select_candidate(observed: tuple[tuple[int, int], ...], prior: tuple[float, ...],
                     permitted: tuple[int, ...]) -> int:
    if len(prior) != GROUPS or len(observed) != 2*len(permitted):
        raise ValueError("incomplete diagnostic sequence")
    if len(set(permitted)) != len(permitted) or any(not 0 <= g < GROUPS for g in permitted):
        raise ValueError("invalid candidate group set")
    totals = {g: 0 for g in permitted}
    expected = permitted * 2
    for (g, label), x in zip(observed, expected):
        if type(g) is not int or g != x or type(label) is not int or label not in (0, 1):
            raise ValueError("invalid diagnostic reply")
        totals[g] += label
    return max(permitted, key=lambda g: (totals[g], prior[g], -g))


def multiplier(label: int, p1: float) -> float:
    if type(label) is not int or label not in (0, 1) or p1 not in (.96, .99):
        raise ValueError("invalid e-step")
    return p1/P0 if label else (1-p1)/(1-P0)


def null_expectation(p: float, p1: float) -> float:
    if not 0 <= p <= 1:
        raise ValueError("invalid hypothetical null")
    return p*multiplier(1,p1) + (1-p)*multiplier(0,p1)


@dataclass(frozen=True)
class Trace:
    grade: dict
    selected: int | None
    diag_count: int
    cert_count: int
    e_final: float
    certified: bool


def play(world: World, prior: tuple[float, ...], method: str, cap: int) -> Trace:
    if method not in METHODS or cap not in BUDGETS:
        raise ValueError("unsupported method or cap")
    evaluator = Evaluator(world, cap)
    narrow = method.startswith("narrow")
    sequence = NARROW_SEQUENCE if narrow else FULL_SEQUENCE
    permitted = (0, 4, 5) if narrow else tuple(range(GROUPS))
    alpha = 1.0 + 12*0  # Posterior parameters use weak Beta(1,1) plus counts
    successes = [0] * GROUPS
    counts = [0] * GROUPS
    observations = []
    for g in sequence[:cap]:
        y = evaluator.buy(g)
        successes[g] += y
        counts[g] += 1
        observations.append((g, y))
    chosen = None
    if len(observations) == len(sequence):
        if method == "random099":
            chosen = rand_for("r75-random-select", world.uid).randrange(GROUPS)
        else:
            chosen = select_candidate(tuple(observations), prior, permitted)
    e_value = 1.0
    cert_count = 0
    certified = False
    p1 = .96 if method.endswith("096") else .99
    if method != "diag_abstain" and chosen is not None:
        while evaluator.purchases < cap:
            y = evaluator.buy(chosen)
            successes[chosen] += y
            counts[chosen] += 1
            cert_count += 1
            e_value *= multiplier(y, p1)
            if cert_count >= 3 and e_value >= THRESHOLD:
                certified = True
                break
    decision = chosen if certified else None
    estimates = tuple((1+successes[g])/(2+counts[g]) for g in range(GROUPS))
    graded = evaluator.grade(decision, estimates)
    return Trace(graded, chosen, len(observations), cert_count, e_value, certified)


def summarize(tasks: tuple[World, ...], prior: tuple[float, ...],
              method: str, cap: int) -> dict:
    traces = [play(w, prior, method, cap) for w in tasks]
    bins = [[0., 0., 0] for _ in range(10)]
    for rec in traces:
        for k in range(10):
            for j in range(3):
                bins[k][j] += rec.grade['bins'][k][j]
    n = sum(x.grade['scored_probes'] for x in traces)
    agg = {key: sum(t.grade[key] for t in traces) for key in
           ('true_accepts','false_accepts','abstained','purchases')}
    accepted = agg['true_accepts']+agg['false_accepts']
    agg.update(tasks=len(tasks), label_cap=cap,
               ece=round(sum(abs(p-y) for p,y,c in bins if c)/n, 6),
               brier=round(sum(t.grade['brier_sum'] for t in traces)/n, 6),
               false_acceptance_rate=round(agg['false_accepts']/accepted, 6) if accepted else None,
               correct_per_100_labels=round(100*agg['true_accepts']/agg['purchases'], 6)
                                      if agg['purchases'] else None,
               diagnostic_labels=sum(t.diag_count for t in traces),
               certificate_labels=sum(t.cert_count for t in traces),
               certified_tasks=sum(t.certified for t in traces),
               selected_groups={str(g):sum(t.selected == g for t in traces)
                                for g in range(GROUPS)})
    agg['utility'] = 20*agg['true_accepts']-60*agg['false_accepts']-2*agg['abstained']-agg['purchases']
    return agg


def validation() -> dict:
    prior, train_cost = fit_source_prior()
    bank = worlds("validation", "stable", SEED_TRAIN, 12)
    return dict(status="VALIDATION_ONLY", prior=prior, train_offline_labels=train_cost,
                results={method:summarize(bank,prior,method,24) for method in METHODS})


def final_once() -> dict:
    prior, train_cost = fit_source_prior()
    outcomes = {}
    manifest = {}
    for family in FAMILIES:
        outcomes[family] = {}
        manifest[family] = {}
        for seed in FINAL_SEEDS:
            bank = worlds("test", family, seed, 24)
            manifest[family][str(seed)] = checksum([w.uid for w in bank])
            rows = {}
            for cap in BUDGETS:
                rows[str(cap)] = {name:summarize(bank,prior,name,cap) for name in METHODS}
            outcomes[family][str(seed)] = rows
    def summed(family: str, method: str, field: str) -> int:
        return sum(outcomes[family][str(seed)]["24"][method][field] for seed in FINAL_SEEDS)
    shifted = ("swap", "reverse", "new01", "new23")
    a,b='full099','narrow099'
    gate = {
        'new23_correct_better':summed('new23',a,'true_accepts') > summed('new23',b,'true_accepts'),
        'coverage_nondecrease_3_of_4':sum(summed(f,a,'true_accepts') >= summed(f,b,'true_accepts') for f in shifted)>=3,
        'all_null_wrong_nondecrease':summed('all_null',a,'false_accepts') <= summed('all_null',b,'false_accepts'),
        'five_family_utility_nondecrease':sum(summed(f,a,'utility') for f in ('stable',*shifted)) >=
                                         sum(summed(f,b,'utility') for f in ('stable',*shifted)),
        'online_caps_and_one_certificate':all(
            outcomes[f][str(seed)][str(cap)][name]['purchases'] <=24*cap and
            outcomes[f][str(seed)][str(cap)][name]['certified_tasks'] <=24
            for f in FAMILIES for seed in FINAL_SEEDS for cap in BUDGETS for name in METHODS),
    }
    return dict(status='PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY', seed_train=SEED_TRAIN,
                seeds=FINAL_SEEDS, protocol='R75_PROTOCOL.md', training_labels=train_cost,
                source_prior=prior, split_id_hashes=manifest, by_family_seed=outcomes,
                locked_gate=gate, locked_gate_pass=all(gate.values()),
                scientific_decision='HOLD_NOT_INDEPENDENTLY_CONFIRMED',
                evaluator_only_oracle_ceiling={family:{str(seed):sum(w.p[g]>=P0 for w in worlds('test',family,seed,24) for g in range(GROUPS)) for seed in FINAL_SEEDS} for family in FAMILIES},
                caveats=['public synthetic seeded mechanism families',
                         'in-process evaluator not independently sealed',
                         'e-value conditional IID Bernoulli assumption violated by correlated family',
                         'single selected candidate per task; not global familywise error control',
                         'all scoring outcomes now development-visible; never retune on this bank'])


def main() -> None:
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--phase',required=True,choices=('validation','final'))
    args=parser.parse_args()
    print(json.dumps(validation() if args.phase == 'validation' else final_once(),
                     indent=2,sort_keys=True,allow_nan=False))


if __name__ == '__main__':
    main()
