"""Target adapter hypothesis class: single-feature literals and two-feature pairs.

Fast vectorised bitwise evaluation over all candidate hypotheses against label vectors.
Hypotheses are evaluated consistently against train labels; candidate with minimal
validation errors is chosen. If validation errors == 0, the candidate is admitted;
otherwise the adapter abstains.
"""
from __future__ import annotations

import itertools
from typing import Sequence
from .features import Feature

OP_AND, OP_OR, OP_XOR = 0, 1, 2
OP_NAMES = ("and", "or", "xor")


class Hypothesis:
    __slots__ = ("name", "complexity", "predict", "cost_fn")

    def __init__(self, name: str, complexity: int, predict, cost_fn):
        self.name = name
        self.complexity = complexity
        self.predict = predict
        self.cost_fn = cost_fn

    def __repr__(self):
        return f"<Hypothesis {self.name} c={self.complexity}>"


def bitvec(pred, words) -> int:
    v = 0
    for i, w in enumerate(words):
        if pred(w):
            v |= 1 << i
    return v


def fit_adapter(features: Sequence[Feature], train: list[tuple[str, bool]], validation: list[tuple[str, bool]]) -> tuple[Hypothesis | None, dict]:
    """Fit a single-feature or two-feature hypothesis.

    Returns:
        (admitted_hypothesis_or_None, stats_dict)
    """
    tr_words, tr_labels = [w for w, _ in train], [label for _, label in train]
    va_words, va_labels = [w for w, _ in validation], [label for _, label in validation]

    tr_mask = (1 << len(tr_words)) - 1
    va_mask = (1 << len(va_words)) - 1

    tr_target = sum((1 << i) for i, label in enumerate(tr_labels) if label)
    va_target = sum((1 << i) for i, label in enumerate(va_labels) if label)

    # Precompute feature values as bitvectors.
    # Feature cost on a word is len(w); total feature cost across an evaluation is sum of lengths.
    tr_len_sum = sum(len(w) for w in tr_words)
    va_len_sum = sum(len(w) for w in va_words)

    f_tr = [bitvec(f.apply, tr_words) for f in features]
    f_va = [bitvec(f.apply, va_words) for f in features]

    # Build literals: pos=0, neg=1
    # Literal index: 2*k + sign
    N = len(features)
    L = 2 * N
    l_tr = [0] * L
    l_va = [0] * L
    l_names = [""] * L
    for k in range(N):
        l_tr[2 * k] = f_tr[k]
        l_tr[2 * k + 1] = tr_mask ^ f_tr[k]
        l_va[2 * k] = f_va[k]
        l_va[2 * k + 1] = va_mask ^ f_va[k]
        l_names[2 * k] = features[k].name
        l_names[2 * k + 1] = f"(not {features[k].name})"

    best = None  # (va_err, complexity, name, kind, k1, s1, op, k2, s2)
    hyp_eval_count = 0
    symbols_train = 0
    symbols_val = 0

    # 1. Single literals (complexity 1)
    for lit in range(L):
        hyp_eval_count += 1
        symbols_train += tr_len_sum
        if l_tr[lit] == tr_target:
            symbols_val += va_len_sum
            diff = l_va[lit] ^ va_target
            va_err = bin(diff).count("1")
            cand = (va_err, 1, l_names[lit], "single", lit // 2, lit % 2, None, None, None)
            if best is None or cand < best:
                best = cand

    # 2. Pairs over distinct features (complexity 2).
    # Combinations of feature indices k1 < k2; literals l1 in (2*k1, 2*k1+1), l2 in (2*k2, 2*k2+1).
    for k1, k2 in itertools.combinations(range(N), 2):
        for s1 in (0, 1):
            lit1 = 2 * k1 + s1
            v1_tr = l_tr[lit1]
            v1_va = l_va[lit1]
            for s2 in (0, 1):
                lit2 = 2 * k2 + s2
                v2_tr = l_tr[lit2]
                v2_va = l_va[lit2]
                # Three operations: AND, OR, XOR
                # AND
                hyp_eval_count += 1
                symbols_train += 2 * tr_len_sum
                if (v1_tr & v2_tr) == tr_target:
                    symbols_val += 2 * va_len_sum
                    va_err = bin((v1_va & v2_va) ^ va_target).count("1")
                    cand = (va_err, 2, f"({l_names[lit1]} and {l_names[lit2]})", "pair", k1, s1, OP_AND, k2, s2)
                    if best is None or cand < best:
                        best = cand
                # OR
                hyp_eval_count += 1
                symbols_train += 2 * tr_len_sum
                if ((v1_tr | v2_tr) & tr_mask) == tr_target:
                    symbols_val += 2 * va_len_sum
                    va_err = bin(((v1_va | v2_va) & va_mask) ^ va_target).count("1")
                    cand = (va_err, 2, f"({l_names[lit1]} or {l_names[lit2]})", "pair", k1, s1, OP_OR, k2, s2)
                    if best is None or cand < best:
                        best = cand
                # XOR
                hyp_eval_count += 1
                symbols_train += 2 * tr_len_sum
                if ((v1_tr ^ v2_tr) & tr_mask) == tr_target:
                    symbols_val += 2 * va_len_sum
                    va_err = bin(((v1_va ^ v2_va) & va_mask) ^ va_target).count("1")
                    cand = (va_err, 2, f"({l_names[lit1]} xor {l_names[lit2]})", "pair", k1, s1, OP_XOR, k2, s2)
                    if best is None or cand < best:
                        best = cand

    stats = {
        "hypotheses_evaluated": hyp_eval_count,
        "symbols_train": symbols_train,
        "symbols_val": symbols_val,
        "symbols_total": symbols_train + symbols_val,
        "best_candidate_name": best[2] if best else None,
        "best_candidate_validation_errors": best[0] if best else None,
    }

    if best is None or best[0] != 0:
        # Abstain: no candidate with zero validation errors.
        return None, stats

    # Materialise admitted hypothesis.
    _, complexity, name, kind, k1, s1, op, k2, s2 = best
    f1 = features[k1]
    if kind == "single":
        if s1 == 0:
            pred = f1.apply
        else:
            pred = lambda s, f=f1: not f.apply(s)
        cost_fn = lambda s, f=f1: f.cost(s)
    else:
        f2 = features[k2]
        p1 = f1.apply if s1 == 0 else (lambda s, f=f1: not f.apply(s))
        p2 = f2.apply if s2 == 0 else (lambda s, f=f2: not f.apply(s))
        if op == OP_AND:
            pred = lambda s, a=p1, b=p2: a(s) and b(s)
        elif op == OP_OR:
            pred = lambda s, a=p1, b=p2: a(s) or b(s)
        else:
            pred = lambda s, a=p1, b=p2: a(s) != b(s)
        cost_fn = lambda s, a=f1, b=f2: a.cost(s) + b.cost(s)

    return Hypothesis(name, complexity, pred, cost_fn), stats
