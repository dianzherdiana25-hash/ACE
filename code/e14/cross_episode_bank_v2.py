"""E1.4c-v2: preallocate unlabelled pools independently of hidden rule words.

Correction to v1: all pools are generated before the first word-conditioned
source or target demonstration. Per-task pool PRNGs are separately seeded from
family/role/pair slots, and never advanced by target oracle or demos.
"""

import hashlib
import json
import random
from dataclasses import dataclass

from e13.contract import canonical_json, parse_fit_request
from e13.evaluator.selection import input_key
from e14.query_bank import _used_public, oracle
from e14.query_replication import bank as previous_replication
from .cross_episode_bank import (
    FAMILIES, SEED, Task, _contains, _pairs, _random_events, _raw, bank as v1_bank,
)

POOL_SEED = 141711
DEMO_SEED = 141712


def _prior_inputs():
    used = _used_public()
    for prior in previous_replication():
        family = prior.episode.family
        request = json.loads(prior.episode.fit_request)
        used[family].update(input_key(family, demo["input"]) for demo in request["target"])
        used[family].update(prior.pool)
        used[family].update(p.input for p in (*prior.episode.in_distribution, *prior.episode.extrapolation))
    # Reserve the full earlier E1.4c-v1 public task inputs too. This fixed
    # historical inventory is independent of the v2 rule assignments.
    for source, target in v1_bank():
        for task in (source, target):
            family = task.family
            used[family].update(input_key(family, d["input"]) for d in task.demos)
            used[family].update(input_key(family, x) for x in task.pool)
            used[family].update(input_key(family, p["input"]) for p in task.probes)
    return used


def preallocate_pools(pairs):
    """No word/oracle/label access. Uses only the family and pair/role coordinates."""
    used = _prior_inputs()
    pools = {}
    for family in FAMILIES:
        for pair_id in range(6):
            for role_index, role in enumerate(("source", "target")):
                rng = random.Random(POOL_SEED + 100 * FAMILIES.index(family) + 2 * pair_id + role_index)
                pool = tuple(_raw(family, _random_events(family, rng, rng.randint(8, 14)),
                                  rng, used[family]) for _ in range(8))
                pools[family, role, pair_id] = pool
    return pools, used


def _make_task(family, regime, role, pair_id, word, pool, used):
    rng = random.Random(DEMO_SEED + 100 * FAMILIES.index(family) +
                        2 * pair_id + int(role == "target"))
    demos = []
    for _ in range(1000):
        if len(demos) == 2:
            break
        events = _random_events(family, rng, rng.randint(5, 8))
        if _contains(events, word):
            continue
        value = _raw(family, events, rng, used)
        demos.append({"input": value, "output": oracle(family, word, value)})
    if len(demos) != 2:
        raise ValueError("could not build two negative demonstrations")
    probes = []
    for i in range(8):
        if i % 2 == 0:
            if family == "S":
                events = (*_random_events(family, rng, rng.randint(1, 3)), *word)
            else:
                events = word if word[0] == 0 else (0, *word)
                events = (*events, *((1,) if i >= 4 else ()))
        else:
            for _ in range(256):
                events = _random_events(family, rng, rng.randint(6, 12))
                if not _contains(events, word):
                    break
            else:
                raise ValueError("could not construct a word-avoiding probe")
        value = _raw(family, events, rng, used)
        probes.append({"input": value, "output": oracle(family, word, value)})
    task_id = f"{rng.getrandbits(128):032x}"
    parse_fit_request(canonical_json({"version": 1, "task_id": task_id,
        "family": family, "seed": rng.getrandbits(32), "fuel": 75_000,
        "source": demos[:1], "target": demos}))
    return Task(family, regime, role, pair_id, word, task_id,
                tuple(demos), pool, tuple(probes))


def bank():
    pairs_by_family = {family: _pairs(family) for family in FAMILIES}
    pools, used = preallocate_pools(pairs_by_family)
    result = []
    for family in FAMILIES:
        for pair_id, (regime, source, target) in enumerate(pairs_by_family[family]):
            result.append((
                _make_task(family, regime, "source", pair_id, source,
                           pools[family, "source", pair_id], used[family]),
                _make_task(family, regime, "target", pair_id, target,
                           pools[family, "target", pair_id], used[family]),
            ))
    return tuple(result)


def bank_digest(pairs):
    return hashlib.sha256(canonical_json([
        [{"family": t.family, "regime": t.regime, "role": t.role,
          "pair": t.pair_id, "word": t.word, "task_id": t.task_id,
          "demos": t.demos, "pool": t.pool, "probes": t.probes}
         for t in pair] for pair in pairs])).hexdigest()
