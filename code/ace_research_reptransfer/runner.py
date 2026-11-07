"""Canonical R9 experiment runner.

Outputs deterministic JSON report: pre-registered gates, per-unit metrics,
compute accounting, and summary tables.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .tasks import TARGETS, DRIFT, TARGET_BY_ID
from .sampling import labeled_sample
from .evaluator import terminal_bank, independent_truth
from .arms import ARMS, get_dictionaries

BUDGETS = (16, 32, 64)
SEEDS = (1, 2, 3, 4, 5)
PRIMARY_BUDGET = 32


def digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode("utf-8")).hexdigest()


def evaluate_candidate(cand, terminal_data):
    if cand is None:
        return {
            "admitted": False,
            "terminal_correct": 0,
            "terminal_accuracy": 0.0,
            "symbols_eval": 0,
            "predictions_sha256": None,
        }
    preds = [cand.predict(w) for w, _ in terminal_data]
    corr = sum(p == label for p, (_, label) in zip(preds, terminal_data))
    syms = sum(cand.cost_fn(w) for w, _ in terminal_data)
    return {
        "admitted": True,
        "candidate_name": cand.name,
        "terminal_correct": corr,
        "terminal_accuracy": round(corr / len(terminal_data), 6),
        "symbols_eval": syms,
        "predictions_sha256": digest(preds),
    }


def run_experiment() -> dict:
    dicts = get_dictionaries()
    source_stats = {
        "A_features": len(dicts["A"][0]),
        "A_merges": dicts["A"][1],
        "A0_features": len(dicts["A0"][0]),
        "A0_merges": dicts["A0"][1],
        "C_features": len(dicts["C"]),
        "C2_features": len(dicts["C2"]),
    }

    units = []

    # 1. Nominal units: 11 tasks * 5 seeds * 3 budgets = 165 units
    for task_id, stratum, spec in TARGETS:
        for seed in SEEDS:
            for budget in BUDGETS:
                train = labeled_sample(spec, 0, 5, budget // 2, "train", task_id, seed, budget)
                val = labeled_sample(spec, 6, 12, budget // 2, "val", task_id, seed, budget)
                terminal = terminal_bank(task_id, seed)

                unit = {
                    "kind": "nominal",
                    "task_id": task_id,
                    "stratum": stratum,
                    "seed": seed,
                    "budget": budget,
                    "train_sha256": digest(train),
                    "val_sha256": digest(val),
                    "terminal_sha256": digest(terminal),
                    "arms": {},
                }
                for arm_name in ("A", "A0", "B", "C", "C2", "D0"):
                    cand, fit_stats = ARMS[arm_name](train, val)
                    eval_stats = evaluate_candidate(cand, terminal)
                    unit["arms"][arm_name] = {
                        "fit": fit_stats,
                        "evaluation": eval_stats,
                    }
                units.append(unit)

    # 2. Drift controls: 2 controls * 5 seeds * 3 budgets = 30 units
    for drift_id, nominal_task_id in DRIFT:
        _, spec = TARGET_BY_ID[nominal_task_id]
        for seed in SEEDS:
            for budget in BUDGETS:
                train = labeled_sample(spec, 0, 5, budget // 2, "train", nominal_task_id, seed, budget)
                val = labeled_sample(spec, 6, 12, budget // 2, "val", nominal_task_id, seed, budget)
                nominal_terminal = terminal_bank(nominal_task_id, seed)
                # Complemented terminal truth
                inverted_terminal = [(w, not label) for w, label in nominal_terminal]

                unit = {
                    "kind": "drift",
                    "drift_id": drift_id,
                    "nominal_task_id": nominal_task_id,
                    "seed": seed,
                    "budget": budget,
                    "train_sha256": digest(train),
                    "val_sha256": digest(val),
                    "terminal_sha256": digest(inverted_terminal),
                    "arms": {},
                }
                for arm_name in ("A", "A0", "B", "C", "C2", "D0"):
                    cand, fit_stats = ARMS[arm_name](train, val)
                    eval_stats = evaluate_candidate(cand, inverted_terminal)
                    unit["arms"][arm_name] = {
                        "fit": fit_stats,
                        "evaluation": eval_stats,
                    }
                units.append(unit)

    report = {
        "schema": "ace.r9.gemini.v1",
        "scientific_decision": "NOT_ASSESSED",
        "release_gate": "BLOCK_RELEASE",
        "oaie_established": False,
        "candidate_deployed": False,
        "source_pretraining": source_stats,
        "units": units,
    }
    # Compute aggregations and evaluate hypotheses.
    report["analysis"] = analyze_report(report)
    return report


def analyze_report(report: dict) -> dict:
    nominals = [u for u in report["units"] if u["kind"] == "nominal"]
    drifts = [u for u in report["units"] if u["kind"] == "drift"]

    def m_score(unit, arm):
        ev = unit["arms"][arm]["evaluation"]
        return ev["terminal_accuracy"] if ev["admitted"] else 0.0

    def admitted(unit, arm):
        return unit["arms"][arm]["evaluation"]["admitted"]

    # Slice summaries by (stratum, budget)
    strata = ("U", "L", "N")
    arm_names = ("A", "A0", "B", "C", "C2", "D0")
    by_slice = {}
    for st in strata:
        for b in BUDGETS:
            subset = [u for u in nominals if u["stratum"] == st and u["budget"] == b]
            key = f"{st}_b{b}"
            by_slice[key] = {
                "n_units": len(subset),
                "means": {arm: round(sum(m_score(u, arm) for u in subset) / len(subset), 4) for arm in arm_names},
                "coverage": {arm: round(sum(admitted(u, arm) for u in subset) / len(subset), 4) for arm in arm_names},
            }

    # Primary budget B=32 checks
    u_b32 = [u for u in nominals if u["stratum"] == "U" and u["budget"] == PRIMARY_BUDGET]
    l_b32 = [u for u in nominals if u["stratum"] == "L" and u["budget"] == PRIMARY_BUDGET]
    n_b32 = [u for u in nominals if u["stratum"] == "N" and u["budget"] == PRIMARY_BUDGET]

    mean_A_U = sum(m_score(u, "A") for u in u_b32) / len(u_b32)
    mean_A0_U = sum(m_score(u, "A0") for u in u_b32) / len(u_b32)
    mean_B_U = sum(m_score(u, "B") for u in u_b32) / len(u_b32)
    mean_C_U = sum(m_score(u, "C") for u in u_b32) / len(u_b32)
    mean_C2_U = sum(m_score(u, "C2") for u in u_b32) / len(u_b32)
    best_control_U = max(mean_B_U, mean_C_U)

    # Per-task means for H1 (over seeds at B=32)
    u_tasks = sorted({u["task_id"] for u in u_b32})
    task_gains = []
    for tid in u_tasks:
        tu = [u for u in u_b32 if u["task_id"] == tid]
        mA = sum(m_score(u, "A") for u in tu) / len(tu)
        mB = sum(m_score(u, "B") for u in tu) / len(tu)
        mC = sum(m_score(u, "C") for u in tu) / len(tu)
        task_gains.append((tid, mA, max(mB, mC), mA - max(mB, mC)))
    tasks_beating = sum(gain >= 0.05 for _, _, _, gain in task_gains)

    # H1
    h1 = (mean_A_U - best_control_U >= 0.15) and (tasks_beating >= 4)
    # H2
    h2 = (mean_A_U - mean_A0_U >= 0.15)
    # H3
    mean_A_L = sum(m_score(u, "A") for u in l_b32) / len(l_b32)
    mean_C_L = sum(m_score(u, "C") for u in l_b32) / len(l_b32)
    h3 = (mean_A_L >= mean_C_L - 0.05)
    # H4 sample efficiency curve (U)
    b_at_80_A = min((b for b in BUDGETS if by_slice[f"U_b{b}"]["means"]["A"] >= 0.80), default=None)
    b_at_80_B = min((b for b in BUDGETS if by_slice[f"U_b{b}"]["means"]["B"] >= 0.80), default=None)
    h4 = (b_at_80_A is not None) and (b_at_80_B is None or b_at_80_A <= b_at_80_B // 2)
    # H5 admission safety (N) - false admissions on N
    false_adm_N = {
        arm: sum(admitted(u, arm) and (u["arms"][arm]["evaluation"]["terminal_accuracy"] < 0.90) for u in n_b32)
        for arm in arm_names
    }
    h5 = false_adm_N["A"] <= max(false_adm_N["B"], false_adm_N["C"])
    # H6 drift false-accepts: admitted with acc < 0.10
    drift_b32 = [u for u in drifts if u["budget"] == PRIMARY_BUDGET]
    drift_false_accepts = {
        arm: sum(admitted(u, arm) and (u["arms"][arm]["evaluation"]["terminal_accuracy"] < 0.10) for u in drift_b32)
        for arm in arm_names
    }
    h6_pass = drift_false_accepts["A"] == 0  # Expected False: semantic drift fails
    # H7 feature recovery (U): A reaches within 0.10 of C2
    h7 = (mean_A_U >= mean_C2_U - 0.10)

    gate_G = h1 and h2 and h3 and h5 and h7

    return {
        "slices": by_slice,
        "primary_b32": {
            "U_means": {
                "A": round(mean_A_U, 4),
                "A0": round(mean_A0_U, 4),
                "B": round(mean_B_U, 4),
                "C": round(mean_C_U, 4),
                "C2": round(mean_C2_U, 4),
                "best_baseline": round(best_control_U, 4),
                "gain_vs_baseline": round(mean_A_U - best_control_U, 4),
            },
            "U_task_gains": [
                {"task": tid, "A": round(a, 4), "baseline": round(b, 4), "gain": round(g, 4)}
                for tid, a, b, g in task_gains
            ],
            "L_means": {
                "A": round(mean_A_L, 4),
                "C": round(mean_C_L, 4),
                "diff": round(mean_A_L - mean_C_L, 4),
            },
            "N_false_admissions": false_adm_N,
            "drift_false_accepts": drift_false_accepts,
        },
        "hypotheses": {
            "H1_transfer_U": bool(h1),
            "H2_source_causality_U": bool(h2),
            "H3_no_regression_L": bool(h3),
            "H4_sample_efficiency_U": bool(h4),
            "H5_admission_safety_N": bool(h5),
            "H6_drift_safe": bool(h6_pass),
            "H7_feature_recovery_U": bool(h7),
        },
        "gate_G_pass": bool(gate_G),
        "open_world_safe": bool(h6_pass),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = run_experiment()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.output.write_text(payload, encoding="utf-8")
    print(json.dumps({
        "schema": report["schema"],
        "gate_G_pass": report["analysis"]["gate_G_pass"],
        "H1": report["analysis"]["hypotheses"]["H1_transfer_U"],
        "H2": report["analysis"]["hypotheses"]["H2_source_causality_U"],
        "H3": report["analysis"]["hypotheses"]["H3_no_regression_L"],
        "H6_open_world_safe": report["analysis"]["hypotheses"]["H6_drift_safe"],
        "primary_U_means": report["analysis"]["primary_b32"]["U_means"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
