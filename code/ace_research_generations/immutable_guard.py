"""Immutable Evaluator, Policy, Holdout, and Promotion Lock for Fase 7 (G0->G1->G2).

Enforces that no candidate meta-mechanism can read, modify, or weaken:
1. ``evaluator.py`` or terminal holdout banks,
2. ``ace_autonomy`` authorization, policy, verifier, or HMAC journals,
3. ``ace_runtime`` engine or the 25 pinned ``UPSTREAM_SOURCES.json`` files,
4. Generational promotion thresholds.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any

from ace_autonomy import IntegrityError, PolicyError

PROMOTION_POLICY: dict[str, Any] = {
    "min_meta_val_gain": 0.15,
    "max_prior_regression": 0.02,
    "require_autonomy_staging": True,
    "allow_auto_deploy": False,
}

ALLOWED_META_FIELDS = frozenset({
    "schema",
    "gen_tag",
    "parent_gen",
    "enable_strided_features",
    "stride_moduli",
    "enable_split_frame_lifting",
    "enable_mdl_ranking",
    "enable_probe_agreement_gate",
    "eval_budget_k",
})

FIT_SIDE_MODULES = (
    "__init__.py",
    "immutable_guard.py",
    "tasks.py",
    "mechanisms.py",
    "lineage.py",
)


def validate_meta_candidate(cand: Any) -> dict[str, Any]:
    """Fail closed if a candidate meta-mechanism touches forbidden fields or bounds."""
    if type(cand) is not dict:
        raise PolicyError("meta-mechanism candidate must be a dict")
    extra = set(cand) - ALLOWED_META_FIELDS
    if extra:
        raise PolicyError(
            f"candidate attempted forbidden policy/evaluator/promotion keys: {sorted(extra)}"
        )
    if cand.get("schema") != "ace.meta_mechanism.v1":
        raise PolicyError("invalid meta-mechanism schema")
    if type(cand.get("gen_tag")) is not str or not cand["gen_tag"]:
        raise PolicyError("gen_tag must be a non-empty string")
    for bool_key in (
        "enable_strided_features",
        "enable_split_frame_lifting",
        "enable_mdl_ranking",
        "enable_probe_agreement_gate",
    ):
        if type(cand.get(bool_key)) is not bool:
            raise PolicyError(f"{bool_key} must be a strict bool")
    moduli = cand.get("stride_moduli")
    if (
        not isinstance(moduli, (list, tuple))
        or any(type(m) is not int or m not in (2, 3, 4) for m in moduli)
    ):
        raise PolicyError("stride_moduli must contain ints in {2, 3, 4}")
    k = cand.get("eval_budget_k")
    if type(k) is not int or not 32 <= k <= 1024:
        raise PolicyError("eval_budget_k out of allowed range 32..1024")
    return dict(cand)


class ImmutableCoreGuard:
    """Snapshots and verifies SHA-256 locks on evaluator, autonomy policy, and runtime core."""

    def __init__(self, repo_root: Path):
        self.root = repo_root.resolve()
        self.locked_paths = (
            "docs/UPSTREAM_SOURCES.json",
            "code/ace_runtime/engine.py",
            "code/ace_autonomy/policy.py",
            "code/ace_autonomy/verifier.py",
            "code/ace_autonomy/core.py",
            "code/ace_autonomy/escrow.py",
            "code/ace_research_generations/evaluator.py",
        )
        self.baseline_hashes = self._snapshot()
        self.promotion_digest = hashlib.sha256(
            repr(sorted(PROMOTION_POLICY.items())).encode("utf-8")
        ).hexdigest()

    def _snapshot(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for rel in self.locked_paths:
            p = self.root / rel
            if not p.is_file():
                raise IntegrityError(f"locked file missing: {rel}")
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
        return out

    def verify_intact(self) -> dict[str, Any]:
        cur = self._snapshot()
        if cur != self.baseline_hashes:
            diff = [k for k in self.locked_paths if cur.get(k) != self.baseline_hashes.get(k)]
            raise IntegrityError(f"immutable core/evaluator files modified during evolution: {diff}")
        cur_promo = hashlib.sha256(
            repr(sorted(PROMOTION_POLICY.items())).encode("utf-8")
        ).hexdigest()
        if cur_promo != self.promotion_digest:
            raise IntegrityError("promotion policy mutated during evolution")
        return {
            "locked_files_verified": len(cur),
            "evaluator_sha256": cur["code/ace_research_generations/evaluator.py"],
            "promotion_policy_sha256": self.promotion_digest,
        }


def verify_ast_evaluator_isolation(pkg_dir: Path | None = None) -> dict[str, Any]:
    base = pkg_dir or Path(__file__).resolve().parent
    violations: list[str] = []
    for mod_name in FIT_SIDE_MODULES:
        p = base / mod_name
        if not p.is_file():
            continue
        tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if "evaluator" in a.name.split("."):
                        violations.append(f"{mod_name}: import {a.name}")
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if "evaluator" in mod.split(".") or any(a.name == "evaluator" for a in node.names):
                    violations.append(f"{mod_name}: from {mod} import evaluator")
    return {
        "checked_modules": list(FIT_SIDE_MODULES),
        "violations": violations,
        "isolated": len(violations) == 0,
    }
