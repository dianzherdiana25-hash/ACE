"""Bounded Generational Evolution Lineage (G0 -> G1 -> G2) for Fase 7.

Integrates live ``ace_runtime`` (via ``Autonomy``), ``ExperienceMemory`` + ``SelfReflection``
(from ``ace_selfmodel``), and ``Autonomy`` candidate staging (``STAGED_FOR_REVIEW``).
NEVER imports ``evaluator.py``.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from ace_autonomy import Autonomy, BudgetCeiling, GoalPolicy
from ace_selfmodel import ExperienceMemory, MetacognitiveForecast, SelfReflection

from .immutable_guard import PROMOTION_POLICY, validate_meta_candidate
from .mechanisms import build_features_for_mechanism, fit_with_mechanism
from .tasks import (
    M1_DEV,
    M1_VAL,
    M2_DEV,
    M2_VAL,
    TARGETS,
    even_a,
    odd_b,
    sample_labeled,
    split_halves,
    unlabeled_probes,
    words_of_len,
)

G0_MECHANISM: dict[str, Any] = {
    "schema": "ace.meta_mechanism.v1",
    "gen_tag": "G0",
    "parent_gen": "ROOT",
    "enable_strided_features": False,
    "stride_moduli": [2],
    "enable_split_frame_lifting": False,
    "enable_mdl_ranking": False,
    "enable_probe_agreement_gate": False,
    "eval_budget_k": 256,
}

DEV_SEEDS = (1, 2, 3)
BASE_SANITY = tuple((tid, spec) for tid, st, spec in TARGETS if st == "L_base")


def seed_ace_runtime_lineage_anchors(autonomy: Autonomy) -> dict[str, Any]:
    """Execute real ``ace_runtime`` anchor learning + validated model inheritance via ``Autonomy``."""
    from ace_runtime.engine import Runtime

    train_words = [w for n in range(0, 6) for w in words_of_len(n)]  # 63 prefixes <= 63 limit
    val_words = list(words_of_len(6))  # 64 words <= 128 limit, disjoint from train

    def _rows(words: list[str]) -> list[list[Any]]:
        return [[w, w.count("a") % 2 == 0] for w in words]

    tasks = [
        {
            "name": "gen_anchor_parity_seed",
            "train": _rows(train_words),
            "validation": _rows(val_words),
        },
        {
            "name": "gen_anchor_parity_inherit",
            "train": _rows(train_words),
            "validation": _rows(val_words),
        },
    ]
    goal = {
        "schema": "ace.goal.v1",
        "name": "fase7_ace_runtime_lineage_seed",
        "objective": {
            "kind": "ace_task_learning_cycle",
            "tasks": tasks,
        },
        "policy": GoalPolicy(
            authorized_tools=(
                "ace_enqueue_task",
                "ace_run_tasks",
                "ace_status",
            ),
            read_prefixes=("",),
            write_prefixes=("candidates/",),
            review_policy="complete",
        ).to_dict(),
        "budget": BudgetCeiling(
            max_steps=6,
            max_candidates=1,
            max_retries_per_step=0,
            wall_seconds=10.0,
            cpu_seconds=5.0,
        ).to_dict(),
    }
    gid = autonomy.enqueue(goal)
    autonomy.run_until_stopped(gid, max_iterations=12)
    rep = autonomy.report(gid)

    tid1 = rep["results"][0]["evidence"]["task_id"]
    tid2 = rep["results"][1]["evidence"]["task_id"]
    status_out = rep["results"][3]["evidence"]

    with Runtime(autonomy.workspace / "real_ace_workspace") as rt:
        r1_rep = rt.report(tid1)
        r2_rep = rt.report(tid2)

    outcomes = [
        {
            "task_id": r1_rep["task_id"],
            "phase": r1_rep["phase"],
            "reused": r1_rep["phase"] == "REUSE_VALIDATED",
            "model_id": r1_rep["model_id"],
        },
        {
            "task_id": r2_rep["task_id"],
            "phase": r2_rep["phase"],
            "reused": r2_rep["phase"] == "REUSE_VALIDATED",
            "model_id": r2_rep["model_id"],
        },
    ]
    return {
        "goal_id": gid,
        "goal_status": rep["status"],
        "tasks_processed": len(outcomes),
        "outcomes": outcomes,
        "inheritance_verified": any(o["reused"] is True for o in outcomes),
        "ace_runtime_status": status_out,
    }


def _eval_meta_on_bank(
    meta: dict[str, Any],
    bank: tuple[tuple[str, tuple], ...],
    seeds: tuple[int, ...] = DEV_SEEDS,
) -> dict[str, Any]:
    """Fit-side evaluation using lengths 0..6 (train), 7..13 (val), and 14..15 (disjoint meta-eval)."""
    validate_meta_candidate(meta)
    feats = build_features_for_mechanism(meta)
    accs: list[float] = []
    admitted_cnt = 0
    total_evals = 0
    failures: list[dict[str, Any]] = []

    for tid, spec in bank:
        for seed in seeds:
            tr = sample_labeled(spec, 0, 6, 16, "meta_tr", tid, seed)
            va = sample_labeled(spec, 7, 13, 16, "meta_va", tid, seed)
            me = sample_labeled(spec, 14, 15, 64, "meta_hold", tid, seed)
            probes = unlabeled_probes(seed + 100)
            prog, diag = fit_with_mechanism(
                feats,
                tr,
                va,
                eval_budget_k=meta["eval_budget_k"],
                enable_mdl_ranking=meta["enable_mdl_ranking"],
                enable_probe_agreement_gate=meta["enable_probe_agreement_gate"],
                probes=probes,
            )
            total_evals += diag["evals_used"]
            if prog is None:
                accs.append(0.5)
                failures.append({"task_id": tid, "seed": seed, "reason": diag["abstain_reason"]})
            else:
                admitted_cnt += 1
                acc = sum(1 for w, y in me if prog.predict(w) == y) / len(me)
                accs.append(acc)
                if acc < 0.95:
                    failures.append({"task_id": tid, "seed": seed, "reason": f"low_meta_acc:{acc:.3f}"})

    return {
        "mean_acc": round(sum(accs) / len(accs), 6),
        "admitted_rate": round(admitted_cnt / len(accs), 6),
        "mean_evals_used": round(total_evals / len(accs), 2),
        "feature_count": len(feats),
        "failure_count": len(failures),
        "failures": failures,
    }


def _diagnose_anagram_collisions(bank: tuple[tuple[str, tuple], ...]) -> dict[str, Any]:
    """Detect whether flat symbol-count + 2-char boundary signatures collide across opposite labels."""
    collisions = 0
    strided_separable = 0
    for tid, spec in bank:
        rows = sample_labeled(spec, 4, 10, 32, "diag_m1", tid, 1)
        by_flat: dict[tuple[int, int, str, str], list[tuple[str, bool]]] = {}
        for w, y in rows:
            sig = (w.count("a"), w.count("b"), w[:2], w[-2:])
            by_flat.setdefault(sig, []).append((w, y))
        for bucket in by_flat.values():
            labels = {y for _, y in bucket}
            if len(labels) > 1:
                collisions += 1
                strided_sigs = {(even_a(w) % 2, odd_b(w) % 2, even_a(w) % 3, odd_b(w) % 3) for w, _ in bucket}
                if len(strided_sigs) > 1:
                    strided_separable += 1
    return {
        "flat_anagram_collisions": collisions,
        "strided_separable_buckets": strided_separable,
    }


def _diagnose_split_frame_collisions(bank: tuple[tuple[str, tuple], ...]) -> dict[str, Any]:
    """Detect whether global + strided counts collide while split-half projections separate labels."""
    collisions = 0
    split_separable = 0
    for tid, spec in bank:
        rows = sample_labeled(spec, 6, 12, 32, "diag_m2", tid, 1)
        by_global: dict[tuple[int, int, int, int], list[tuple[str, bool]]] = {}
        for w, y in rows:
            sig = (w.count("a") % 2, w.count("b") % 2, even_a(w) % 2, odd_b(w) % 2)
            by_global.setdefault(sig, []).append((w, y))
        for bucket in by_global.values():
            if len({y for _, y in bucket}) > 1:
                collisions += 1
                split_sigs = {
                    (split_halves(w)[0].count("a") % 2, split_halves(w)[1].count("b") % 2)
                    for w, _ in bucket
                }
                if len(split_sigs) > 1:
                    split_separable += 1
    return {
        "global_strided_collisions": collisions,
        "split_frame_separable_buckets": split_separable,
    }


def _stage_candidates_in_autonomy(
    autonomy: Autonomy,
    stage_label: str,
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Stage candidate meta-mechanisms in batches of <=4 via ``Autonomy`` (``STAGED_FOR_REVIEW``)."""
    staged_receipts: list[dict[str, Any]] = []
    for batch_idx in range(0, len(candidates), 4):
        chunk = candidates[batch_idx : batch_idx + 4]
        cand_specs = [
            {
                "rel_path": f"{stage_label}_{c['gen_tag']}.json",
                "content": json.dumps(c, sort_keys=True, indent=2) + "\n",
                "kind": "meta_mechanism_v1",
            }
            for c in chunk
        ]
        goal = {
            "schema": "ace.goal.v1",
            "name": f"stage_{stage_label}_batch_{batch_idx // 4}",
            "objective": {
                "kind": "stage_candidate_for_review",
                "inspect_paths": ["docs/ACE_G0_G2_PRESCORE_V1.md"],
                "candidates": cand_specs,
            },
            "policy": GoalPolicy(
                authorized_tools=("inspect_file", "stage_candidate"),
                read_prefixes=("docs", "code/ace_research_generations"),
                write_prefixes=("candidates/",),
                review_policy="stage-for-review",
            ).to_dict(),
            "budget": BudgetCeiling(
                max_steps=8,
                max_candidates=4,
                max_retries_per_step=0,
                wall_seconds=10.0,
                cpu_seconds=5.0,
            ).to_dict(),
        }
        gid = autonomy.enqueue(goal)
        autonomy.run_until_stopped(gid, max_iterations=12)
        rep = autonomy.report(gid)
        if rep["status"] != "STAGED_FOR_REVIEW":
            raise RuntimeError(f"expected STAGED_FOR_REVIEW, got {rep['status']}")
        staged_receipts.append({
            "goal_id": gid,
            "status": rep["status"],
            "staged_count": len(chunk),
        })
    return staged_receipts


def evolve_g0_to_g1(autonomy: Autonomy, memory: ExperienceMemory) -> dict[str, Any]:
    """Run G0 on M1_DEV, diagnose flat-counter bottleneck, stage 8 candidates, and promote G1."""
    g0_dev = _eval_meta_on_bank(G0_MECHANISM, M1_DEV)
    g0_val = _eval_meta_on_bank(G0_MECHANISM, M1_VAL)
    g0_base = _eval_meta_on_bank(G0_MECHANISM, BASE_SANITY, seeds=(1, 2))
    diag = _diagnose_anagram_collisions(M1_DEV)

    reflection = SelfReflection().reflect_and_record(
        goal={"name": "evaluate_G0_on_M1_DEV"},
        family_tag="generations_M1_strided",
        forecast=MetacognitiveForecast(
            p_success=0.75,
            uncertainty=0.18,
            expected_steps=6,
            expected_cpu_s=0.1,
            predicted_failure_mode="NONE",
            recommendation="EXECUTE",
            recalled_episodes=0,
            blockers=(),
        ),
        actual_success=g0_dev["mean_acc"] >= 0.80,
        actual_failure_mode="REPRESENTATION_GAP_STRIDED_PARITY",
        steps_used=len(M1_DEV),
        cpu_seconds=0.05,
        memory=memory,
    )

    candidates = [
        validate_meta_candidate({
            "schema": "ace.meta_mechanism.v1",
            "gen_tag": f"G1_c{idx}",
            "parent_gen": "G0",
            "enable_strided_features": strided,
            "stride_moduli": list(mods),
            "enable_split_frame_lifting": False,
            "enable_mdl_ranking": mdl,
            "enable_probe_agreement_gate": gate,
            "eval_budget_k": 256,
        })
        for idx, (strided, mods, mdl, gate) in enumerate(
            [
                (False, (2,), True, False),
                (False, (2,), False, True),
                (True, (2,), False, False),
                (True, (2,), True, False),
                (True, (2, 3), False, False),
                (True, (2, 3), False, True),
                (True, (2, 3, 4), False, False),
                (True, (3,), False, False),
            ],
            start=1,
        )
    ]

    staged = _stage_candidates_in_autonomy(autonomy, "g0_to_g1", candidates)

    scored: list[dict[str, Any]] = []
    for cand in candidates:
        c_val = _eval_meta_on_bank(cand, M1_VAL)
        c_base = _eval_meta_on_bank(cand, BASE_SANITY, seeds=(1, 2))
        gain = round(c_val["mean_acc"] - g0_val["mean_acc"], 6)
        base_reg = round(max(0.0, g0_base["mean_acc"] - c_base["mean_acc"]), 6)
        eligible = (
            gain >= PROMOTION_POLICY["min_meta_val_gain"]
            and base_reg <= PROMOTION_POLICY["max_prior_regression"]
        )
        scored.append({
            "candidate": cand,
            "m1_val_acc": c_val["mean_acc"],
            "m1_val_gain": gain,
            "base_sanity_acc": c_base["mean_acc"],
            "base_regression": base_reg,
            "feature_count": c_val["feature_count"],
            "eligible": eligible,
        })

    eligible_pool = [s for s in scored if s["eligible"]]
    if not eligible_pool:
        raise RuntimeError("G0 -> G1 failed promotion gate on M1_VAL")
    # Select highest M1_VAL accuracy, tie-breaking by smallest feature vocabulary & earliest tag
    eligible_pool.sort(
        key=lambda s: (-s["m1_val_acc"], s["feature_count"], s["candidate"]["gen_tag"])
    )
    winner = dict(eligible_pool[0]["candidate"])
    winner["gen_tag"] = "G1"
    validate_meta_candidate(winner)

    return {
        "parent": G0_MECHANISM,
        "promoted": winner,
        "g0_m1_dev": g0_dev,
        "g0_m1_val": g0_val,
        "diagnostic": diag,
        "reflection": reflection,
        "autonomy_staging": staged,
        "candidate_evaluations": scored,
    }


def evolve_g1_to_g2(
    g1_meta: dict[str, Any],
    autonomy: Autonomy,
    memory: ExperienceMemory,
) -> dict[str, Any]:
    """Start strictly from G1, diagnose split-frame failures on M2_DEV, stage 8 candidates, promote G2."""
    validate_meta_candidate(g1_meta)
    g1_m2_dev = _eval_meta_on_bank(g1_meta, M2_DEV)
    g1_m2_val = _eval_meta_on_bank(g1_meta, M2_VAL)
    g1_m1_val = _eval_meta_on_bank(g1_meta, M1_VAL)
    diag = _diagnose_split_frame_collisions(M2_DEV)

    reflection = SelfReflection().reflect_and_record(
        goal={"name": "evaluate_G1_on_M2_DEV"},
        family_tag="generations_M2_split_frame",
        forecast=MetacognitiveForecast(
            p_success=0.72,
            uncertainty=0.19,
            expected_steps=6,
            expected_cpu_s=0.1,
            predicted_failure_mode="NONE",
            recommendation="EXECUTE",
            recalled_episodes=0,
            blockers=(),
        ),
        actual_success=g1_m2_dev["mean_acc"] >= 0.80,
        actual_failure_mode="REPRESENTATION_GAP_SPLIT_FRAME_AND_AMBIGUITY",
        steps_used=len(M2_DEV),
        cpu_seconds=0.06,
        memory=memory,
    )

    inh_strided = g1_meta["enable_strided_features"]
    inh_moduli = list(g1_meta["stride_moduli"])

    candidates = [
        validate_meta_candidate({
            "schema": "ace.meta_mechanism.v1",
            "gen_tag": f"G2_c{idx}",
            "parent_gen": "G1",
            "enable_strided_features": keep_strided,
            "stride_moduli": inh_moduli if keep_strided else [2],
            "enable_split_frame_lifting": split_lift,
            "enable_mdl_ranking": mdl,
            "enable_probe_agreement_gate": gate,
            "eval_budget_k": 256,
        })
        for idx, (keep_strided, split_lift, mdl, gate) in enumerate(
            [
                (inh_strided, False, True, False),
                (inh_strided, False, True, True),
                (False, True, False, False),  # forgets G1 strided inheritance -> fails M1_VAL regression!
                (False, True, True, True),     # forgets G1 strided inheritance -> fails M1_VAL regression!
                (inh_strided, True, False, False),
                (inh_strided, True, True, False),
                (inh_strided, True, False, True),
                (inh_strided, True, True, True),
            ],
            start=1,
        )
    ]

    staged = _stage_candidates_in_autonomy(autonomy, "g1_to_g2", candidates)

    ood_sanity = (("ood_sanity_eq", ("exact_eq_ab",)),)
    scored: list[dict[str, Any]] = []
    for cand in candidates:
        c_m2_val = _eval_meta_on_bank(cand, M2_VAL)
        c_m1_val = _eval_meta_on_bank(cand, M1_VAL)
        c_ood = _eval_meta_on_bank(cand, ood_sanity, seeds=(1, 2, 3))
        gain = round(c_m2_val["mean_acc"] - g1_m2_val["mean_acc"], 6)
        m1_reg = round(max(0.0, g1_m1_val["mean_acc"] - c_m1_val["mean_acc"]), 6)
        eligible = (
            gain >= PROMOTION_POLICY["min_meta_val_gain"]
            and m1_reg <= PROMOTION_POLICY["max_prior_regression"]
        )
        scored.append({
            "candidate": cand,
            "m2_val_acc": c_m2_val["mean_acc"],
            "m2_val_gain": gain,
            "m1_val_acc": c_m1_val["mean_acc"],
            "m1_regression": m1_reg,
            "ood_false_admit_rate": c_ood["admitted_rate"],
            "feature_count": c_m2_val["feature_count"],
            "eligible": eligible,
        })

    eligible_pool = [s for s in scored if s["eligible"]]
    if not eligible_pool:
        raise RuntimeError("G1 -> G2 failed promotion gate on M2_VAL / M1_VAL non-regression")
    # Maximize M2_VAL + M1_VAL accuracy, minimize OOD false-admission rate, prefer MDL + probe gating
    eligible_pool.sort(
        key=lambda s: (
            -round(s["m2_val_acc"] + s["m1_val_acc"], 4),
            s["ood_false_admit_rate"],
            not s["candidate"]["enable_mdl_ranking"],
            not s["candidate"]["enable_probe_agreement_gate"],
            s["candidate"]["gen_tag"],
        )
    )
    winner = dict(eligible_pool[0]["candidate"])
    winner["gen_tag"] = "G2"
    validate_meta_candidate(winner)

    return {
        "parent": g1_meta,
        "promoted": winner,
        "g1_m2_dev": g1_m2_dev,
        "g1_m2_val": g1_m2_val,
        "g1_m1_val": g1_m1_val,
        "diagnostic": diag,
        "reflection": reflection,
        "autonomy_staging": staged,
        "candidate_evaluations": scored,
    }


def evolve_random_mutation(seed: int) -> dict[str, Any]:
    """B_random_mut: Unguided 2-step random meta-mutation from G0 without diagnostic selection."""
    cur = dict(G0_MECHANISM)
    cur["stride_moduli"] = list(G0_MECHANISM["stride_moduli"])
    mutable_ops = (
        "flip_strided",
        "cycle_moduli",
        "flip_split_frame",
        "flip_mdl",
        "flip_probe_gate",
    )
    for step in (1, 2):
        dig = hashlib.sha256(f"b_random_mut|{seed}|{step}".encode("utf-8")).digest()
        op = mutable_ops[dig[0] % len(mutable_ops)]
        if op == "flip_strided":
            cur["enable_strided_features"] = not cur["enable_strided_features"]
        elif op == "cycle_moduli":
            options = ([2], [3], [2, 3], [2, 4])
            cur["stride_moduli"] = list(options[dig[1] % len(options)])
        elif op == "flip_split_frame":
            cur["enable_split_frame_lifting"] = not cur["enable_split_frame_lifting"]
        elif op == "flip_mdl":
            cur["enable_mdl_ranking"] = not cur["enable_mdl_ranking"]
        elif op == "flip_probe_gate":
            cur["enable_probe_agreement_gate"] = not cur["enable_probe_agreement_gate"]
        cur["parent_gen"] = "G0" if step == 1 else f"B_rand_step1_s{seed}"
        cur["gen_tag"] = f"B_rand_s{seed}"
    return validate_meta_candidate(cur)
