"""Deterministic SHA-256 sample ranking and unlabeled Catalan Dyck generators.

100% Python-version independent (zero reliance on `random.Random` or `hash()`).
Contains zero task labels and zero task-specific ground-truth logic, so learners
may draw unlabeled structural probes without any evaluator leakage.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib


def sha256_rank(tag: str, seed: int, item: str) -> str:
    """Return deterministic FIPS 180-4 SHA-256 hex key for ordering items."""
    payload = f"{tag}:{seed}:{item}".encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def rank_select(items: tuple[str, ...] | list[str], tag: str, seed: int, count: int) -> list[str]:
    """Deterministically select `count` unique items ordered by SHA-256 rank."""
    unique = sorted(set(items), key=lambda w: (sha256_rank(tag, seed, w), len(w), w))
    if len(unique) < count:
        raise ValueError(f"insufficient pool for {tag} (seed={seed}): need {count}, got {len(unique)}")
    return unique[:count]


@lru_cache(maxsize=16)
def prime_dyck_by_vertices(max_v: int) -> dict[int, tuple[str, ...]]:
    """Generate all canonical single-tree prime Dyck words `a...b` for `1 <= v <= max_v`.

    Uses exact Catalan recurrence: every ordered rooted tree with `v >= 2` vertices
    decomposes uniquely into a first child subtree of `i` vertices (`1 <= i <= v - 1`)
    followed by the remaining root forest of `v - i` vertices.
    """
    if max_v < 1:
        raise ValueError("max_v must be >= 1")
    dp: dict[int, tuple[str, ...]] = {1: ("ab",)}
    for v in range(2, max_v + 1):
        words: list[str] = []
        for first_v in range(1, v):
            rest_v = v - first_v
            for left in dp[first_v]:
                for rest_root in dp[rest_v]:
                    words.append("a" + left + rest_root[1:])
        words.sort()
        dp[v] = tuple(words)
    return dp


@lru_cache(maxsize=16)
def single_tree_pool(min_v: int = 2, max_v: int = 9) -> tuple[str, ...]:
    """Return all prime Dyck single-tree encodings with `min_v <= v <= max_v`."""
    dp = prime_dyck_by_vertices(max_v)
    out: list[str] = []
    for v in range(min_v, max_v + 1):
        out.extend(dp[v])
    return tuple(out)


@lru_cache(maxsize=16)
def paired_tree_general_pool(
    min_sum_v: int,
    max_sum_v: int,
    per_pair_cap: int = 48,
    max_single_v: int = 10,
) -> tuple[str, ...]:
    """Build deterministic task-agnostic paired-tree pool `enc(T1) + enc(T2)`.

    Covers vertex-count pairs `(v1, v2)` with `2 <= v1, v2 <= max_single_v` and
    `min_sum_v <= v1 + v2 <= max_sum_v` so frame boundaries vary dynamically
    while bounding individual Catalan tables to `v <= 10` (`C_9 = 4,862`).
    """
    dp = prime_dyck_by_vertices(min(max_single_v, max_sum_v - 2))
    words: list[str] = []
    for total_v in range(min_sum_v, max_sum_v + 1):
        v1_min = max(2, total_v - max_single_v)
        v1_max = min(max_single_v, total_v - 2)
        for v1 in range(v1_min, v1_max + 1):
            v2 = total_v - v1
            left_pool = rank_select(dp[v1], f"pair_left:{total_v}:{v1}", 0, min(len(dp[v1]), per_pair_cap))
            right_pool = rank_select(dp[v2], f"pair_right:{total_v}:{v2}", 0, min(len(dp[v2]), per_pair_cap))
            candidates = [t1 + t2 for t1 in left_pool for t2 in right_pool]
            take = min(len(candidates), per_pair_cap)
            words.extend(rank_select(candidates, f"pair_cell:{total_v}:{v1}:{v2}", 0, take))
    words_unique = sorted(set(words), key=lambda w: (len(w), w))
    return tuple(words_unique)


@lru_cache(maxsize=32)
def unlabeled_single_tree_probes(seed: int, count: int = 64) -> tuple[str, ...]:
    """Deterministic unlabeled single-tree probes for MDL entropy & deduplication."""
    pool = single_tree_pool(2, 9)
    chosen = rank_select(pool, "unlabeled_single_probe", seed, count)
    return tuple(sorted(chosen, key=lambda w: (len(w), w)))


@lru_cache(maxsize=32)
def unlabeled_paired_tree_probes(seed: int, count: int = 64) -> tuple[str, ...]:
    """Deterministic unlabeled paired-tree probes (lengths 30..40) for stability gating."""
    pool = paired_tree_general_pool(15, 20, per_pair_cap=32)
    chosen = rank_select(pool, "unlabeled_paired_probe", seed, count)
    return tuple(sorted(chosen, key=lambda w: (len(w), w)))
