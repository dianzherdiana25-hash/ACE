"""Hypothesis Selector: Selects a concrete, falsifiable research hypothesis targeting weaknesses."""
from __future__ import annotations

import hashlib
import time
from typing import Dict

from .models import ResearchHypothesis, SystemDiagnosis


class HypothesisSelector:
    """Formulates falsifiable hypotheses based on empirical system diagnosis."""

    def select_hypothesis(
        self,
        diagnosis: SystemDiagnosis,
        cycle_id: int,
    ) -> ResearchHypothesis:
        """Formulate a falsifiable hypothesis with strict pre-registered confirmation thresholds."""
        target_tid = diagnosis.diagnosed_weakness_task
        family = diagnosis.diagnosed_weakness_family
        fail_rate = diagnosis.observed_failure_rate

        statement = (
            f"Cycle {cycle_id}: Introducing a bounded typed source mutation for {target_tid} "
            f"({family}) will achieve holdout gain >= 0.1500 without prior regression > 0.0200, "
            f"resolving diagnosed weakness (baseline fail rate {fail_rate})."
        )
        hyp_id = f"HYP_SELF_DEV_C{cycle_id}_{target_tid}"

        # Compute commitment digest of hypothesis
        h_payload = f"{hyp_id}:{target_tid}:{statement}".encode("utf-8")
        prereg_hash = hashlib.sha256(h_payload).hexdigest()

        return ResearchHypothesis(
            hypothesis_id=hyp_id,
            statement=statement,
            target_task_id=target_tid,
            min_required_gain=0.1500,
            max_regression_tolerance=0.0200,
            max_search_budget_cost_usd=0.0,
            preregistration_hash=prereg_hash,
        )
