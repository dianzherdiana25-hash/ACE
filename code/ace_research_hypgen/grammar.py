"""Typed Hypothesis AST Grammar and Formal Falsification Predicates."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any


class HypothesisDomain:
    REGULAR_LANGUAGE = "REGULAR_LANGUAGE"
    CONTEXT_FREE_MIRROR = "CONTEXT_FREE_MIRROR"
    ARITHMETIC_INVARIANT = "ARITHMETIC_INVARIANT"
    REPRESENTATION_OCCUPANCY = "REPRESENTATION_OCCUPANCY"
    ALL = (REGULAR_LANGUAGE, CONTEXT_FREE_MIRROR, ARITHMETIC_INVARIANT, REPRESENTATION_OCCUPANCY)


class PropertyKind:
    EXPRESSIBILITY_BOUNDARY = "EXPRESSIBILITY_BOUNDARY"
    SAMPLE_COMPLEXITY = "SAMPLE_COMPLEXITY"
    DRIFT_VULNERABILITY = "DRIFT_VULNERABILITY"
    TRANSFER_EFFICIENCY = "TRANSFER_EFFICIENCY"
    ALL = (EXPRESSIBILITY_BOUNDARY, SAMPLE_COMPLEXITY, DRIFT_VULNERABILITY, TRANSFER_EFFICIENCY)


class FalsificationMetric:
    ACCURACY_MIN = "ACCURACY_MIN"
    ACCURACY_DELTA = "ACCURACY_DELTA"
    COMPUTE_RATIO = "COMPUTE_RATIO"
    DRIFT_ERROR_RATE = "DRIFT_ERROR_RATE"
    ALL = (ACCURACY_MIN, ACCURACY_DELTA, COMPUTE_RATIO, DRIFT_ERROR_RATE)


@dataclass(frozen=True)
class TypedHypothesis:
    hyp_id: str
    domain: str
    property_kind: str
    gap_reference: str
    statement: str
    metric: str
    threshold: float
    comparator: str  # "<", ">", "<=", ">="
    goal_spec: dict[str, Any]
    epistemic_context: dict[str, Any]

    def __post_init__(self):
        if self.domain not in HypothesisDomain.ALL:
            raise ValueError(f"invalid domain {self.domain}")
        if self.property_kind not in PropertyKind.ALL:
            raise ValueError(f"invalid property_kind {self.property_kind}")
        if self.metric not in FalsificationMetric.ALL:
            raise ValueError(f"invalid metric {self.metric}")
        if self.comparator not in ("<", ">", "<=", ">="):
            raise ValueError(f"invalid comparator {self.comparator}")

    def is_falsified(self, observed_value: float) -> bool:
        """Evaluate if observed metric falsifies the hypothesis."""
        if self.comparator == "<":
            return observed_value < self.threshold
        elif self.comparator == ">":
            return observed_value > self.threshold
        elif self.comparator == "<=":
            return observed_value <= self.threshold
        elif self.comparator == ">=":
            return observed_value >= self.threshold
        raise ValueError(f"unsupported comparator {self.comparator}")

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "hyp_id": self.hyp_id,
            "domain": self.domain,
            "property_kind": self.property_kind,
            "gap_reference": self.gap_reference,
            "statement": self.statement,
            "metric": self.metric,
            "threshold": self.threshold,
            "comparator": self.comparator,
            "goal_spec": self.goal_spec,
            "epistemic_context": self.epistemic_context,
        }

    def sha256(self) -> str:
        serialized = json.dumps(self.canonical_dict(), sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
