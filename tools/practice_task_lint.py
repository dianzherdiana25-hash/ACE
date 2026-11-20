#!/usr/bin/env python3
"""Linter definisi tugas praktik 10 keluarga (AG32): deterministik, idempoten, tak bocor jawaban.

Kenapa: penilai tugas praktik yang acak, bergantung pada state antar-panggilan
(tak idempoten), atau membocorkan jawaban di prompt akan menghasilkan skor palsu
dan merusak sinyal pengajaran. Perkakas ini memvalidasi seluruh 10 keluarga tugas
praktik sebelum masuk ke mesin latihan.
"""
from __future__ import annotations

import argparse
import ast
from collections.abc import Callable
from copy import deepcopy
import json
from pathlib import Path
import re
import sys
from typing import Any


SCHEMA = "ace.practice-task-lint.v1"

PRACTICE_FAMILIES: tuple[str, ...] = (
    "dedup_csv",
    "progressive_tax",
    "json_parser",
    "bfs",
    "backoff",
    "text_similarity",
    "security_detector",
    "bug_repair",
    "binary_search",
    "lru_cache",
)

_NONDET_CALLS = frozenset(
    {
        "random", "randint", "randrange", "choice", "shuffle", "sample", "uniform",
        "urandom", "uuid1", "uuid4", "monotonic", "perf_counter", "time", "token_hex",
    }
)


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_solution_payloads(reference_solution: str) -> list[str]:
    """Ambil potongan solusi non-trivial untuk mendeteksi kebocoran verbatim di prompt."""
    payloads: list[str] = []
    norm_full = _normalize_ws(reference_solution)
    if len(norm_full) >= 12:
        payloads.append(norm_full)
    # Kumpulkan baris badan penting (selain `def ...:` pembuka dan baris komentar singkat)
    for raw_line in reference_solution.splitlines():
        line = _normalize_ws(raw_line)
        if not line or line.startswith("#") or line.startswith("def "):
            continue
        if len(line) >= 14:
            payloads.append(line)
    return payloads


def _check_prompt_leak(prompt: str, reference_solution: str) -> list[str]:
    reasons: list[str] = []
    norm_prompt = _normalize_ws(prompt)
    for snippet in _extract_solution_payloads(reference_solution):
        if snippet in norm_prompt:
            reasons.append("answer_leak_in_prompt")
            break
    return reasons


def _compile_evaluator(evaluator_code: str) -> tuple[Callable[..., Any] | None, list[str]]:
    reasons: list[str] = []
    try:
        tree = ast.parse(evaluator_code, filename="evaluator_code")
    except SyntaxError:
        return None, ["invalid_evaluator_syntax"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in {"random", "secrets", "uuid"}:
                    reasons.append("non_deterministic_evaluator")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in {"random", "secrets", "uuid"}:
                reasons.append("non_deterministic_evaluator")
        elif isinstance(node, ast.Attribute) and node.attr in _NONDET_CALLS:
            reasons.append("non_deterministic_evaluator")
        elif isinstance(node, ast.Name) and node.id in _NONDET_CALLS:
            reasons.append("non_deterministic_evaluator")

    namespace: dict[str, Any] = {}
    try:
        exec(compile(tree, "evaluator_code", "exec"), namespace, namespace)
    except Exception:
        return None, [*reasons, "evaluator_compile_failed"]

    fn = namespace.get("evaluate")
    if not callable(fn):
        return None, [*reasons, "missing_evaluate_callable"]
    return fn, reasons


def _invoke_evaluator(fn: Callable[..., Any], solution: str, test_cases: list[Any]) -> Any:
    try:
        return fn(solution, test_cases)
    except TypeError:
        return fn(solution)


def _normalize_result(raw: Any) -> Any:
    if isinstance(raw, dict):
        return json.loads(json.dumps(raw, sort_keys=True, ensure_ascii=False))
    if isinstance(raw, (list, tuple)):
        return json.loads(json.dumps(list(raw), sort_keys=True, ensure_ascii=False))
    return raw


def _is_passing_result(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, dict):
        if "passed" in raw:
            return bool(raw["passed"])
        if "ok" in raw:
            return bool(raw["ok"])
    if isinstance(raw, (list, tuple)) and raw:
        return bool(raw[0])
    return False


def lint_practice_task(task: dict[str, Any]) -> dict[str, Any]:
    """Validasi satu definisi tugas praktik beserta penilainya."""
    if not isinstance(task, dict):
        raise ValueError("Definisi tugas wajib berupa objek.")

    task_id = str(task.get("id") or "<missing>")
    family = task.get("family")
    reasons: list[str] = []

    if family not in PRACTICE_FAMILIES:
        reasons.append("unknown_practice_family")

    prompt = task.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        reasons.append("missing_prompt")

    ref_sol = task.get("reference_solution")
    if not isinstance(ref_sol, str) or not ref_sol.strip():
        reasons.append("missing_reference_solution")

    if isinstance(prompt, str) and isinstance(ref_sol, str) and prompt.strip() and ref_sol.strip():
        reasons.extend(_check_prompt_leak(prompt, ref_sol))

    test_cases = task.get("test_cases")
    if test_cases is None:
        test_cases = []
    if not isinstance(test_cases, list):
        reasons.append("invalid_test_cases")
        test_cases = []

    evaluator_fn = task.get("evaluator")
    evaluator_code = task.get("evaluator_code")
    if evaluator_fn is None and isinstance(evaluator_code, str):
        evaluator_fn, compile_reasons = _compile_evaluator(evaluator_code)
        reasons.extend(compile_reasons)
    elif not callable(evaluator_fn):
        reasons.append("missing_evaluator")
        evaluator_fn = None

    if evaluator_fn is not None and isinstance(ref_sol, str) and ref_sol.strip():
        snapshot_before = deepcopy(test_cases)
        runs: list[Any] = []
        errored = False
        for _ in range(3):
            cases_arg = deepcopy(test_cases)
            try:
                res = _invoke_evaluator(evaluator_fn, ref_sol, cases_arg)
                runs.append(_normalize_result(res))
                if cases_arg != snapshot_before:
                    reasons.append("non_idempotent_evaluator")
                    break
            except Exception:
                errored = True
                reasons.append("evaluator_runtime_error")
                break
        if not errored and len(runs) == 3:
            if not all(r == runs[0] for r in runs):
                # Deteksi: bila gagal identik vs acak, bedakan pola acak vs tak idempoten
                if "non_deterministic_evaluator" not in reasons:
                    reasons.append("non_idempotent_evaluator")
                    reasons.append("non_deterministic_evaluator")
            if not _is_passing_result(runs[0]):
                reasons.append("reference_solution_failed_evaluator")

        # Uji konsistensi penolakan atas solusi kosong/salah
        neg_runs: list[Any] = []
        for _ in range(2):
            try:
                neg_runs.append(_normalize_result(_invoke_evaluator(evaluator_fn, "def wrong(): return None\n", deepcopy(test_cases))))
            except Exception:
                neg_runs.append({"error": True})
        if len(neg_runs) == 2:
            if neg_runs[0] != neg_runs[1] and "non_deterministic_evaluator" not in reasons:
                reasons.append("non_deterministic_evaluator")
            if _is_passing_result(neg_runs[0]):
                reasons.append("vacuous_evaluator_passed_wrong_solution")

    deduped = list(dict.fromkeys(reasons))
    return {
        "task_id": task_id,
        "family": family,
        "valid": len(deduped) == 0,
        "reasons": deduped,
    }


def lint_practice_tasks(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("Daftar tugas praktik wajib berupa larik berisi.")
    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    families_seen: set[str] = set()

    for idx, task in enumerate(tasks, 1):
        res = lint_practice_task(task)
        if res["task_id"] in seen_ids:
            res["reasons"] = list(dict.fromkeys([*res["reasons"], f"duplicate_task_id:{res['task_id']}"]))
            res["valid"] = False
        seen_ids.add(res["task_id"])
        if res["valid"] and isinstance(res["family"], str):
            families_seen.add(res["family"])
        results.append(res)

    invalid_count = sum(1 for r in results if not r["valid"])
    return {
        "schema": SCHEMA,
        "summary": {
            "total_tasks": len(results),
            "valid_tasks": len(results) - invalid_count,
            "invalid_tasks": invalid_count,
            "families_covered": sorted(families_seen),
            "all_ten_families_covered": len(families_seen) == len(PRACTICE_FAMILIES),
        },
        "all_valid": invalid_count == 0,
        "tasks": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", required=True, type=Path, help="Berkas JSON/JSONL definisi tugas praktik.")
    parser.add_argument("--require-all-families", action="store_true")
    args = parser.parse_args(argv)
    try:
        raw = args.tasks.read_text(encoding="utf-8")
        if args.tasks.suffix.lower() == ".jsonl":
            tasks = [json.loads(ln) for ln in raw.splitlines() if ln.strip()]
        else:
            tasks = json.loads(raw)
        report = lint_practice_tasks(tasks)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["all_valid"]:
        return 1
    if args.require_all_families and not report["summary"]["all_ten_families_covered"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
