"""Diagnostic Engine: Inspects system capabilities and identifies structural weaknesses."""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Tuple

from .models import SystemDiagnosis
from .confirmation_suite import ConfirmationTask


class DiagnosticEngine:
    """Evaluates an active baseline candidate against tasks to diagnose structural failure patterns."""

    def diagnose_weakness(
        self,
        baseline_fn: Callable[[str], bool],
        baseline_head_id: str,
        tasks: Dict[str, ConfirmationTask],
    ) -> SystemDiagnosis:
        """Run diagnostic pass across tasks' train pools to identify lowest-performing capability."""
        task_scores: Dict[str, float] = {}
        task_cues: Dict[str, str] = {}

        for tid, task in tasks.items():
            hits = sum(1 for w, lbl in task.train_pool if baseline_fn(w) == lbl)
            acc = round(hits / max(1, len(task.train_pool)), 4)
            task_scores[tid] = acc

            # Analyze error patterns on train pool
            false_pos = sum(1 for w, lbl in task.train_pool if baseline_fn(w) and not lbl)
            false_neg = sum(1 for w, lbl in task.train_pool if not baseline_fn(w) and lbl)
            task_cues[tid] = f"acc={acc}, fp={false_pos}, fn={false_neg}"

        # Identify weakest task
        weakest_tid = min(task_scores, key=lambda k: task_scores[k])
        weakest_task = tasks[weakest_tid]
        weakest_score = task_scores[weakest_tid]
        failure_rate = round(1.0 - weakest_score, 4)

        return SystemDiagnosis(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            baseline_head_id=baseline_head_id,
            baseline_score=round(sum(task_scores.values()) / max(1, len(task_scores)), 4),
            diagnosed_weakness_task=weakest_tid,
            diagnosed_weakness_family=weakest_task.family,
            observed_failure_rate=failure_rate,
            error_cue=task_cues[weakest_tid],
            diagnostic_details={
                "task_scores": task_scores,
                "task_cues": task_cues,
                "target_description": weakest_task.description,
            },
        )
