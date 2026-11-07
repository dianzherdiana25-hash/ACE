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

        # Check if next_agenda_priority from previous cycle has a recommendation
        if state.next_agenda_priority:
            rec_tid = state.next_agenda_priority.get("priority_task_id")
            rec_ord = state.next_agenda_priority.get("suggested_ordinal", 1)
            if rec_tid in tasks:
                # Check how many times rec_tid has already failed
                past_failures = state.failure_catalog.get(rec_tid, [])
                tried_ordinals = {f.get("mutation_ordinal") for f in past_failures}
                if len(past_failures) < self.max_attempts_per_task:
                    selected_task_id = rec_tid
                    selected_ordinal = rec_ord
                    # Ensure we don't repeat an already tried ordinal
                    while selected_ordinal in tried_ordinals and selected_ordinal <= 10:
                        selected_ordinal += 1

        # If the top ranked task was already attempted too many times, find the next one
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
            # Advance ordinal if 1 was already tried
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
            past_attempts = len(state.failure_catalog.get(current_task_id, [])) + 1
            if past_attempts < self.max_attempts_per_task:
                # Explore next mutation ordinal on the same task
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
                # Exhausted attempts on current task; shift focus to next task
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
