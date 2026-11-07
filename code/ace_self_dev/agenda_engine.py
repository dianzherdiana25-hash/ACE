"""Agenda Engine: Autonomous Research Agenda and Hypothesis Formulation for ACE V0.2.

Eliminates static manual parameters (cycle=1, task_seed=42, mutation_ordinal=1).
ACE autonomously determines:
1. Dynamic task seed derived deterministically from prior state digest and cycle count.
2. Target task selected based on real diagnostic error cues and failure catalog history.
3. Mutation strategy and ordinal selected to avoid repeating previously falsified configurations.
4. Next research agenda formulation based on empirical evaluation outcomes and StrategyRepairEngine.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional, Tuple

from .confirmation_suite import ConfirmationTask
from .models import (
    NextAgendaPriority,
    PersistentResearchState,
    ResearchHypothesis,
    SystemDiagnosis,
)
from .strategy_repair import (
    FAMILY_TO_STRATEGY,
    STRATEGY_TO_FAMILY,
    RepresentationFamily,
    StrategyRepairDecision,
    StrategyRepairEngine,
)


class AgendaEngine:
    """Autonomous search policy and agenda planner."""

    def __init__(self, max_attempts_per_task: int = 2):
        self.max_attempts_per_task = max_attempts_per_task
        self.strategy_repair = StrategyRepairEngine(max_attempts_per_family=max_attempts_per_task)

    def derive_task_seed(self, cycle_id: int, state_digest: str) -> int:
        """Derive a reproducible, independent pseudo-random task seed from state entropy."""
        seed_hash = hashlib.sha256(f"seed:{cycle_id}:{state_digest}".encode("utf-8")).hexdigest()
        # Range: 1000 - 9999
        return (int(seed_hash[:8], 16) % 9000) + 1000

    def select_cycle_strategy(
        self,
        state: PersistentResearchState,
        diagnosis: SystemDiagnosis,
        tasks: Dict[str, ConfirmationTask],
    ) -> Tuple[str, int, int]:
        """Autonomously select target_task_id, task_seed, and mutation_ordinal based on state history.
        
        Returns:
            (target_task_id, task_seed, mutation_ordinal)
        """
        cycle_id = state.cycle_count + 1
        state_digest = state.state_digest or "GENESIS"
        task_seed = self.derive_task_seed(cycle_id, state_digest)

        # Ranked tasks by failure rate (highest failure rate first)
        task_scores = diagnosis.diagnostic_details.get("task_scores", {})
        ranked_tasks = sorted(tasks.keys(), key=lambda tid: task_scores.get(tid, 0.5))

        initial_task = ranked_tasks[0] if ranked_tasks else "task_k2_modular_stride_shift"
        initial_strategy = "LINEAR_MUTATION"
        if state.next_agenda_priority:
            rec_tid = state.next_agenda_priority.get("priority_task_id")
            rec_strat = state.next_agenda_priority.get("strategy")
            if rec_tid in tasks:
                initial_task = rec_tid
            if rec_strat in STRATEGY_TO_FAMILY:
                initial_strategy = rec_strat

        decision = self.strategy_repair.repair_strategy(
            current_task_id=initial_task,
            current_strategy=initial_strategy,
            state=state,
            tasks=tasks,
        )

        if decision.status == "SEARCH_SPACE_EXHAUSTED" or decision.is_terminal:
            return "SEARCH_SPACE_EXHAUSTED", task_seed, 0

        return decision.next_task_id, task_seed, decision.suggested_ordinal

    def formulate_hypothesis(
        self,
        cycle_id: int,
        target_task_id: str,
        target_task: Optional[ConfirmationTask],
        ordinal: int,
        state: PersistentResearchState,
        strategy: Optional[str] = None,
    ) -> ResearchHypothesis:
        """Formulate a falsifiable hypothesis tailored to the selected task, strategy, and ordinal."""
        if target_task_id == "SEARCH_SPACE_EXHAUSTED":
            statement = f"Cycle {cycle_id}: Search space is exhausted across all representation families."
            return ResearchHypothesis(
                hypothesis_id=f"HYP_EXHAUSTED_C{cycle_id}",
                statement=statement,
                target_task_id="NONE",
                min_required_gain=0.1500,
                max_regression_tolerance=0.0200,
                preregistration_hash=hashlib.sha256(statement.encode()).hexdigest(),
                strategy="SEARCH_SPACE_EXHAUSTED",
            )

        task_family = target_task.family if target_task else "unknown"

        if strategy is None:
            if state.next_agenda_priority and state.next_agenda_priority.get("priority_task_id") == target_task_id:
                strategy = state.next_agenda_priority.get("strategy", "LINEAR_MUTATION")
            else:
                rep_dec = self.strategy_repair.repair_strategy(
                    current_task_id=target_task_id,
                    current_strategy="LINEAR_MUTATION",
                    state=state,
                    tasks={target_task_id: target_task} if target_task else {},
                )
                strategy = rep_dec.next_strategy or "LINEAR_MUTATION"

        past_failures = state.failure_catalog.get(target_task_id, [])

        if strategy == "MULTI_TASK_DISPATCH":
            statement = (
                f"Cycle {cycle_id}: Applying multi-task dispatch router synthesis (ordinal {ordinal}) for {target_task_id} "
                f"({task_family}) will achieve holdout gain >= 0.1500 without prior regression > 0.0200."
            )
            hyp_id = f"HYP_AUTONOMOUS_C{cycle_id}_{target_task_id}_dispatch_ord{ordinal}"
        elif strategy == "RELATIONAL_MULTI_CLAUSE":
            statement = (
                f"Cycle {cycle_id}: Applying relational multi-clause expression synthesis (ordinal {ordinal}) for {target_task_id} "
                f"({task_family}) will achieve holdout gain >= 0.1500 without prior regression > 0.0200."
            )
            hyp_id = f"HYP_AUTONOMOUS_C{cycle_id}_{target_task_id}_relational_ord{ordinal}"
        elif strategy == "SYNTHESIZE_GATED_EXPRESSION_TREE":
            statement = (
                f"Cycle {cycle_id}: Applying gated modular expression tree synthesis (ordinal {ordinal}) for {target_task_id} "
                f"({task_family}) will achieve holdout gain >= 0.1500 without prior regression > 0.0200."
            )
            hyp_id = f"HYP_AUTONOMOUS_C{cycle_id}_{target_task_id}_gated_ord{ordinal}"
        elif strategy == "SYNTHESIZE_COMPOSITE_MECHANISM":
            statement = (
                f"Cycle {cycle_id}: Applying composite mechanism synthesis (operator ordinal {ordinal}) for {target_task_id} "
                f"({task_family}) will achieve holdout gain >= 0.1500 without prior regression > 0.0200."
            )
            hyp_id = f"HYP_AUTONOMOUS_C{cycle_id}_{target_task_id}_comp_ord{ordinal}"
        else:
            strategy = "LINEAR_MUTATION"
            prior_context = f" (after {len(past_failures)} prior falsified attempts)" if past_failures else ""
            statement = (
                f"Cycle {cycle_id}: Applying typed AST mutation ordinal {ordinal} for {target_task_id} "
                f"({task_family}){prior_context} will achieve holdout gain >= 0.1500 without prior regression > 0.0200."
            )
            hyp_id = f"HYP_AUTONOMOUS_C{cycle_id}_{target_task_id}_ord{ordinal}"

        # Hash commitment of hypothesis
        h_payload = f"{hyp_id}:{target_task_id}:{ordinal}:{statement}:{strategy}".encode("utf-8")
        prereg_hash = hashlib.sha256(h_payload).hexdigest()

        return ResearchHypothesis(
            hypothesis_id=hyp_id,
            statement=statement,
            target_task_id=target_task_id,
            min_required_gain=0.1500,
            max_regression_tolerance=0.0200,
            max_search_budget_cost_usd=0.0,
            preregistration_hash=prereg_hash,
            strategy=strategy,
        )

    def formulate_next_goal(
        self,
        current_cycle_id: int,
        current_task_id: str,
        current_ordinal: int,
        decision: str,
        gain: float,
        tasks: Dict[str, ConfirmationTask],
        state: PersistentResearchState,
        current_strategy: str = "LINEAR_MUTATION",
    ) -> NextAgendaPriority:
        """Determine ACE's autonomous next research goal based on empirical outcome and strategy repair."""
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if decision == "ACCEPTED":
            remaining_tasks = [tid for tid in tasks.keys() if tid != current_task_id]
            next_tid = remaining_tasks[0] if remaining_tasks else current_task_id
            return NextAgendaPriority(
                priority_task_id=next_tid,
                priority_family=tasks[next_tid].family if next_tid in tasks else "unknown",
                strategy="EXPAND_PROMOTED_CAPABILITY",
                suggested_ordinal=1,
                rationalization=(
                    f"Candidate for {current_task_id} was successfully accepted (gain {gain:+.4f}). "
                    f"Next objective is to extend capability to {next_tid}."
                ),
                timestamp=now,
            )

        # Failure / Stagnation: Query StrategyRepairEngine to determine next strategy
        rep_decision = self.strategy_repair.repair_strategy(
            current_task_id=current_task_id,
            current_strategy=current_strategy,
            state=state,
            tasks=tasks,
        )

        if rep_decision.is_terminal or rep_decision.status == "SEARCH_SPACE_EXHAUSTED":
            return NextAgendaPriority(
                priority_task_id=current_task_id,
                priority_family="SEARCH_SPACE_EXHAUSTED",
                strategy="SEARCH_SPACE_EXHAUSTED",
                suggested_ordinal=0,
                rationalization=rep_decision.repair_rationalization,
                timestamp=now,
            )

        next_tid = rep_decision.next_task_id
        next_family_name = tasks[next_tid].family if next_tid in tasks else "unknown"
        return NextAgendaPriority(
            priority_task_id=next_tid,
            priority_family=next_family_name,
            strategy=rep_decision.next_strategy,
            suggested_ordinal=rep_decision.suggested_ordinal,
            rationalization=rep_decision.repair_rationalization,
            timestamp=now,
        )
