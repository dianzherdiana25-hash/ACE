"""Admission-aware selection, separate pos/neg reporting, and second counterexample round (W3)."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple


class AdmissionAwareSelector:
    """Prioritizes admission criteria over raw validation accuracy, reporting pos/neg rates separately."""

    def __init__(self, max_errors: int = 0):
        self.max_errors = max_errors

    def evaluate_and_select(
        self,
        candidate_fn: Callable[[str], bool],
        train_data: List[Tuple[str, bool]],
        val_data: List[Tuple[str, bool]],
    ) -> Dict[str, Any]:
        pos_train = [w for w, y in train_data if y is True]
        neg_train = [w for w, y in train_data if y is False]

        errors = 0
        pos_hits = 0
        neg_hits = 0

        for w, y in train_data:
            pred = bool(candidate_fn(w))
            if pred == y:
                if y:
                    pos_hits += 1
                else:
                    neg_hits += 1
            else:
                errors += 1

        val_errors = 0
        for w, y in val_data:
            if bool(candidate_fn(w)) != y:
                val_errors += 1

        pos_acc = pos_hits / len(pos_train) if pos_train else 1.0
        neg_acc = neg_hits / len(neg_train) if neg_train else 1.0
        val_acc = (len(val_data) - val_errors) / len(val_data) if val_data else 1.0

        if errors == 0:
            status = "ADMITTED"
        elif errors <= self.max_errors:
            status = "ADMITTED_WITH_ERRORS"
        else:
            status = "REJECTED"

        return {
            "status": status,
            "errors": errors,
            "max_errors_allowed": self.max_errors,
            "pos_accuracy": round(pos_acc, 4),
            "neg_accuracy": round(neg_acc, 4),
            "train_accuracy": round((len(train_data) - errors) / len(train_data), 4),
            "val_accuracy": round(val_acc, 4),
        }


def verify_guard_robustness(
    guard_fn: Callable[[str], bool],
    guard_type: str = "contains_aa"
) -> Tuple[bool, Dict[str, Any]]:
    """Executes a second counterexample round on count-matched order mutations to catch guard overfit."""
    # Count-matched pairs: words with identical character multiset but distinct order
    counterexample_probes = [
        ("aab", "aba"),
        ("baa", "aba"),
        ("baab", "baba"),
        ("aabaa", "ababa"),
    ]

    counterexamples = []
    for w1, w2 in counterexample_probes:
        # If guard evaluates True on w1 but False on w2 (or vice-versa) solely on order
        p1 = bool(guard_fn(w1))
        p2 = bool(guard_fn(w2))
        if p1 != p2:
            counterexamples.append({"w1": w1, "p1": p1, "w2": w2, "p2": p2})

    robust = len(counterexamples) == 0
    return robust, {
        "robust": robust,
        "counterexamples_found": len(counterexamples),
        "counterexamples": counterexamples,
    }
