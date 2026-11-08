"""Deterministic Planner translating high-level typed objectives into bounded step plans."""
from __future__ import annotations

from typing import Any

from .errors import PolicyError
from .policy import BudgetCeiling, GoalPolicy, validate_step

OBJECTIVE_KINDS = frozenset({
    "inspect_and_verify",
    "ace_runtime_demo_and_verify",
    "ace_task_learning_cycle",
    "stage_candidate_for_review",
    "abstain_insufficient_evidence",
})


def plan_objective(
    objective: Any,
    *,
    policy: GoalPolicy,
    budget: BudgetCeiling,
) -> list[dict[str, Any]]:
    """Expand a structured ``objective`` into a deterministic, policy-checked step list."""
    if type(objective) is not dict or type(objective.get("kind")) is not str:
        raise PolicyError("objective must be a dict with string 'kind'")
    kind = objective["kind"]
    if kind not in OBJECTIVE_KINDS:
        raise PolicyError(f"unsupported objective kind: {kind}")

    steps: list[dict[str, Any]] = []
    if kind == "inspect_and_verify":
        paths = objective.get("paths")
        if type(paths) is not list or not paths or any(type(p) is not str for p in paths):
            raise PolicyError("inspect_and_verify requires non-empty 'paths' list")
        for p in paths:
            steps.append({"tool": "inspect_file", "path": p})
        if objective.get("verify_upstream", False):
            steps.append({"tool": "verify_upstream_sources"})
        suite = objective.get("trusted_suite")
        if suite is not None:
            steps.append({"tool": "run_trusted_suite", "suite": suite})

    elif kind == "ace_runtime_demo_and_verify":
        steps = [
            {"tool": "ace_demo"},
            {"tool": "ace_status"},
        ]
        if objective.get("run_engine_tests", False):
            steps.append({"tool": "run_trusted_suite", "suite": "ace_runtime.test_engine"})

    elif kind == "ace_task_learning_cycle":
        tasks = objective.get("tasks")
        if type(tasks) is not list or not tasks:
            raise PolicyError("ace_task_learning_cycle requires non-empty 'tasks' list")
        for t in tasks:
            steps.append({"tool": "ace_enqueue_task", "task": t})
        steps.append({"tool": "ace_run_tasks", "max_tasks": len(tasks)})
        evals = objective.get("evaluations", [])
        if type(evals) is not list:
            raise PolicyError("evaluations must be a list")
        for ev in evals:
            if type(ev) is not dict or "task_id" not in ev or "examples" not in ev:
                raise PolicyError("invalid evaluation item in objective")
            steps.append({
                "tool": "ace_evaluate",
                "task_id": ev["task_id"],
                "examples": ev["examples"],
            })
        steps.append({"tool": "ace_status"})

    elif kind == "stage_candidate_for_review":
        inspect_paths = objective.get("inspect_paths", [])
        if type(inspect_paths) is not list:
            raise PolicyError("inspect_paths must be a list")
        for p in inspect_paths:
            steps.append({"tool": "inspect_file", "path": p})
        candidates = objective.get("candidates")
        if type(candidates) is not list or not candidates:
            raise PolicyError("stage_candidate_for_review requires 'candidates'")
        for cand in candidates:
            if type(cand) is not dict or set(cand) != {"rel_path", "content", "kind"}:
                raise PolicyError("invalid candidate specification")
            steps.append({
                "tool": "stage_candidate",
                "rel_path": cand["rel_path"],
                "content": cand["content"],
                "kind": cand["kind"],
            })

    elif kind == "abstain_insufficient_evidence":
        reason = objective.get("reason")
        if type(reason) is not str or not reason:
            raise PolicyError("abstain_insufficient_evidence requires 'reason'")
        for p in objective.get("inspect_paths", []):
            steps.append({"tool": "inspect_file", "path": p})
        steps.append({"tool": "abstain", "reason": reason})

    if not 1 <= len(steps) <= budget.max_steps:
        raise PolicyError("planned steps exceed goal step budget")
    for s in steps:
        validate_step(s, policy=policy)
    return steps
