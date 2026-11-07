"""Deterministic benchmark runner for ACE Fase 5 Autonomous Software Repair (`ace.repair.v1`).

Produces canonical JSON and deterministic RFC 1952 gzipped evidence (`evidence/repair/ace_repair_v1.json.gz`)
with zero wall-clock timestamps or temporary filesystem paths inside the canonical hashed payload,
ensuring byte-identical output across Python 3.12 and Python 3.13.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import shutil
import struct
import tempfile
from typing import Any
import zlib

from .corpus import (
    ARMS,
    BUDGET_K,
    FAMILIES,
    PRESCORE_COMMIT,
    PRESCORE_DOC_SHA256,
    canonical_json,
    sha256_digest,
    source_units,
    target_units,
)
from .engine import PIPELINE_STAGES, RepairEngine
from .evaluator import evaluate_target_trial

REPORT_SCHEMA = "ace.repair.public.v1"


def compress_deterministic_gzip(raw_bytes: bytes) -> bytes:
    """RFC 1952 deterministic gzip (`mtime=0`, `XFL=2`, `OS=255`) identical across Python 3.12/3.13."""
    compressor = zlib.compressobj(level=9, method=zlib.DEFLATED, wbits=-zlib.MAX_WBITS)
    deflated = compressor.compress(raw_bytes) + compressor.flush()
    crc = zlib.crc32(raw_bytes) & 0xFFFFFFFF
    isize = len(raw_bytes) & 0xFFFFFFFF
    header = b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x02\xff"
    return header + deflated + struct.pack("<II", crc, isize)


def decompress_gzip(gz_bytes: bytes) -> bytes:
    return gzip.decompress(gz_bytes)


def _strip_trial_for_evidence(
    trial: dict[str, Any],
    unit_meta: dict[str, str],
    terminal_eval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "unit_id": trial["unit_id"],
        "split": unit_meta["split"],
        "category": unit_meta["category"],
        "family_truth": unit_meta["family_truth"],
        "arm": trial["arm"],
        "outcome": trial["outcome"],
        "staged": trial["staged"],
        "abstained": trial["abstained"],
        "selected_patch": trial["selected_patch"],
        "patched_source_sha256": trial["patched_source_sha256"],
        "budget_k": trial["budget_k"],
        "candidate_pool_size": trial["candidate_pool_size"],
        "reproduce_sandbox_runs": trial["reproduce_sandbox_runs"],
        "dev_sandbox_evals": trial["dev_sandbox_evals"],
        "verify_sandbox_evals": trial["verify_sandbox_evals"],
        "total_candidate_sandbox_evals": trial["total_candidate_sandbox_evals"],
        "verify_rejections": trial["verify_rejections"],
        "stages": trial["stages"],
    }
    if terminal_eval is not None:
        out["terminal"] = terminal_eval
    return out


def _summarize_arm(arm_trials: list[dict[str, Any]]) -> dict[str, Any]:
    nominal = [t for t in arm_trials if t["category"] == "nominal"]
    ood = [t for t in arm_trials if t["category"] == "OOD_abstain"]
    traps = [t for t in arm_trials if t["category"] == "TRAP_overfit"]

    nominal_solved = [t for t in nominal if t["staged"] and t["terminal"]["terminal_all_passed"]]
    by_family: dict[str, dict[str, Any]] = {}
    for fam in FAMILIES:
        fam_rows = [t for t in nominal if t["family_truth"] == fam]
        fam_solved = [t for t in fam_rows if t["staged"] and t["terminal"]["terminal_all_passed"]]
        by_family[fam] = {
            "total": len(fam_rows),
            "staged": sum(1 for t in fam_rows if t["staged"]),
            "terminal_verified": len(fam_solved),
            "mean_evals_all": round(
                sum(t["total_candidate_sandbox_evals"] for t in fam_rows) / len(fam_rows), 4
            ),
            "mean_evals_solved": (
                round(
                    sum(t["total_candidate_sandbox_evals"] for t in fam_solved) / len(fam_solved), 4
                )
                if fam_solved
                else None
            ),
        }

    admitted_all = [t for t in arm_trials if t["staged"]]
    admitted_terminal_ok = [t for t in admitted_all if t["terminal"]["terminal_all_passed"]]

    trap_false_admissions = sum(1 for t in traps if t["staged"] and t["terminal"]["overfit_false_admission"])
    ood_false_admissions = sum(1 for t in ood if t["staged"] and t["terminal"]["overfit_false_admission"])
    nominal_false_admissions = sum(
        1 for t in nominal if t["staged"] and t["terminal"]["overfit_false_admission"]
    )

    return {
        "nominal_total": len(nominal),
        "nominal_staged": sum(1 for t in nominal if t["staged"]),
        "nominal_terminal_verified": len(nominal_solved),
        "nominal_false_admissions": nominal_false_admissions,
        "nominal_total_evals": sum(t["total_candidate_sandbox_evals"] for t in nominal),
        "nominal_mean_evals_all": round(
            sum(t["total_candidate_sandbox_evals"] for t in nominal) / len(nominal), 4
        ),
        "nominal_mean_evals_solved": (
            round(
                sum(t["total_candidate_sandbox_evals"] for t in nominal_solved) / len(nominal_solved),
                4,
            )
            if nominal_solved
            else None
        ),
        "by_family": by_family,
        "ood_total": len(ood),
        "ood_abstained": sum(1 for t in ood if t["abstained"]),
        "ood_false_admissions": ood_false_admissions,
        "trap_total": len(traps),
        "trap_abstained": sum(1 for t in traps if t["abstained"]),
        "trap_false_admissions": trap_false_admissions,
        "trap_verify_rejections": sum(len(t["verify_rejections"]) for t in traps),
        "total_false_admissions": nominal_false_admissions + ood_false_admissions + trap_false_admissions,
        "admitted_count": len(admitted_all),
        "admitted_terminal_verified_count": len(admitted_terminal_ok),
        "total_candidate_sandbox_evals_all_18": sum(
            t["total_candidate_sandbox_evals"] for t in arm_trials
        ),
        "total_reproduce_runs_all_18": sum(t["reproduce_sandbox_runs"] for t in arm_trials),
    }


def run_benchmark() -> dict[str, Any]:
    src_bank = source_units()
    tgt_bank = target_units()
    src_views = [u.public_view() for u in src_bank]
    tgt_views = [u.public_view() for u in tgt_bank]

    with tempfile.TemporaryDirectory(prefix="ace_repair_bench_") as tmp_root_str:
        tmp_root = Path(tmp_root_str)

        # 1. Source acquisition in R_ace workspace + snapshot for cold-restart test
        ace_ws = tmp_root / "ws_R_ace"
        with RepairEngine(ace_ws) as ace_engine:
            source_raw_trials = ace_engine.train_source_bank(src_views, budget_k=BUDGET_K)
            post_source_runtime_status = ace_engine.bridge.status()
            post_source_memory_status = ace_engine.memory.status()

        # Copy post-source workspace BEFORE target runs to test pure cold-restart inheritance (H4)
        restart_ws = tmp_root / "ws_R_ace_cold_restart"
        shutil.copytree(ace_ws, restart_ws)

        # 2. Execute all 4 arms on the 18 unseen target units
        raw_target_by_arm: dict[str, list[dict[str, Any]]] = {}
        for arm in ARMS:
            arm_ws = ace_ws if arm == "R_ace" else (tmp_root / f"ws_{arm}")
            with RepairEngine(arm_ws) as eng:
                arm_rows = [
                    eng.solve_unit(
                        view,
                        arm=arm,
                        budget_k=BUDGET_K,
                        remember=(arm == "R_ace"),
                    )
                    for view in tgt_views
                ]
                raw_target_by_arm[arm] = arm_rows
                if arm == "R_ace":
                    final_runtime_status = eng.bridge.status()
                    final_memory_status = eng.memory.status()

        # 3. Cold-restart replay on nominal targets without re-running source training (H4)
        nominal_views = [u.public_view() for u in tgt_bank if u.category == "nominal"]
        with RepairEngine(restart_ws) as restart_eng:
            restart_status = restart_eng.memory.status()
            restart_runtime_status = restart_eng.bridge.status()
            restart_nominal_trials = [
                restart_eng.solve_unit(view, arm="R_ace", budget_k=BUDGET_K, remember=False)
                for view in nominal_views
            ]

    # 4. Terminal evaluation (strictly post-selection via evaluator.py)
    source_evidence = [
        _strip_trial_for_evidence(
            trial,
            {"split": u.split, "category": u.category, "family_truth": u.family_truth},
        )
        for u, trial in zip(src_bank, source_raw_trials)
    ]

    target_evidence_by_arm: dict[str, list[dict[str, Any]]] = {}
    arm_summaries: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        scored_rows: list[dict[str, Any]] = []
        for u, trial in zip(tgt_bank, raw_target_by_arm[arm]):
            term_eval = evaluate_target_trial(
                unit_id=u.unit_id,
                entrypoint=u.entrypoint,
                staged=bool(trial["staged"]),
                patched_source=trial["patched_source"],
            )
            scored_rows.append(
                _strip_trial_for_evidence(
                    trial,
                    {"split": u.split, "category": u.category, "family_truth": u.family_truth},
                    terminal_eval=term_eval,
                )
            )
        target_evidence_by_arm[arm] = scored_rows
        arm_summaries[arm] = _summarize_arm(scored_rows)

    # 5. Evaluate pre-registered hypotheses H1..H4 objectively
    s_rule = arm_summaries["R_rule"]
    s_fixed = arm_summaries["R_fixed"]
    s_fresh = arm_summaries["R_fresh"]
    s_ace = arm_summaries["R_ace"]

    h1_pass = (
        s_ace["nominal_terminal_verified"] > s_rule["nominal_terminal_verified"]
        and s_ace["nominal_terminal_verified"] > s_fixed["nominal_terminal_verified"]
        and s_ace["nominal_terminal_verified"] >= 9
        and all(s_ace["by_family"][f]["terminal_verified"] >= 2 for f in FAMILIES)
    )

    ace_mean_solved = s_ace["nominal_mean_evals_solved"]
    fresh_mean_solved = s_fresh["nominal_mean_evals_solved"]
    eval_reduction_ratio = (
        round((fresh_mean_solved - ace_mean_solved) / fresh_mean_solved, 4)
        if (ace_mean_solved is not None and fresh_mean_solved is not None and fresh_mean_solved > 0)
        else 0.0
    )
    h2_pass = (
        s_ace["nominal_terminal_verified"] > s_fresh["nominal_terminal_verified"]
        or (
            s_ace["nominal_terminal_verified"] >= s_fresh["nominal_terminal_verified"]
            and eval_reduction_ratio >= 0.20
        )
    )

    baseline_trap_false_adm = (
        s_rule["trap_false_admissions"]
        + s_fixed["trap_false_admissions"]
        + s_fresh["trap_false_admissions"]
    )
    h3_pass = (
        baseline_trap_false_adm >= 1
        and s_ace["trap_false_admissions"] == 0
        and s_ace["trap_abstained"] == 2
        and s_ace["ood_abstained"] == 4
        and s_ace["total_false_admissions"] == 0
        and s_ace["admitted_count"] == s_ace["admitted_terminal_verified_count"]
    )

    live_nominal_rows = [
        t for t in target_evidence_by_arm["R_ace"] if t["category"] == "nominal"
    ]
    live_digests = [t["patched_source_sha256"] for t in live_nominal_rows]
    restart_digests = [t["patched_source_sha256"] for t in restart_nominal_trials]
    restart_reuse_phases = [
        t["stages"]["Represent"]["runtime"]["runtime_phase"] == "REUSE_VALIDATED"
        and t["stages"]["Represent"]["runtime"]["runtime_learning_called"] is False
        for t in restart_nominal_trials
    ]
    source_reuse_count = sum(
        1
        for t in source_evidence
        if t["stages"]["Represent"]["runtime"]["runtime_phase"] == "REUSE_VALIDATED"
    )
    h4_pass = (
        restart_status["total_records"] == post_source_memory_status["total_records"] == 8
        and restart_status["head_event_hash"] == post_source_memory_status["head_event_hash"]
        and restart_runtime_status["capabilities"] == 4
        and source_reuse_count == 4
        and all(restart_reuse_phases)
        and live_digests == restart_digests
    )

    scientific_capability_validated = bool(h1_pass and h2_pass and h3_pass and h4_pass)

    return {
        "schema": REPORT_SCHEMA,
        "protocol_commit": PRESCORE_COMMIT,
        "protocol_doc_sha256": PRESCORE_DOC_SHA256,
        "pipeline_stages": list(PIPELINE_STAGES),
        "families": list(FAMILIES),
        "arms": list(ARMS),
        "budget_k": BUDGET_K,
        "budget_matched": True,
        "source_bank_size": len(src_bank),
        "target_bank_size": len(tgt_bank),
        "source_acquisition": {
            "source_solved_and_remembered": sum(1 for t in source_evidence if t["staged"]),
            "runtime_capabilities_learned": post_source_runtime_status["capabilities"],
            "runtime_source_reuse_validated_count": source_reuse_count,
            "memory_records_after_source": post_source_memory_status["total_records"],
            "memory_head_hash_after_source": post_source_memory_status["head_event_hash"],
            "trials": source_evidence,
        },
        "arm_summaries": arm_summaries,
        "target_trials_by_arm": target_evidence_by_arm,
        "cold_restart_verification": {
            "restored_memory_records": restart_status["total_records"],
            "restored_memory_head_hash": restart_status["head_event_hash"],
            "restored_runtime_capabilities": restart_runtime_status["capabilities"],
            "all_nominal_runtime_reuse_validated": all(restart_reuse_phases),
            "exact_patch_digest_agreement": live_digests == restart_digests,
            "nominal_patch_digests": restart_digests,
        },
        "final_ace_state": {
            "runtime_completed_tasks": final_runtime_status["completed"],
            "runtime_capabilities": final_runtime_status["capabilities"],
            "runtime_events": final_runtime_status["events"],
            "runtime_implementation_sha256": final_runtime_status["implementation"],
            "memory_total_records": final_memory_status["total_records"],
            "memory_head_event_hash": final_memory_status["head_event_hash"],
        },
        "hypotheses": {
            "H1_nominal_accuracy_and_coverage": {
                "passed": h1_pass,
                "ace_nominal_verified": s_ace["nominal_terminal_verified"],
                "rule_nominal_verified": s_rule["nominal_terminal_verified"],
                "fixed_nominal_verified": s_fixed["nominal_terminal_verified"],
            },
            "H2_efficiency_or_accuracy_vs_fresh": {
                "passed": h2_pass,
                "ace_nominal_verified": s_ace["nominal_terminal_verified"],
                "fresh_nominal_verified": s_fresh["nominal_terminal_verified"],
                "ace_mean_evals_solved": ace_mean_solved,
                "fresh_mean_evals_solved": fresh_mean_solved,
                "eval_reduction_ratio": eval_reduction_ratio,
            },
            "H3_anti_overfit_and_ood_abstention": {
                "passed": h3_pass,
                "baseline_trap_false_admissions": baseline_trap_false_adm,
                "ace_trap_false_admissions": s_ace["trap_false_admissions"],
                "ace_ood_abstained": s_ace["ood_abstained"],
                "ace_total_false_admissions": s_ace["total_false_admissions"],
            },
            "H4_cross_restart_persistence": {
                "passed": h4_pass,
                "source_reuse_validated_count": source_reuse_count,
                "cold_restart_digest_match": live_digests == restart_digests,
            },
        },
        "evidence_flags": {
            "ACE_BASE_RUNTIME_EXECUTED": True,
            "NEW_CAPABILITY_INTEGRATED_AND_EXECUTED": True,
            "SCIENTIFIC_CAPABILITY_VALIDATED": scientific_capability_validated,
        },
        "open_world_safe": False,
        "scientific_decision": "NOT_ASSESSED",
        "release_gate": "BLOCK_RELEASE",
        "oaie_established": False,
        "candidate_deployed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/repair/ace_repair_v1.json.gz"),
        help="Output path for deterministic .json.gz evidence artifact",
    )
    args = parser.parse_args(argv)

    report = run_benchmark()
    raw_json = canonical_json(report)
    gz_bytes = compress_deterministic_gzip(raw_json)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(gz_bytes)

    summary = {
        "schema": report["schema"],
        "canonical_json_bytes": len(raw_json),
        "canonical_json_sha256": sha256_digest(raw_json),
        "gzip_bytes": len(gz_bytes),
        "gzip_sha256": sha256_digest(gz_bytes),
        "nominal_verified": {
            arm: report["arm_summaries"][arm]["nominal_terminal_verified"] for arm in ARMS
        },
        "false_admissions": {
            arm: report["arm_summaries"][arm]["total_false_admissions"] for arm in ARMS
        },
        "hypotheses": {k: v["passed"] for k, v in report["hypotheses"].items()},
        "evidence_flags": report["evidence_flags"],
        "scientific_decision": report["scientific_decision"],
        "release_gate": report["release_gate"],
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
