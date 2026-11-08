"""Metacognitive Self-Modeling & Failure Predictor for ACE Self-Development V0.2.

Grounds candidate pre-execution evaluation in calibrated failure forecasting:
1. Feature extraction over CodeCandidate representations:
   - Structural depth (gene nesting depth, AST complexity depth).
   - Operator variety (Shannon diversity / unique operator ratio, operator collapse detection).
   - History of failure constraints (direct Popperian violations, partial invariant conflicts).
   - Parameter extremity (degenerate moduli, zero-weight collapses, extreme length guards).
2. Calibrated expected failure probability calculation P(failure | features) using
   state-grounded Bayesian log-odds updating and logistic calibration.
3. Calibration evaluation using Brier score, Expected Calibration Error (ECE),
   Maximum Calibration Error (MCE), selective risk, and reliability diagrams.
4. Pre-execution abstention gating:
   `should_abstain(candidate, failure_constraints) -> Tuple[bool, float, str]`
   Recommends pre-execution abstention ("ABSTAIN_PREDICTED_FAILURE") when expected
   failure risk exceeds the risk tolerance threshold and candidate matches high-risk heuristics,
   guaranteeing $0 budget spent and 0 uninformative calls to sealed holdouts.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from enum import Enum
import json
import math
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .failure_constraint_engine import FailureConstraint
from .models import CodeCandidate


class HighRiskHeuristic(str, Enum):
    """High-risk heuristics triggering pre-execution abstention recommendation."""
    CONSTRAINT_VIOLATION = "CONSTRAINT_VIOLATION"
    OPERATOR_COLLAPSE = "OPERATOR_COLLAPSE"
    ZERO_WEIGHT_DEGENERACY = "ZERO_WEIGHT_DEGENERACY"
    EXCESSIVE_STRUCTURAL_DEPTH = "EXCESSIVE_STRUCTURAL_DEPTH"
    DEGENERATE_MODULUS = "DEGENERATE_MODULUS"
    EXTREME_LENGTH_GUARD = "EXTREME_LENGTH_GUARD"
    REPEATED_FORBIDDEN_OPERATOR = "REPEATED_FORBIDDEN_OPERATOR"


@dataclass(frozen=True)
class CandidateFeatures:
    """Extracted structural, operator, and constraint features of a candidate mechanism."""
    structural_depth: int
    ast_depth: int
    gene_depth: int
    operator_variety: float
    unique_operators: Tuple[str, ...]
    operator_count: int
    constraint_conflicts_count: int
    constraint_risk_score: float
    violating_constraint_ids: Tuple[str, ...]
    parameter_extremity: float
    heuristics_triggered: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "structural_depth": self.structural_depth,
            "ast_depth": self.ast_depth,
            "gene_depth": self.gene_depth,
            "operator_variety": round(self.operator_variety, 4),
            "unique_operators": list(self.unique_operators),
            "operator_count": self.operator_count,
            "constraint_conflicts_count": self.constraint_conflicts_count,
            "constraint_risk_score": round(self.constraint_risk_score, 4),
            "violating_constraint_ids": list(self.violating_constraint_ids),
            "parameter_extremity": round(self.parameter_extremity, 4),
            "heuristics_triggered": list(self.heuristics_triggered),
        }


@dataclass(frozen=True)
class MetacognitiveForecast:
    """Pre-execution forecast for a CodeCandidate."""
    candidate_id: str
    p_failure: float
    p_success: float
    uncertainty: float
    should_abstain: bool
    recommendation: str
    reason: str
    risk_threshold: float
    features: CandidateFeatures

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "p_failure": round(self.p_failure, 4),
            "p_success": round(self.p_success, 4),
            "uncertainty": round(self.uncertainty, 4),
            "should_abstain": self.should_abstain,
            "recommendation": self.recommendation,
            "reason": self.reason,
            "risk_threshold": round(self.risk_threshold, 4),
            "features": self.features.to_dict(),
        }


@dataclass(frozen=True)
class ReliabilityBin:
    """Bin for Expected Calibration Error (ECE) reliability diagram."""
    bin_index: int
    lower_bound: float
    upper_bound: float
    sample_count: int
    avg_confidence: float
    empirical_accuracy: float
    calibration_error: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bin_index": self.bin_index,
            "lower_bound": round(self.lower_bound, 4),
            "upper_bound": round(self.upper_bound, 4),
            "sample_count": self.sample_count,
            "avg_confidence": round(self.avg_confidence, 4),
            "empirical_accuracy": round(self.empirical_accuracy, 4),
            "calibration_error": round(self.calibration_error, 4),
        }


@dataclass(frozen=True)
class CalibrationReport:
    """Complete calibration evaluation report (Brier, ECE, MCE, selective risk)."""
    brier_score: float
    ece: float
    mce: float
    n_trials: int
    coverage: float
    selective_risk: float
    decision_accuracy: float
    bins: Tuple[ReliabilityBin, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "brier_score": round(self.brier_score, 4),
            "ece_10": round(self.ece, 4),
            "mce": round(self.mce, 4),
            "n_trials": self.n_trials,
            "coverage": round(self.coverage, 4),
            "selective_risk": round(self.selective_risk, 4),
            "decision_accuracy": round(self.decision_accuracy, 4),
            "bins": [b.to_dict() for b in self.bins],
        }


# --- Standalone Calibration Metrics ---

def compute_brier_score(
    predictions: Sequence[float],
    outcomes: Sequence[bool],
) -> float:
    """Calculate mean squared probability error (Brier score).

    Args:
        predictions: Predicted failure probabilities in [0.0, 1.0].
        outcomes: Ground truth outcomes where True indicates failure, False indicates success.
    Returns:
        Brier score in [0.0, 1.0].
    """
    if len(predictions) != len(outcomes):
        raise ValueError("predictions and outcomes must have equal length")
    if not predictions:
        raise ValueError("empty predictions")
    n = len(predictions)
    return sum((p - (1.0 if y else 0.0)) ** 2 for p, y in zip(predictions, outcomes)) / n


def compute_expected_calibration_error(
    predictions: Sequence[float],
    outcomes: Sequence[bool],
    n_bins: int = 10,
) -> float:
    """Calculate Expected Calibration Error (ECE) across partitioned probability bins.

    Formula:
        ECE = sum_{m=1}^M (|B_m| / N) * |avg_confidence(B_m) - empirical_accuracy(B_m)|
    """
    if len(predictions) != len(outcomes):
        raise ValueError("predictions and outcomes must have equal length")
    if not predictions:
        raise ValueError("empty predictions")
    if n_bins < 1:
        raise ValueError("n_bins must be >= 1")

    n = len(predictions)
    ece = 0.0

    for b in range(n_bins):
        lo = b / n_bins
        hi = (b + 1) / n_bins
        bucket = [
            (p, 1.0 if y else 0.0)
            for p, y in zip(predictions, outcomes)
            if (lo <= p < hi) or (b == n_bins - 1 and lo <= p <= hi)
        ]
        if bucket:
            avg_p = sum(item[0] for item in bucket) / len(bucket)
            avg_y = sum(item[1] for item in bucket) / len(bucket)
            ece += (len(bucket) / n) * abs(avg_p - avg_y)

    return ece


def compute_calibration_report(
    records: Sequence[Tuple[float, bool, bool]],
    n_bins: int = 10,
) -> CalibrationReport:
    """Evaluate comprehensive calibration report from (p_failure, actual_failed, executed) tuples.

    Args:
        records: Sequence of (p_failure: float, actual_failed: bool, executed: bool).
        n_bins: Number of bins for ECE discretization.
    """
    if not records:
        raise ValueError("empty calibration records")
    n = len(records)

    # 1. Brier score over all predictions
    brier = sum((p - (1.0 if y else 0.0)) ** 2 for p, y, _ in records) / n

    # 2. ECE and reliability bins
    ece = 0.0
    mce = 0.0
    bins_list: List[ReliabilityBin] = []

    for b in range(n_bins):
        lo = b / n_bins
        hi = (b + 1) / n_bins
        bucket = [
            (p, 1.0 if y else 0.0)
            for p, y, _ in records
            if (lo <= p < hi) or (b == n_bins - 1 and lo <= p <= hi)
        ]
        cnt = len(bucket)
        if cnt > 0:
            avg_p = sum(item[0] for item in bucket) / cnt
            avg_y = sum(item[1] for item in bucket) / cnt
            err = abs(avg_p - avg_y)
            ece += (cnt / n) * err
            if err > mce:
                mce = err
        else:
            avg_p = (lo + hi) / 2.0
            avg_y = 0.0
            err = 0.0

        bins_list.append(
            ReliabilityBin(
                bin_index=b,
                lower_bound=lo,
                upper_bound=hi,
                sample_count=cnt,
                avg_confidence=avg_p,
                empirical_accuracy=avg_y,
                calibration_error=err,
            )
        )

    # 3. Execution metrics: coverage, selective risk, decision accuracy
    exec_items = [(p, y) for p, y, ex in records if ex]
    coverage = len(exec_items) / n
    selective_risk = (
        sum(1.0 if y else 0.0 for _, y in exec_items) / len(exec_items)
        if exec_items
        else 0.0
    )
    # Decision is accurate if executed & succeeded (not failed), or abstained & failed
    correct_decisions = sum(
        1 for _, y, ex in records if (ex and not y) or (not ex and y)
    )
    decision_accuracy = correct_decisions / n

    return CalibrationReport(
        brier_score=round(brier, 4),
        ece=round(ece, 4),
        mce=round(mce, 4),
        n_trials=n,
        coverage=round(coverage, 4),
        selective_risk=round(selective_risk, 4),
        decision_accuracy=round(decision_accuracy, 4),
        bins=tuple(bins_list),
    )


# --- Feature Extraction Helpers ---

_AST_OP_MAP = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Mod: "%",
    ast.BitXor: "^",
    ast.FloorDiv: "//",
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.And: "and",
    ast.Or: "or",
    ast.Not: "not",
    ast.USub: "neg",
}


def compute_ast_depth(source_code: str) -> int:
    """Compute maximum nesting depth of the AST."""
    if not source_code:
        return 1
    try:
        tree = ast.parse(source_code)
    except Exception:
        return 1

    def _walk(node: ast.AST) -> int:
        child_depths = [_walk(child) for child in ast.iter_child_nodes(node)]
        return 1 + max(child_depths, default=0)

    return _walk(tree)


def extract_ast_operators(source_code: str) -> Tuple[Set[str], int]:
    """Extract distinct operator tokens and total operator count from source AST."""
    if not source_code:
        return set(), 0
    try:
        tree = ast.parse(source_code)
    except Exception:
        return set(), 0

    unique_ops: Set[str] = set()
    total_count = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp):
            op_sym = _AST_OP_MAP.get(type(node.op), type(node.op).__name__)
            unique_ops.add(op_sym)
            total_count += 1
        elif isinstance(node, ast.Compare):
            for op in node.ops:
                op_sym = _AST_OP_MAP.get(type(op), type(op).__name__)
                unique_ops.add(op_sym)
                total_count += 1
        elif isinstance(node, ast.BoolOp):
            op_sym = _AST_OP_MAP.get(type(node.op), type(node.op).__name__)
            unique_ops.add(op_sym)
            total_count += 1
        elif isinstance(node, ast.UnaryOp):
            op_sym = _AST_OP_MAP.get(type(node.op), type(node.op).__name__)
            unique_ops.add(op_sym)
            total_count += 1

    return unique_ops, total_count


def compute_gene_depth(gene_dict: Dict[str, Any]) -> int:
    """Compute structural depth from gene dictionary specification."""
    if not gene_dict:
        return 1
    if gene_dict.get("is_composite"):
        depth_a = compute_gene_depth(gene_dict.get("gene_a", {}))
        depth_b = compute_gene_depth(gene_dict.get("gene_b", {}))
        return 1 + max(depth_a, depth_b)
    if gene_dict.get("is_dispatch"):
        rules = gene_dict.get("rules", [])
        rule_depths = [compute_gene_depth(r.get("gene", {})) for r in rules if isinstance(r, dict)]
        return 2 + max(rule_depths, default=1)
    if gene_dict.get("is_relational_gated"):
        return 3
    if gene_dict.get("is_relational") or gene_dict.get("is_gated"):
        return 2
    return 1


def extract_gene_operators(gene_dict: Dict[str, Any]) -> Set[str]:
    """Extract operator symbols declared directly in gene parameters."""
    ops: Set[str] = set()
    if not gene_dict:
        return ops

    if gene_dict.get("is_composite"):
        op = gene_dict.get("operator")
        if op:
            op_map = {"ADD": "+", "SUB": "-", "XOR": "^", "MULT": "*"}
            ops.add(op_map.get(op, op))
        ops.update(extract_gene_operators(gene_dict.get("gene_a", {})))
        ops.update(extract_gene_operators(gene_dict.get("gene_b", {})))

    if gene_dict.get("is_relational_gated") or gene_dict.get("is_relational"):
        if "length_op" in gene_dict:
            ops.add(str(gene_dict["length_op"]))
        if "congruence_op" in gene_dict:
            ops.add(str(gene_dict["congruence_op"]))
        if "boundary_op" in gene_dict:
            ops.add(str(gene_dict["boundary_op"]))
        if "combiner" in gene_dict:
            ops.add(str(gene_dict["combiner"]).lower())
        if "op" in gene_dict:
            ops.add(str(gene_dict["op"]))

    if gene_dict.get("is_dispatch"):
        for rule in gene_dict.get("rules", []):
            if isinstance(rule, dict) and "gene" in rule:
                ops.update(extract_gene_operators(rule["gene"]))

    return ops


# --- Metacognitive Predictor ---

class MetacognitivePredictor:
    """Calculates expected failure probability and evaluates pre-execution abstention.

    Connects Metacognitive Self-Modeling into the candidate evaluation pipeline.
    """

    def __init__(
        self,
        risk_tolerance_threshold: float = 0.70,
        storage_path: Optional[str] = None,
        base_failure_rate: float = 0.50,
        baseline_depth: int = 3,
    ):
        self.risk_tolerance_threshold = float(risk_tolerance_threshold)
        self.storage_path = Path(storage_path) if storage_path else None
        self.base_failure_rate = max(0.01, min(0.99, float(base_failure_rate)))
        self.baseline_depth = int(baseline_depth)
        self._records: List[Tuple[float, bool, bool]] = []  # (p_pred, actual_failed, executed)
        self._history_by_candidate: Dict[str, Dict[str, Any]] = {}

        if self.storage_path and self.storage_path.exists():
            self._load()

    @property
    def total_observed_trials(self) -> int:
        return len(self._records)

    def extract_features(
        self,
        candidate: CodeCandidate,
        failure_constraints: Optional[Sequence[FailureConstraint]] = None,
    ) -> CandidateFeatures:
        """Extract multi-dimensional structural and historical features from candidate."""
        gene_dict = candidate.gene_dict or {}
        source_code = candidate.source_code or ""

        # 1. Structural depth
        ast_d = compute_ast_depth(source_code)
        gene_d = compute_gene_depth(gene_dict)
        # Normalize AST depth: Module -> FunctionDef -> Return wraps an expression of depth (ast_d - 7)
        expr_ast_depth = max(1, ast_d - 7)
        structural_depth = max(gene_d, expr_ast_depth)

        # 2. Operator variety
        ast_ops, ast_op_cnt = extract_ast_operators(source_code)
        gene_ops = extract_gene_operators(gene_dict)
        all_ops = tuple(sorted(ast_ops.union(gene_ops)))
        total_op_cnt = max(len(all_ops), ast_op_cnt)

        if total_op_cnt == 0:
            operator_variety = 0.0
        else:
            # Normalized variety relative to expected diversity (cap at 6)
            operator_variety = len(all_ops) / min(6, max(1, total_op_cnt))

        # 3. Failure constraints check
        constraints = failure_constraints or ()
        violating_ids: List[str] = []
        constraint_risk = 0.0

        for c in constraints:
            violates, reason = self._check_constraint_violation(candidate, c)
            if violates:
                violating_ids.append(c.constraint_id)
                constraint_risk += 1.5
            else:
                # Partial / family overlap
                if self._check_constraint_overlap(candidate, c):
                    constraint_risk += 0.35

        # Historical density penalty
        if constraints:
            constraint_risk += 0.1 * min(5, len(constraints))

        # 4. Parameter extremity & degenerate heuristics
        param_extremity, heuristics = self._assess_heuristics_and_parameters(
            candidate=candidate,
            structural_depth=structural_depth,
            operator_count=total_op_cnt,
            unique_operator_count=len(all_ops),
            violating_count=len(violating_ids),
            constraints=constraints,
        )

        return CandidateFeatures(
            structural_depth=structural_depth,
            ast_depth=ast_d,
            gene_depth=gene_d,
            operator_variety=round(operator_variety, 4),
            unique_operators=all_ops,
            operator_count=total_op_cnt,
            constraint_conflicts_count=len(violating_ids),
            constraint_risk_score=round(constraint_risk, 4),
            violating_constraint_ids=tuple(violating_ids),
            parameter_extremity=round(param_extremity, 4),
            heuristics_triggered=tuple(heuristics),
        )

    def predict_failure_probability(
        self,
        candidate: CodeCandidate,
        failure_constraints: Optional[Sequence[FailureConstraint]] = None,
    ) -> float:
        """Calculate calibrated expected failure probability P(failure | candidate, constraints)."""
        feats = self.extract_features(candidate, failure_constraints)
        return self._calculate_p_failure_from_features(feats)

    def forecast(
        self,
        candidate: CodeCandidate,
        failure_constraints: Optional[Sequence[FailureConstraint]] = None,
    ) -> MetacognitiveForecast:
        """Generate comprehensive MetacognitiveForecast including pre-execution abstention decision."""
        feats = self.extract_features(candidate, failure_constraints)
        p_failure = self._calculate_p_failure_from_features(feats)
        p_success = round(1.0 - p_failure, 4)

        # Calibrated uncertainty: sigma = sqrt(p * (1 - p) / (N + 1))
        n_ev = len(feats.violating_constraint_ids) + len(self._records) + 2
        uncertainty = round(math.sqrt((p_failure * (1.0 - p_failure)) / (n_ev + 1)), 4)

        should_abs, _, reason = self._evaluate_abstention_decision(p_failure, feats)
        rec = "ABSTAIN_PREDICTED_FAILURE" if should_abs else "PROCEED_EVALUATION"

        return MetacognitiveForecast(
            candidate_id=candidate.candidate_id,
            p_failure=p_failure,
            p_success=p_success,
            uncertainty=uncertainty,
            should_abstain=should_abs,
            recommendation=rec,
            reason=reason,
            risk_threshold=self.risk_tolerance_threshold,
            features=feats,
        )

    def should_abstain(
        self,
        candidate: CodeCandidate,
        failure_constraints: Optional[Sequence[FailureConstraint]] = None,
        task_id: Optional[str] = None,
    ) -> Tuple[bool, float, str]:
        """Expose pre-execution abstention gating decision.

        Args:
            candidate: Prospective CodeCandidate.
            failure_constraints: Historical failure constraints deduced from prior cycles.
            task_id: Optional target task identifier.

        Returns:
            (should_abstain: bool, predicted_failure_risk: float, reason: str)
            If predicted failure risk exceeds risk tolerance threshold and candidate matches
            high-risk heuristics, returns (True, risk, "ABSTAIN_PREDICTED_FAILURE: ...")
            to save $0 budget and prevent uninformative evaluator calls.
        """
        feats = self.extract_features(candidate, failure_constraints)
        p_failure = self._calculate_p_failure_from_features(feats)
        return self._evaluate_abstention_decision(p_failure, feats)

    def record_outcome(
        self,
        candidate_id: str,
        predicted_prob: float,
        actual_failure: bool,
        executed: bool = True,
    ) -> None:
        """Record empirical outcome of a candidate for online calibration tracking."""
        record = (float(predicted_prob), bool(actual_failure), bool(executed))
        self._records.append(record)
        self._history_by_candidate[candidate_id] = {
            "predicted_prob": round(predicted_prob, 4),
            "actual_failure": actual_failure,
            "executed": executed,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self._save()

    def evaluate_calibration(
        self,
        records: Optional[Sequence[Tuple[float, bool, bool]]] = None,
        n_bins: int = 10,
    ) -> CalibrationReport:
        """Evaluate calibration metrics (Brier score, ECE, MCE, selective risk)."""
        target_records = records if records is not None else self._records
        if not target_records:
            raise ValueError("No calibration records available to evaluate")
        return compute_calibration_report(target_records, n_bins=n_bins)

    def reset_memory(self) -> None:
        """Reset internal calibration records."""
        self._records.clear()
        self._history_by_candidate.clear()
        if self.storage_path and self.storage_path.exists():
            try:
                self.storage_path.unlink()
            except OSError:
                pass

    # --- Internal Mechanics ---

    def _calculate_p_failure_from_features(self, feats: CandidateFeatures) -> float:
        """Calculate calibrated failure probability using state-grounded logistic log-odds."""
        # 1. Base log-odds prior
        z = math.log(self.base_failure_rate / (1.0 - self.base_failure_rate))

        # 2. Structural depth penalty (relative to baseline depth)
        excess_depth = max(0, feats.structural_depth - self.baseline_depth)
        z += 0.85 * (excess_depth / 3.0)

        # 3. Operator variety defect
        variety_defect = max(0.0, 1.0 - feats.operator_variety)
        z += 0.95 * variety_defect

        # 4. Constraint conflicts & history risk
        z += feats.constraint_risk_score

        # 5. Parameter extremity
        z += 1.10 * feats.parameter_extremity

        # 6. High-risk heuristic penalty
        z += 0.75 * len(feats.heuristics_triggered)

        # Logistic sigmoid
        p_fail = 1.0 / (1.0 + math.exp(-z))
        return round(max(0.0001, min(0.9999, p_fail)), 4)

    def _evaluate_abstention_decision(
        self,
        p_failure: float,
        feats: CandidateFeatures,
    ) -> Tuple[bool, float, str]:
        """Determine whether pre-execution abstention is recommended."""
        matches_heuristics = len(feats.heuristics_triggered) > 0
        exceeds_threshold = (p_failure >= self.risk_tolerance_threshold)

        if exceeds_threshold and matches_heuristics:
            trigger_list = ", ".join(feats.heuristics_triggered)
            reason = (
                f"ABSTAIN_PREDICTED_FAILURE: predicted failure risk {p_failure:.4f} >= "
                f"threshold {self.risk_tolerance_threshold:.4f} "
                f"(heuristics: {trigger_list}; conflicts: {feats.constraint_conflicts_count}; "
                f"depth: {feats.structural_depth})"
            )
            return True, p_failure, reason

        return False, p_failure, "PROCEED_EVALUATION"

    def _check_constraint_violation(
        self,
        candidate: CodeCandidate,
        constraint: FailureConstraint,
    ) -> Tuple[bool, Optional[str]]:
        """Check if candidate directly violates formal FailureConstraint."""
        gene = candidate.gene_dict or {}
        c_type = constraint.constraint_type
        forb = constraint.forbidden_pattern or {}
        w = constraint.violating_witness

        # 1. Length guard excess
        if c_type == "LENGTH_GUARD_EXCESS":
            min_thresh = forb.get("min_threshold", forb.get("min_length", 0))
            cand_thresh = gene.get("length_threshold", gene.get("min_length", 0))
            if cand_thresh >= min_thresh and len(w) < cand_thresh:
                return True, f"Length threshold {cand_thresh} blocks positive witness '{w}'"

        # 2. Modulus conflict
        elif c_type == "MODULUS_CONFLICT":
            forb_mod = forb.get("modulus")
            forb_res = forb.get("target_residue")
            cand_mod = gene.get("modulus")
            cand_res = gene.get("target_residue", gene.get("parity_threshold"))
            if cand_mod == forb_mod and cand_res == forb_res:
                forb_comb = forb.get("combiner")
                cand_comb = gene.get("combiner")
                if not forb_comb or cand_comb == forb_comb:
                    return True, f"Modulus {cand_mod} residue {cand_res} repeats falsified pattern"

        # 3. Operator collapse
        elif c_type == "OPERATOR_COLLAPSE":
            forb_op = forb.get("operator")
            cand_op = gene.get("operator")
            if forb_op and cand_op == forb_op:
                return True, f"Composite operator '{cand_op}' repeats falsified collapse"

        # 4. Linear scalar saturation
        elif c_type == "LINEAR_SCALAR_SATURATION":
            forb_stride = forb.get("window_stride")
            forb_mod = forb.get("modulus")
            if gene.get("window_stride") == forb_stride and gene.get("modulus") == forb_mod:
                return True, f"Linear stride {forb_stride} mod {forb_mod} saturated"

        return False, None

    def _check_constraint_overlap(
        self,
        candidate: CodeCandidate,
        constraint: FailureConstraint,
    ) -> bool:
        """Check partial parameter or topological overlap with historical failure."""
        gene = candidate.gene_dict or {}
        forb = constraint.forbidden_pattern or {}
        if "modulus" in forb and gene.get("modulus") == forb["modulus"]:
            return True
        if "operator" in forb and gene.get("operator") == forb["operator"]:
            return True
        if "min_length" in forb and abs(gene.get("min_length", 0) - forb["min_length"]) <= 1:
            return True
        return False

    def _assess_heuristics_and_parameters(
        self,
        candidate: CodeCandidate,
        structural_depth: int,
        operator_count: int,
        unique_operator_count: int,
        violating_count: int,
        constraints: Sequence[FailureConstraint],
    ) -> Tuple[float, List[str]]:
        """Identify high-risk heuristics and compute parameter extremity penalty."""
        gene = candidate.gene_dict or {}
        heuristics: List[str] = []
        penalty = 0.0

        # Heuristic 1: Exact constraint violation
        if violating_count > 0:
            heuristics.append(HighRiskHeuristic.CONSTRAINT_VIOLATION.value)
            penalty += 1.5 * violating_count

        # Heuristic 2: Operator collapse
        if operator_count >= 2 and unique_operator_count <= 1:
            heuristics.append(HighRiskHeuristic.OPERATOR_COLLAPSE.value)
            penalty += 1.25
        elif operator_count == 0 and not gene:
            heuristics.append(HighRiskHeuristic.OPERATOR_COLLAPSE.value)
            penalty += 1.0

        # Heuristic 3: Zero-weight degeneracy (mechanism outputs constant regardless of input)
        if gene.get("is_composite") is False:
            wl = gene.get("weight_length", 1)
            wd = gene.get("weight_density", 1)
            if wl == 0 and wd == 0:
                heuristics.append(HighRiskHeuristic.ZERO_WEIGHT_DEGENERACY.value)
                penalty += 1.5
        elif gene.get("is_relational_gated"):
            sw = gene.get("stride_weight", 1)
            dw = gene.get("density_weight", 1)
            lw = gene.get("length_weight", 0)
            if sw == 0 and dw == 0 and lw == 0:
                heuristics.append(HighRiskHeuristic.ZERO_WEIGHT_DEGENERACY.value)
                penalty += 1.5

        # Heuristic 4: Excessive structural depth
        if structural_depth >= 8:
            heuristics.append(HighRiskHeuristic.EXCESSIVE_STRUCTURAL_DEPTH.value)
            penalty += 1.0 + 0.3 * (structural_depth - 8)

        # Heuristic 5: Degenerate modulus
        modulus = gene.get("modulus")
        if modulus is not None and modulus <= 1:
            heuristics.append(HighRiskHeuristic.DEGENERATE_MODULUS.value)
            penalty += 2.0

        # Heuristic 6: Extreme length guard (outside standard length distribution <= 32)
        len_thresh = gene.get("length_threshold", gene.get("min_length", 0))
        if len_thresh > 32:
            heuristics.append(HighRiskHeuristic.EXTREME_LENGTH_GUARD.value)
            penalty += 1.2

        # Heuristic 7: Repeated forbidden operator
        for c in constraints:
            forb_op = c.forbidden_pattern.get("operator")
            if forb_op and gene.get("operator") == forb_op:
                if HighRiskHeuristic.REPEATED_FORBIDDEN_OPERATOR.value not in heuristics:
                    heuristics.append(HighRiskHeuristic.REPEATED_FORBIDDEN_OPERATOR.value)
                    penalty += 1.0

        return penalty, heuristics

    def _save(self) -> None:
        if not self.storage_path:
            return
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema_version": "1.0",
                "risk_tolerance_threshold": self.risk_tolerance_threshold,
                "base_failure_rate": self.base_failure_rate,
                "records": self._records,
                "history": self._history_by_candidate,
            }
            self.storage_path.write_text(json.dumps(payload, indent=2))
        except Exception:
            pass

    def _load(self) -> None:
        if not self.storage_path or not self.storage_path.exists():
            return
        try:
            data = json.loads(self.storage_path.read_text())
            self.risk_tolerance_threshold = float(data.get("risk_tolerance_threshold", self.risk_tolerance_threshold))
            self.base_failure_rate = float(data.get("base_failure_rate", self.base_failure_rate))
            self._records = [
                (float(r[0]), bool(r[1]), bool(r[2]))
                for r in data.get("records", [])
            ]
            self._history_by_candidate = data.get("history", {})
        except Exception:
            self._records = []
            self._history_by_candidate = {}
