"""Parameterized task family generators with count-matched adversarial negatives (W2)."""
from __future__ import annotations

import random
from typing import List, Tuple

TASK_FAMILIES = [
    "counter_ratio",
    "parity",
    "boundary",
    "graph",
    "an_bn",
    "sequence",
]


def _generate_boundary_instances(rng: random.Random, count: int) -> List[Tuple[str, bool]]:
    """Generates strings starting with 'a' and ending with 'b', with count-matched negatives."""
    half = count // 2
    instances: List[Tuple[str, bool]] = []

    for _ in range(half):
        inner_len = rng.randint(1, 8)
        inner = "".join(rng.choice(["a", "b"]) for _ in range(inner_len))
        pos_word = "a" + inner + "b"
        instances.append((pos_word, True))

        # Count-matched negative: swap first and last if needed so it starts with 'b' or ends with 'a'
        # with identical total 'a' and 'b' counts
        chars = list(pos_word)
        # To make it negative without changing character counts, swap endpoints
        chars[0], chars[-1] = "b", "a"
        neg_word = "".join(chars)
        # Verify it is indeed negative
        if neg_word.startswith("a") and neg_word.endswith("b"):
            # Fallback if inner allows: reverse
            neg_word = pos_word[::-1]
            if neg_word.startswith("a") and neg_word.endswith("b"):
                neg_word = "b" + inner + "a"
        instances.append((neg_word, False))

    rng.shuffle(instances)
    return instances


def _generate_an_bn_instances(rng: random.Random, count: int) -> List[Tuple[str, bool]]:
    """Generates a^n b^n instances with count-matched permutation negatives."""
    half = count // 2
    instances: List[Tuple[str, bool]] = []

    for i in range(half):
        n = (i % 8) + 1
        pos_word = ("a" * n) + ("b" * n)
        instances.append((pos_word, True))

        # Count-matched negative: exact same n a's and n b's, but permuted (e.g. b^n a^n or interspersed)
        if n == 1:
            neg_word = "ba"
        else:
            neg_word = ("b" * n) + ("a" * n)
        instances.append((neg_word, False))

    rng.shuffle(instances)
    return instances


def _generate_sequence_instances(rng: random.Random, count: int) -> List[Tuple[str, bool]]:
    """Generates strings where 'ab' occurs before 'ba', with count-matched negatives."""
    half = count // 2
    instances: List[Tuple[str, bool]] = []

    for _ in range(half):
        middle_len = rng.randint(0, 4)
        middle = "".join(rng.choice(["a", "b"]) for _ in range(middle_len))
        pos_word = "a" + "ab" + middle + "ba" + "b"
        instances.append((pos_word, True))

        # Count-matched negative: reverse so 'ba' precedes 'ab'
        neg_word = pos_word[::-1]
        instances.append((neg_word, False))

    rng.shuffle(instances)
    return instances


def _generate_counter_ratio_instances(rng: random.Random, count: int, ratio_mult: int = 4) -> List[Tuple[str, bool]]:
    """Generates strings where count(a) > ratio_mult * count(b) (e.g. 4:1 ratio)."""
    half = count // 2
    instances: List[Tuple[str, bool]] = []

    for _ in range(half):
        n_b = rng.randint(0, 3)
        n_a = (ratio_mult * n_b) + rng.randint(1, 4)
        chars = ["a"] * n_a + ["b"] * n_b
        rng.shuffle(chars)
        instances.append(("".join(chars), True))

        # Negative: count(a) <= ratio_mult * count(b)
        n_b_neg = rng.randint(1, 5)
        n_a_neg = rng.randint(0, ratio_mult * n_b_neg)
        chars_neg = ["a"] * n_a_neg + ["b"] * n_b_neg
        rng.shuffle(chars_neg)
        instances.append(("".join(chars_neg), False))

    rng.shuffle(instances)
    return instances


def _generate_parity_instances(rng: random.Random, count: int) -> List[Tuple[str, bool]]:
    """Generates strings where count(a) is even."""
    half = count // 2
    instances: List[Tuple[str, bool]] = []

    for _ in range(half):
        n_a_even = 2 * rng.randint(0, 5)
        n_b = rng.randint(0, 5)
        chars = ["a"] * n_a_even + ["b"] * n_b
        rng.shuffle(chars)
        instances.append(("".join(chars), True))

        # Negative: count(a) is odd
        n_a_odd = (2 * rng.randint(0, 4)) + 1
        n_b_neg = rng.randint(0, 5)
        chars_neg = ["a"] * n_a_odd + ["b"] * n_b_neg
        rng.shuffle(chars_neg)
        instances.append(("".join(chars_neg), False))

    rng.shuffle(instances)
    return instances


def _generate_graph_instances(rng: random.Random, count: int) -> List[Tuple[str, bool]]:
    """Generates 4-vertex adjacency strings (length 6: edges 01,02,03,12,13,23) testing connectivity."""
    half = count // 2
    instances: List[Tuple[str, bool]] = []
    edges = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]

    def is_connected(edge_str: str) -> bool:
        adj = {0: [], 1: [], 2: [], 3: []}
        for idx, ch in enumerate(edge_str):
            if ch == "a":  # 'a' denotes edge present
                u, v = edges[idx]
                adj[u].append(v)
                adj[v].append(u)
        visited = set()
        queue = [0]
        while queue:
            node = queue.pop(0)
            if node not in visited:
                visited.add(node)
                queue.extend(adj[node])
        return len(visited) == 4

    pos_pool = []
    neg_pool = []
    all_bitstrings = [f"{i:06b}".replace("1", "a").replace("0", "b") for i in range(64)]
    for s in all_bitstrings:
        if is_connected(s):
            pos_pool.append(s)
        else:
            neg_pool.append(s)

    pos_instances = [(rng.choice(pos_pool), True) for _ in range(half)]
    neg_instances = [(rng.choice(neg_pool), False) for _ in range(half)]
    instances = pos_instances + neg_instances
    rng.shuffle(instances)
    return instances


def generate_family_instances(family_name: str, seed: int, count: int = 128) -> List[Tuple[str, bool]]:
    """Deterministic generator producing count balanced instances with count-matched negatives."""
    rng = random.Random(seed)

    generators = {
        "counter_ratio": _generate_counter_ratio_instances,
        "parity": _generate_parity_instances,
        "boundary": _generate_boundary_instances,
        "graph": _generate_graph_instances,
        "an_bn": _generate_an_bn_instances,
        "sequence": _generate_sequence_instances,
    }

    if family_name not in generators:
        raise ValueError(f"Unknown task family '{family_name}', allowed: {TASK_FAMILIES}")

    return generators[family_name](rng, count)
