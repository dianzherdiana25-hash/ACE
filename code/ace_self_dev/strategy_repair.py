"""Autonomous Strategy Repair Engine for ACE Self-Development Loop.

When a search strategy stagnates or exhausts its expressiveness:
1. Analyzes empirical failure modes (parametric vs structural).
2. Distinguishes coefficient/parameter changes from true algorithmic innovations.
3. Climbs the type-bounded representation hierarchy:
   Linear -> Composite -> Gated Single-Clause -> Relational Multi-Clause -> Multi-Task Ensemble.
4. Cleanly signals SEARCH_SPACE_EXHAUSTED when all available families are saturated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import PersistentResearchState, SystemDiagnosis


class MutationClass(str, Enum):
    PARAMETRIC = "PARAMETRIC"       # Coefficient, weight, or threshold mutation within same structure
    STRUCTURAL = "STRUCTURAL"       # Addition of conditional clauses, new operators, or multi-branch logic
    ENSEMBLE = "ENSEMBLE"           # Multi-capability routing across distinct benchmark tasks


class StrategyLadder(str, Enum):
    LINEAR = "LINEAR_MUTATION"
    COMPOSITE = "SYNTHESIZE_COMPOSITE_MECHANISM"
    GATED_SINGLE = "SYNTHESIZE_GATED_EXPRESSION_TREE"
    RELATIONAL_MULTI = "SYNTHESIZE_RELATIONAL_MULTI_CLAUSE"
    MULTI_TASK_ENSEMBLE = "SYNTHESIZE_MULTI_TASK_ENSEMBLE"


STRATEGY_ORDER: Tuple[str, ...] = (
    StrategyLadder.LINEAR.value,
    StrategyLadder.COMPOSITE.value,
    StrategyLadder.GATED_SINGLE.value,
    StrategyLadder.RELATIONAL_MULTI.value,
    StrategyLadder.MULTI_TASK_ENSEMBLE.value,
)

# Number of distinct, non-wrapping ordinals supported by each representation family
STRATEGY_ORDINAL_CAPS: Dict[str, int] = {
    StrategyLadder.LINEAR.value: 16,
    StrategyLadder.COMPOSITE.value: 4,
    StrategyLadder.GATED_SINGLE.value: 10,
    StrategyLadder.RELATIONAL_MULTI.value: 8,
    StrategyLadder.MULTI_TASK_ENSEMBLE.value: 4,
}


@dataclass(frozen=True)
class RepairDecision:
    """Actionable outcome of strategy repair analysis."""
    status: str  # "REPAIRED", "SEARCH_SPACE_EXHAUSTED", "CONTINUE_CURRENT"
    next_strategy: str
    target_task_id: str
    suggested_ordinal: int
    mutation_class: str
    rationalization: str
    exhausted_strategies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "next_strategy": self.next_strategy,
            "target_task_id": self.target_task_id,
            "suggested_ordinal": self.suggested_ordinal,
            "mutation_class": self.mutation_class,
            "rationalization": self.rationalization,
            "exhausted_strategies": self.exhausted_strategies,
        }


class StrategyRepairEngine:
    """Autonomously diagnoses strategy failures and guides representation escalation."""

    def __init__(self, max_attempts_per_strategy_task: int = 2):
        self.max_attempts_per_strategy_task = max_attempts_per_strategy_task

    def classify_mutation(
        self,
        base_gene: Optional[Dict[str, Any]],
        novel_gene: Dict[str, Any],
    ) -> str:
        """Strictly distinguish parameter coefficient tuning from structural algorithmic novelty."""
        if base_gene is None:
            return MutationClass.STRUCTURAL.value

        base_is_comp = base_gene.get("is_composite", False)
        novel_is_comp = novel_gene.get("is_composite", False)
        base_is_gated = base_gene.get("is_gated", False)
        novel_is_gated = novel_gene.get("is_gated", False)
        base_is_rel = base_gene.get("is_relational", False)
        novel_is_rel = novel_gene.get("is_relational", False)
        base_is_ens = base_gene.get("is_ensemble", False)
        novel_is_ens = novel_gene.get("is_ensemble", False)

        # Structural changes: representation family, operator, or control-flow changes
        if (base_is_comp != novel_is_comp) or (base_is_gated != novel_is_gated) or \
           (base_is_rel != novel_is_rel) or (base_is_ens != novel_is_ens):
            return MutationClass.STRUCTURAL.value

        if novel_is_ens:
            return MutationClass.ENSEMBLE.value

        if base_is_comp and novel_is_comp:
            if base_gene.get("operator") != novel_gene.get("operator"):
                return MutationClass.STRUCTURAL.value

        if base_is_rel and novel_is_rel:
            if base_gene.get("clause_type") != novel_gene.get("clause_type"):
                return MutationClass.STRUCTURAL.value

        # Otherwise, only numerical weights, strides, thresholds, or moduli changed
        return MutationClass.PARAMETRIC.value

    def determine_strategy_exhaustion(
        self,
        strategy: str,
        state: PersistentResearchState,
        tasks: List[str],
    ) -> bool:
        """Check if all tasks have exhausted the allowed exploration quota or ordinals for a strategy."""
        max_ordinals = STRATEGY_ORDINAL_CAPS.get(strategy, 10)

        for tid in tasks:
            failures = state.failure_catalog.get(tid, [])
            # Filter failures for this strategy
            strat_failures = [
                f for f in failures
                if self._matches_strategy(strategy, f.get("gene_dict", {}))
            ]
            tried_ordinals = {f.get("mutation_ordinal") for f in strat_failures if f.get("mutation_ordinal") is not None}
            # If any ordinal in 1..max_ordinals remains untried AND under attempts quota, task is not exhausted
            untried = set(range(1, max_ordinals + 1)) - tried_ordinals
            if untried and len(strat_failures) < self.max_attempts_per_strategy_task:
                return False

        # All tasks have met attempts quota or tried all ordinals
        return True

    def _matches_strategy(self, strategy: str, gene_dict: Dict[str, Any]) -> bool:
        if strategy == StrategyLadder.LINEAR.value:
            return not gene_dict.get("is_composite") and not gene_dict.get("is_gated") and not gene_dict.get("is_relational") and not gene_dict.get("is_ensemble")
        if strategy == StrategyLadder.COMPOSITE.value:
            return gene_dict.get("is_composite", False)
        if strategy == StrategyLadder.GATED_SINGLE.value:
            return gene_dict.get("is_gated", False) and not gene_dict.get("is_relational")
        if strategy == StrategyLadder.RELATIONAL_MULTI.value:
            return gene_dict.get("is_relational", False)
        if strategy == StrategyLadder.MULTI_TASK_ENSEMBLE.value:
            return gene_dict.get("is_ensemble", False)
        return False

    def repair_search_strategy(
        self,
        current_strategy: str,
        current_task_id: str,
        stagnation_reason: str,
        state: PersistentResearchState,
        diagnosis: SystemDiagnosis,
        tasks: List[str],
    ) -> RepairDecision:
        """Autonomously formulate the next non-stagnant research strategy."""
        # Find exhausted strategies
        exhausted_strategies = [
            strat for strat in STRATEGY_ORDER
            if self.determine_strategy_exhaustion(strat, state, tasks)
        ]

        # Prioritize weakest task by diagnostic failure rate
        task_scores = diagnosis.diagnostic_details.get("task_scores", {})
        ranked_tasks = sorted(tasks, key=lambda tid: task_scores.get(tid, 0.5))

        # Determine next viable strategy from ladder
        next_strategy = None
        for strat in STRATEGY_ORDER:
            if strat not in exhausted_strategies:
                next_strategy = strat
                break

        if next_strategy is None:
            # Entire representation hierarchy exhausted
            return RepairDecision(
                status="SEARCH_SPACE_EXHAUSTED",
                next_strategy=current_strategy,
                target_task_id=current_task_id,
                suggested_ordinal=1,
                mutation_class=MutationClass.STRUCTURAL.value,
                rationalization=(
                    f"All {len(STRATEGY_ORDER)} representation families "
                    f"({', '.join(STRATEGY_ORDER)}) have been systematically explored and exhausted "
                    f"without reaching promotion threshold. Halting autonomously to prevent uninformative loops."
                ),
                exhausted_strategies=exhausted_strategies,
            )

        # Select target task for next_strategy
        selected_task = ranked_tasks[0]
        max_ords = STRATEGY_ORDINAL_CAPS.get(next_strategy, 10)
        selected_ordinal = 1

        for cand_task in ranked_tasks:
            failures = state.failure_catalog.get(cand_task, [])
            strat_failures = [
                f for f in failures
                if self._matches_strategy(next_strategy, f.get("gene_dict", {}))
            ]
            tried_ords = {f.get("mutation_ordinal") for f in strat_failures if f.get("mutation_ordinal") is not None}
            untried = [o for o in range(1, max_ords + 1) if o not in tried_ords]
            if untried and len(strat_failures) < self.max_attempts_per_strategy_task:
                selected_task = cand_task
                selected_ordinal = untried[0]
                break
            elif untried:
                selected_task = cand_task
                selected_ordinal = untried[0]

        is_structural = (next_strategy != current_strategy)
        mutation_class = MutationClass.STRUCTURAL.value if is_structural else MutationClass.PARAMETRIC.value

        rationalization = (
            f"Stagnation [{stagnation_reason}] detected on '{current_strategy}'. "
            f"Repairing search policy: pivoting to '{next_strategy}' (Family: {mutation_class}) "
            f"on weakest capability '{selected_task}' (Ordinal {selected_ordinal}/{max_ords})."
        )

        return RepairDecision(
            status="REPAIRED",
            next_strategy=next_strategy,
            target_task_id=selected_task,
            suggested_ordinal=selected_ordinal,
            mutation_class=mutation_class,
            rationalization=rationalization,
            exhausted_strategies=exhausted_strategies,
        )
