"""Autonomous Problem Selector & Hypothesis Generator.

Analyzes diagnostic evidence from CodebaseReader to identify
high-priority research problems and formulate falsifiable code-improvement hypotheses.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional

from .models import ImprovementHypothesis, ResearchProblem


class ProblemSelector:
    """Autonomously selects research problems and formulates improvement hypotheses."""

    def __init__(self):
        pass

    def select_next_problem(self, diagnostics: Dict[str, Any]) -> Tuple[ResearchProblem, ImprovementHypothesis]:
        """Examines failure diagnostics and selects the most impactful research problem."""
        cycle_count = diagnostics.get("cycle_count", 0)
        task_failures = diagnostics.get("task_failure_counts", {})
        rejection_reasons = diagnostics.get("common_rejection_reasons", {})
        stagnation_events = diagnostics.get("stagnation_events", 0)

        # Problem Type 1: High Stagnation or Representation Saturation
        if stagnation_events > 0 or "NO_VALIDATION_IMPROVEMENT" in rejection_reasons:
            prob_id = f"prob_rep_saturation_{cycle_count}"
            problem = ResearchProblem(
                problem_id=prob_id,
                category="REPRESENTATION_BOTTLENECK",
                title="Search Space Representation Saturation",
                description=(
                    f"Diagnostics detected {stagnation_events} stagnation events and persistent "
                    "rejections due to representation saturation in single-clause mutations."
                ),
                target_files=["code/ace_self_dev/strategy_repair.py", "code/ace_self_dev/source_evolution.py"],
                failure_evidence={
                    "stagnation_events": stagnation_events,
                    "rejection_reasons": rejection_reasons,
                },
                priority_score=0.95,
            )
            hypothesis = ImprovementHypothesis(
                hypothesis_id=f"hyp_expand_dispatch_{cycle_count}",
                problem_id=prob_id,
                statement=(
                    "Expanding dispatch topology with multi-task composite predicates allows solving "
                    "both modular congruence and run-length parity simultaneously."
                ),
                proposed_strategy="MULTI_TASK_COMPOSITE_DISPATCH",
                expected_metric_gain=0.1875,
                target_module="code/ace_self_dev/strategy_repair.py",
                rationale="Single-task candidates cannot mathematically cross the +0.1500 promotion gate.",
            )
            return problem, hypothesis

        # Problem Type 2: Task-Specific Coverage Gap
        unaddressed = diagnostics.get("unaddressed_tasks", [])
        if unaddressed:
            target_task = unaddressed[0]
            fail_count = task_failures.get(target_task, 0)
            prob_id = f"prob_task_gap_{target_task}_{cycle_count}"
            problem = ResearchProblem(
                problem_id=prob_id,
                category="ALGORITHMIC_GAP",
                title=f"Algorithmic Coverage Deficit on {target_task}",
                description=(
                    f"Target task family {target_task} has accumulated {fail_count} failures "
                    "without achieving threshold promotion."
                ),
                target_files=["code/ace_self_dev/primitive_synthesizer.py"],
                failure_evidence={"target_task": target_task, "failures": fail_count},
                priority_score=0.85,
            )
            hypothesis = ImprovementHypothesis(
                hypothesis_id=f"hyp_synthesize_kernel_{target_task}_{cycle_count}",
                problem_id=prob_id,
                statement=(
                    f"Synthesizing modular balance primitives tailored for {target_task} "
                    "will eliminate repeated search failures."
                ),
                proposed_strategy="LIBRARY_PRIMITIVE_SYNTHESIS",
                expected_metric_gain=0.1600,
                target_module="code/ace_self_dev/primitive_synthesizer.py",
                rationale="Extracting proven sub-expression kernels shortens search depth.",
            )
            return problem, hypothesis

        # Problem Type 3: General Algorithmic Enhancement (Default)
        prob_id = f"prob_general_optimization_{cycle_count}"
        problem = ResearchProblem(
            problem_id=prob_id,
            category="LATENCY_INEFFICIENCY",
            title="Pre-Execution Constraint Pruning Optimization",
            description="Optimize candidate pre-screening to eliminate uninformative evaluation overhead.",
            target_files=["code/ace_self_dev/failure_constraint_engine.py"],
            failure_evidence={"cycle_count": cycle_count},
            priority_score=0.75,
        )
        hypothesis = ImprovementHypothesis(
            hypothesis_id=f"hyp_pre_pruning_{cycle_count}",
            problem_id=prob_id,
            statement="Applying in-memory Popperian constraint checking before holdout evaluation reduces wasted compute to 0.",
            proposed_strategy="CONSTRAINT_PRUNING",
            expected_metric_gain=0.1500,
            target_module="code/ace_self_dev/failure_constraint_engine.py",
            rationale="Eliminates redundant evaluations on falsified candidate classes.",
        )
        return problem, hypothesis
