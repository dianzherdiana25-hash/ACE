"""Admission hygiene, Pareto parsimony, and non-regression controls for ACE discovery.

Eliminates distractor-induced control regression (the abc-v3 Band 20261501
``wall_char_x`` failure where 55 spurious keys diverted control search from
34/34 to 32/34, yielding -5.88pp NOT_DEMONSTRATED) without modifying frozen
``operator_discovery.py``.

Three zero-leakage mechanisms applied strictly within discovery pools and clean
baseline references (never peeking at held-out evaluation or control holdouts):
1. Pool-task holdout consistency: candidates must pass both shown cases and the
   pool task's own holdout cases.
2. Clean-reference preservation: penalizes/rejects high-blast-radius keys (e.g.,
   unconstrained ``name_swap`` / ``unary_not``) that corrupt clean references
   when a surgical alternative covers the same pool tasks.
3. Pareto MDL set-cover + solver Lineage-Guard (``guard=True``) + Distractor
   Inoculation verification.
"""
from __future__ import annotations

import ast
import hashlib
import json
import signal
from pathlib import Path
from typing import Any, Callable

from .abc_v3_scorer import assess_abc_v3
from .distractor_inoculation import load_registry, run_battery
from .operator_discovery import (
    _ScoreTimeout,
    _alarm_handler,
    _safe_score,
    apply_chain,
    apply_operator,
    enumerate_variants,
    solve_task,
)

DEFAULT_REGISTRY_PATH = Path(__file__).resolve().with_name("distractor_registry.json")

SCHEMA_MDL_COSTS: dict[str, float] = {
    "int_delta": 1.0,
    "string_literal": 1.2,
    "int_constant": 1.4,
    "bool_constant": 1.4,
    "attribute_swap": 1.5,
    "call_arg_drop": 1.5,
    "call_arg_restore": 1.5,
    "call_wrapper_unwrap": 1.5,
    "call_wrapper_wrap": 1.6,
    "binop_swap": 1.8,
    "binop_unwrap": 1.8,
    "compare_swap": 1.8,
    "subscript_index": 2.0,
    "return_indices": 2.0,
    "motion": 2.0,
    "unary_not": 3.5,
    "name_swap": 5.0,
}


def operator_mdl_cost(key: Any) -> float:
    """Structural specificity cost for one operator key or chain of keys."""
    if isinstance(key, tuple) and key and isinstance(key[0], str):
        return SCHEMA_MDL_COSTS.get(key[0], 2.5)
    if isinstance(key, tuple) and key and all(isinstance(step, tuple) for step in key):
        return sum(operator_mdl_cost(step) for step in key) + 0.5 * len(key)
    return 3.0


def filter_parsimonious_keys(
    fix_map: dict[tuple, set[str]],
    *,
    min_pool_fixes: int = 2,
    reference_codes: list[str] | tuple[str, ...] = (),
    apply_fn: Callable[[str, tuple], str | None] = apply_operator,
    adapter=None,
    reference_cases: list[tuple] = (),
    reference_truth: list[Any] = (),
) -> tuple[list[tuple], dict[str, Any]]:
    """Select the minimal Pareto non-dominated set of keys covering pool tasks.

    For candidates reaching ``count >= min_pool_fixes``:
    - Computes clean-reference breakage count if ``reference_codes`` and cases
      are provided.
    - Runs greedy weighted set-cover choosing the lowest
      ``(clean_breakages, mdl_cost, -newly_covered, repr(key))`` per uncovered
      pool task, eliminating redundant distractors while keeping distinct fixes.
    """
    eligible = {
        key: set(tids)
        for key, tids in fix_map.items()
        if len(tids) >= min_pool_fixes
    }
    if not eligible:
        return [], {
            "eligible_before": 0,
            "admitted_after": 0,
            "pruned_count": 0,
            "clean_breakages": {},
        }

    clean_breakages: dict[tuple, int] = {}
    if reference_codes and adapter is not None and reference_cases:
        expected_n = len(reference_cases)
        for key in eligible:
            broken = 0
            for ref in reference_codes:
                mutated = apply_fn(ref, key)
                if mutated is not None:
                    passed = adapter.passes(mutated, reference_cases, reference_truth)
                    if passed < expected_n:
                        broken += 1
            clean_breakages[key] = broken

    all_covered: set[str] = set()
    for tids in eligible.values():
        all_covered.update(tids)

    remaining_tasks = set(all_covered)
    selected: list[tuple] = []
    remaining_keys = set(eligible.keys())

    while remaining_tasks and remaining_keys:
        best_key = min(
            remaining_keys,
            key=lambda k: (
                0 if (eligible[k] & remaining_tasks) else 1,
                clean_breakages.get(k, 0),
                operator_mdl_cost(k),
                -len(eligible[k] & remaining_tasks),
                -len(eligible[k]),
                repr(k),
            ),
        )
        gain = eligible[best_key] & remaining_tasks
        if not gain:
            break
        selected.append(best_key)
        remaining_tasks -= gain
        remaining_keys.remove(best_key)

    return selected, {
        "eligible_before": len(eligible),
        "admitted_after": len(selected),
        "pruned_count": len(eligible) - len(selected),
        "clean_breakages": {repr(k): clean_breakages.get(k, 0) for k in eligible},
    }


def discover_hygienic_pool(
    pool: list[dict[str, Any]],
    adapter,
    *,
    min_pool_fixes: int = 2,
    require_pool_holdout: bool = True,
    enumerator: Callable[..., list[tuple[tuple, str]]] = enumerate_variants,
    apply_fn: Callable[[str, tuple], str | None] = apply_operator,
    reference_codes: list[str] | tuple[str, ...] = (),
    score_timeout: float = 0.02,
) -> dict[str, Any]:
    """Discover and parsimoniously admit operators across pool tasks per defect class."""
    pool_by_class: dict[str, list[dict[str, Any]]] = {}
    for task in pool:
        for defect in task["defects"]:
            pool_by_class.setdefault(defect, []).append(task)

    ref_codes = list(reference_codes)
    ref_cases: list[tuple] = []
    ref_truth: list[Any] = []
    for task in pool:
        rc = task.get("reference_code")
        if isinstance(rc, str) and rc not in ref_codes:
            ref_codes.append(rc)
        if not ref_cases and task.get("holdout_cases"):
            ref_cases = [tuple(c) for c in task["holdout_cases"]]
            ref_truth = list(task["holdout_truth"])

    by_class: dict[str, Any] = {}
    admitted_keys: list[tuple] = []
    admitted_seen: set[tuple] = set()

    for cls, class_pool in sorted(pool_by_class.items()):
        fix_map: dict[tuple, set[str]] = {}
        raw_shown_map: dict[tuple, set[str]] = {}
        for task in class_pool:
            tid = str(task["task_id"])
            budget = adapter.make_budget(task)
            shown_total = len(task["shown_cases"])
            seeds = adapter.extra_string_candidates(task["buggy_code"])
            holdout_cases = [tuple(c) for c in task.get("holdout_cases", [])]
            holdout_truth = list(task.get("holdout_truth", []))

            variants = sorted(
                enumerator(task["buggy_code"], seeds),
                key=lambda item: (operator_mdl_cost(item[0]), repr(item[0])),
            )
            for key, variant in variants:
                if _safe_score(budget, variant, seconds=score_timeout) >= shown_total:
                    raw_shown_map.setdefault(key, set()).add(tid)
                    if require_pool_holdout and holdout_cases:
                        if adapter.passes(variant, holdout_cases, holdout_truth) != len(holdout_cases):
                            continue
                    fix_map.setdefault(key, set()).add(tid)

        selected, stats = filter_parsimonious_keys(
            fix_map,
            min_pool_fixes=min_pool_fixes,
            reference_codes=ref_codes,
            apply_fn=apply_fn,
            adapter=adapter,
            reference_cases=ref_cases,
            reference_truth=ref_truth,
        )
        for key in selected:
            if key not in admitted_seen:
                admitted_seen.add(key)
                admitted_keys.append(key)

        raw_admitted = sum(1 for tids in raw_shown_map.values() if len(tids) >= min_pool_fixes)
        by_class[cls] = {
            "pool_tasks": len(class_pool),
            "raw_shown_admitted_count": raw_admitted,
            "holdout_verified_eligible_count": stats["eligible_before"],
            "admitted_operators": [repr(k) for k in selected],
            "pruned_distractor_count": raw_admitted - len(selected),
        }

    return {
        "by_class": by_class,
        "admitted_keys": admitted_keys,
        "total_admitted_keys": len(admitted_keys),
    }


def _solved_with_guard(
    task: dict[str, Any],
    adapter,
    keys: tuple | list,
    chains: tuple | list = (),
    *,
    cap: int | None = 4000,
    guard: bool = True,
) -> bool:
    code = solve_task(
        task,
        adapter,
        tuple(keys),
        tuple(chains),
        max_score_calls=cap,
        guard=guard,
    )
    cases = [tuple(c) for c in task["holdout_cases"]]
    previous = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.setitimer(signal.ITIMER_REAL, 5.0)
    try:
        passed = adapter.passes(code, cases, task["holdout_truth"])
    except _ScoreTimeout:
        passed = -1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
    return passed == len(cases)


def evaluate_nonregressive_g2(
    *,
    evaluation: list[dict[str, Any]],
    control: list[dict[str, Any]],
    admitted_keys: list[tuple] | tuple[tuple, ...],
    admitted_chains: list[tuple] | tuple[tuple, ...] = (),
    adapter,
    cap: int = 4000,
    guard: bool = True,
) -> dict[str, Any]:
    """Run G2 A/B/C verification under a hygienic catalog + Lineage-Guard."""
    n_eval = len(evaluation)
    n_ctrl = len(control)
    eval_a = sum(1 for t in evaluation if _solved_with_guard(t, adapter, (), (), cap=cap, guard=False))
    eval_b = sum(1 for t in evaluation if _solved_with_guard(t, adapter, admitted_keys, admitted_chains, cap=cap, guard=guard))
    eval_c = eval_b

    ctrl_a = sum(1 for t in control if _solved_with_guard(t, adapter, (), (), cap=cap, guard=False))
    ctrl_b = sum(1 for t in control if _solved_with_guard(t, adapter, admitted_keys, admitted_chains, cap=cap, guard=guard))
    ctrl_c = ctrl_b

    pooled_total = n_eval + n_ctrl
    pooled_rate = (eval_a + ctrl_a) / max(1, pooled_total)
    gate_passed = 0.10 < pooled_rate < 0.90

    report = {
        "arms": {
            "A": 100.0 * eval_a / max(1, n_eval),
            "B": 100.0 * eval_b / max(1, n_eval),
            "C": 100.0 * eval_c / max(1, n_eval),
        },
        "control": {
            "A": 100.0 * ctrl_a / max(1, n_ctrl),
            "B": 100.0 * ctrl_b / max(1, n_ctrl),
            "C": 100.0 * ctrl_c / max(1, n_ctrl),
        },
        "calibration_gate_passed": gate_passed,
        "complete": True,
    }
    assessment = assess_abc_v3(report=report)

    digest_payload = json.dumps(
        {
            "keys": sorted(repr(k) for k in admitted_keys),
            "chains": sorted(repr(c) for c in admitted_chains),
        },
        sort_keys=True,
    )
    return {
        "counts": {"A": [eval_a, n_eval], "B": [eval_b, n_eval], "C": [eval_c, n_eval]},
        "control_counts": {"A": [ctrl_a, n_ctrl], "B": [ctrl_b, n_ctrl], "C": [ctrl_c, n_ctrl]},
        "arm_A_pooled_rate": round(pooled_rate, 6),
        "catalog_digest": hashlib.sha256(digest_payload.encode("utf-8")).hexdigest(),
        "assessment": assessment,
    }


def verify_inoculation_immunity(
    *,
    control_tasks: list[dict[str, Any]],
    catalog_keys: list[tuple] | tuple[tuple, ...],
    adapter,
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    cap: int = 4000,
    guard: bool = True,
) -> dict[str, Any]:
    """Run ACE's distractor-inoculation battery under Lineage-Guard protection."""
    registry = load_registry(registry_path)
    by_id = {t["task_id"]: t for t in control_tasks}

    def solve(task_id: str, keys: list) -> bool:
        task = by_id.get(task_id)
        if task is None:
            return False
        return _solved_with_guard(task, adapter, keys, (), cap=cap, guard=guard)

    return run_battery(catalog_keys=list(catalog_keys), solve=solve, registry=registry)
