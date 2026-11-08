"""Disjoint task banks for Fase 7 (M1_dev/val, M2_dev/val, and unseen target T_unseen).

Never imports ``evaluator.py``. Uses SHA-256 deterministic ranking so sampling is
100% identical across Python 3.11, 3.12, and 3.13.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import itertools

ALPHABET = ("a", "b")
PRIMARY_BUDGET = 32
SEEDS = (1, 2, 3, 4, 5)


def even_a(w: str) -> int:
    return sum(1 for i in range(0, len(w), 2) if w[i] == "a")


def odd_b(w: str) -> int:
    return sum(1 for i in range(1, len(w), 2) if w[i] == "b")


def block2_aa(w: str) -> int:
    return sum(1 for i in range(0, len(w) - 1, 2) if w[i : i + 2] == "aa")


def split_halves(w: str) -> tuple[str, str]:
    mid = len(w) // 2
    return w[:mid], w[mid:]


def eval_spec(spec: tuple, w: str) -> bool:
    kind = spec[0]
    if kind == "even_a_mod":
        _, m, r = spec
        return even_a(w) % m == r
    if kind == "odd_b_mod":
        _, m, r = spec
        return odd_b(w) % m == r
    if kind == "block2_aa_mod":
        _, m, r = spec
        return block2_aa(w) % m == r
    if kind == "flat_mod":
        _, sym, m, r = spec
        return w.count(sym) % m == r
    if kind == "ends":
        return w.endswith(spec[1])
    if kind == "starts":
        return w.startswith(spec[1])
    if kind == "contains":
        return spec[1] in w
    if kind == "len_mod":
        return len(w) % spec[1] == spec[2]
    if kind == "left_a_mod":
        left, _ = split_halves(w)
        return left.count("a") % spec[1] == spec[2]
    if kind == "right_b_mod":
        _, right = split_halves(w)
        return right.count("b") % spec[1] == spec[2]
    if kind == "half_a_eq_mod":
        left, right = split_halves(w)
        return (left.count("a") % spec[1]) == (right.count("a") % spec[1])
    if kind == "half_even_a_eq_mod":
        left, right = split_halves(w)
        return (even_a(left) % spec[1]) == (even_a(right) % spec[1])
    if kind == "half_odd_b_neq_mod":
        left, right = split_halves(w)
        return (odd_b(left) % spec[1]) != (odd_b(right) % spec[1])
    if kind == "half_block2_aa_eq_mod":
        left, right = split_halves(w)
        return (block2_aa(left) % spec[1]) == (block2_aa(right) % spec[1])
    if kind == "and":
        return eval_spec(spec[1], w) and eval_spec(spec[2], w)
    if kind == "or":
        return eval_spec(spec[1], w) or eval_spec(spec[2], w)
    if kind == "xor":
        return eval_spec(spec[1], w) != eval_spec(spec[2], w)
    if kind == "not":
        return not eval_spec(spec[1], w)
    if kind == "exact_eq_ab":
        return w.count("a") == w.count("b")
    if kind == "dyck":
        bal = 0
        for ch in w:
            bal += 1 if ch == "a" else -1
            if bal < 0:
                return False
        return bal == 0
    raise ValueError(f"unknown spec kind: {kind}")


# Meta-Bank 1 (G0 -> G1): Strided & 2-gram block tasks (disjoint from M2 and Targets)
M1_DEV = (
    ("M1_d1", ("even_a_mod", 2, 0)),
    ("M1_d2", ("odd_b_mod", 2, 1)),
    ("M1_d3", ("block2_aa_mod", 2, 1)),
    ("M1_d4", ("even_a_mod", 3, 1)),
    ("M1_d5", ("and", ("even_a_mod", 2, 1), ("ends", "b"))),
    ("M1_d6", ("or", ("odd_b_mod", 2, 0), ("starts", "aa"))),
)

M1_VAL = (
    ("M1_v1", ("and", ("even_a_mod", 2, 0), ("starts", "ab"))),
    ("M1_v2", ("xor", ("odd_b_mod", 2, 1), ("ends", "ba"))),
    ("M1_v3", ("and", ("block2_aa_mod", 2, 0), ("flat_mod", "b", 2, 1))),
    ("M1_v4", ("odd_b_mod", 3, 2)),
)

# Meta-Bank 2 (G1 -> G2): Split-half frame & multi-feature ambiguity tasks
M2_DEV = (
    ("M2_d1", ("half_a_eq_mod", 2)),
    ("M2_d2", ("and", ("left_a_mod", 2, 0), ("right_b_mod", 2, 1))),
    ("M2_d3", ("xor", ("left_a_mod", 2, 1), ("ends", "ab"))),
    ("M2_d4", ("or", ("right_b_mod", 3, 0), ("starts", "bb"))),
    ("M2_d5", ("and", ("left_a_mod", 3, 1), ("even_a_mod", 2, 0))),
    ("M2_d6", ("half_a_eq_mod", 3)),
)

M2_VAL = (
    ("M2_v1", ("and", ("left_a_mod", 2, 1), ("right_b_mod", 2, 0))),
    ("M2_v2", ("xor", ("half_a_eq_mod", 2), ("starts", "ba"))),
    ("M2_v3", ("and", ("right_b_mod", 2, 1), ("odd_b_mod", 2, 0))),
    ("M2_v4", ("or", ("left_a_mod", 3, 2), ("ends", "aa"))),
)

# Unseen Target Bank (T_unseen): Strictly disjoint from M1 and M2!
TARGETS = (
    # U_gen (8 tasks): 3 strided-composites (solvable by G1 & G2, not G0) +
    #                  5 strided x split-frame relational tasks (solvable ONLY by G2!)
    ("U1", "U_gen", ("and", ("even_a_mod", 2, 1), ("odd_b_mod", 2, 1))),
    ("U2", "U_gen", ("xor", ("block2_aa_mod", 2, 1), ("starts", "ab"))),
    ("U3", "U_gen", ("and", ("even_a_mod", 3, 2), ("ends", "ba"))),
    ("U4", "U_gen", ("half_even_a_eq_mod", 2)),
    ("U5", "U_gen", ("half_odd_b_neq_mod", 2)),
    ("U6", "U_gen", ("half_block2_aa_eq_mod", 2)),
    ("U7", "U_gen", ("and", ("half_even_a_eq_mod", 2), ("right_b_mod", 2, 1))),
    ("U8", "U_gen", ("xor", ("half_odd_b_neq_mod", 2), ("starts", "aa"))),
    # L_base (3 tasks): Base surface/flat-counter tasks expressible by G0 & B_fixed
    ("L1", "L_base", ("and", ("flat_mod", "a", 2, 0), ("ends", "ba"))),
    ("L2", "L_base", ("or", ("flat_mod", "b", 3, 1), ("starts", "aa"))),
    ("L3", "L_base", ("xor", ("len_mod", 2, 0), ("contains", "aba"))),
    # N_ood (2 tasks): Unbounded non-regular tasks (abstention safety)
    ("N1", "N_ood", ("exact_eq_ab",)),
    ("N2", "N_ood", ("dyck",)),
)

TARGET_BY_ID = {tid: (st, spec) for tid, st, spec in TARGETS}

DRIFT_CONTROLS = (
    ("D1_U4_inv", "U4"),
    ("D2_L1_inv", "L1"),
)


def words_of_len(n: int):
    return ("".join(p) for p in itertools.product(ALPHABET, repeat=n))


def _rank_key(*parts: object) -> str:
    return hashlib.sha256("|".join(str(x) for x in parts).encode("utf-8")).hexdigest()


@lru_cache(maxsize=None)
def _partition(spec: tuple, lo: int, hi: int) -> tuple[list[str], list[str]]:
    univ = [w for n in range(lo, hi + 1) for w in words_of_len(n)]
    pos = [w for w in univ if eval_spec(spec, w)]
    neg = [w for w in univ if not eval_spec(spec, w)]
    return pos, neg


def sample_labeled(
    spec: tuple,
    lo: int,
    hi: int,
    n: int,
    role: str,
    task_id: str,
    seed: int,
) -> list[tuple[str, bool]]:
    pos, neg = _partition(spec, lo, hi)
    pos_s = sorted(pos, key=lambda w: _rank_key(role, task_id, seed, w))
    neg_s = sorted(neg, key=lambda w: _rank_key(role, task_id, seed, w))
    take_p = min(n // 2, len(pos_s))
    take_n = min(n - take_p, len(neg_s))
    take_p = min(n - take_n, len(pos_s))
    chosen = pos_s[:take_p] + neg_s[:take_n]
    return [(w, eval_spec(spec, w)) for w in sorted(chosen, key=lambda w: (len(w), w))]


def unlabeled_probes(seed: int, count: int = 192) -> list[str]:
    out: list[str] = []
    for i in range(count):
        dig = hashlib.sha256(f"gen_probe|{seed}|{i}".encode("utf-8")).digest()
        ln = 16 + (dig[0] % 13)  # lengths 16..28
        bits = int.from_bytes(dig[1:5], "big")
        out.append("".join(ALPHABET[(bits >> j) & 1] for j in range(ln)))
    return out
