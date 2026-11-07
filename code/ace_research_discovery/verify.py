"""Independent integrity, AST-isolation, semantic replay, and tamper verifier for Fase 6."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from . import PRESCORE_COMMIT, PRESCORE_SHA256, SCHEMA, canonical_json, digest
from .arms import ARM_NAMES
from .dsl import bool_expr_from_data
from .evaluator import parse_paired_trees, parse_single_tree
from .runner import run_benchmark
from .tasks import (
    BUDGETS,
    SEEDS,
    SOURCE_TASKS_SPEC,
    STRATA_ORDER,
    TARGET_TASKS_SPEC,
    build_target_splits,
    build_uncurated_source_pool,
)

ISOLATED_LEARNER_MODULES = ("dsl.py", "discovery.py", "arms.py")
FORBIDDEN_IMPORTS = {"evaluator", "tasks", "ace_research_discovery.evaluator", "ace_research_discovery.tasks"}
FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__"}


def verify_static_ast_isolation(pkg_dir: Path) -> None:
    """Assert via Python `ast` that learner modules never import `evaluator`/`tasks` or execute dynamic code."""
    forbidden_task_tokens = {sp.name for sp in SOURCE_TASKS_SPEC} | {tp.name for tp in TARGET_TASKS_SPEC}
    forbidden_task_tokens.add("surface_distractor")

    for mod_name in ISOLATED_LEARNER_MODULES:
        path = pkg_dir / mod_name
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in FORBIDDEN_IMPORTS or alias.name.endswith((".evaluator", ".tasks")):
                        raise ValueError(f"forbidden import {alias.name} in {mod_name}")
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod in FORBIDDEN_IMPORTS or mod in ("evaluator", "tasks"):
                    raise ValueError(f"forbidden from-import {mod} in {mod_name}")
                for alias in node.names:
                    if alias.name in ("evaluator", "tasks", "eval_source_task", "eval_nominal_target_task"):
                        raise ValueError(f"forbidden symbol import {alias.name} in {mod_name}")
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                    raise ValueError(f"forbidden dynamic call {node.func.id} in {mod_name}")
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in forbidden_task_tokens:
                    raise ValueError(f"task/category token leak {node.value!r} in {mod_name}")


def verify_family_and_task_disjointness() -> None:
    """Verify source tasks are single-tree (`1` component) and target tasks are paired-tree (`2` components) & disjoint."""
    source_names = {s.name for s in SOURCE_TASKS_SPEC}
    target_names = {t.name for t in TARGET_TASKS_SPEC}
    if source_names & target_names:
        raise ValueError("source and target task names overlap")

    src_tasks, _ = build_uncurated_source_pool(seed=1)
    for item in src_tasks:
        for w, _ in item["train"] + item["validation"]:
            if parse_single_tree(w) is None or parse_paired_trees(w) is not None:
                raise ValueError(f"source word {w!r} is not a strict single prime Dyck tree")

    for t_spec in TARGET_TASKS_SPEC:
        tr, va, te = build_target_splits(t_spec.name, seed=1, budget=32)
        for w, _ in tr + va + te:
            if parse_paired_trees(w) is None or parse_single_tree(w) is not None:
                raise ValueError(f"target word {w!r} is not a strict paired-tree frame")


def verify_report_dict(report: dict[str, Any], root: Path, check_replay: bool = False) -> str:
    """Validate report schema, upstream pins, AST isolation, closed AST replay, and optional full replay."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("verify_sources", root / "tools/verify_sources.py")
    assert spec is not None and spec.loader is not None
    vs_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vs_mod)

    upstream_count = vs_mod.verify(root)
    if upstream_count != 25:
        raise ValueError(f"expected 25 upstream pinned files, got {upstream_count}")

    prescore_path = root / "docs/ACE_NOVEL_DISCOVERY_PRESCORE_V1.md"
    actual_prescore_sha = hashlib.sha256(prescore_path.read_bytes()).hexdigest()
    if actual_prescore_sha != PRESCORE_SHA256:
        raise ValueError("pre-score protocol file SHA-256 mismatch")

    verify_static_ast_isolation(Path(__file__).resolve().parent)
    verify_family_and_task_disjointness()

    if type(report) is not dict or report.get("schema") != SCHEMA:
        raise ValueError("unsupported report schema")
    if report.get("prescore_commit") != PRESCORE_COMMIT or report.get("prescore_sha256") != PRESCORE_SHA256:
        raise ValueError("report pre-score provenance mismatch")
    if report.get("open_world_safe") is not False:
        raise ValueError("open_world_safe must remain strictly False")
    if report.get("release_decision") != "BLOCK_RELEASE":
        raise ValueError("release_decision must remain BLOCK_RELEASE")
    if report.get("oaie_established") is not False or report.get("candidate_deployed") is not False:
        raise ValueError("oaie_established and candidate_deployed must remain strictly False")

    trials = report.get("trials")
    expected_trials = len(BUDGETS) * len(SEEDS) * len(TARGET_TASKS_SPEC)
    if not isinstance(trials, list) or len(trials) != expected_trials:
        raise ValueError(f"expected {expected_trials} trials, got {len(trials) if isinstance(trials, list) else 'non-list'}")

    # Verify strict separation of native oracle & independent closed-AST semantic replay
    for trial in trials:
        arms = trial.get("arms")
        if not isinstance(arms, dict) or set(arms.keys()) != set(ARM_NAMES):
            raise ValueError("trial arms mismatch")
        if "U_native_oracle" in arms:
            raise ValueError("upper bound oracle leaked into benchmark arms")
        if "upper_bound_oracle" not in trial or not isinstance(trial["upper_bound_oracle"], dict):
            raise ValueError("missing separate upper_bound_oracle record")

        budget = trial["budget"]
        seed = trial["seed"]
        task_name = trial["task"]
        tr, va, te = build_target_splits(task_name, seed=seed, budget=budget)
        if trial["data_sha256"] != {
            "train": digest(tr),
            "validation": digest(va),
            "terminal": digest(te),
        }:
            raise ValueError(f"data_sha256 mismatch on {task_name} (B={budget}, seed={seed})")

        for arm_name, rec in arms.items():
            if type(rec.get("admitted")) is not bool:
                raise ValueError(f"non-bool admitted flag in {arm_name}")
            if rec["selected_ast"] is not None:
                decoded = bool_expr_from_data(rec["selected_ast"])
                preds = [decoded.predict(w) for w, _ in te]
                corr = sum(1 for p, (_, y) in zip(preds, te) if p == y)
                if corr != rec["terminal_correct"] or digest(preds) != rec["predictions_sha256"]:
                    raise ValueError(f"closed AST replay mismatch on {task_name} / {arm_name}")

    for b_key, strat_map in report["aggregates"]["by_budget_stratum"].items():
        if set(strat_map.keys()) != set(STRATA_ORDER):
            raise ValueError(f"missing strata in budget {b_key}")
        for s_key, arm_map in strat_map.items():
            if "U_native_oracle" in arm_map or set(arm_map.keys()) != set(ARM_NAMES):
                raise ValueError(f"invalid arm set in aggregate {b_key}/{s_key}")

    canonical_bytes = canonical_json(report)
    report_sha = hashlib.sha256(canonical_bytes).hexdigest()

    if check_replay:
        replayed = run_benchmark()
        replayed_bytes = canonical_json(replayed)
        replayed_sha = hashlib.sha256(replayed_bytes).hexdigest()
        if replayed_bytes != canonical_bytes:
            raise ValueError(f"deterministic replay mismatch: stored {report_sha} != replayed {replayed_sha}")

    return report_sha


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("evidence/discovery/f6_novel_discovery_v1.json"),
        help="Path to canonical JSON evidence file to verify",
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=None,
        help="Path to evidence file to verify (alias for --input)",
    )
    parser.add_argument(
        "--replay",
        action="store_true",
        help="Re-execute full benchmark and assert byte-for-bit identical canonical JSON",
    )
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[2]
    target_path = args.artifact or args.input
    if target_path.suffix == ".gz":
        import gzip
        raw_bytes = gzip.decompress(target_path.read_bytes())
    else:
        raw_bytes = target_path.read_bytes()
    report = json.loads(raw_bytes.decode("utf-8"))
    if canonical_json(report) != raw_bytes:
        print("FAIL: input file is not in canonical JSON byte form", file=sys.stderr)
        return 1

    try:
        sha = verify_report_dict(report, root=root, check_replay=args.replay)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "status": "PASS_FASE6_EXACT_VERIFICATION",
                "sha256": sha,
                "bytes": len(raw_bytes),
                "replay_checked": bool(args.replay),
                "scientific_capability_validated": report["evidence_flags"]["SCIENTIFIC_CAPABILITY_VALIDATED"],
                "open_world_safe": report["open_world_safe"],
                "release_decision": report["release_decision"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
