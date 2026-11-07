"""Deterministic Benchmark Runner for ACE Fase 7 (G0 -> G1 -> G2).

Executes:
1. Immutable core/evaluator/policy SHA-256 snapshot (``ImmutableCoreGuard``) + AST isolation check,
2. Live ``ace_runtime`` anchor execution & inheritance via ``Autonomy``,
3. Autonomous generational evolution ``G0 -> G1 -> G2`` with candidate staging (``STAGED_FOR_REVIEW``)
   and ``SelfReflection`` updates in ``ExperienceMemory``,
4. Terminal benchmark across 75 units (13 nominal + 2 drift tasks x 5 seeds) and 7 arms
   (``G0``, ``G1``, ``G2``, ``B_fixed``, ``B_random_mut``, ``B_extra_compute``, ``B_fresh``).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any

from ace_autonomy import Autonomy
from ace_selfmodel import ExperienceMemory

from . import evaluator
from .immutable_guard import ImmutableCoreGuard, verify_ast_evaluator_isolation
from .lineage import (
    G0_MECHANISM,
    evolve_g0_to_g1,
    evolve_g1_to_g2,
    evolve_random_mutation,
    seed_ace_runtime_lineage_anchors,
)
from .mechanisms import (
    build_features_for_mechanism,
    build_strong_fixed_library,
    fit_fresh_r1,
    fit_with_mechanism,
)
from .tasks import (
    DRIFT_CONTROLS,
    PRIMARY_BUDGET,
    SEEDS,
    TARGETS,
    TARGET_BY_ID,
    eval_spec,
    sample_labeled,
    unlabeled_probes,
)

ARMS = (
    "G0",
    "G1",
    "G2",
    "B_fixed",
    "B_random_mut",
    "B_extra_compute",
    "B_fresh",
)


def _strip_volatile_reflection(ref: dict[str, Any]) -> dict[str, Any]:
    return {
        k: v
        for k, v in ref.items()
        if k not in {"episode_id"}
    }


def _score_prog(prog, term: list[tuple[str, bool]]) -> float:
    if prog is None:
        return 0.5
    return sum(1 for w, y in term if prog.predict(w) == y) / len(term)


def run_generations_benchmark(repo_root: Path | None = None) -> dict[str, Any]:
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    guard = ImmutableCoreGuard(root)
    ast_iso = verify_ast_evaluator_isolation()
    if not ast_iso["isolated"]:
        raise RuntimeError(f"AST isolation violated: {ast_iso['violations']}")

    with tempfile.TemporaryDirectory(prefix="ace_fase7_gen_") as tmp:
        ws = Path(tmp) / "autonomy_ws"
        mem_ws = Path(tmp) / "selfmodel_ws"
        with Autonomy(ws, root) as autonomy, ExperienceMemory(mem_ws) as memory:
            ace_seed = seed_ace_runtime_lineage_anchors(autonomy)
            guard_pre_g1 = guard.verify_intact()

            g0_to_g1 = evolve_g0_to_g1(autonomy, memory)
            guard_post_g1 = guard.verify_intact()
            g1_meta = g0_to_g1["promoted"]

            g1_to_g2 = evolve_g1_to_g2(g1_meta, autonomy, memory)
            guard_post_g2 = guard.verify_intact()
            g2_meta = g1_to_g2["promoted"]

            auto_status = autonomy.status()
            if auto_status["capabilities_registered"] < 16:
                raise RuntimeError("expected >=16 staged candidate capabilities registered")
            memory.verify()
            mem_episodes, mem_succ = memory.global_base_rate()

    g_extra_meta = dict(G0_MECHANISM)
    g_extra_meta["gen_tag"] = "B_extra_compute"
    g_extra_meta["eval_budget_k"] = 1024

    feats_g0 = build_features_for_mechanism(G0_MECHANISM)
    feats_g1 = build_features_for_mechanism(g1_meta)
    feats_g2 = build_features_for_mechanism(g2_meta)
    feats_fixed = build_strong_fixed_library()
    rand_metas = {s: evolve_random_mutation(s) for s in SEEDS}
    feats_rand = {s: build_features_for_mechanism(rand_metas[s]) for s in SEEDS}

    n_tr = PRIMARY_BUDGET // 2
    n_va = PRIMARY_BUDGET - n_tr

    unit_records: list[dict[str, Any]] = []

    # 1. Nominal unseen target tasks (13 tasks x 5 seeds = 65 units)
    for tid, stratum, spec in TARGETS:
        for seed in SEEDS:
            tr = sample_labeled(spec, 0, 6, n_tr, "tgt_tr", tid, seed)
            va = sample_labeled(spec, 7, 13, n_va, "tgt_va", tid, seed)
            probes = unlabeled_probes(seed + 500)
            term = evaluator.terminal_bank(tid, spec, seed)
            for w, y in term:
                if eval_spec(spec, w) != y:
                    raise RuntimeError(f"truth mismatch on {tid}")

            arm_out: dict[str, Any] = {}
            for arm in ARMS:
                if arm == "B_fresh":
                    prog, diag = fit_fresh_r1(tr, va)
                elif arm == "B_fixed":
                    prog, diag = fit_with_mechanism(
                        feats_fixed,
                        tr,
                        va,
                        eval_budget_k=256,
                        enable_mdl_ranking=False,
                        enable_probe_agreement_gate=False,
                        probes=probes,
                    )
                elif arm == "B_extra_compute":
                    prog, diag = fit_with_mechanism(
                        feats_g0,
                        tr,
                        va,
                        eval_budget_k=1024,
                        enable_mdl_ranking=False,
                        enable_probe_agreement_gate=False,
                        probes=probes,
                    )
                elif arm == "B_random_mut":
                    rm = rand_metas[seed]
                    prog, diag = fit_with_mechanism(
                        feats_rand[seed],
                        tr,
                        va,
                        eval_budget_k=rm["eval_budget_k"],
                        enable_mdl_ranking=rm["enable_mdl_ranking"],
                        enable_probe_agreement_gate=rm["enable_probe_agreement_gate"],
                        probes=probes,
                    )
                else:
                    meta = {"G0": G0_MECHANISM, "G1": g1_meta, "G2": g2_meta}[arm]
                    fset = {"G0": feats_g0, "G1": feats_g1, "G2": feats_g2}[arm]
                    prog, diag = fit_with_mechanism(
                        fset,
                        tr,
                        va,
                        eval_budget_k=meta["eval_budget_k"],
                        enable_mdl_ranking=meta["enable_mdl_ranking"],
                        enable_probe_agreement_gate=meta["enable_probe_agreement_gate"],
                        probes=probes,
                    )
                acc = round(_score_prog(prog, term), 6)
                arm_out[arm] = {
                    "acc": acc,
                    "admitted": bool(diag["admitted"]),
                    "evals_used": int(diag["evals_used"]),
                    "symbol_reads": int(diag["symbol_reads"]),
                    "program": diag.get("program_name", "ABSTAIN"),
                }

            unit_records.append({
                "task_id": tid,
                "stratum": stratum,
                "seed": seed,
                "arms": arm_out,
            })

    # 2. Hidden terminal-inversion drift controls (2 tasks x 5 seeds = 10 units)
    for did, base_tid in DRIFT_CONTROLS:
        _, base_spec = TARGET_BY_ID[base_tid]
        inv_spec = ("not", base_spec)
        for seed in SEEDS:
            # Train and validation observed under unflipped base_spec; terminal flips to inv_spec!
            tr = sample_labeled(base_spec, 0, 6, n_tr, "tgt_tr", did, seed)
            va = sample_labeled(base_spec, 7, 13, n_va, "tgt_va", did, seed)
            probes = unlabeled_probes(seed + 700)
            term = evaluator.terminal_bank(did, inv_spec, seed)

            arm_out = {}
            for arm in ("G0", "G1", "G2"):
                meta = {"G0": G0_MECHANISM, "G1": g1_meta, "G2": g2_meta}[arm]
                fset = {"G0": feats_g0, "G1": feats_g1, "G2": feats_g2}[arm]
                prog, diag = fit_with_mechanism(
                    fset,
                    tr,
                    va,
                    eval_budget_k=meta["eval_budget_k"],
                    enable_mdl_ranking=meta["enable_mdl_ranking"],
                    enable_probe_agreement_gate=meta["enable_probe_agreement_gate"],
                    probes=probes,
                )
                acc = round(_score_prog(prog, term), 6)
                arm_out[arm] = {
                    "acc": acc,
                    "admitted": bool(diag["admitted"]),
                    "false_admission_under_hidden_flip": bool(diag["admitted"]) and acc < 0.25,
                }
            unit_records.append({
                "task_id": did,
                "stratum": "D_drift",
                "seed": seed,
                "arms": arm_out,
            })

    guard_final = guard.verify_intact()

    # Aggregate summaries by stratum
    summary_by_stratum: dict[str, dict[str, dict[str, float]]] = {}
    for st in ("U_gen", "L_base", "N_ood"):
        rows = [u for u in unit_records if u["stratum"] == st]
        summary_by_stratum[st] = {}
        for arm in ARMS:
            accs = [r["arms"][arm]["acc"] for r in rows]
            adms = [1 if r["arms"][arm]["admitted"] else 0 for r in rows]
            evals = [r["arms"][arm]["evals_used"] for r in rows]
            syms = [r["arms"][arm]["symbol_reads"] for r in rows]
            false_adms = sum(
                1 for r in rows if r["arms"][arm]["admitted"] and r["arms"][arm]["acc"] < 0.80
            )
            summary_by_stratum[st][arm] = {
                "mean_acc": round(sum(accs) / len(accs), 6),
                "admit_rate": round(sum(adms) / len(adms), 6),
                "false_admissions": false_adms,
                "mean_evals_used": round(sum(evals) / len(evals), 2),
                "mean_symbol_reads": round(sum(syms) / len(syms), 1),
            }

    drift_rows = [u for u in unit_records if u["stratum"] == "D_drift"]
    drift_summary = {
        arm: {
            "mean_acc": round(sum(r["arms"][arm]["acc"] for r in drift_rows) / len(drift_rows), 6),
            "false_admissions_under_hidden_flip": sum(
                1 for r in drift_rows if r["arms"][arm]["false_admission_under_hidden_flip"]
            ),
            "total_units": len(drift_rows),
        }
        for arm in ("G0", "G1", "G2")
    }

    u_sum = summary_by_stratum["U_gen"]
    l_sum = summary_by_stratum["L_base"]
    n_sum = summary_by_stratum["N_ood"]

    g2_vs_g1 = round(u_sum["G2"]["mean_acc"] - u_sum["G1"]["mean_acc"], 6)
    g1_vs_g0 = round(u_sum["G1"]["mean_acc"] - u_sum["G0"]["mean_acc"], 6)
    best_non_lineage = max(
        u_sum["B_extra_compute"]["mean_acc"],
        u_sum["B_fixed"]["mean_acc"],
        u_sum["B_fresh"]["mean_acc"],
    )
    g2_vs_non_lineage = round(u_sum["G2"]["mean_acc"] - best_non_lineage, 6)
    g2_vs_rand = round(u_sum["G2"]["mean_acc"] - u_sum["B_random_mut"]["mean_acc"], 6)

    h1_pass = g2_vs_g1 >= 0.15 and g1_vs_g0 >= 0.15
    h2_pass = g2_vs_non_lineage >= 0.15
    h3_pass = g2_vs_rand >= 0.15
    h4_pass = (
        l_sum["G2"]["mean_acc"] >= l_sum["G0"]["mean_acc"] - 0.05
        and n_sum["G2"]["false_admissions"] <= n_sum["G0"]["false_admissions"]
    )
    h5_pass = (
        guard_pre_g1 == guard_post_g1 == guard_post_g2 == guard_final
        and ast_iso["isolated"]
        and drift_summary["G2"]["false_admissions_under_hidden_flip"] > 0
    )

    return {
        "schema": "ace.generations.g0_g2.v1",
        "scientific_status": "NOT_ASSESSED",
        "release_status": "BLOCK_RELEASE",
        "oaie_established": False,
        "evidence_flags": {
            "ACE_BASE_RUNTIME_EXECUTED": bool(
                ace_seed["goal_status"] == "SUCCEEDED" and ace_seed["inheritance_verified"]
            ),
            "NEW_CAPABILITY_INTEGRATED_AND_EXECUTED": True,
            "SCIENTIFIC_CAPABILITY_VALIDATED": bool(
                h1_pass and h2_pass and h3_pass and h4_pass and h5_pass
            ),
            "PASSIVE_SEMANTIC_DRIFT_DETECTABLE": False,
        },
        "integrity_locks": {
            "ast_isolation": ast_iso,
            "immutable_guard": guard_final,
            "verified_across_all_transitions": (
                guard_pre_g1 == guard_post_g1 == guard_post_g2 == guard_final
            ),
        },
        "ace_runtime_seed": {
            "goal_id": ace_seed["goal_id"],
            "goal_status": ace_seed["goal_status"],
            "tasks_processed": ace_seed["tasks_processed"],
            "inheritance_verified": ace_seed["inheritance_verified"],
            "outcomes": [
                {
                    "task_id": o["task_id"],
                    "phase": o["phase"],
                    "reused": o["reused"],
                    "model_id": o["model_id"],
                }
                for o in ace_seed["outcomes"]
            ],
        },
        "lineage_transitions": {
            "G0": G0_MECHANISM,
            "G0_to_G1": {
                "promoted": g1_meta,
                "g0_m1_dev_acc": g0_to_g1["g0_m1_dev"]["mean_acc"],
                "g0_m1_val_acc": g0_to_g1["g0_m1_val"]["mean_acc"],
                "diagnostic": g0_to_g1["diagnostic"],
                "reflection": _strip_volatile_reflection(g0_to_g1["reflection"]),
                "autonomy_staging": g0_to_g1["autonomy_staging"],
                "candidate_evaluations": g0_to_g1["candidate_evaluations"],
            },
            "G1_to_G2": {
                "promoted": g2_meta,
                "g1_m2_dev_acc": g1_to_g2["g1_m2_dev"]["mean_acc"],
                "g1_m2_val_acc": g1_to_g2["g1_m2_val"]["mean_acc"],
                "g1_m1_val_acc": g1_to_g2["g1_m1_val"]["mean_acc"],
                "diagnostic": g1_to_g2["diagnostic"],
                "reflection": _strip_volatile_reflection(g1_to_g2["reflection"]),
                "autonomy_staging": g1_to_g2["autonomy_staging"],
                "candidate_evaluations": g1_to_g2["candidate_evaluations"],
            },
            "random_mutation_lineages": {str(s): rand_metas[s] for s in SEEDS},
            "experience_memory_episodes_recorded": mem_episodes,
            "experience_memory_successes": mem_succ,
        },
        "summary_by_stratum": summary_by_stratum,
        "drift_negative_control": drift_summary,
        "hypotheses": {
            "H1_monotonic_lineage_gain_on_U_gen": {
                "g1_minus_g0": g1_vs_g0,
                "g2_minus_g1": g2_vs_g1,
                "pass": h1_pass,
            },
            "H2_g2_beats_4x_compute_fixed_and_fresh": {
                "g2_acc": u_sum["G2"]["mean_acc"],
                "best_non_lineage_acc": best_non_lineage,
                "margin": g2_vs_non_lineage,
                "pass": h2_pass,
            },
            "H3_g2_beats_random_meta_mutation": {
                "g2_acc": u_sum["G2"]["mean_acc"],
                "random_mut_acc": u_sum["B_random_mut"]["mean_acc"],
                "margin": g2_vs_rand,
                "pass": h3_pass,
            },
            "H4_non_regression_and_ood_safety": {
                "g0_l_base_acc": l_sum["G0"]["mean_acc"],
                "g2_l_base_acc": l_sum["G2"]["mean_acc"],
                "g0_n_ood_false_admissions": n_sum["G0"]["false_admissions"],
                "g2_n_ood_false_admissions": n_sum["G2"]["false_admissions"],
                "pass": h4_pass,
            },
            "H5_immutable_evaluator_and_drift_honesty": {
                "locks_intact": guard_pre_g1 == guard_post_g1 == guard_post_g2 == guard_final,
                "ast_isolated": ast_iso["isolated"],
                "g2_drift_false_admissions": drift_summary["G2"]["false_admissions_under_hidden_flip"],
                "pass": h5_pass,
            },
            "all_gates_pass": bool(h1_pass and h2_pass and h3_pass and h4_pass and h5_pass),
        },
        "unit_records": unit_records,
    }


def write_evidence_gz(report: dict[str, Any], out_path: Path) -> str:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(report, sort_keys=True, indent=2) + "\n").encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    with out_path.open("wb") as fh, gzip.GzipFile(filename="", mode="wb", fileobj=fh, mtime=0) as gz:
        gz.write(raw)
    return sha


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ACE Fase 7 G0->G1->G2 benchmark.")
    parser.add_argument(
        "--out",
        default="evidence/generations/ace_g0_g2_v1.json.gz",
        help="Output gzip JSON path relative to repo root.",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    report = run_generations_benchmark(root)
    out = root / args.out
    sha = write_evidence_gz(report, out)
    print(
        json.dumps(
            {
                "artifact": str(args.out),
                "uncompressed_sha256": sha,
                "u_gen_G0": report["summary_by_stratum"]["U_gen"]["G0"]["mean_acc"],
                "u_gen_G1": report["summary_by_stratum"]["U_gen"]["G1"]["mean_acc"],
                "u_gen_G2": report["summary_by_stratum"]["U_gen"]["G2"]["mean_acc"],
                "u_gen_B_extra_compute": report["summary_by_stratum"]["U_gen"]["B_extra_compute"]["mean_acc"],
                "u_gen_B_fixed": report["summary_by_stratum"]["U_gen"]["B_fixed"]["mean_acc"],
                "u_gen_B_random_mut": report["summary_by_stratum"]["U_gen"]["B_random_mut"]["mean_acc"],
                "u_gen_B_fresh": report["summary_by_stratum"]["U_gen"]["B_fresh"]["mean_acc"],
                "all_gates_pass": report["hypotheses"]["all_gates_pass"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
