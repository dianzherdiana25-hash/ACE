"""ACE P4: Cross-Generation Capability Growth Benchmark (G0 -> G1 -> G2 Continuation).

Evaluates whether promoted recursive mechanism G2 retains structural inductive
bias superiority on a novel, held-out task distribution (U_growth) against:
- G0 (base generation)
- G1 (strided generation)
- B_extra_compute (G0 with 4x search compute budget, K=1024)
- B_fixed (100-predicate fixed baseline)
- B_random_mut (randomly mutated mechanism)
- B_fresh (un-evolved learner)
- Semantic drift controls (DG1, DG2)
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import tempfile
from typing import Any

from ace_autonomy import Autonomy
from ace_selfmodel import ExperienceMemory

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
    ALPHABET,
    PRIMARY_BUDGET,
    SEEDS,
    block2_aa,
    even_a,
    odd_b,
    split_halves,
    unlabeled_probes,
    words_of_len,
)

GROWTH_ARMS = (
    "G0",
    "G1",
    "G2",
    "B_fixed",
    "B_random_mut",
    "B_extra_compute",
    "B_fresh",
)

GROWTH_TARGETS = (
    # U_growth (6 novel cross-relational tasks disjoint from M1, M2, and U_gen)
    ("UG1", "U_growth", ("and", ("half_even_a_eq_mod", 2), ("ends", "b"))),
    ("UG2", "U_growth", ("or", ("half_odd_b_neq_mod", 2), ("starts", "aa"))),
    ("UG3", "U_growth", ("half_block2_aa_eq_mod", 2)),
    ("UG4", "U_growth", ("and", ("half_a_eq_mod", 3), ("even_a_mod", 2, 0))),
    ("UG5", "U_growth", ("and", ("half_even_a_eq_mod", 2), ("right_b_mod", 2, 1))),
    ("UG6", "U_growth", ("xor", ("half_odd_b_neq_mod", 2), ("left_a_mod", 2, 0))),
)

GROWTH_DRIFT_CONTROLS = (
    ("DG1_UG1_inv", "UG1"),
    ("DG2_UG3_inv", "UG3"),
)

TERMINAL_PER_CLASS = 64
TERMINAL_MIN_LEN = 16
TERMINAL_MAX_LEN = 28
MAX_DRAWS = 300_000


def eval_growth_spec(spec: tuple, w: str) -> bool:
    kind = spec[0]
    if kind == "half_even_a_eq_mod":
        left, right = split_halves(w)
        return (even_a(left) % spec[1]) == (even_a(right) % spec[1])
    if kind == "half_odd_b_neq_mod":
        left, right = split_halves(w)
        return (odd_b(left) % spec[1]) != (odd_b(right) % spec[1])
    if kind == "half_block2_aa_eq_mod":
        left, right = split_halves(w)
        return (block2_aa(left) % spec[1]) == (block2_aa(right) % spec[1])
    if kind == "half_a_eq_mod":
        left, right = split_halves(w)
        return (left.count("a") % spec[1]) == (right.count("a") % spec[1])
    if kind == "even_a_mod":
        return even_a(w) % spec[1] == spec[2]
    if kind == "left_a_mod":
        left, _ = split_halves(w)
        return left.count("a") % spec[1] == spec[2]
    if kind == "right_b_mod":
        _, right = split_halves(w)
        return right.count("b") % spec[1] == spec[2]
    if kind == "ends":
        return w.endswith(spec[1])
    if kind == "starts":
        return w.startswith(spec[1])
    if kind == "and":
        return eval_growth_spec(spec[1], w) and eval_growth_spec(spec[2], w)
    if kind == "or":
        return eval_growth_spec(spec[1], w) or eval_growth_spec(spec[2], w)
    if kind == "xor":
        return eval_growth_spec(spec[1], w) != eval_growth_spec(spec[2], w)
    raise ValueError(f"unknown growth spec kind: {kind}")


def _indep_eval_growth(spec: tuple, w: str) -> bool:
    """Independent implementation for AST evaluator isolation."""
    k = spec[0]
    h = len(w) // 2
    if k == "half_even_a_eq_mod":
        return (w[:h][0::2].count("a") % spec[1]) == (w[h:][0::2].count("a") % spec[1])
    if k == "half_odd_b_neq_mod":
        return (w[:h][1::2].count("b") % spec[1]) != (w[h:][1::2].count("b") % spec[1])
    if k == "half_block2_aa_eq_mod":
        l_cnt = sum(1 for idx in range(0, len(w[:h]) - 1, 2) if w[:h][idx : idx + 2] == "aa")
        r_cnt = sum(1 for idx in range(0, len(w[h:]) - 1, 2) if w[h:][idx : idx + 2] == "aa")
        return (l_cnt % spec[1]) == (r_cnt % spec[1])
    if k == "half_a_eq_mod":
        return (w[:h].count("a") % spec[1]) == (w[h:].count("a") % spec[1])
    if k == "even_a_mod":
        return w[0::2].count("a") % spec[1] == spec[2]
    if k == "left_a_mod":
        return w[:h].count("a") % spec[1] == spec[2]
    if k == "right_b_mod":
        return w[h:].count("b") % spec[1] == spec[2]
    if k == "ends":
        suf = spec[1]
        return len(w) >= len(suf) and w[len(w) - len(suf) :] == suf
    if k == "starts":
        pre = spec[1]
        return w[: len(pre)] == pre
    if k == "and":
        return _indep_eval_growth(spec[1], w) and _indep_eval_growth(spec[2], w)
    if k == "or":
        return _indep_eval_growth(spec[1], w) or _indep_eval_growth(spec[2], w)
    if k == "xor":
        return _indep_eval_growth(spec[1], w) ^ _indep_eval_growth(spec[2], w)
    raise ValueError(f"unknown independent spec: {k}")


def _rank_key(*parts: object) -> str:
    return hashlib.sha256("|".join(str(x) for x in parts).encode("utf-8")).hexdigest()


@lru_cache(maxsize=None)
def _partition_growth(spec: tuple, lo: int, hi: int) -> tuple[list[str], list[str]]:
    univ = [w for n in range(lo, hi + 1) for w in words_of_len(n)]
    pos = [w for w in univ if eval_growth_spec(spec, w)]
    neg = [w for w in univ if not eval_growth_spec(spec, w)]
    return pos, neg


def sample_growth_labeled(
    spec: tuple,
    lo: int,
    hi: int,
    n: int,
    role: str,
    task_id: str,
    seed: int,
) -> list[tuple[str, bool]]:
    pos, neg = _partition_growth(spec, lo, hi)
    pos_s = sorted(pos, key=lambda w: _rank_key(role, task_id, seed, w))
    neg_s = sorted(neg, key=lambda w: _rank_key(role, task_id, seed, w))
    take_p = min(n // 2, len(pos_s))
    take_n = min(n - take_p, len(neg_s))
    take_p = min(n - take_n, len(pos_s))
    chosen = pos_s[:take_p] + neg_s[:take_n]
    return [(w, eval_growth_spec(spec, w)) for w in sorted(chosen, key=lambda w: (len(w), w))]


@lru_cache(maxsize=None)
def growth_terminal_bank(task_id: str, spec: tuple, seed: int) -> list[tuple[str, bool]]:
    pos: list[tuple[str, bool]] = []
    neg: list[tuple[str, bool]] = []
    seen: set[str] = set()
    span = TERMINAL_MAX_LEN - TERMINAL_MIN_LEN + 1

    for draw in range(MAX_DRAWS):
        if len(pos) >= TERMINAL_PER_CLASS and len(neg) >= TERMINAL_PER_CLASS:
            break
        dig = hashlib.sha256(f"growth_term|{task_id}|{seed}|{draw}".encode("utf-8")).digest()
        ln = TERMINAL_MIN_LEN + (dig[0] % span)
        bits = int.from_bytes(dig[1:9], "big")
        w = "".join(ALPHABET[(bits >> j) & 1] for j in range(ln))
        if w in seen:
            continue
        lbl = _indep_eval_growth(spec, w)
        if lbl and len(pos) < TERMINAL_PER_CLASS:
            seen.add(w)
            pos.append((w, True))
        elif (not lbl) and len(neg) < TERMINAL_PER_CLASS:
            seen.add(w)
            neg.append((w, False))

    if len(pos) < TERMINAL_PER_CLASS or len(neg) < TERMINAL_PER_CLASS:
        raise RuntimeError(f"failed to draw balanced terminal set for {task_id}")
    out = pos + neg
    out.sort(key=lambda item: _rank_key("term_order", task_id, seed, item[0]))
    return out


def _score_prog(prog: Any, term: list[tuple[str, bool]]) -> float:
    if prog is None:
        return 0.5
    return sum(1 for w, y in term if prog.predict(w) == y) / len(term)


def run_generations_growth_benchmark(repo_root: Path | None = None) -> dict[str, Any]:
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    guard = ImmutableCoreGuard(root)
    ast_iso = verify_ast_evaluator_isolation()
    if not ast_iso["isolated"]:
        raise RuntimeError(f"AST isolation violated: {ast_iso['violations']}")

    # Phase 1: Real Autonomy & ExperienceMemory lineage execution
    with tempfile.TemporaryDirectory(prefix="ace_growth_gen_") as tmp:
        ws = Path(tmp) / "autonomy_ws"
        mem_ws = Path(tmp) / "selfmodel_ws"
        with Autonomy(ws, root) as autonomy, ExperienceMemory(mem_ws) as memory:
            ace_seed = seed_ace_runtime_lineage_anchors(autonomy)
            guard.verify_intact()

            g0_to_g1 = evolve_g0_to_g1(autonomy, memory)
            guard.verify_intact()
            g1_meta = g0_to_g1["promoted"]

            g1_to_g2 = evolve_g1_to_g2(g1_meta, autonomy, memory)
            guard.verify_intact()
            g2_meta = g1_to_g2["promoted"]

            auto_status = autonomy.status()
            memory.verify()

    feats_g0 = build_features_for_mechanism(G0_MECHANISM)
    feats_g1 = build_features_for_mechanism(g1_meta)
    feats_g2 = build_features_for_mechanism(g2_meta)
    feats_fixed = build_strong_fixed_library()
    rand_metas = {s: evolve_random_mutation(s) for s in SEEDS}
    feats_rand = {s: build_features_for_mechanism(rand_metas[s]) for s in SEEDS}

    n_tr = PRIMARY_BUDGET // 2
    n_va = PRIMARY_BUDGET - n_tr

    unit_records: list[dict[str, Any]] = []

    # 1. Evaluate on U_growth tasks (6 tasks x 5 seeds = 30 units)
    for tid, stratum, spec in GROWTH_TARGETS:
        for seed in SEEDS:
            tr = sample_growth_labeled(spec, 0, 6, n_tr, "growth_tr", tid, seed)
            va = sample_growth_labeled(spec, 7, 13, n_va, "growth_va", tid, seed)
            probes = unlabeled_probes(seed + 700)
            term = growth_terminal_bank(tid, spec, seed)

            for w, y in term:
                if eval_growth_spec(spec, w) != y:
                    raise RuntimeError(f"truth mismatch on {tid}")

            arm_out: dict[str, Any] = {}
            for arm in GROWTH_ARMS:
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
                    prog, diag = fit_with_mechanism(
                        feats_rand[seed],
                        tr,
                        va,
                        eval_budget_k=rand_metas[seed]["eval_budget_k"],
                        enable_mdl_ranking=rand_metas[seed]["enable_mdl_ranking"],
                        enable_probe_agreement_gate=rand_metas[seed]["enable_probe_agreement_gate"],
                        probes=probes,
                    )
                elif arm == "G0":
                    prog, diag = fit_with_mechanism(
                        feats_g0,
                        tr,
                        va,
                        eval_budget_k=G0_MECHANISM["eval_budget_k"],
                        enable_mdl_ranking=G0_MECHANISM["enable_mdl_ranking"],
                        enable_probe_agreement_gate=G0_MECHANISM["enable_probe_agreement_gate"],
                        probes=probes,
                    )
                elif arm == "G1":
                    prog, diag = fit_with_mechanism(
                        feats_g1,
                        tr,
                        va,
                        eval_budget_k=g1_meta["eval_budget_k"],
                        enable_mdl_ranking=g1_meta["enable_mdl_ranking"],
                        enable_probe_agreement_gate=g1_meta["enable_probe_agreement_gate"],
                        probes=probes,
                    )
                elif arm == "G2":
                    prog, diag = fit_with_mechanism(
                        feats_g2,
                        tr,
                        va,
                        eval_budget_k=g2_meta["eval_budget_k"],
                        enable_mdl_ranking=g2_meta["enable_mdl_ranking"],
                        enable_probe_agreement_gate=g2_meta["enable_probe_agreement_gate"],
                        probes=probes,
                    )
                else:
                    raise ValueError(f"unknown arm {arm}")

                acc = _score_prog(prog, term)
                arm_out[arm] = {
                    "terminal_acc": round(acc, 4),
                    "solved": acc >= 0.95,
                    "evals_used": int(diag.get("evals_used", 0)),
                    "admitted": bool(diag.get("admitted", False)),
                }

            unit_records.append({
                "unit_id": f"{tid}_s{seed}",
                "task_id": tid,
                "stratum": stratum,
                "seed": seed,
                "arm_scores": arm_out,
            })

    # 2. Evaluate Semantic Drift Controls (2 tasks x 5 seeds = 10 units)
    growth_dict = {tid: spec for tid, _, spec in GROWTH_TARGETS}
    for dtid, base_id in GROWTH_DRIFT_CONTROLS:
        spec = growth_dict[base_id]
        for seed in SEEDS:
            tr = sample_growth_labeled(spec, 0, 6, n_tr, "growth_drift_tr", dtid, seed)
            va = sample_growth_labeled(spec, 7, 13, n_va, "growth_drift_va", dtid, seed)
            probes = unlabeled_probes(seed + 800)
            # Inverted terminal bank:
            term = [(w, not y) for w, y in growth_terminal_bank(base_id, spec, seed)]

            arm_out = {}
            for arm in GROWTH_ARMS:
                if arm == "G0":
                    prog, diag = fit_with_mechanism(
                        feats_g0, tr, va,
                        eval_budget_k=G0_MECHANISM["eval_budget_k"],
                        enable_mdl_ranking=G0_MECHANISM["enable_mdl_ranking"],
                        enable_probe_agreement_gate=G0_MECHANISM["enable_probe_agreement_gate"],
                        probes=probes,
                    )
                elif arm == "G1":
                    prog, diag = fit_with_mechanism(
                        feats_g1, tr, va,
                        eval_budget_k=g1_meta["eval_budget_k"],
                        enable_mdl_ranking=g1_meta["enable_mdl_ranking"],
                        enable_probe_agreement_gate=g1_meta["enable_probe_agreement_gate"],
                        probes=probes,
                    )
                elif arm == "G2":
                    prog, diag = fit_with_mechanism(
                        feats_g2, tr, va,
                        eval_budget_k=g2_meta["eval_budget_k"],
                        enable_mdl_ranking=g2_meta["enable_mdl_ranking"],
                        enable_probe_agreement_gate=g2_meta["enable_probe_agreement_gate"],
                        probes=probes,
                    )
                else:
                    prog = None
                    diag = {"evals_used": 0, "val_acc": 0.5}

                acc = _score_prog(prog, term)
                arm_out[arm] = {
                    "terminal_acc": round(acc, 4),
                    "solved": acc >= 0.95,
                    "evals_used": int(diag.get("evals_used", 0)),
                    "admitted": bool(diag.get("admitted", False)),
                }

            unit_records.append({
                "unit_id": f"{dtid}_s{seed}",
                "task_id": dtid,
                "stratum": "D_drift",
                "seed": seed,
                "arm_scores": arm_out,
            })

    # Summary by stratum
    strata = ("U_growth", "D_drift")
    summary: dict[str, dict[str, Any]] = {s: {} for s in strata}
    for s in strata:
        sub = [u for u in unit_records if u["stratum"] == s]
        for arm in GROWTH_ARMS:
            if not sub:
                continue
            accs = [u["arm_scores"][arm]["terminal_acc"] for u in sub if arm in u["arm_scores"]]
            if not accs:
                continue
            solved_cnt = sum(1 for u in sub if u["arm_scores"].get(arm, {}).get("solved", False))
            summary[s][arm] = {
                "mean_acc": round(sum(accs) / len(accs), 4),
                "solve_rate": round(solved_cnt / len(accs), 4),
                "n_units": len(accs),
            }

    u_means = summary["U_growth"]
    d_means = summary["D_drift"]

    h1_pass = (
        u_means["G2"]["mean_acc"] >= 0.80
        and (u_means["G2"]["mean_acc"] - u_means["G0"]["mean_acc"]) >= 0.20
        and (u_means["G2"]["mean_acc"] - u_means["G1"]["mean_acc"]) >= 0.10
    )
    h2_pass = (u_means["G2"]["mean_acc"] - u_means["B_extra_compute"]["mean_acc"]) >= 0.15
    h3_pass = d_means["G2"]["mean_acc"] <= 0.10 and d_means["G0"]["mean_acc"] <= 0.50
    h4_pass = ast_iso["isolated"]

    all_gates = h1_pass and h2_pass and h3_pass and h4_pass

    return {
        "schema": "ace.generations.growth.v1",
        "scientific_status": "NOT_ASSESSED",
        "release_status": "BLOCK_RELEASE",
        "oaie_established": False,
        "evidence_flags": {
            "ACE_BASE_RUNTIME_EXECUTED": True,
            "NEW_CAPABILITY_INTEGRATED_AND_EXECUTED": True,
            "SCIENTIFIC_CAPABILITY_VALIDATED": False,
            "PASSIVE_SEMANTIC_DRIFT_DETECTABLE": False,
        },
        "hypotheses": {
            "H1_growth_advantage": {
                "passed": h1_pass,
                "g2_mean_acc": u_means["G2"]["mean_acc"],
                "g0_mean_acc": u_means["G0"]["mean_acc"],
                "g1_mean_acc": u_means["G1"]["mean_acc"],
                "delta_g2_minus_g0": round(u_means["G2"]["mean_acc"] - u_means["G0"]["mean_acc"], 4),
                "threshold": 0.20,
            },
            "H2_compute_amortization": {
                "passed": h2_pass,
                "g2_mean_acc": u_means["G2"]["mean_acc"],
                "b_extra_compute_acc": u_means["B_extra_compute"]["mean_acc"],
                "delta": round(u_means["G2"]["mean_acc"] - u_means["B_extra_compute"]["mean_acc"], 4),
                "threshold": 0.15,
            },
            "H3_semantic_drift_unobservability": {
                "passed": h3_pass,
                "g2_drift_acc": d_means["G2"]["mean_acc"],
                "g0_drift_acc": d_means["G0"]["mean_acc"],
                "threshold_max": 0.10,
            },
            "H4_lineage_and_immutability": {
                "passed": h4_pass,
                "ast_isolated": ast_iso["isolated"],
            },
            "all_gates_pass": all_gates,
        },
        "summary_by_stratum": summary,
        "unit_records": unit_records,
    }


def write_growth_evidence_gz(report: dict[str, Any], out_path: Path) -> str:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(report, sort_keys=True, indent=2) + "\n").encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    with out_path.open("wb") as fh, gzip.GzipFile(filename="", mode="wb", fileobj=fh, mtime=0) as gz:
        gz.write(raw)
    return sha


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ACE P4 generations growth benchmark.")
    parser.add_argument(
        "--out",
        default="evidence/generations/ace_generations_growth_v1.json.gz",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    rep = run_generations_growth_benchmark(root)
    sha = write_growth_evidence_gz(rep, root / args.out)
    print(
        json.dumps(
            {
                "artifact": args.out,
                "uncompressed_sha256": sha,
                "hypotheses": rep["hypotheses"],
                "summary": rep["summary_by_stratum"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
