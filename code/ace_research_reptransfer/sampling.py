"""Fit-side deterministic sampling. Never touches terminal data.

Words are ranked by ``sha256(role|task|seed|budget|word)`` so results do not depend on the
algorithm inside ``random`` and are identical across Python versions.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import itertools

from .tasks import ALPHABET, truth

PROBE_COUNT = 256
PROBE_MIN, PROBE_MAX = 16, 30


def words(length: int):
    return ("".join(x) for x in itertools.product(ALPHABET, repeat=length))


def key(*parts) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


@lru_cache(maxsize=None)
def _partition(spec, lo: int, hi: int):
    universe = [w for n in range(lo, hi + 1) for w in words(n)]
    pos = [w for w in universe if truth(spec, w)]
    neg = [w for w in universe if not truth(spec, w)]
    return pos, neg


def labeled_sample(spec, lo: int, hi: int, n: int, role: str, task_id: str, seed: int, budget: int):
    """``min(available, n/2)`` positives, remaining slots negatives; hash-ranked."""
    pos, neg = _partition(spec, lo, hi)
    rank = lambda w: key(role, task_id, seed, budget, w)
    pos = sorted(pos, key=rank)
    neg = sorted(neg, key=rank)
    take_pos = min(n // 2, len(pos))
    take_neg = min(n - take_pos, len(neg))
    take_pos = min(n - take_neg, len(pos))
    chosen = pos[:take_pos] + neg[:take_neg]
    return [(w, truth(spec, w)) for w in sorted(chosen, key=lambda w: (len(w), w))]


def probe_strings(seed: int):
    """256 *unlabeled* strings of length 16-30, independent of every task and of terminal data."""
    out = []
    for i in range(PROBE_COUNT):
        digest = hashlib.sha256(f"probe|{seed}|{i}".encode("utf-8")).digest()
        length = PROBE_MIN + digest[0] % (PROBE_MAX - PROBE_MIN + 1)
        bits = int.from_bytes(digest[1:5], "big")
        out.append("".join(ALPHABET[(bits >> j) & 1] for j in range(length)))
    return out
