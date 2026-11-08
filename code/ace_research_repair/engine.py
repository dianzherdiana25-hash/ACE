"""Autonomous Software Repair Engine (`Goal -> Inspect -> Reproduce -> Diagnose -> Represent -> Patch -> Test -> Verify -> Remember`).

Implements all four pre-registered experimental arms (`R_rule`, `R_fixed`, `R_fresh`, `R_ace`)
over the shared typed AST candidate space under a strictly matched `K = 16` sandbox execution budget.
Exposes `RepairEngine` cleanly for downstream multi-capability integration without importing `evaluator.py`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .corpus import ARMS, BUDGET_K, PublicUnitView, sha256_digest
from .memory import RepairMemory
from .operators import STATIC_FAMILY_ORDER, CandidatePatch, generate_candidates
from .represent import (
    RuntimeTraceBridge,
    diagnose_reproduction,
    extract_fault_representation,
    inspect_module_ast,
)
from .sandbox import run_dev_suite, run_perturbation_suite

PIPELINE_STAGES = (
    "Goal",
    "Inspect",
    "Reproduce",
    "Diagnose",
    "Represent",
    "Patch",
    "Test",
    "Verify",
    "Remember",
)


def _candidate_ochiai(candidate: CandidatePatch, ochiai_by_line: dict[str, float]) -> float:
    direct = ochiai_by_line.get(str(candidate.target_lineno))
    if direct is not None:
        return direct
    if not candidate.in_entrypoint or not ochiai_by_line:
        return 0.0
    nearby = [
        score
        for line_s, score in ochiai_by_line.items()
        if abs(int(line_s) - candidate.target_lineno) <= 3
    ]
    return max(nearby) if nearby else max(ochiai_by_line.values(), default=0.0)


def rank_candidates(
    arm: str,
    candidates: list[CandidatePatch],
    ochiai_by_line: dict[str, float],
    priors: dict[str, Any],
) -> list[CandidatePatch]:
    if arm == "R_rule":
        return sorted(
            candidates,
            key=lambda c: (
                c.target_lineno,
                STATIC_FAMILY_ORDER[c.operator_family],
                c.operator_name,
                c.patch_id,
            ),
        )
    if arm == "R_fixed":
        return sorted(
            candidates,
            key=lambda c: (
                -int(c.in_entrypoint),
                c.edit_complexity,
                STATIC_FAMILY_ORDER[c.operator_family],
                c.target_lineno,
                c.patch_id,
            ),
        )
    if arm == "R_fresh":
        return sorted(
            candidates,
            key=lambda c: (
                -_candidate_ochiai(c, ochiai_by_line),
                -int(c.in_entrypoint),
                STATIC_FAMILY_ORDER[c.operator_family],
                c.target_lineno,
                c.patch_id,
            ),
        )
    if arm == "R_ace":
        fam_counts: dict[str, int] = priors.get("family_counts", {})
        op_counts: dict[str, int] = priors.get("operator_counts", {})
        return sorted(
            candidates,
            key=lambda c: (
                1 if (c.operator_family == "overfit_probe" and fam_counts.get(c.operator_family, 0) == 0) else 0,
                -(1 if fam_counts.get(c.operator_family, 0) > 0 else 0),
                -fam_counts.get(c.operator_family, 0),
                -op_counts.get(c.operator_name, 0),
                -_candidate_ochiai(c, ochiai_by_line),
                -int(c.in_entrypoint),
                c.edit_complexity,
                STATIC_FAMILY_ORDER[c.operator_family],
                c.target_lineno,
                c.patch_id,
            ),
        )
    raise ValueError(f"unsupported repair arm: {arm}")


class RepairEngine:
    """Bounded staged software repair engine integrating `ace_runtime` and `RepairMemory`."""

    def __init__(self, workspace: Path | str) -> None:
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.bridge = RuntimeTraceBridge(self.workspace / "ace_runtime")
        self.memory = RepairMemory(self.workspace / "repair_memory.sqlite3")

    def __enter__(self) -> RepairEngine:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def close(self) -> None:
        try:
            self.memory.close()
        finally:
            self.bridge.close()

    def status(self) -> dict[str, Any]:
        return {
            "workspace": str(self.workspace),
            "runtime_status": self.bridge.status(),
            "memory_status": self.memory.status(),
            "scientific_decision": "NOT_ASSESSED",
            "release_gate": "BLOCK_RELEASE",
            "oaie_established": False,
            "candidate_deployed": False,
        }

    def train_source_bank(
        self,
        source_views: tuple[PublicUnitView, ...] | list[PublicUnitView],
        *,
        budget_k: int = BUDGET_K,
    ) -> list[dict[str, Any]]:
        """Acquire typed fault representations and repair schemas from the source bug bank."""
        receipts: list[dict[str, Any]] = []
        for view in source_views:
            receipt = self.solve_unit(view, arm="R_ace", budget_k=budget_k, remember=True)
            receipts.append(receipt)
        return receipts

    def solve_unit(
        self,
        unit: PublicUnitView,
        *,
        arm: str = "R_ace",
        budget_k: int = BUDGET_K,
        remember: bool = False,
    ) -> dict[str, Any]:
        """Run a repair trial on `unit` under `arm` within `budget_k` candidate sandbox runs."""
        if arm not in ARMS:
            raise ValueError(f"arm must be one of {ARMS}")
        if type(budget_k) is not int or not 1 <= budget_k <= 64:
            raise ValueError("budget_k must be an integer in 1..64")

        # Stage 0: Goal
        goal_stage = {
            "unit_id": unit.unit_id,
            "entrypoint": unit.entrypoint,
            "source_sha256": unit.source_sha256,
            "arm": arm,
            "budget_k": budget_k,
            "staging_only": True,
        }

        # Stage 1: Inspect
        ast_inspection = inspect_module_ast(unit.buggy_source, unit.entrypoint)

        # Stage 2 & 3: Reproduce & Diagnose (executed only by dynamic arms R_fresh and R_ace)
        uses_dynamic_spectrum = arm in ("R_fresh", "R_ace")
        reproduce_runs = 0
        if uses_dynamic_spectrum:
            repro_res = run_dev_suite(
                unit.buggy_source,
                unit.entrypoint,
                unit.dev_tests,
                collect_trace=True,
            )
            reproduce_runs = 1
            diagnosis = diagnose_reproduction(repro_res, ast_inspection)
            failing_names: set[str] | None = set(diagnosis["failing_test_names"])
            ochiai_map = {k: float(v) for k, v in diagnosis["ochiai_by_line"].items()}
        else:
            repro_res = {"skipped": True, "reason": "static_arm"}
            diagnosis = {
                "failing_count": None,
                "passing_count": None,
                "failing_test_names": [],
                "passing_test_names": [],
                "primary_failure_mode": "StaticUnknown",
                "exception_types": [],
                "ochiai_by_line": {},
                "top_suspicious_lines": [],
            }
            failing_names = None
            ochiai_map = {}

        # Stage 4: Represent (`ace_runtime` + `RepairMemory` priors for R_ace only)
        if arm == "R_ace":
            representation = extract_fault_representation(
                ast_inspection=ast_inspection,
                diagnosis=diagnosis,
                source_sha256=unit.source_sha256,
                task_label=unit.unit_id.lower(),
                bridge=self.bridge,
            )
            priors = self.memory.query_priors(
                representation["runtime"]["runtime_model_id"],
                representation["fine_signature"],
            )
        else:
            representation = {
                "trace_regime": None,
                "fine_signature": None,
                "primary_failure_mode": diagnosis["primary_failure_mode"],
                "top_suspicious_lines": diagnosis["top_suspicious_lines"],
                "runtime": {
                    "runtime_task_id": None,
                    "runtime_phase": "DISABLED",
                    "runtime_staged": False,
                    "runtime_learning_called": False,
                    "runtime_model_id": None,
                    "probe_words": [],
                    "probe_predictions": [],
                },
            }
            priors = {
                "matched_capability_records": 0,
                "family_counts": {},
                "operator_counts": {},
            }

        # Stage 5: Patch (shared AST candidate enumeration + arm-specific ranking)
        raw_candidates = generate_candidates(
            unit.buggy_source,
            unit.entrypoint,
            unit.dev_tests,
            failing_test_names=failing_names,
        )
        ranked_candidates = rank_candidates(arm, raw_candidates, ochiai_map, priors)

        # Stage 6 (`Test`) & Stage 7 (`Verify`)
        sandbox_evals_used = 0
        dev_evals_used = 0
        verify_evals_used = 0
        evaluated_log: list[dict[str, Any]] = []
        verify_rejections: list[dict[str, Any]] = []
        selected_patch: CandidatePatch | None = None
        final_verify_report: dict[str, Any] | None = None
        outcome = "ABSTAIN_BUDGET_EXHAUSTED"

        for rank_idx, cand in enumerate(ranked_candidates, 1):
            if sandbox_evals_used >= budget_k:
                break
            dev_check = run_dev_suite(
                cand.patched_source,
                unit.entrypoint,
                unit.dev_tests,
                collect_trace=False,
            )
            sandbox_evals_used += 1
            dev_evals_used += 1

            entry_log: dict[str, Any] = {
                "rank": rank_idx,
                "patch_id": cand.patch_id,
                "operator_family": cand.operator_family,
                "operator_name": cand.operator_name,
                "target_lineno": cand.target_lineno,
                "dev_passed_count": dev_check["passed_count"],
                "dev_total_count": dev_check["total_count"],
                "dev_all_passed": dev_check["all_passed"],
                "timed_out": dev_check["timed_out"],
                "verify_executed": False,
                "verify_passed": None,
            }

            if dev_check["all_passed"]:
                if arm != "R_ace":
                    selected_patch = cand
                    outcome = "ADMITTED_DEV_ONLY"
                    evaluated_log.append(entry_log)
                    break

                # R_ace Stage 7: Behavioral Perturbation Consistency Gate (charged to budget_k!)
                if sandbox_evals_used >= budget_k:
                    entry_log["verify_passed"] = False
                    entry_log["verify_rejection_reasons"] = ["verify_budget_exhausted"]
                    verify_rejections.append(
                        {
                            "patch_id": cand.patch_id,
                            "operator_family": cand.operator_family,
                            "operator_name": cand.operator_name,
                            "reasons": ["verify_budget_exhausted"],
                        }
                    )
                    evaluated_log.append(entry_log)
                    outcome = "ABSTAIN_VERIFY_BUDGET_EXHAUSTED"
                    break

                verify_res = run_perturbation_suite(
                    cand.patched_source,
                    unit.entrypoint,
                    unit.perturbation_spec,
                )
                sandbox_evals_used += 1
                verify_evals_used += 1
                entry_log["verify_executed"] = True
                entry_log["verify_passed"] = verify_res["passed"]
                entry_log["verify_rejection_reasons"] = verify_res["rejection_reasons"]

                if verify_res["passed"]:
                    selected_patch = cand
                    final_verify_report = verify_res
                    outcome = "STAGED_VERIFIED"
                    evaluated_log.append(entry_log)
                    break

                verify_rejections.append(
                    {
                        "patch_id": cand.patch_id,
                        "operator_family": cand.operator_family,
                        "operator_name": cand.operator_name,
                        "reasons": verify_res["rejection_reasons"],
                    }
                )

            evaluated_log.append(entry_log)

        if selected_patch is None and verify_rejections and outcome == "ABSTAIN_BUDGET_EXHAUSTED":
            outcome = "ABSTAIN_OVERFIT_REJECTED"
        elif selected_patch is None and len(ranked_candidates) < budget_k and sandbox_evals_used < budget_k:
            outcome = (
                "ABSTAIN_OVERFIT_REJECTED"
                if verify_rejections
                else "ABSTAIN_NO_PLAUSIBLE_CANDIDATE"
            )

        # Stage 8: Remember (durable schema commit for verified R_ace repairs when enabled)
        remember_receipt: dict[str, Any] = {"remembered": False, "record_id": None}
        if (
            arm == "R_ace"
            and remember
            and selected_patch is not None
            and representation["runtime"]["runtime_model_id"] is not None
        ):
            mem_res = self.memory.remember_validated_repair(
                unit_id=unit.unit_id,
                runtime_model_id=str(representation["runtime"]["runtime_model_id"]),
                trace_regime=str(representation["trace_regime"]),
                fine_signature=str(representation["fine_signature"]),
                ast_node_kind=selected_patch.ast_node_kind,
                operator_family=selected_patch.operator_family,
                operator_name=selected_patch.operator_name,
                patch_id=selected_patch.patch_id,
            )
            remember_receipt = {
                "remembered": True,
                "record_id": mem_res["record_id"],
                "inserted": mem_res["inserted"],
                "ordinal": mem_res["ordinal"],
            }

        return {
            "unit_id": unit.unit_id,
            "arm": arm,
            "outcome": outcome,
            "staged": selected_patch is not None,
            "abstained": selected_patch is None,
            "selected_patch": selected_patch.summary() if selected_patch is not None else None,
            "patched_source": selected_patch.patched_source if selected_patch is not None else None,
            "patched_source_sha256": (
                sha256_digest(selected_patch.patched_source) if selected_patch is not None else None
            ),
            "budget_k": budget_k,
            "candidate_pool_size": len(ranked_candidates),
            "reproduce_sandbox_runs": reproduce_runs,
            "dev_sandbox_evals": dev_evals_used,
            "verify_sandbox_evals": verify_evals_used,
            "total_candidate_sandbox_evals": sandbox_evals_used,
            "verify_rejections": verify_rejections,
            "stages": {
                "Goal": goal_stage,
                "Inspect": {
                    "function_names": ast_inspection["function_names"],
                    "entrypoint_lineno": ast_inspection["entrypoint_lineno"],
                    "has_mutable_default": ast_inspection["has_mutable_default"],
                    "has_index_bound_loop": ast_inspection["has_index_bound_loop"],
                    "has_string_tokenizer_ops": ast_inspection["has_string_tokenizer_ops"],
                    "has_element_state_loop": ast_inspection["has_element_state_loop"],
                    "has_stale_dataflow_chain": ast_inspection["has_stale_dataflow_chain"],
                },
                "Reproduce": {
                    "executed": uses_dynamic_spectrum,
                    "passed_count": repro_res.get("passed_count") if uses_dynamic_spectrum else None,
                    "total_count": repro_res.get("total_count") if uses_dynamic_spectrum else None,
                },
                "Diagnose": diagnosis,
                "Represent": {
                    **representation,
                    "memory_priors": priors,
                },
                "Patch": {
                    "candidate_pool_size": len(ranked_candidates),
                    "top_5_candidates": [c.summary() for c in ranked_candidates[:5]],
                },
                "Test": {
                    "dev_sandbox_evals": dev_evals_used,
                    "evaluated_candidates": evaluated_log,
                },
                "Verify": {
                    "enabled": arm == "R_ace",
                    "verify_sandbox_evals": verify_evals_used,
                    "rejections": verify_rejections,
                    "admitted_report": final_verify_report,
                },
                "Remember": remember_receipt,
            },
            "scientific_decision": "NOT_ASSESSED",
            "candidate_deployed": False,
        }
