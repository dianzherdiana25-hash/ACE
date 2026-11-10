"""Admission-aware selection, separate pos/neg reporting, and second counterexample round (W3)."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple


def _validate_development(train_data, val_data):
    # Reuse the existing bounded runtime contract. These are development labels,
    # not independently sealed evaluation data.
    from ace_capability_evolution.compositional import validate_rows
    validate_rows(train_data, 63)
    validate_rows(val_data, 128)
    if {w for w, _ in train_data} & {w for w, _ in val_data}:
        raise ValueError("overlapping train/validation")


class AdmissionAwareSelector:
    """Admit only on training tolerance AND exact validation fit.

    Callables must be trusted internal programs. This class is not a Python
    sandbox and must never receive dynamically executed advisor source.
    ADMITTED is a development decision only, never a release authorization.
    """

    def __init__(self, max_errors: int = 0):
        if type(max_errors) is not int or max_errors < 0:
            raise ValueError("max_errors must be a nonnegative integer")
        self.max_errors = max_errors

    def evaluate_and_select(
        self,
        candidate_fn: Callable[[str], bool],
        train_data: List[Tuple[str, bool]],
        val_data: List[Tuple[str, bool]],
    ) -> Dict[str, Any]:
        _validate_development(train_data, val_data)
        report = {
            "status": "REJECTED",
            "reason": "EVALUATION_INCOMPLETE",
            "errors": None,
            "validation_errors": None,
            "max_errors_allowed": self.max_errors,
            "train_total": len(train_data), "validation_total": len(val_data),
            "train_evaluated": 0, "validation_evaluated": 0,
            "candidate_predictions": 0, "counterexamples": [],
            "pos_accuracy": None, "neg_accuracy": None,
            "train_accuracy": None, "val_accuracy": None,
            "evidence_scope": "DEVELOPMENT_ONLY",
            "scientific_status": "NOT_ASSESSED", "release_gate": "BLOCK_RELEASE",
            "candidate_deployed": False, "external_ai_calls": 0,
        }
        scores = {}
        for split, rows in (("train", train_data), ("validation", val_data)):
            hits = {True: 0, False: 0}
            totals = {True: 0, False: 0}
            errors = 0
            for word, label in rows:
                report["candidate_predictions"] += 1
                try:
                    prediction = candidate_fn(word)
                except Exception as exc:
                    report.update(reason="CANDIDATE_EVALUATION_ERROR",
                                  evaluation_error=type(exc).__name__)
                    return report
                if type(prediction) is not bool:
                    report.update(reason="NONBOOLEAN_PREDICTION")
                    return report
                report[split + "_evaluated"] += 1
                totals[label] += 1
                if prediction == label:
                    hits[label] += 1
                else:
                    errors += 1
                    if len(report["counterexamples"]) < 8:
                        report["counterexamples"].append({"split": split, "word": word,
                                                          "expected": label, "actual": prediction})
            scores[split] = errors
            def rate(label):
                return round(hits[label] / totals[label], 4) if totals[label] else None
            if split == "train":
                report.update(errors=errors, pos_accuracy=rate(True), neg_accuracy=rate(False),
                              train_accuracy=round(1 - errors / len(rows), 4))
            else:
                report.update(validation_errors=errors, val_accuracy=round(1 - errors / len(rows), 4),
                              validation_pos_accuracy=rate(True), validation_neg_accuracy=rate(False))
        if scores["validation"]:
            report["reason"] = "VALIDATION_ERRORS"
        elif scores["train"] > self.max_errors:
            report["reason"] = "TRAIN_ERROR_BUDGET_EXCEEDED"
        else:
            report.update(status="ADMITTED_WITH_ERRORS" if scores["train"] else "ADMITTED",
                          reason="DEVELOPMENT_FIT_ONLY")
        return report


def fit_with_admission(train_data, val_data, *, max_errors=0):
    """Reuse the existing four fitted arm winners; return no program on failure.

    No new grammar, retraining loop, provider call or terminal input is added.
    Fit's own validation-based arm selection is unchanged. Repeated identities
    are checked once, and a caller can replay the serialized selected program.
    """
    from ace_capability_evolution import compositional as c
    selector = AdmissionAwareSelector(max_errors)
    _validate_development(train_data, val_data)
    learned, fit_report = c.fit(train_data, val_data)
    work = c.Work()
    checked, arms, eligible = {}, {}, []
    for arm, program in sorted(learned.items()):
        if program.identity not in checked:
            checked[program.identity] = selector.evaluate_and_select(
                lambda word, p=program: p.predict(word, work), train_data, val_data)
        result = checked[program.identity]
        arms[arm] = {"identity": program.identity, **result}
        if result["status"] in ("ADMITTED", "ADMITTED_WITH_ERRORS"):
            eligible.append((result["errors"], program.identity, arm, program))
    chosen = min(eligible, key=lambda item: item[:3]) if eligible else None
    # The best failed arm is diagnostic only: never return it as usable knowledge.
    diagnostic_arm = min(arms, key=lambda arm: (
        arms[arm]["validation_errors"] if arms[arm]["validation_errors"] is not None else float("inf"),
        arms[arm]["errors"] if arms[arm]["errors"] is not None else float("inf"), arm))
    selected_arm = chosen[2] if chosen else None
    report = dict(arms[selected_arm or diagnostic_arm])
    report.update(selected_arm=selected_arm, diagnostic_arm=diagnostic_arm,
                  program=chosen[3].data() if chosen else None,
                  program_identity=chosen[1] if chosen else None,
                  arms=arms, fit_report=fit_report,
                  candidate_predictions=sum(r["candidate_predictions"] for r in checked.values()),
                  unique_programs_evaluated=len(checked), admission_work=vars(work))
    return (chosen[3] if chosen else None), report


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
