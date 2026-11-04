"""Replicate one-label selection on unconditioned public question pools."""

import argparse
import hashlib
import json
import random
from itertools import permutations, product
from pathlib import Path

from e13.contract import canonical_json, parse_fit_request
from e13.evaluator.bank import Episode
from e13.evaluator.pilot import source_digest as e13_digest
from e13.evaluator.selection import input_key
from e13.evaluator.selection_budget import LIMITS
from e13.public_bank import Probe

from .pilot import source_digest
from .pilot_bank import WORDS
from .query_bank import (
    EXAMPLES, QueryCase, _subwords, _take, _used_public, bank as prior_query_bank, bank_digest, oracle,
)
from .query_pilot import _budget, _decision, _episode, _summary, deterministic
from .query_selector import QUERY_CPU_US, QUERY_STEPS, QUERY_WALL_US

SEED = 141611
POOL_SEED = 141612
REGIME = "unconditioned_pool"


def _words(family, rng):
    if family == "S":
        used = {*WORDS["S"], (0, 1, 2), (1, 0, 2), *(x[0] for x in EXAMPLES["S"])}
        available = [word for word in product(range(3), repeat=3)
                     if word[0] != word[1] and word not in used]
    else:
        available = list(WORDS["G"])
    rng.shuffle(available)
    return available[:6]


def _initial_traces(family, word, rng):
    if family == "S":
        return word, (word[1], word[0], word[2]), (word[-1],)
    positive = word if word[0] == 0 else (0, *word)
    rivals = sorted({(0, *order) for order in permutations(positive[1:])
                     if word not in _subwords((0, *order), len(word))})
    shorter = _subwords(positive, 2)
    negatives = [(0, *tail) for n in (4, 5, 6) for tail in product((1, 2), repeat=n)
                 if word not in _subwords((0, *tail), len(word))]
    coverage = [len(shorter & _subwords(trace, 2)) for trace in negatives]
    maximum = max(coverage)
    best = [trace for trace, score in zip(negatives, coverage, strict=True) if score == maximum]
    return positive, rng.choice(rivals), rng.choice(best)


def _pool(family, rng, used):
    """Generate queries without using the target word, oracle or predictions."""
    result = []
    for _ in range(8):
        length = rng.randint(2, 8)
        events = (tuple(rng.randrange(3) for _ in range(length)) if family == "S"
                  else (0, *(rng.randint(1, 2) for _ in range(length))))
        result.append(_take(family, events, rng, used))
    return tuple(result)


def _context_pair(family, word, positive, rival, pair, rng):
    if pair == 0:
        return positive, rival
    alphabet = (0, 1, 2) if family == "S" else (1, 2)
    n = 1 if pair == 1 else pair + 2
    contexts = [ctx for ctx in product(alphabet, repeat=n)
                if word not in _subwords(rival + ctx, len(word))]
    suffix = rng.choice(contexts)
    return positive + suffix, rival + suffix


def bank():
    rng, pool_rng = random.Random(SEED), random.Random(POOL_SEED)
    used = _used_public()
    for case in prior_query_bank():
        family = case.episode.family
        request = json.loads(case.episode.fit_request)
        used[family].update(input_key(family, d["input"]) for d in request["target"])
        used[family].update(case.pool)
        used[family].update(p.input for p in case.episode.in_distribution + case.episode.extrapolation)

    cases = []
    for family in ("S", "G"):
        for index, word in enumerate(_words(family, rng)):
            positive, rival, negative = _initial_traces(family, word, rng)
            demos = []
            for events in (positive, negative):
                value = json.loads(_take(family, events, rng, used[family]))
                demos.append({"input": value, "output": oracle(family, word, value)})
            pool = _pool(family, pool_rng, used[family])
            probes = []
            for pair in range(4):
                for events in _context_pair(family, word, positive, rival, pair, rng):
                    raw = _take(family, events, rng, used[family])
                    probes.append(Probe(raw, oracle(family, word, json.loads(raw))))
            request = canonical_json({
                "version": 1, "family": family, "task_id": f"{rng.getrandbits(128):032x}",
                "seed": rng.getrandbits(32), "fuel": 75_000, "source": demos[:1], "target": demos,
            })
            parse_fit_request(request)
            episode = Episode(family, REGIME, "unused", f"{family}-replication-{index}",
                              request, tuple(probes[:4]), tuple(probes[4:]))
            cases.append(QueryCase(episode, pool, word))
    return tuple(cases)


def run():
    cases = bank()
    rows = [_episode(case) for case in cases]
    summary = _summary(rows, regimes=(REGIME,))
    budget = _budget(rows)
    decision = "hold_for_resource_review" if any(
        budget[key] for key in ("selector_caps", "fit_caps", "prediction_caps")
    ) else _decision(summary, primary_regime=REGIME)
    if decision == "go_to_public_replication":
        decision = "go_to_cross_episode_development"
    return {
        "mode": "public_development_replication", "scope": "unconditioned pools, short words, graph chains",
        "bank_sha256": bank_digest(cases),
        "source_sha256": hashlib.sha256(canonical_json([e13_digest(), source_digest()])).hexdigest(),
        "bank_seed": SEED, "pool_seed": POOL_SEED, "episodes": len(cases),
        "isolated_fits": sum(3 + len(row["uniform_one_label_arms"]) for row in rows),
        "limits": {**LIMITS, "query_steps": QUERY_STEPS, "query_cpu_us": QUERY_CPU_US,
                   "query_wall_us": QUERY_WALL_US},
        "summary": summary, "budget": budget, "decision": decision, "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    report = run()
    if args.verify is not None and deterministic(report) != deterministic(json.loads(args.verify.read_text())):
        raise ValueError("query replication replay differs")
    print(json.dumps(report, separators=(",", ":")))


if __name__ == "__main__":
    main()
