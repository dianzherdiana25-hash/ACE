"""E1.4c candidate-only finite hypothesis learner and unlabeled query policies.

Does not import the evaluator or its hidden target word/oracle. Any policy
selection that uses source outcomes is performed outside this module.
"""

from __future__ import annotations

import random
from collections import Counter
from itertools import pairwise, product

POLICIES = (
    "first_disagreement", "last_disagreement", "short_disagreement",
    "long_disagreement", "max_partition", "min_partition",
    "seeded_disagreement", "seeded_uniform",
)


def inventory(family):
    if family == "S":
        return tuple(product(range(3), repeat=4))
    if family == "G":
        return tuple((0, *tail) for tail in product((1, 2), repeat=3)) + tuple(
            product((1, 2), repeat=4)
        )
    raise ValueError("unknown family")


def events_for(family, value):
    if family == "S":
        return tuple(0 if a < b else 1 if a == b else 2 for a, b in pairwise(value))
    if family != "G":
        raise ValueError("unknown family")
    edges = sorted(value["edges"])
    if (not edges or len(edges) + 1 != value["nodes"] or
            value["start"] != 0 or value["goal"] != len(edges) or
            any(edge[0] != i or edge[1] != i + 1 for i, edge in enumerate(edges))):
        raise ValueError("expected a single graph chain")
    labels = [edge[2] for edge in edges]
    return (0,) + tuple(1 if a == b else 2 for a, b in pairwise(labels))


def predict(family, word, value):
    events = events_for(family, value)
    matching = [events[i:i + len(word)] == word
                for i in range(max(0, len(events) - len(word) + 1))]
    if family == "S":
        return tuple(int(i >= len(word) and matching[i-len(word)])
                     for i in range(1, len(events)+1))
    return sum(edge[3] for edge in value["edges"]) if any(matching) else None


def fit(family, demos):
    """Fit finite 4-event grammar using target-visible examples only."""
    words = inventory(family)
    scored = [(sum(predict(family, word, d["input"]) == d["output"]
                   for d in demos), word) for word in words]
    best_score = max(score for score, _ in scored)
    candidates = tuple(word for score, word in scored if score == best_score)
    return candidates, best_score


def _size(family, raw):
    return len(raw) if family == "S" else len(raw["edges"])


def choose(policy, family, candidates, pool, *, seed):
    """Choose a query from *unlabeled* inputs and fitted hypotheses only."""
    if policy not in POLICIES or not candidates or len(pool) != 8:
        raise ValueError("invalid query policy or candidate set")
    rng = random.Random(seed)
    if policy == "seeded_uniform":
        return rng.randrange(len(pool)), "uniform"
    predictions = [[predict(family, word, value) for word in candidates]
                   for value in pool]
    mixed = [i for i, values in enumerate(predictions) if len(set(values)) > 1]
    if not mixed:
        return rng.randrange(len(pool)), "no_disagreement"
    if policy == "first_disagreement":
        return mixed[0], "disagreement"
    if policy == "last_disagreement":
        return mixed[-1], "disagreement"
    if policy == "short_disagreement":
        return min(mixed, key=lambda i: (_size(family,pool[i]),i)), "disagreement"
    if policy == "long_disagreement":
        return min(mixed, key=lambda i: (-_size(family,pool[i]),i)), "disagreement"
    if policy == "seeded_disagreement":
        return rng.choice(mixed), "disagreement"
    # Gini impurity of predicted output partitions; values are program outputs,
    # not oracle labels. For S predictions are tuples; for G integer/None.
    partition = {}
    for i in mixed:
        counts = Counter(predictions[i]).values()
        n = len(candidates)
        partition[i] = n*n - sum(count*count for count in counts)
    if policy == "max_partition":
        return min(mixed, key=lambda i: (-partition[i],i)), "disagreement"
    return min(mixed, key=lambda i: (partition[i],i)), "disagreement"
