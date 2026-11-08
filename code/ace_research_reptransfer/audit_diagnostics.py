"""Post-score independent audit diagnostics for R9 (Gemini lane).

Leaves ``r9_gemini_v1.json.gz`` and all original ``5e70863`` modules untouched.
Provides executable verification for items declared in ``ACE_R9_GEMINI_PRESCORE.md``
that were omitted from the primary runner summary:
1. AST-level import isolation confirming fit modules never import ``evaluator``.
2. Per-unit and per-slice ``transfer_regret = max(M_B, M_C, M_C2) - M_A``.
3. Secondary unlabeled ``probe_strings`` agreement-gate arms (``A_g, A0_g, C_g, C2_g``),
   verifying both spurious-admission suppression on ``N`` at low budget and the
   information-theoretic impossibility of detecting identical-observation ``H6`` flips.
"""
from __future__ import annotations

import ast
import gzip
import hashlib
import itertools
import json
from pathlib import Path
from typing import Sequence

from .arms import Candidate, get_dictionaries
from .evaluator import terminal_bank
from .features import Feature
from .head import OP_AND, OP_NAMES, OP_OR, OP_XOR, bitvec
from .runner import BUDGETS, PRIMARY_BUDGET, SEEDS, evaluate_candidate
from .sampling import labeled_sample, probe_strings
from .tasks import DRIFT, TARGET_BY_ID, TARGETS

FIT_SIDE_MODULES = (
    "__init__.py",
    "tasks.py",
    "sampling.py",
    "features.py",
    "head.py",
    "arms.py",
)


def check_ast_import_isolation(pkg_dir: Path | None = None) -> dict:
    """Verify via AST parsing that no fit-side module imports ``evaluator``."""
    base = pkg_dir or Path(__file__).resolve().parent
    violations: list[str] = []
    checked: list[str] = []
    for mod_name in FIT_SIDE_MODULES:
        mod_path = base / mod_name
        checked.append(mod_name)
        tree = ast.parse(mod_path.read_text(encoding="utf-8"), filename=str(mod_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "evaluator" in alias.name.split("."):
                        violations.append(f"{mod_name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if "evaluator" in mod.split("."):
                    violations.append(f"{mod_name}: from {mod} import ...")
                for alias in node.names:
                    if alias.name == "evaluator":
                        violations.append(f"{mod_name}: from {mod} import evaluator")
    return {
        "checked_modules": checked,
        "violations": violations,
        "isolated": len(violations) == 0,
    }


def compute_transfer_regret(report: dict) -> dict:
    """Compute ``max(M_B, M_C, M_C2) - M_A`` and blind regret ``max(M_B, M_C) - M_A``."""

    def m_score(unit: dict, arm: str) -> float:
        ev = unit["arms"][arm]["evaluation"]
        return float(ev["terminal_accuracy"]) if ev["admitted"] else 0.0

    nominals = [u for u in report["units"] if u["kind"] == "nominal"]
    by_slice: dict[str, dict] = {}
    for st in ("U", "L", "N"):
        for b in BUDGETS:
            sub = [u for u in nominals if u["stratum"] == st and u["budget"] == b]
            regrets_all = [
                max(m_score(u, "B"), m_score(u, "C"), m_score(u, "C2")) - m_score(u, "A")
                for u in sub
            ]
            regrets_blind = [
                max(m_score(u, "B"), m_score(u, "C")) - m_score(u, "A")
                for u in sub
            ]
            by_slice[f"{st}_b{b}"] = {
                "n_units": len(sub),
                "mean_regret_vs_BC_C2": round(sum(regrets_all) / len(sub), 4),
                "max_regret_vs_BC_C2": round(max(regrets_all), 4),
                "mean_regret_vs_blind_BC": round(sum(regrets_blind) / len(sub), 4),
                "positive_regret_units_vs_BC_C2": sum(r > 0.0 for r in regrets_all),
            }
    return by_slice


def fit_adapter_agreement_gated(
    features: Sequence[Feature],
    train: list[tuple[str, bool]],
    validation: list[tuple[str, bool]],
    probes: list[str],
) -> tuple[Candidate | None, dict]:
    """Secondary agreement-gate adapter declared in ``ACE_R9_GEMINI_PRESCORE.md`` §4.

    Among all hypotheses of minimal complexity that achieve 0 train errors and
    0 validation errors, abstain if any two such hypotheses disagree on any of
    the 256 unlabeled ``probe_strings(seed)``.
    """
    tr_words, tr_labels = [w for w, _ in train], [lbl for _, lbl in train]
    va_words, va_labels = [w for w, _ in validation], [lbl for _, lbl in validation]

    tr_mask = (1 << len(tr_words)) - 1
    va_mask = (1 << len(va_words)) - 1
    pr_mask = (1 << len(probes)) - 1

    tr_target = sum((1 << i) for i, lbl in enumerate(tr_labels) if lbl)
    va_target = sum((1 << i) for i, lbl in enumerate(va_labels) if lbl)

    f_tr = [bitvec(f.apply, tr_words) for f in features]
    f_va = [bitvec(f.apply, va_words) for f in features]

    n_feats = len(features)
    n_lits = 2 * n_feats
    l_tr = [0] * n_lits
    l_va = [0] * n_lits
    l_names = [""] * n_lits
    for k in range(n_feats):
        l_tr[2 * k] = f_tr[k]
        l_tr[2 * k + 1] = tr_mask ^ f_tr[k]
        l_va[2 * k] = f_va[k]
        l_va[2 * k + 1] = va_mask ^ f_va[k]
        l_names[2 * k] = features[k].name
        l_names[2 * k + 1] = f"(not {features[k].name})"

    exact_singles: list[tuple[str, int, int]] = []
    for lit in range(n_lits):
        if l_tr[lit] == tr_target and l_va[lit] == va_target:
            exact_singles.append((l_names[lit], lit // 2, lit % 2))

    if exact_singles:
        exact_singles.sort(key=lambda x: x[0])
        f_pr = {k: bitvec(features[k].apply, probes) for _, k, _ in exact_singles}
        ref_vec = None
        disagreed = False
        for _, k, s in exact_singles:
            vec = (pr_mask ^ f_pr[k]) if s else f_pr[k]
            if ref_vec is None:
                ref_vec = vec
            elif vec != ref_vec:
                disagreed = True
                break
        if disagreed:
            return None, {
                "admitted": False,
                "abstain_reason": "probe_disagreement_c1",
                "exact_survivors": len(exact_singles),
            }
        name, k1, s1 = exact_singles[0]
        f1 = features[k1]
        pred = (lambda w, f=f1: not f.apply(w)) if s1 else f1.apply
        return Candidate(name, pred, len), {
            "admitted": True,
            "complexity": 1,
            "exact_survivors": len(exact_singles),
        }

    exact_pairs: list[tuple[str, int, int, int, int, int]] = []
    for k1, k2 in itertools.combinations(range(n_feats), 2):
        for s1 in (0, 1):
            lit1 = 2 * k1 + s1
            tr1, va1, nm1 = l_tr[lit1], l_va[lit1], l_names[lit1]
            for s2 in (0, 1):
                lit2 = 2 * k2 + s2
                tr2, va2, nm2 = l_tr[lit2], l_va[lit2], l_names[lit2]
                for op in (OP_AND, OP_OR, OP_XOR):
                    if op == OP_AND and s1 == 1 and s2 == 1:
                        continue
                    if op == OP_OR and s1 == 1 and s2 == 1:
                        continue
                    if op == OP_XOR and (s1 == 1 or (s2 == 1 and s1 == 0)):
                        pass
                    if op == OP_AND:
                        htr = tr1 & tr2
                    elif op == OP_OR:
                        htr = tr1 | tr2
                    else:
                        htr = tr1 ^ tr2
                    if htr != tr_target:
                        continue
                    if op == OP_AND:
                        hva = va1 & va2
                    elif op == OP_OR:
                        hva = va1 | va2
                    else:
                        hva = va1 ^ va2
                    if hva == va_target:
                        name = f"({nm1} {OP_NAMES[op]} {nm2})"
                        exact_pairs.append((name, k1, s1, op, k2, s2))

    if not exact_pairs:
        return None, {
            "admitted": False,
            "abstain_reason": "no_zero_val_error_hypothesis",
            "exact_survivors": 0,
        }

    exact_pairs.sort(key=lambda x: x[0])
    used_k = {k1 for _, k1, _, _, _, _ in exact_pairs} | {k2 for _, _, _, _, k2, _ in exact_pairs}
    f_pr = {k: bitvec(features[k].apply, probes) for k in used_k}
    ref_vec = None
    disagreed = False
    for _, k1, s1, op, k2, s2 in exact_pairs:
        v1 = (pr_mask ^ f_pr[k1]) if s1 else f_pr[k1]
        v2 = (pr_mask ^ f_pr[k2]) if s2 else f_pr[k2]
        if op == OP_AND:
            vec = v1 & v2
        elif op == OP_OR:
            vec = v1 | v2
        else:
            vec = v1 ^ v2
        if ref_vec is None:
            ref_vec = vec
        elif vec != ref_vec:
            disagreed = True
            break

    if disagreed:
        return None, {
            "admitted": False,
            "abstain_reason": "probe_disagreement_c2",
            "exact_survivors": len(exact_pairs),
        }

    name, k1, s1, op, k2, s2 = exact_pairs[0]
    f1, f2 = features[k1], features[k2]

    def _pred(w: str, _f1=f1, _s1=s1, _op=op, _f2=f2, _s2=s2) -> bool:
        b1 = (not _f1.apply(w)) if _s1 else _f1.apply(w)
        b2 = (not _f2.apply(w)) if _s2 else _f2.apply(w)
        if _op == OP_AND:
            return b1 and b2
        if _op == OP_OR:
            return b1 or b2
        return b1 != b2

    return Candidate(name, _pred, lambda w: 2 * len(w)), {
        "admitted": True,
        "complexity": 2,
        "exact_survivors": len(exact_pairs),
    }


def run_agreement_gate_diagnostic() -> dict:
    """Evaluate ``A_g, A0_g, C_g, C2_g`` across all 165 nominal + 30 drift units."""
    dicts = get_dictionaries()
    arm_feats = {
        "A_g": dicts["A"][0],
        "A0_g": dicts["A0"][0],
        "C_g": dicts["C"],
        "C2_g": dicts["C2"],
    }

    slice_scores: dict[str, dict[str, list[float]]] = {}
    slice_cov: dict[str, dict[str, list[int]]] = {}
    false_adm_n: dict[int, dict[str, int]] = {b: {a: 0 for a in arm_feats} for b in BUDGETS}
    drift_false_accepts: dict[int, dict[str, int]] = {b: {a: 0 for a in arm_feats} for b in BUDGETS}

    for task_id, stratum, spec in TARGETS:
        for seed in SEEDS:
            probes = probe_strings(seed)
            terminal = terminal_bank(task_id, seed)
            for budget in BUDGETS:
                train = labeled_sample(spec, 0, 5, budget // 2, "train", task_id, seed, budget)
                val = labeled_sample(spec, 6, 12, budget // 2, "val", task_id, seed, budget)
                skey = f"{stratum}_b{budget}"
                slice_scores.setdefault(skey, {a: [] for a in arm_feats})
                slice_cov.setdefault(skey, {a: [] for a in arm_feats})
                for arm_name, feats in arm_feats.items():
                    cand, _ = fit_adapter_agreement_gated(feats, train, val, probes)
                    ev = evaluate_candidate(cand, terminal)
                    adm = bool(ev["admitted"])
                    acc = float(ev["terminal_accuracy"]) if adm else 0.0
                    slice_scores[skey][arm_name].append(acc)
                    slice_cov[skey][arm_name].append(1 if adm else 0)
                    if stratum == "N" and adm and acc < 0.90:
                        false_adm_n[budget][arm_name] += 1

    for _, nominal_task_id in DRIFT:
        _, spec = TARGET_BY_ID[nominal_task_id]
        for seed in SEEDS:
            probes = probe_strings(seed)
            nominal_terminal = terminal_bank(nominal_task_id, seed)
            inverted_terminal = [(w, not lbl) for w, lbl in nominal_terminal]
            for budget in BUDGETS:
                train = labeled_sample(spec, 0, 5, budget // 2, "train", nominal_task_id, seed, budget)
                val = labeled_sample(spec, 6, 12, budget // 2, "val", nominal_task_id, seed, budget)
                for arm_name, feats in arm_feats.items():
                    cand, _ = fit_adapter_agreement_gated(feats, train, val, probes)
                    ev = evaluate_candidate(cand, inverted_terminal)
                    if ev["admitted"] and ev["terminal_accuracy"] < 0.10:
                        drift_false_accepts[budget][arm_name] += 1

    slices_out = {}
    for skey in sorted(slice_scores):
        slices_out[skey] = {
            "means": {
                a: round(sum(vals) / len(vals), 4)
                for a, vals in slice_scores[skey].items()
            },
            "coverage": {
                a: round(sum(vals) / len(vals), 4)
                for a, vals in slice_cov[skey].items()
            },
        }
    return {
        "slices": slices_out,
        "N_false_admissions_by_budget": {str(b): false_adm_n[b] for b in BUDGETS},
        "drift_false_accepts_by_budget": {str(b): drift_false_accepts[b] for b in BUDGETS},
    }


def run_full_audit(report_gz_path: Path | None = None) -> dict:
    root = Path(__file__).resolve().parents[2]
    gz_path = report_gz_path or (root / "evidence" / "reptransfer" / "r9_gemini_v1.json.gz")
    raw_bytes = gzip.decompress(gz_path.read_bytes())
    raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    report = json.loads(raw_bytes.decode("utf-8"))
    return {
        "schema": "ace.r9.independent_audit.v1",
        "committed_report_uncompressed_sha256": raw_sha256,
        "ast_import_isolation": check_ast_import_isolation(),
        "transfer_regret": compute_transfer_regret(report),
        "agreement_gate": run_agreement_gate_diagnostic(),
    }


if __name__ == "__main__":
    print(json.dumps(run_full_audit(), indent=2, sort_keys=True))
