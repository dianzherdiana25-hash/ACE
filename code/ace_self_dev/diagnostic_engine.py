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
        train_scores: Dict[str, float] = {}
        val_scores: Dict[str, float] = {}
        task_cues: Dict[str, str] = {}

        for tid, task in tasks.items():
            train_hits = sum(1 for w, lbl in task.train_pool if baseline_fn(w) == lbl)
            train_acc = round(train_hits / max(1, len(task.train_pool)), 4)
            train_scores[tid] = train_acc

            val_hits = sum(1 for w, lbl in task.validation_pool if baseline_fn(w) == lbl)
            val_acc = round(val_hits / max(1, len(task.validation_pool)), 4)
            val_scores[tid] = val_acc

            # Strategy selection relies on combined train and validation metrics
            composite_acc = round(0.5 * train_acc + 0.5 * val_acc, 4)
            task_scores[tid] = composite_acc

            # Analyze error patterns on train pool
            false_pos = sum(1 for w, lbl in task.train_pool if baseline_fn(w) and not lbl)
            false_neg = sum(1 for w, lbl in task.train_pool if not baseline_fn(w) and lbl)
            task_cues[tid] = f"train={train_acc}, val={val_acc}, fp={false_pos}, fn={false_neg}"

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
                "train_scores": train_scores,
                "val_scores": val_scores,
                "task_cues": task_cues,
                "target_description": weakest_task.description,
            },
        )
