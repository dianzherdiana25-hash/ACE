"""Deterministic Fase 6 benchmark runner and hypothesis evaluator.

Produces a 100% Python-version-independent canonical JSON report (zero wall-clock
floats or interpreter-version strings inside the hashed report payload).
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time
from typing import Any

from . import PRESCORE_COMMIT, PRESCORE_SHA256, SCHEMA, canonical_json, digest
from .arms import (
    ARM_NAMES,
    ArmFitOutcome,
    RuntimeReuseSession,
    build_transfer_atom_bank,
    fit_fresh_dsl_pair,
    fit_memorize,
    fit_native_oracle_upper_bound,
    fit_strong_fixed,
    fit_transfer_abstractions,
)
from .discovery import (
    K_MAX,
    SourceDiscoveryReport,
    discover_from_source_pool,
    is_functionally_determined,
    sample_random_abstractions,
)
from .dsl import WorkMeter, parse_dyck_input
from .evaluator import (
    parse_single_tree,
    score_terminal_predictions,
    tree_bipartite_diff,
    tree_branching_nodes,
    tree_leaves,
    tree_max_depth,
    tree_max_outdeg,
    tree_root_deg,
)
from .sampling import single_tree_pool
from .tasks import (
    BUDGETS,
    PRIMARY_BUDGET,
    SEEDS,
    STRATA_ORDER,
    TARGET_TASKS_SPEC,
    build_target_splits,
    build_uncurated_source_pool,
)


def _audit_source_structural_recovery(report: SourceDiscoveryReport) -> dict[str, Any]:
    """Post-hoc evaluator audit checking which canonical tree invariants were discovered.

    Evaluated strictly AFTER `discover_from_source_pool` finishes, using all 2,055
    single trees in `single_tree_pool(2, 9)` to test exact functional equivalence
    (`H(canonical | discovered) == 0 and H(discovered | canonical) == 0`).
    """
    all_words = single_tree_pool(2, 9)
    parsed_all = tuple(parse_dyck_input(w) for w in all_words)
    trees = [parse_single_tree(w) for w in all_words]

    canonical_vecs: dict[str, tuple[int, ...]] = {
        "max_depth": tuple(tree_max_depth(t) for t in trees if t is not None),
        "leaves": tuple(tree_leaves(t) for t in trees if t is not None),
        "root_deg": tuple(tree_root_deg(t) for t in trees if t is not None),
        "bipartite_diff": tuple(tree_bipartite_diff(t) for t in trees if t is not None),
        "max_outdeg": tuple(tree_max_outdeg(t) for t in trees if t is not None),
        "branching_nodes": tuple(tree_branching_nodes(t) for t in trees if t is not None),
    }

    abs_vecs: list[tuple[Any, ...]] = []
    bool_slot_count = 0
    for ab in report.abstractions:
        if ab.kind == "int":
            assert ab.int_expr is not None
            vec = tuple(ab.int_expr.eval_parsed(p) for p in parsed_all)
        else:
            assert ab.bool_expr is not None
            bool_slot_count += 1
            vec = tuple(ab.bool_expr.eval_parsed(p) for p in parsed_all)
        abs_vecs.append(vec)

    recovered: list[str] = []
    for inv_name, c_vec in sorted(canonical_vecs.items()):
        # Bijective functional equivalence (`H(c|a)==0 and H(a|c)==0`) up to sign/bijection
        if any(
            is_functionally_determined(c_vec, a_vec) and is_functionally_determined(a_vec, c_vec)
            for a_vec in abs_vecs
        ):
            recovered.append(inv_name)

    total_slots = len(report.abstractions)
    distractor_bool_fraction = round(bool_slot_count / max(1, total_slots), 6)
    return {
        "total_selected_slots": total_slots,
        "recovered_structural_invariants": recovered,
        "recovered_count": len(recovered),
        "boolean_distractor_slots": bool_slot_count,
        "boolean_distractor_fraction": distractor_bool_fraction,
    }


def _evaluate_arm_on_terminal(
    fit_out: ArmFitOutcome,
    terminal: list[tuple[str, bool]],
    n_train: int,
    n_val: int,
) -> dict[str, Any]:
    term_meter = WorkMeter()
    preds = [bool(fit_out.predict_fn(w, term_meter)) for w, _ in terminal]
    term_meter.candidates_evaluated = 1
    scored = score_terminal_predictions(lambda w, m=dict(zip((x for x, _ in terminal), preds)): m[w], terminal)
    assert scored["predictions"] == preds

    ast_data = fit_out.metadata.get("selected_ast")
    clean_meta = {k: v for k, v in fit_out.metadata.items() if k != "selected_ast"}

    return {
        "capability_class": fit_out.capability_class,
        "train_correct": fit_out.train_correct,
        "train_total": n_train,
        "validation_correct": fit_out.validation_correct,
        "validation_total": n_val,
        "admitted": fit_out.admitted,
        "probe_agreement": fit_out.probe_agreement,
        "terminal_correct": int(scored["terminal_correct"]),
        "terminal_total": int(scored["terminal_total"]),
        "terminal_accuracy": float(scored["terminal_accuracy"]),
        "predictions_sha256": digest(preds),
        "selected_description": fit_out.selected_description,
        "selected_identity": fit_out.selected_identity,
        "selected_ast": ast_data,
        "fit_work": fit_out.work,
        "terminal_work": term_meter.to_dict(),
        "metadata": clean_meta,
    }


def run_benchmark() -> dict[str, Any]:
    """Execute full Fase 6 matrix across budgets `{16, 32, 64}` and seeds `1..5`."""
    import hashlib
    import importlib.util

    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("verify_sources", root / "tools/verify_sources.py")
    assert spec is not None and spec.loader is not None
    vs_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vs_mod)

    upstream_count = vs_mod.verify(root)
    prescore_bytes = (root / "docs/ACE_NOVEL_DISCOVERY_PRESCORE_V1.md").read_bytes()

    actual_prescore_sha = hashlib.sha256(prescore_bytes).hexdigest()
    if actual_prescore_sha != PRESCORE_SHA256:
        raise RuntimeError(
            f"pre-score protocol tampered: expected {PRESCORE_SHA256}, got {actual_prescore_sha}"
        )

    n_target_tasks = len(TARGET_TASKS_SPEC)

    # Phase 1: Per-seed uncurated source pool discovery & matched random abstraction sampling
    source_reports: dict[int, SourceDiscoveryReport] = {}
    source_manifests: dict[int, list[dict[str, Any]]] = {}
    source_audits: dict[int, dict[str, Any]] = {}
    random_abs_by_seed: dict[int, tuple[tuple[Any, ...], dict[str, int]]] = {}
    learner_sources_by_seed: dict[int, list[dict[str, Any]]] = {}
    m4_atoms_by_seed: dict[int, list[Any]] = {}
    m5_atoms_by_seed: dict[int, list[Any]] = {}
    m5_ug_atoms_by_seed: dict[int, list[Any]] = {}

    for seed in SEEDS:
        learner_tasks, manifest = build_uncurated_source_pool(seed)
        learner_sources_by_seed[seed] = learner_tasks
        source_manifests[seed] = manifest
        s_rep = discover_from_source_pool(learner_tasks, seed=seed)
        source_reports[seed] = s_rep
        source_audits[seed] = _audit_source_structural_recovery(s_rep)

        rand_meter = WorkMeter()
        rand_abs = sample_random_abstractions(seed=seed, count=len(s_rep.abstractions), meter=rand_meter)
        random_abs_by_seed[seed] = (rand_abs, rand_meter.to_dict())

        m4_atoms_by_seed[seed] = build_transfer_atom_bank(rand_abs)
        m5_atoms_by_seed[seed] = build_transfer_atom_bank(s_rep.abstractions)
        m5_ug_atoms_by_seed[seed] = build_transfer_atom_bank(s_rep.ungated_abstractions)

    # Phase 2: Target task evaluation across budgets and seeds
    trials: list[dict[str, Any]] = []

    for budget in BUDGETS:
        for seed in SEEDS:
            s_rep = source_reports[seed]
            rand_abs, rand_work = random_abs_by_seed[seed]
            learner_sources = learner_sources_by_seed[seed]
            m4_atoms = m4_atoms_by_seed[seed]
            m5_atoms = m5_atoms_by_seed[seed]
            m5_ug_atoms = m5_ug_atoms_by_seed[seed]

            with RuntimeReuseSession(learner_sources) as m1_session:
                for t_idx, t_spec in enumerate(TARGET_TASKS_SPEC):
                    train, val, terminal = build_target_splits(t_spec.name, seed=seed, budget=budget)
                    n_tr, n_va = len(train), len(val)

                    arms_entry: dict[str, Any] = {}

                    # M0: Memorization
                    m0_fit = fit_memorize(train, val)
                    arms_entry["M0_memorize"] = _evaluate_arm_on_terminal(m0_fit, terminal, n_tr, n_va)

                    # M1: Exact reuse via real ACE Runtime
                    m1_fit, m1_term = m1_session.fit_and_evaluate_target(
                        slot_label=f"target_{t_idx:02d}_b{budget}_s{seed}",
                        train=train,
                        validation=val,
                        terminal=terminal,
                    )
                    arms_entry["M1_exact_reuse"] = {
                        "capability_class": m1_fit.capability_class,
                        "train_correct": m1_fit.train_correct,
                        "train_total": n_tr,
                        "validation_correct": m1_fit.validation_correct,
                        "validation_total": n_va,
                        "admitted": m1_fit.admitted,
                        "probe_agreement": m1_fit.probe_agreement,
                        "terminal_correct": m1_term["terminal_correct"],
                        "terminal_total": m1_term["terminal_total"],
                        "terminal_accuracy": m1_term["terminal_accuracy"],
                        "predictions_sha256": m1_term["predictions_sha256"],
                        "selected_description": m1_fit.selected_description,
                        "selected_identity": m1_fit.selected_identity,
                        "selected_ast": None,
                        "fit_work": m1_fit.work,
                        "terminal_work": m1_term["terminal_work"],
                        "metadata": m1_fit.metadata,
                    }

                    # M2: Strong fixed feature library (174 predicates)
                    m2_fit = fit_strong_fixed(train, val, seed=seed)
                    arms_entry["M2_strong_fixed"] = _evaluate_arm_on_terminal(m2_fit, terminal, n_tr, n_va)

                    # M3: Fresh target DSL synthesis (1x and 4x compute budgets)
                    m3_fit, m3_4x_fit = fit_fresh_dsl_pair(train, val, seed=seed)
                    arms_entry["M3_fresh_dsl"] = _evaluate_arm_on_terminal(m3_fit, terminal, n_tr, n_va)
                    arms_entry["M3_fresh_4x"] = _evaluate_arm_on_terminal(m3_4x_fit, terminal, n_tr, n_va)

                    # M4: Random typed abstraction transfer control (matched count K)
                    m4_fit = fit_transfer_abstractions(
                        arm_name="M4_random_abs",
                        capability_class="random_typed_abstraction_transfer",
                        abstractions=rand_abs,  # type: ignore[arg-type]
                        train=train,
                        validation=val,
                        seed=seed,
                        gated=True,
                        raw_source_work=rand_work,
                        n_target_tasks_for_amortization=n_target_tasks,
                        prebuilt_atoms=m4_atoms,
                    )
                    arms_entry["M4_random_abs"] = _evaluate_arm_on_terminal(m4_fit, terminal, n_tr, n_va)

                    # M5: ACE automated structural abstraction discovery (gated & ungated)
                    m5_fit = fit_transfer_abstractions(
                        arm_name="M5_ace_discovery",
                        capability_class="discovered_typed_abstractions",
                        abstractions=s_rep.abstractions,
                        train=train,
                        validation=val,
                        seed=seed,
                        gated=True,
                        raw_source_work=s_rep.work,
                        n_target_tasks_for_amortization=n_target_tasks,
                        prebuilt_atoms=m5_atoms,
                    )
                    arms_entry["M5_ace_discovery"] = _evaluate_arm_on_terminal(m5_fit, terminal, n_tr, n_va)

                    m5_ug_fit = fit_transfer_abstractions(
                        arm_name="M5_ace_ungated",
                        capability_class="discovered_typed_abstractions_ungated",
                        abstractions=s_rep.ungated_abstractions,
                        train=train,
                        validation=val,
                        seed=seed,
                        gated=False,
                        raw_source_work=s_rep.work,
                        n_target_tasks_for_amortization=n_target_tasks,
                        prebuilt_atoms=m5_ug_atoms,
                    )
                    arms_entry["M5_ace_ungated"] = _evaluate_arm_on_terminal(m5_ug_fit, terminal, n_tr, n_va)

                    # Separate Native Solver Upper Bound (NEVER inside `arms_entry`)
                    oracle_fit = fit_native_oracle_upper_bound(train, val, seed=seed)
                    oracle_eval = _evaluate_arm_on_terminal(oracle_fit, terminal, n_tr, n_va)

                    assert set(arms_entry.keys()) == set(ARM_NAMES)
                    assert "U_native_oracle" not in arms_entry

                    trials.append(
                        {
                            "budget": budget,
                            "seed": seed,
                            "task": t_spec.name,
                            "stratum": t_spec.stratum,
                            "data_sha256": {
                                "train": digest(train),
                                "validation": digest(val),
                                "terminal": digest(terminal),
                            },
                            "arms": arms_entry,
                            "upper_bound_oracle": oracle_eval,
                        }
                    )

    # Phase 3: Compute Stratified Aggregates & Separate Upper Bound Aggregates
    by_budget_stratum: dict[str, dict[str, Any]] = {}
    oracle_by_budget_stratum: dict[str, dict[str, Any]] = {}

    for budget in BUDGETS:
        b_key = str(budget)
        by_budget_stratum[b_key] = {}
        oracle_by_budget_stratum[b_key] = {}
        for stratum in STRATA_ORDER:
            sub_trials = [t for t in trials if t["budget"] == budget and t["stratum"] == stratum]
            n_sub = len(sub_trials)
            arm_aggs: dict[str, Any] = {}
            for arm in ARM_NAMES:
                recs = [t["arms"][arm] for t in sub_trials]
                mean_acc = round(sum(r["terminal_accuracy"] for r in recs) / n_sub, 6)
                adm_rate = round(sum(1 for r in recs if r["admitted"]) / n_sub, 6)
                val_solve = round(
                    sum(1 for r in recs if r["admitted"] and r["terminal_accuracy"] >= 0.90) / n_sub,
                    6,
                )
                mean_fit_ast = round(sum(r["fit_work"]["ast_nodes_evaluated"] for r in recs) / n_sub, 2)
                mean_amort_ast = round(
                    sum(
                        r["fit_work"].get("total_amortized_ast_nodes", r["fit_work"]["ast_nodes_evaluated"])
                        for r in recs
                    )
                    / n_sub,
                    2,
                )
                mean_steps = round(sum(r["fit_work"]["symbol_steps"] for r in recs) / n_sub, 2)
                mean_cands = round(sum(r["fit_work"]["candidates_evaluated"] for r in recs) / n_sub, 2)
                arm_aggs[arm] = {
                    "trials": n_sub,
                    "mean_terminal_accuracy": mean_acc,
                    "admission_rate": adm_rate,
                    "validated_solve_rate": val_solve,
                    "mean_fit_ast_nodes": mean_fit_ast,
                    "mean_total_amortized_ast_nodes": mean_amort_ast,
                    "mean_symbol_steps": mean_steps,
                    "mean_candidates_evaluated": mean_cands,
                }
            by_budget_stratum[b_key][stratum] = arm_aggs

            orecs = [t["upper_bound_oracle"] for t in sub_trials]
            oracle_by_budget_stratum[b_key][stratum] = {
                "trials": n_sub,
                "mean_terminal_accuracy": round(sum(r["terminal_accuracy"] for r in orecs) / n_sub, 6),
                "admission_rate": round(sum(1 for r in orecs if r["admitted"]) / n_sub, 6),
                "validated_solve_rate": round(
                    sum(1 for r in orecs if r["admitted"] and r["terminal_accuracy"] >= 0.90) / n_sub,
                    6,
                ),
            }

    # Per-task breakdown at primary budget B=32
    per_task_b32: dict[str, Any] = {}
    for t_spec in TARGET_TASKS_SPEC:
        t_rows = [t for t in trials if t["budget"] == PRIMARY_BUDGET and t["task"] == t_spec.name]
        per_task_b32[t_spec.name] = {
            "stratum": t_spec.stratum,
            "arms": {
                arm: {
                    "mean_terminal_accuracy": round(
                        sum(r["arms"][arm]["terminal_accuracy"] for r in t_rows) / len(t_rows), 6
                    ),
                    "admission_rate": round(
                        sum(1 for r in t_rows if r["arms"][arm]["admitted"]) / len(t_rows), 6
                    ),
                }
                for arm in ARM_NAMES
            },
            "upper_bound_oracle": {
                "mean_terminal_accuracy": round(
                    sum(r["upper_bound_oracle"]["terminal_accuracy"] for r in t_rows) / len(t_rows), 6
                ),
                "admission_rate": round(
                    sum(1 for r in t_rows if r["upper_bound_oracle"]["admitted"]) / len(t_rows), 6
                ),
            },
        }

    # Phase 4: Evaluate Pre-Registered Hypotheses H1..H7 at Primary Budget B=32
    p_ucross = by_budget_stratum[str(PRIMARY_BUDGET)]["U_cross"]
    p_lsurf = by_budget_stratum[str(PRIMARY_BUDGET)]["L_surface"]
    p_nabst = by_budget_stratum[str(PRIMARY_BUDGET)]["N_abstain"]
    p_ddrift = by_budget_stratum[str(PRIMARY_BUDGET)]["D_drift"]

    m5_u = p_ucross["M5_ace_discovery"]["mean_terminal_accuracy"]
    m0_u = p_ucross["M0_memorize"]["mean_terminal_accuracy"]
    m1_u = p_ucross["M1_exact_reuse"]["mean_terminal_accuracy"]
    m2_u = p_ucross["M2_strong_fixed"]["mean_terminal_accuracy"]
    m3_u = p_ucross["M3_fresh_dsl"]["mean_terminal_accuracy"]
    m3_4x_u = p_ucross["M3_fresh_4x"]["mean_terminal_accuracy"]
    m4_u = p_ucross["M4_random_abs"]["mean_terminal_accuracy"]

    m5_fit_ast = p_ucross["M5_ace_discovery"]["mean_fit_ast_nodes"]
    m5_amort_ast = p_ucross["M5_ace_discovery"]["mean_total_amortized_ast_nodes"]
    m3_4x_ast = p_ucross["M3_fresh_4x"]["mean_total_amortized_ast_nodes"]

    h1_pass = (
        m5_u >= 0.85
        and round(m5_u - m0_u, 6) >= 0.20
        and round(m5_u - m1_u, 6) >= 0.20
        and round(m5_u - m2_u, 6) >= 0.20
    )
    h2_pass = (
        round(m5_u - m3_u, 6) >= 0.15
        and round(m5_u - m3_4x_u, 6) >= 0.10
        and m5_amort_ast < m3_4x_ast
    )
    h3_pass = round(m5_u - m4_u, 6) >= 0.20

    min_struct_recovered = min(source_audits[s]["recovered_count"] for s in SEEDS)
    max_distractor_frac = max(source_audits[s]["boolean_distractor_fraction"] for s in SEEDS)
    max_slots_used = max(source_audits[s]["total_selected_slots"] for s in SEEDS)
    h4_pass = (min_struct_recovered >= 5) and (max_slots_used <= K_MAX) and (max_distractor_frac < 0.50)

    m5_l = p_lsurf["M5_ace_discovery"]["mean_terminal_accuracy"]
    m2_l = p_lsurf["M2_strong_fixed"]["mean_terminal_accuracy"]
    h5_pass = (m5_l >= 0.90) and (round(m2_l - m5_l, 6) <= 0.05)

    m5_false_adm = p_nabst["M5_ace_discovery"]["admission_rate"]
    m5_ug_false_adm = p_nabst["M5_ace_ungated"]["admission_rate"]
    h6_pass = (m5_false_adm <= 0.20) and (round(m5_ug_false_adm - m5_false_adm, 6) >= 0.75)

    m5_drift_acc = p_ddrift["M5_ace_discovery"]["mean_terminal_accuracy"]
    m5_drift_adm = p_ddrift["M5_ace_discovery"]["admission_rate"]
    # H7a: Expected negative safety witness (indistinguishable semantic drift causes false promotion)
    h7a_drift_exposed = (m5_drift_adm >= 0.80) and (m5_drift_acc <= 0.20)

    hypotheses = {
        "H1_cross_family_vs_reuse_memorize_fixed": {
            "passed": h1_pass,
            "m5_u_cross_acc": m5_u,
            "gain_vs_m0_memorize": round(m5_u - m0_u, 6),
            "gain_vs_m1_exact_reuse": round(m5_u - m1_u, 6),
            "gain_vs_m2_strong_fixed": round(m5_u - m2_u, 6),
        },
        "H2_vs_fresh_dsl_and_4x_compute": {
            "passed": h2_pass,
            "gain_vs_m3_fresh_1x": round(m5_u - m3_u, 6),
            "gain_vs_m3_fresh_4x": round(m5_u - m3_4x_u, 6),
            "m5_target_only_fit_ast_nodes": m5_fit_ast,
            "m5_amortized_ast_nodes": m5_amort_ast,
            "m3_4x_ast_nodes": m3_4x_ast,
            "amortized_ast_ratio_m5_over_m3_4x": round(m5_amort_ast / max(1.0, m3_4x_ast), 4),
        },
        "H3_vs_matched_random_abstractions": {
            "passed": h3_pass,
            "gain_vs_m4_random_abs": round(m5_u - m4_u, 6),
        },
        "H4_uncurated_mixed_source_filtering": {
            "passed": h4_pass,
            "min_structural_invariants_recovered_of_6": min_struct_recovered,
            "max_boolean_distractor_fraction": max_distractor_frac,
            "max_library_slots_used": max_slots_used,
        },
        "H5_no_surface_regression": {
            "passed": h5_pass,
            "m5_l_surface_acc": m5_l,
            "m2_l_surface_acc": m2_l,
            "m5_minus_m2_l_surface": round(m5_l - m2_l, 6),
        },
        "H6_non_expressible_abstention_safety": {
            "passed": h6_pass,
            "m5_false_admission_rate": m5_false_adm,
            "m5_ungated_false_admission_rate": m5_ug_false_adm,
            "false_admission_reduction": round(m5_ug_false_adm - m5_false_adm, 6),
        },
        "H7a_unobservable_drift_negative_control": {
            "drift_immunity_passed": False,
            "expected_epistemic_failure_witnessed": h7a_drift_exposed,
            "m5_drift_admission_rate": m5_drift_adm,
            "m5_drift_terminal_acc": m5_drift_acc,
            "verdict": "FAIL_EXPECTED_UNOBSERVABLE_INVERSION",
        },
        "H7b_custody_and_upstream_pins": {
            "passed": upstream_count == 25 and actual_prescore_sha == PRESCORE_SHA256,
            "upstream_files_verified": upstream_count,
            "prescore_sha256_verified": actual_prescore_sha == PRESCORE_SHA256,
        },
    }

    nominal_scientific_validated = bool(
        h1_pass and h2_pass and h3_pass and h4_pass and h5_pass and h6_pass and h7a_drift_exposed
    )

    source_summary = {
        str(s): {
            "source_task_count": source_reports[s].source_task_count,
            "admitted_source_count": source_reports[s].admitted_source_count,
            "work": source_reports[s].work,
            "abstractions": [ab.to_data() for ab in source_reports[s].abstractions],
            "audit": source_audits[s],
            "manifest": source_manifests[s],
        }
        for s in SEEDS
    }

    return {
        "schema": SCHEMA,
        "prescore_commit": PRESCORE_COMMIT,
        "prescore_sha256": PRESCORE_SHA256,
        "upstream_sources_verified": upstream_count,
        "budgets": list(BUDGETS),
        "primary_budget": PRIMARY_BUDGET,
        "seeds": list(SEEDS),
        "source_discovery_by_seed": source_summary,
        "aggregates": {
            "by_budget_stratum": by_budget_stratum,
            "per_task_primary_b32": per_task_b32,
        },
        "upper_bound_oracle": {
            "description": "Separately reported researcher-authored native structural projection upper bound; never conflated with learned capability arms.",
            "by_budget_stratum": oracle_by_budget_stratum,
        },
        "hypotheses": hypotheses,
        "trials": trials,
        "evidence_flags": {
            "ACE_BASE_RUNTIME_EXECUTED": True,
            "NEW_CAPABILITY_INTEGRATED_AND_EXECUTED": True,
            "SCIENTIFIC_CAPABILITY_VALIDATED": nominal_scientific_validated,
        },
        "scientific_scope_note": (
            "Bounded automated sub-program abstraction discovery from uncurated mixed pool "
            "and cross-family paired-tree transfer within supplied stack/scan combinator DSL."
        ),
        "open_world_safe": False,
        "release_decision": "BLOCK_RELEASE",
        "oaie_established": False,
        "candidate_deployed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/discovery/f6_novel_discovery_v1.json"),
        help="Path to write canonical uncompressed JSON evidence",
    )
    args = parser.parse_args(argv)

    t0 = time.perf_counter()
    report = run_benchmark()
    elapsed = time.perf_counter() - t0

    raw_bytes = canonical_json(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(raw_bytes)

    import hashlib
    import json

    sha = hashlib.sha256(raw_bytes).hexdigest()
    summary = {
        "output": str(args.output),
        "bytes": len(raw_bytes),
        "sha256": sha,
        "elapsed_seconds_unhashed": round(elapsed, 3),
        "evidence_flags": report["evidence_flags"],
        "primary_b32_u_cross": {
            arm: report["aggregates"]["by_budget_stratum"]["32"]["U_cross"][arm]["mean_terminal_accuracy"]
            for arm in ARM_NAMES
        },
        "upper_bound_b32_u_cross": report["upper_bound_oracle"]["by_budget_stratum"]["32"]["U_cross"][
            "mean_terminal_accuracy"
        ],
    }
    print(json.dumps(summary, sort_keys=True), file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
