"""Agenda Engine: Autonomous Research Agenda and Hypothesis Formulation for ACE V0.2.

Eliminates static manual parameters (cycle=1, task_seed=42, mutation_ordinal=1).
ACE autonomously determines:
1. Dynamic task seed derived deterministically from prior state digest and cycle count.
2. Target task selected based on real diagnostic error cues and failure catalog history.
3. Mutation strategy and ordinal selected to avoid repeating previously falsified configurations.
4. Next research agenda formulation based on empirical evaluation outcomes.
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


class AgendaEngine:
    """Autonomous search policy and agenda planner."""

    def __init__(self, max_attempts_per_task: int = 2):
        self.max_attempts_per_task = max_attempts_per_task

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

        selected_task_id = ranked_tasks[0]
        selected_ordinal = 1

        # Check if all tasks have exhausted linear mutations
        linear_failures_per_task = {
            tid: len([f for f in state.failure_catalog.get(tid, []) if not f.get("gene_dict", {}).get("is_composite", False) and not f.get("gene_dict", {}).get("is_gated", False)])
            for tid in tasks.keys()
        }
        all_linear_exhausted = all(c >= self.max_attempts_per_task for c in linear_failures_per_task.values())

        composite_failures_per_task = {
            tid: [f for f in state.failure_catalog.get(tid, []) if f.get("gene_dict", {}).get("is_composite", False)]
            for tid in tasks.keys()
        }
        all_composite_exhausted = all_linear_exhausted and all(
            len(c) >= self.max_attempts_per_task for c in composite_failures_per_task.values()
        )

        if all_composite_exhausted:
            gated_failures_per_task = {
                tid: [f for f in state.failure_catalog.get(tid, []) if f.get("gene_dict", {}).get("is_gated", False)]
                for tid in tasks.keys()
            }
            under_quota = [tid for tid in ranked_tasks if len(gated_failures_per_task.get(tid, [])) < self.max_attempts_per_task]
            if under_quota:
                if state.next_agenda_priority and state.next_agenda_priority.get("priority_task_id") in under_quota:
                    selected_task_id = state.next_agenda_priority.get("priority_task_id")
                else:
                    selected_task_id = under_quota[0]
            else:
                if state.next_agenda_priority and state.next_agenda_priority.get("priority_task_id") in tasks:
                    selected_task_id = state.next_agenda_priority.get("priority_task_id")
                else:
                    selected_task_id = min(ranked_tasks, key=lambda tid: len(gated_failures_per_task.get(tid, [])))

            tried_gated = {f.get("mutation_ordinal") for f in gated_failures_per_task.get(selected_task_id, [])}
            selected_ordinal = 1
            while selected_ordinal in tried_gated and selected_ordinal <= 10:
                selected_ordinal += 1

            return selected_task_id, task_seed, selected_ordinal

        if all_linear_exhausted:
            if state.next_agenda_priority:
                rec_tid = state.next_agenda_priority.get("priority_task_id")
                if rec_tid in tasks and len(composite_failures_per_task.get(rec_tid, [])) < self.max_attempts_per_task:
                    selected_task_id = rec_tid
                else:
                    for cand_tid in ranked_tasks:
                        if len(composite_failures_per_task.get(cand_tid, [])) < self.max_attempts_per_task:
                            selected_task_id = cand_tid
                            break
            else:
                for cand_tid in ranked_tasks:
                    if len(composite_failures_per_task.get(cand_tid, [])) < self.max_attempts_per_task:
                        selected_task_id = cand_tid
                        break

            tried_comp = {f.get("mutation_ordinal") for f in composite_failures_per_task.get(selected_task_id, [])}
            selected_ordinal = 1
            while selected_ordinal in tried_comp and selected_ordinal <= 10:
                selected_ordinal += 1

            return selected_task_id, task_seed, selected_ordinal

        # Linear mutation regime
        if state.next_agenda_priority:
            rec_tid = state.next_agenda_priority.get("priority_task_id")
            rec_ord = state.next_agenda_priority.get("suggested_ordinal", 1)
            if rec_tid in tasks:
                past_failures = state.failure_catalog.get(rec_tid, [])
                tried_ordinals = {f.get("mutation_ordinal") for f in past_failures}
                if len(past_failures) < self.max_attempts_per_task:
                    selected_task_id = rec_tid
                    selected_ordinal = rec_ord
                    while selected_ordinal in tried_ordinals and selected_ordinal <= 10:
                        selected_ordinal += 1

        past_failures = state.failure_catalog.get(selected_task_id, [])
        tried_ordinals = {f.get("mutation_ordinal") for f in past_failures}
        if len(past_failures) >= self.max_attempts_per_task:
            for cand_tid in ranked_tasks:
                if len(state.failure_catalog.get(cand_tid, [])) < self.max_attempts_per_task:
                    selected_task_id = cand_tid
                    tried_cand = {f.get("mutation_ordinal") for f in state.failure_catalog.get(cand_tid, [])}
                    cand_ord = 1
                    while cand_ord in tried_cand and cand_ord <= 10:
                        cand_ord += 1
                    selected_ordinal = cand_ord
                    break
        else:
            while selected_ordinal in tried_ordinals and selected_ordinal <= 10:
                selected_ordinal += 1

        return selected_task_id, task_seed, selected_ordinal

    def formulate_hypothesis(
        self,
        cycle_id: int,
        target_task_id: str,
        target_task: ConfirmationTask,
        ordinal: int,
        state: PersistentResearchState,
    ) -> ResearchHypothesis:
        """Formulate a falsifiable hypothesis tailored to the selected task and mutation ordinal."""
        past_failures = state.failure_catalog.get(target_task_id, [])
        gated_failures = [f for f in past_failures if f.get("gene_dict", {}).get("is_gated", False)]
        composite_failures = [f for f in past_failures if f.get("gene_dict", {}).get("is_composite", False)]
        linear_failures = [f for f in past_failures if not f.get("gene_dict", {}).get("is_composite", False) and not f.get("gene_dict", {}).get("is_gated", False)]

        is_gated = (len(linear_failures) >= self.max_attempts_per_task and len(composite_failures) >= self.max_attempts_per_task)
        is_composite = len(linear_failures) >= self.max_attempts_per_task and not is_gated

        if is_gated:
            strategy = "SYNTHESIZE_GATED_EXPRESSION_TREE"
            statement = (
                f"Cycle {cycle_id}: Applying gated modular expression tree synthesis (ordinal {ordinal}) for {target_task_id} "
                f"({target_task.family}) will achieve holdout gain >= 0.1500 without prior regression > 0.0200."
            )
            hyp_id = f"HYP_AUTONOMOUS_C{cycle_id}_{target_task_id}_gated_ord{ordinal}"
        elif is_composite:
            strategy = "SYNTHESIZE_COMPOSITE_MECHANISM"
            statement = (
                f"Cycle {cycle_id}: Applying composite mechanism synthesis (operator ordinal {ordinal}) for {target_task_id} "
                f"({target_task.family}) will achieve holdout gain >= 0.1500 without prior regression > 0.0200."
            )
            hyp_id = f"HYP_AUTONOMOUS_C{cycle_id}_{target_task_id}_comp_ord{ordinal}"
        else:
            strategy = "LINEAR_MUTATION"
            prior_context = f" (after {len(past_failures)} prior falsified attempts)" if past_failures else ""
            statement = (
                f"Cycle {cycle_id}: Applying typed AST mutation ordinal {ordinal} for {target_task_id} "
                f"({target_task.family}){prior_context} will achieve holdout gain >= 0.1500 without prior regression > 0.0200."
            )
            hyp_id = f"HYP_AUTONOMOUS_C{cycle_id}_{target_task_id}_ord{ordinal}"

        # Hash commitment of hypothesis
        h_payload = f"{hyp_id}:{target_task_id}:{ordinal}:{statement}".encode("utf-8")
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
    ) -> NextAgendaPriority:
        """Determine ACE's autonomous next research goal based on empirical outcome."""
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if decision == "ACCEPTED":
            # Promotion occurred: Next goal is to reinforce gains across other weak tasks
            remaining_tasks = [tid for tid in tasks.keys() if tid != current_task_id]
            next_tid = remaining_tasks[0] if remaining_tasks else current_task_id
            return NextAgendaPriority(
                priority_task_id=next_tid,
                priority_family=tasks[next_tid].family,
                strategy="EXPAND_PROMOTED_CAPABILITY",
                suggested_ordinal=1,
                rationalization=(
                    f"Candidate for {current_task_id} was successfully accepted (gain {gain:+.4f}). "
                    f"Next objective is to extend capability to {next_tid}."
                ),
                timestamp=now,
            )
        else:
            # Rejection: Negative result cataloged.
            past_failures = state.failure_catalog.get(current_task_id, [])
            gated_failures = [f for f in past_failures if f.get("gene_dict", {}).get("is_gated", False)]
            composite_failures = [f for f in past_failures if f.get("gene_dict", {}).get("is_composite", False)]
            linear_failures = [f for f in past_failures if not f.get("gene_dict", {}).get("is_composite", False) and not f.get("gene_dict", {}).get("is_gated", False)]

            is_gated = (len(linear_failures) >= self.max_attempts_per_task and len(composite_failures) >= self.max_attempts_per_task)
            is_composite = len(linear_failures) >= self.max_attempts_per_task and not is_gated

            if is_gated:
                gated_attempts = len(gated_failures) + 1
                if gated_attempts < self.max_attempts_per_task:
                    next_ord = current_ordinal + 1
                    return NextAgendaPriority(
                        priority_task_id=current_task_id,
                        priority_family=tasks[current_task_id].family,
                        strategy="SYNTHESIZE_GATED_EXPRESSION_TREE",
                        suggested_ordinal=next_ord,
                        rationalization=(
                            f"Gated expression tree ordinal {current_ordinal} on {current_task_id} failed with gain {gain:+.4f}. "
                            f"Attempt {gated_attempts}/{self.max_attempts_per_task}: exploring gated ordinal {next_ord}."
                        ),
                        timestamp=now,
                    )
                else:
                    all_tids = list(tasks.keys())
                    curr_idx = all_tids.index(current_task_id) if current_task_id in all_tids else 0
                    next_tid = all_tids[(curr_idx + 1) % len(all_tids)]
                    return NextAgendaPriority(
                        priority_task_id=next_tid,
                        priority_family=tasks[next_tid].family,
                        strategy="SYNTHESIZE_GATED_EXPRESSION_TREE",
                        suggested_ordinal=1,
                        rationalization=(
                            f"Target {current_task_id} reached {gated_attempts} gated expression attempts. "
                            f"Advancing gated synthesis agenda to {next_tid} ({tasks[next_tid].family})."
                        ),
                        timestamp=now,
                    )
            elif is_composite:
                composite_attempts = len(composite_failures) + 1
                if composite_attempts < self.max_attempts_per_task:
                    next_ord = current_ordinal + 1
                    return NextAgendaPriority(
                        priority_task_id=current_task_id,
                        priority_family=tasks[current_task_id].family,
                        strategy="SYNTHESIZE_COMPOSITE_MECHANISM",
                        suggested_ordinal=next_ord,
                        rationalization=(
                            f"Composite mechanism ordinal {current_ordinal} on {current_task_id} failed with gain {gain:+.4f}. "
                            f"Attempt {composite_attempts}/{self.max_attempts_per_task}: exploring composite ordinal {next_ord}."
                        ),
                        timestamp=now,
                    )
                else:
                    all_tids = list(tasks.keys())
                    curr_idx = all_tids.index(current_task_id) if current_task_id in all_tids else 0
                    next_tid = all_tids[(curr_idx + 1) % len(all_tids)]
                    other_tasks_comp = [
                        len([f for f in state.failure_catalog.get(tid, []) if f.get("gene_dict", {}).get("is_composite", False)])
                        for tid in tasks.keys() if tid != current_task_id
                    ]
                    all_comp_full = all(c >= self.max_attempts_per_task for c in other_tasks_comp)
                    next_strat = "SYNTHESIZE_GATED_EXPRESSION_TREE" if all_comp_full else "SYNTHESIZE_COMPOSITE_MECHANISM"
                    return NextAgendaPriority(
                        priority_task_id=next_tid,
                        priority_family=tasks[next_tid].family,
                        strategy=next_strat,
                        suggested_ordinal=1,
                        rationalization=(
                            f"Target {current_task_id} reached {composite_attempts} composite attempts. "
                            f"Advancing synthesis agenda to {next_tid} ({tasks[next_tid].family}) via {next_strat}."
                        ),
                        timestamp=now,
                    )
            else:
                past_attempts = len(past_failures) + 1
                if past_attempts < self.max_attempts_per_task:
                    next_ord = current_ordinal + 1
                    return NextAgendaPriority(
                        priority_task_id=current_task_id,
                        priority_family=tasks[current_task_id].family,
                        strategy="EXPLORE_MUTATION_ORDINAL",
                        suggested_ordinal=next_ord,
                        rationalization=(
                            f"Mutation ordinal {current_ordinal} on {current_task_id} failed with gain {gain:+.4f}. "
                            f"Attempt {past_attempts}/{self.max_attempts_per_task}: exploring ordinal {next_ord}."
                        ),
                        timestamp=now,
                    )
                else:
                    all_tids = list(tasks.keys())
                    curr_idx = all_tids.index(current_task_id) if current_task_id in all_tids else 0
                    next_tid = all_tids[(curr_idx + 1) % len(all_tids)]
                    return NextAgendaPriority(
                        priority_task_id=next_tid,
                        priority_family=tasks[next_tid].family,
                        strategy="SHIFT_TO_NEXT_WEAKEST_TASK",
                        suggested_ordinal=1,
                        rationalization=(
                            f"Target {current_task_id} reached {past_attempts} falsified attempts. "
                            f"Shifting research agenda to alternative capability {next_tid} ({tasks[next_tid].family})."
                        ),
                        timestamp=now,
                    )
