"""Arms definitions: A, A0, B (fresh R1), C, C2, and D0 (constant False).

Each arm exposes ``fit(train, validation) -> (Candidate | None, stats)``.
"""
from __future__ import annotations

from ace_research_primitives import primitive_discovery as r1
from .head import fit_adapter, Hypothesis
from .features import (
    learned_dictionary,
    base_hand_library,
    extended_hand_library,
)
from .tasks import SOURCE_REL, SOURCE_IRR


class Candidate:
    __slots__ = ("name", "predict", "cost_fn")

    def __init__(self, name: str, predict, cost_fn):
        self.name = name
        self.predict = predict
        self.cost_fn = cost_fn


# Pre-built feature dictionaries (admitted offline).
_A_FEATS, _A_MERGES = None, None
_A0_FEATS, _A0_MERGES = None, None
_C_FEATS = None
_C2_FEATS = None


def get_dictionaries():
    global _A_FEATS, _A_MERGES, _A0_FEATS, _A0_MERGES, _C_FEATS, _C2_FEATS
    if _A_FEATS is None:
        _A_FEATS, _A_MERGES = learned_dictionary(SOURCE_REL)
        _A0_FEATS, _A0_MERGES = learned_dictionary(SOURCE_IRR)
        _C_FEATS = base_hand_library()
        _C2_FEATS = extended_hand_library()
    return {
        "A": (_A_FEATS, _A_MERGES),
        "A0": (_A0_FEATS, _A0_MERGES),
        "C": _C_FEATS,
        "C2": _C2_FEATS,
    }


def fit_arm_A(train, validation):
    feats, _ = get_dictionaries()["A"]
    hyp, stats = fit_adapter(feats, train, validation)
    cand = Candidate(hyp.name, hyp.predict, hyp.cost_fn) if hyp else None
    return cand, stats


def fit_arm_A0(train, validation):
    feats, _ = get_dictionaries()["A0"]
    hyp, stats = fit_adapter(feats, train, validation)
    cand = Candidate(hyp.name, hyp.predict, hyp.cost_fn) if hyp else None
    return cand, stats


def fit_arm_C(train, validation):
    feats = get_dictionaries()["C"]
    hyp, stats = fit_adapter(feats, train, validation)
    cand = Candidate(hyp.name, hyp.predict, hyp.cost_fn) if hyp else None
    return cand, stats


def fit_arm_C2(train, validation):
    feats = get_dictionaries()["C2"]
    hyp, stats = fit_adapter(feats, train, validation)
    cand = Candidate(hyp.name, hyp.predict, hyp.cost_fn) if hyp else None
    return cand, stats


def fit_arm_B(train, validation):
    """Fresh R1 infer on target train labels; admit iff validation errors == 0."""
    # Compute accounting: merge attempts, symbols evaluated.
    tr_len_sum = sum(len(w) for w, _ in train)
    va_len_sum = sum(len(w) for w, _ in validation)
    try:
        dfa, attempts = r1.infer(train)
        va_err = sum(dfa.run(w) != label for w, label in validation)
        # Upper bound on symbols evaluated during training: attempts * tr_len_sum
        symbols_train = attempts * tr_len_sum
        symbols_val = va_len_sum
        stats = {
            "r1_merge_attempts": attempts,
            "validation_errors": va_err,
            "symbols_train": symbols_train,
            "symbols_val": symbols_val,
            "symbols_total": symbols_train + symbols_val,
            "best_candidate_name": f"r1:states={dfa.reachable()}",
        }
        if va_err != 0:
            return None, stats
        cand = Candidate(f"r1:states={dfa.reachable()}", dfa.run, lambda s: len(s))
        return cand, stats
    except Exception as exc:
        return None, {
            "r1_merge_attempts": -1,
            "error": str(exc),
            "symbols_train": tr_len_sum,
            "symbols_val": 0,
            "symbols_total": tr_len_sum,
        }


def fit_arm_D0(train, validation):
    cand = Candidate("const:false", lambda s: False, lambda s: 0)
    # Always admitted; no hypotheses evaluated
    return cand, {"symbols_total": 0, "hypotheses_evaluated": 1}


ARMS = {
    "A": fit_arm_A,
    "A0": fit_arm_A0,
    "B": fit_arm_B,
    "C": fit_arm_C,
    "C2": fit_arm_C2,
    "D0": fit_arm_D0,
}
