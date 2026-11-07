"""Stagnation Detector: Early detection of algorithmic, semantic, and structural stagnation.

Guarantees:
1. Detect duplicate source_sha against persistent research history.
2. Detect semantic equivalence via prediction bitvector comparison on train/validation pools.
3. Detect no-validation-improvement over K consecutive attempts (patience window).
4. Detect exhausted search space for the active strategy.
5. Halt redundant evaluations and prevent uninformative commits.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from ace_loop.source_evolution import compile_function, gene_from_dict
from .confirmation_suite import ConfirmationTask
from .models import (
    CandidateDecision,
    CodeCandidate,
    EvaluationReceipt,
    PersistentResearchState,
    ResearchHypothesis,
)


class StagnationType(str, Enum):
    """Categorization of detected research stagnation."""
    NONE = "NONE"
    DUPLICATE_SOURCE_SHA = "DUPLICATE_SOURCE_SHA"
    SEMANTIC_EQUIVALENCE = "SEMANTIC_EQUIVALENCE"
    NO_VALIDATION_IMPROVEMENT = "NO_VALIDATION_IMPROVEMENT"
    SEARCH_SPACE_EXHAUSTED = "SEARCH_SPACE_EXHAUSTED"
    PERSISTENT_STAGNATION = "PERSISTENT_STAGNATION"


@dataclass(frozen=True)
class StagnationCheckResult:
    """Outcome of pre-evaluation or post-evaluation stagnation analysis."""
    is_stagnated: bool
    stagnation_type: StagnationType
    reason: str
    should_evaluate: bool
    should_commit: bool
    historical_match_id: Optional[str] = None
    bitvector: Optional[str] = None
    bitvector_hash: Optional[str] = None
    consecutive_no_improvement: int = 0
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_stagnated": self.is_stagnated,
            "stagnation_type": self.stagnation_type.value,
            "reason": self.reason,
            "should_evaluate": self.should_evaluate,
            "should_commit": self.should_commit,
            "historical_match_id": self.historical_match_id,
            "bitvector": self.bitvector,
            "bitvector_hash": self.bitvector_hash,
            "consecutive_no_improvement": self.consecutive_no_improvement,
            "details": self.details,
        }


class BitvectorRegistry:
    """Persistent catalog of candidate prediction bitvectors on confirmation pools.
    
    Enables O(1) detection of semantically equivalent candidates (candidates that produce
    identical output bitvectors across train and validation inputs despite syntactical differences).
    """

    def __init__(self, persistence_path: Optional[Path] = None):
        self.persistence_path = persistence_path
        # Map: task_id -> {bitvector_hash: record_dict}
        self._registry: Dict[str, Dict[str, Dict[str, Any]]] = {}
        if self.persistence_path and self.persistence_path.exists():
            self.load()

    def register(
        self,
        task_id: str,
        bitvector_hash: str,
        candidate_id: str,
        cycle_id: Optional[int] = None,
        source_sha: str = "",
        score: float = 0.0,
        bitvector: Optional[str] = None,
    ) -> None:
        """Register a candidate's bitvector in the catalog."""
        if task_id not in self._registry:
            self._registry[task_id] = {}
        self._registry[task_id][bitvector_hash] = {
            "candidate_id": candidate_id,
            "cycle_id": cycle_id,
            "source_sha": source_sha,
            "score": score,
            "bitvector_preview": bitvector[:32] if bitvector else "",
        }
        if self.persistence_path:
            self.save()

    def lookup(self, task_id: str, bitvector_hash: str) -> Optional[Dict[str, Any]]:
        """Find an existing candidate producing the identical bitvector."""
        return self._registry.get(task_id, {}).get(bitvector_hash)

    def has(self, task_id: str, bitvector_hash: str) -> bool:
        return bitvector_hash in self._registry.get(task_id, {})

    def save(self) -> None:
        """Persist catalog to disk atomically."""
        if not self.persistence_path:
            return
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.persistence_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._registry, indent=2), encoding="utf-8")
        tmp.replace(self.persistence_path)

    def load(self) -> None:
        """Load catalog from disk."""
        if not self.persistence_path or not self.persistence_path.exists():
            return
        try:
            self._registry = json.loads(self.persistence_path.read_text(encoding="utf-8"))
        except Exception:
            self._registry = {}


DEFAULT_STRATEGY_LIMITS: Dict[str, int] = {
    "LINEAR_MUTATION": 16,
    "SYNTHESIZE_COMPOSITE_MECHANISM": 32,
    "SYNTHESIZE_GATED_EXPRESSION_TREE": 10,
    "RELATIONAL_MULTI_CLAUSE": 12,
    "MULTI_TASK_DISPATCH": 8,
}


def candidate_to_string_predicate(fn: Callable[[int, int, int], int]) -> Callable[[str], bool]:
    """Convert raw candidate function into string classifier predicate."""
    def predicate(w: str) -> bool:
        length = len(w)
        density = w.count("a")
        stride_val = sum(1 for i, ch in enumerate(w) if i % 2 == 0 and ch == "a")
        raw_val = fn(length, density, stride_val)
        return (raw_val % 2 == 0)
    return predicate


class StagnationDetector:
    """Detects syntactic duplication, semantic equivalence, plateau stagnation, and search space exhaustion."""

    def __init__(
        self,
        patience_k: int = 3,
        min_improvement: float = 0.0010,
        strategy_limits: Optional[Dict[str, int]] = None,
        registry: Optional[BitvectorRegistry] = None,
        registry_path: Optional[str] = None,
    ):
        self.patience_k = patience_k
        self.min_improvement = min_improvement
        self.strategy_limits = dict(strategy_limits or DEFAULT_STRATEGY_LIMITS)
        if registry is not None:
            self.registry = registry
        elif registry_path is not None:
            self.registry = BitvectorRegistry(persistence_path=Path(registry_path))
        else:
            self.registry = BitvectorRegistry()

    def compute_prediction_bitvector(
        self,
        candidate_fn: Callable[[str], bool],
        eval_pool: List[Tuple[str, bool]],
    ) -> Tuple[str, str]:
        """Evaluate candidate on pool inputs and return binary bitvector and its SHA-256 digest."""
        bits = ["1" if candidate_fn(w) else "0" for w, _ in eval_pool]
        bitvector_str = "".join(bits)
        bitvector_hash = hashlib.sha256(bitvector_str.encode("utf-8")).hexdigest()
        return bitvector_str, bitvector_hash

    def check_duplicate_source_sha(
        self,
        source_sha: str,
        state: PersistentResearchState,
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """Check if source_sha already exists in persistent research state completed cycles."""
        for c in state.completed_cycles:
            if c.get("source_sha") == source_sha:
                return True, c.get("candidate_id"), c.get("cycle_id")
        return False, None, None

    def check_semantic_equivalence(
        self,
        task_id: str,
        bitvector_hash: str,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Check if identical prediction bitvector has already been registered for this task."""
        match = self.registry.lookup(task_id, bitvector_hash)
        if match is not None:
            return True, match
        return False, None

    def check_patience_window(
        self,
        state: PersistentResearchState,
        task_id: Optional[str] = None,
        patience_k: Optional[int] = None,
        k: Optional[int] = None,
    ) -> Tuple[bool, int, float, List[float]]:
        """Detect lack of validation/holdout improvement over K consecutive attempts.
        
        Returns:
            (is_stagnated, consecutive_no_improvement_count, best_score, score_history)
        """
        effective_k = k or patience_k or self.patience_k
        if not state.completed_cycles:
            return False, 0, 0.0, []

        relevant_cycles = [
            c for c in state.completed_cycles
            if task_id is None or c.get("target_task_id") == task_id
        ]
        if not relevant_cycles:
            return False, 0, 0.0, []

        scores = [float(c.get("holdout_score", 0.0)) for c in relevant_cycles]
        if len(scores) < effective_k:
            return False, 0, max(scores), scores

        best_score = scores[0]
        consecutive_no_imp = 0

        for s in scores[1:]:
            if s >= best_score + self.min_improvement:
                best_score = s
                consecutive_no_imp = 0
            else:
                consecutive_no_imp += 1

        is_stagnated = consecutive_no_imp >= effective_k
        return is_stagnated, consecutive_no_imp, best_score, scores

    def check_strategy_exhaustion(
        self,
        strategy: str,
        task_id: str,
        state: PersistentResearchState,
    ) -> Tuple[bool, int, int, str]:
        """Determine if all valid parameter configurations for a strategy have been tried."""
        limit = self.strategy_limits.get(strategy, 10)
        past_failures = state.failure_catalog.get(task_id, [])

        # Collect unique ordinals attempted for this strategy
        tried_ordinals: Set[int] = set()
        for f in past_failures:
            g = f.get("gene_dict", {})
            is_comp = g.get("is_composite", False)
            is_gated = g.get("is_gated", False)
            is_rel = g.get("is_relational", False)
            is_disp = g.get("is_dispatch", False)

            match_strat = False
            if strategy == "LINEAR_MUTATION" and not is_comp and not is_gated and not is_rel and not is_disp:
                match_strat = True
            elif strategy == "SYNTHESIZE_COMPOSITE_MECHANISM" and is_comp:
                match_strat = True
            elif strategy == "SYNTHESIZE_GATED_EXPRESSION_TREE" and is_gated:
                match_strat = True
            elif strategy == "RELATIONAL_MULTI_CLAUSE" and is_rel:
                match_strat = True
            elif strategy == "MULTI_TASK_DISPATCH" and is_disp:
                match_strat = True

            if match_strat:
                ord_val = f.get("mutation_ordinal")
                if ord_val is not None:
                    tried_ordinals.add(int(ord_val))

        attempted_count = len(tried_ordinals)
        if attempted_count >= limit:
            return True, attempted_count, limit, (
                f"Strategy '{strategy}' for task '{task_id}' exhausted: {attempted_count}/{limit} "
                f"parameter ordinals attempted ({sorted(tried_ordinals)})."
            )

        return False, attempted_count, limit, f"{attempted_count}/{limit} ordinals attempted."

    def inspect_pre_evaluation(
        self,
        candidate: CodeCandidate,
        hypothesis: ResearchHypothesis,
        state: PersistentResearchState,
        task: ConfirmationTask,
    ) -> StagnationCheckResult:
        """Comprehensive pre-evaluation gating check.
        
        Evaluates candidate syntactic uniqueness, strategy exhaustion, semantic bitvector uniqueness,
        and patience plateau before burning execution budget or committing uninformative cycles.
        """
        target_tid = hypothesis.target_task_id
        strat = getattr(hypothesis, "strategy", "LINEAR_MUTATION")

        # 1. Syntactic duplicate check (source_sha)
        is_dup, match_cand, match_cycle = self.check_duplicate_source_sha(candidate.source_sha, state)
        if is_dup:
            return StagnationCheckResult(
                is_stagnated=True,
                stagnation_type=StagnationType.DUPLICATE_SOURCE_SHA,
                reason=(
                    f"Candidate {candidate.candidate_id} source_sha '{candidate.source_sha[:12]}' is an exact "
                    f"syntactic duplicate of historical candidate {match_cand} (Cycle {match_cycle})."
                ),
                should_evaluate=False,
                should_commit=False,
                historical_match_id=match_cand,
                details={"source_sha": candidate.source_sha, "prior_cycle": match_cycle},
            )

        # 2. Strategy search space exhaustion check
        is_exhausted, attempted, limit, reason_exhaust = self.check_strategy_exhaustion(strat, target_tid, state)
        if is_exhausted:
            return StagnationCheckResult(
                is_stagnated=True,
                stagnation_type=StagnationType.SEARCH_SPACE_EXHAUSTED,
                reason=reason_exhaust,
                should_evaluate=False,
                should_commit=False,
                details={"strategy": strat, "attempted": attempted, "limit": limit},
            )

        # 3. Semantic equivalence check (output bitvector across train/validation pool)
        try:
            gene = gene_from_dict(candidate.gene_dict)
            source_bytes = candidate.source_code.encode("utf-8")
            raw_fn = compile_function(source_bytes, gene)
            cand_pred = candidate_to_string_predicate(raw_fn)

            combined_pool = list(task.train_pool) + list(task.validation_pool)
            bv_str, bv_hash = self.compute_prediction_bitvector(cand_pred, combined_pool)

            is_equiv, match_rec = self.check_semantic_equivalence(target_tid, bv_hash)
            if is_equiv and match_rec is not None:
                return StagnationCheckResult(
                    is_stagnated=True,
                    stagnation_type=StagnationType.SEMANTIC_EQUIVALENCE,
                    reason=(
                        f"Candidate {candidate.candidate_id} is semantically equivalent to prior candidate "
                        f"{match_rec.get('candidate_id')} (identical {len(combined_pool)}-bit output vector across pools)."
                    ),
                    should_evaluate=False,
                    should_commit=False,
                    historical_match_id=match_rec.get("candidate_id"),
                    bitvector=bv_str,
                    bitvector_hash=bv_hash,
                    details={"bitvector_hash": bv_hash, "matched_candidate": match_rec},
                )
        except Exception as e:
            # If compilation fails, isolated evaluator will reject; let evaluation handle or block
            return StagnationCheckResult(
                is_stagnated=True,
                stagnation_type=StagnationType.NONE,
                reason=f"Compilation/AST failure in pre-evaluation: {e}",
                should_evaluate=False,
                should_commit=False,
                details={"error": str(e)},
            )

        # 4. Patience window check
        is_plateau, consecutive, best_sc, _ = self.check_patience_window(state, task_id=target_tid)
        if is_plateau:
            return StagnationCheckResult(
                is_stagnated=True,
                stagnation_type=StagnationType.NO_VALIDATION_IMPROVEMENT,
                reason=(
                    f"Patience window exceeded: {consecutive} consecutive attempts on '{target_tid}' "
                    f"without validation improvement (best={best_sc:.4f}, min_improvement={self.min_improvement})."
                ),
                should_evaluate=False,
                should_commit=False,
                bitvector=bv_str,
                bitvector_hash=bv_hash,
                consecutive_no_improvement=consecutive,
                details={"best_score": best_sc, "consecutive_no_improvement": consecutive},
            )

        # 5. Clean: candidate is novel, non-redundant, and eligible for evaluation
        return StagnationCheckResult(
            is_stagnated=False,
            stagnation_type=StagnationType.NONE,
            reason="Candidate is novel, syntactically unique, and semantically non-redundant.",
            should_evaluate=True,
            should_commit=True,
            bitvector=bv_str,
            bitvector_hash=bv_hash,
            details={"bitvector_hash": bv_hash},
        )

    def register_evaluated_candidate(
        self,
        task_id: str,
        candidate_id: str,
        source_sha: str,
        score: float,
        bitvector_hash: str,
        cycle_id: Optional[int] = None,
        bitvector: Optional[str] = None,
    ) -> None:
        """Register an evaluated candidate into the bitvector catalog to block future semantic duplicates."""
        self.registry.register(
            task_id=task_id,
            bitvector_hash=bitvector_hash,
            candidate_id=candidate_id,
            cycle_id=cycle_id,
            source_sha=source_sha,
            score=score,
            bitvector=bitvector,
        )
