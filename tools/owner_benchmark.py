#!/usr/bin/env python3
"""Pelaksana tolok ukur berversi milik pemilik (AG39): skor deterministik per tugas dan agregat per domain.

Kenapa: mengukur kemajuan nyata dengan paket tugas tersegel (`pack_id`, `pack_version`,
`pack_sha256`, dan `seed`) sehingga skor lintas domain tidak bergantung klaim sepihak
dan dapat dibandingkan ulang pada perbandingan spesialisasi (AG41).
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Callable
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


SCHEMA = "ace.owner-benchmark.v1"


def evaluate_deterministic(spec: Any, answer: Any) -> dict[str, Any]:
    """Nilai jawaban solver terhadap spesifikasi penilai deterministik tanpa efek samping."""
    if callable(spec):
        res = spec(answer)
        if isinstance(res, bool):
            return {"passed": res, "score": 1.0 if res else 0.0, "reason": "ok" if res else "failed"}
        if isinstance(res, dict):
            passed = bool(res.get("passed"))
            score = float(res.get("score", 1.0 if passed else 0.0))
            return {"passed": passed, "score": score, "reason": str(res.get("reason") or ("ok" if passed else "failed"))}
        raise ValueError("Penilai callable wajib mengembalikan bool atau dict.")

    if not isinstance(spec, dict):
        raise ValueError("Spesifikasi penilai tugas wajib berupa dict atau callable.")
    kind = spec.get("kind")
    text = "" if answer is None else str(answer)

    if kind == "exact_match":
        expected = str(spec.get("expected") or "")
        passed = text.strip() == expected.strip()
        return {"passed": passed, "score": 1.0 if passed else 0.0, "reason": "exact_match" if passed else "mismatch"}

    if kind == "contains_all":
        tokens = spec.get("tokens") or []
        if not isinstance(tokens, list) or not tokens:
            raise ValueError("contains_all memerlukan daftar 'tokens' tak-kosong.")
        missing = [t for t in tokens if str(t) not in text]
        passed = len(missing) == 0
        score = (len(tokens) - len(missing)) / len(tokens)
        return {"passed": passed, "score": round(score, 4), "reason": "all_tokens_present" if passed else f"missing:{','.join(map(str, missing))}"}

    if kind == "regex_fullmatch":
        pattern = str(spec.get("pattern") or "")
        passed = bool(re.fullmatch(pattern, text.strip()))
        return {"passed": passed, "score": 1.0 if passed else 0.0, "reason": "regex_matched" if passed else "regex_mismatch"}

    if kind == "numeric_tolerance":
        expected_num = float(spec["expected"])
        tol = float(spec.get("tolerance", 1e-6))
        try:
            got_num = float(text.strip())
            passed = abs(got_num - expected_num) <= tol
        except ValueError:
            passed = False
        return {"passed": passed, "score": 1.0 if passed else 0.0, "reason": "within_tolerance" if passed else "out_of_tolerance"}

    raise ValueError(f"Jenis penilai deterministik tidak dikenal: {kind!r}")


def load_benchmark_pack(pack_path: Path) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """Muat paket tugas JSONL berversi dan hitung hash SHA-256 tersegel berkas."""
    raw_bytes = Path(pack_path).read_bytes()
    pack_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    pack_meta: dict[str, Any] = {
        "pack_id": Path(pack_path).stem,
        "pack_version": "1.0.0",
        "pack_sha256": pack_sha256,
    }
    tasks: list[dict[str, Any]] = []
    for idx, raw_line in enumerate(raw_bytes.decode("utf-8").splitlines(), 1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        obj = json.loads(stripped)
        if not isinstance(obj, dict):
            raise ValueError(f"Baris {idx} paket tolok ukur wajib berupa objek JSON.")
        if obj.get("kind") == "pack_meta":
            if isinstance(obj.get("pack_id"), str) and obj["pack_id"].strip():
                pack_meta["pack_id"] = obj["pack_id"].strip()
            if isinstance(obj.get("pack_version"), str) and obj["pack_version"].strip():
                pack_meta["pack_version"] = obj["pack_version"].strip()
            continue
        for req in ("id", "domain", "prompt"):
            if not isinstance(obj.get(req), str) or not obj[req].strip():
                raise ValueError(f"Baris {idx} paket tolok ukur wajib memiliki '{req}' tak-kosong.")
        if "evaluator" not in obj:
            raise ValueError(f"Tugas '{obj['id']}' wajib memiliki field 'evaluator'.")
        tasks.append(obj)
    if not tasks:
        raise ValueError("Paket tolok ukur tidak memuat satu pun tugas.")
    return pack_meta, tasks


def run_benchmark(
    tasks: list[dict[str, Any]],
    solver: Callable[[dict[str, Any]], Any],
    *,
    pack_id: str,
    pack_version: str,
    pack_sha256: str = "",
    seed: int = 0,
    solver_id: str = "callable-solver",
) -> dict[str, Any]:
    """Jalankan paket tugas berversi terhadap `solver` callable dan agregasikan per domain."""
    if not callable(solver):
        raise ValueError("Solver wajib berupa callable.")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("Daftar tugas tolok ukur tidak boleh kosong.")
    if type(seed) is not int:
        raise ValueError("seed wajib berupa integer.")
    if not pack_sha256:
        canonical = "\n".join(
            json.dumps(
                {k: v for k, v in t.items() if not callable(v)},
                sort_keys=True,
                ensure_ascii=False,
            )
            for t in tasks
        ).encode("utf-8")
        pack_sha256 = hashlib.sha256(canonical).hexdigest()

    seen_ids: set[str] = set()
    task_results: list[dict[str, Any]] = []
    domain_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for task in tasks:
        tid = str(task["id"])
        if tid in seen_ids:
            raise ValueError(f"ID tugas tolok ukur duplikat: {tid}")
        seen_ids.add(tid)
        domain = str(task["domain"])
        answer = solver(task)
        eval_res = evaluate_deterministic(task["evaluator"], answer)
        row = {
            "id": tid,
            "domain": domain,
            "passed": eval_res["passed"],
            "score": eval_res["score"],
            "reason": eval_res["reason"],
        }
        task_results.append(row)
        domain_buckets[domain].append(row)

    by_domain: dict[str, dict[str, Any]] = {}
    for domain in sorted(domain_buckets):
        rows = domain_buckets[domain]
        passed_cnt = sum(1 for r in rows if r["passed"])
        total_cnt = len(rows)
        by_domain[domain] = {
            "total": total_cnt,
            "passed": passed_cnt,
            "pass_rate": round(passed_cnt / total_cnt, 4),
            "avg_score": round(sum(float(r["score"]) for r in rows) / total_cnt, 4),
        }

    total_tasks = len(task_results)
    passed_tasks = sum(1 for r in task_results if r["passed"])
    return {
        "schema": SCHEMA,
        "sealed_pack": {
            "pack_id": pack_id,
            "pack_version": pack_version,
            "pack_sha256": pack_sha256,
        },
        "seed": seed,
        "solver_id": solver_id,
        "summary": {
            "total_tasks": total_tasks,
            "passed_tasks": passed_tasks,
            "pass_rate": round(passed_tasks / total_tasks, 4),
            "avg_score": round(sum(float(r["score"]) for r in task_results) / total_tasks, 4),
            "domain_count": len(by_domain),
        },
        "by_domain": by_domain,
        "tasks": task_results,
    }


def _answers_file_solver(answers_map: dict[str, Any]) -> Callable[[dict[str, Any]], Any]:
    def solve(task: dict[str, Any]) -> Any:
        return answers_map.get(task["id"], "")

    return solve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", required=True, type=Path, help="Berkas JSONL paket tugas berversi.")
    parser.add_argument("--answers", required=True, type=Path, help="Berkas JSON jawaban solver {task_id: answer}.")
    parser.add_argument("--pack-id", default=None)
    parser.add_argument("--pack-version", default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--solver-id", default="fixture-answers-solver")
    args = parser.parse_args(argv)
    try:
        meta, tasks = load_benchmark_pack(args.pack)
        answers = json.loads(args.answers.read_text(encoding="utf-8"))
        if not isinstance(answers, dict):
            raise ValueError("Berkas jawaban solver wajib berupa objek JSON {task_id: answer}.")
        report = run_benchmark(
            tasks,
            _answers_file_solver(answers),
            pack_id=args.pack_id or meta["pack_id"],
            pack_version=args.pack_version or meta["pack_version"],
            pack_sha256=meta["pack_sha256"],
            seed=args.seed,
            solver_id=args.solver_id,
        )
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
