"""Validator paket tugas praktik hasil generator (AG46).

Memvalidasi setiap tugas praktik yang dihasilkan oleh generator kurikuler:
1. Terpecahkan (solvable): ``reference_answer`` wajib lolos evaluator dan
   seluruh ``test_cases``, sementara probe jawaban salah tidak ikut lolos.
2. Deterministik: pemanggilan evaluator berulang menghasilkan hasil identik,
   dan bila tersedia sumber kode evaluator, bebas dari pemanggilan RNG/jam.
3. Bebas bocoran jawaban (no answer leak): ``prompt`` tidak membocorkan
   ``reference_answer`` secara harfiah maupun lewat penanda jawaban eksplisit.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.practice-task-validator.v1"
_NONDETERMINISTIC_MODULES = frozenset({"random", "secrets", "uuid"})
_NONDETERMINISTIC_ATTRS = frozenset(
    {"time", "monotonic", "perf_counter", "urandom", "randint", "random", "choice", "shuffle", "uuid4"}
)
_LEAK_LABEL_RE = re.compile(
    r"(?:answer|jawaban|kunci|expected|solution)\s*[:=]\s*([^\n;]+)",
    re.IGNORECASE,
)


def _eval_declarative(spec: Mapping[str, Any], answer: Any) -> tuple[bool, float]:
    kind = spec.get("kind")
    text = "" if answer is None else str(answer)

    if kind == "exact_match":
        expected = str(spec.get("expected") if spec.get("expected") is not None else "")
        ok = text.strip() == expected.strip()
        return ok, (1.0 if ok else 0.0)

    if kind == "contains_all":
        tokens = spec.get("tokens") or []
        if not isinstance(tokens, list) or not tokens:
            raise ValueError("contains_all wajib memuat daftar 'tokens' tak-kosong")
        hits = sum(1 for tok in tokens if str(tok) in text)
        ok = hits == len(tokens)
        return ok, round(hits / len(tokens), 6)

    if kind == "regex_fullmatch":
        pattern = str(spec.get("pattern") or "")
        ok = bool(re.fullmatch(pattern, text.strip()))
        return ok, (1.0 if ok else 0.0)

    if kind == "numeric_tolerance":
        expected_num = float(spec["expected"])
        tol = float(spec.get("tolerance", 1e-6))
        try:
            ok = abs(float(text.strip()) - expected_num) <= tol
        except ValueError:
            ok = False
        return ok, (1.0 if ok else 0.0)

    if kind == "json_equal":
        try:
            got_obj = json.loads(text) if isinstance(answer, str) else answer
            expected_obj = spec["expected"]
            ok = got_obj == expected_obj
        except (ValueError, TypeError, KeyError):
            ok = False
        return ok, (1.0 if ok else 0.0)

    if kind == "test_cases_exact":
        # Memetakan candidate berupa dict/JSON {case_id/input_key: output} terhadap expected per kasus.
        try:
            mapping = json.loads(text) if isinstance(answer, str) else answer
        except ValueError:
            return False, 0.0
        cases = spec.get("cases") or []
        if not isinstance(mapping, Mapping) or not isinstance(cases, list) or not cases:
            return False, 0.0
        passed = 0
        for case in cases:
            key = str(case["input"])
            if key in mapping and mapping[key] == case["expected"]:
                passed += 1
        ok = passed == len(cases)
        return ok, round(passed / len(cases), 6)

    raise ValueError(f"Jenis evaluator tidak dikenal: {kind!r}")


def _run_evaluator(evaluator: Any, answer: Any) -> tuple[bool, float]:
    if callable(evaluator):
        res = evaluator(answer)
        if isinstance(res, bool):
            return res, (1.0 if res else 0.0)
        if isinstance(res, Mapping):
            ok = bool(res.get("passed"))
            score = float(res.get("score", 1.0 if ok else 0.0))
            return ok, round(score, 6)
        raise ValueError("Evaluator callable wajib mengembalikan bool atau dict")
    if isinstance(evaluator, Mapping):
        return _eval_declarative(evaluator, answer)
    raise ValueError("Evaluator tugas wajib berupa dict atau callable")


def _ast_has_nondeterminism(source: str) -> str | None:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return f"syntax_error:{exc.msg}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_mod = alias.name.split(".")[0]
                if root_mod in _NONDETERMINISTIC_MODULES:
                    return f"import:{alias.name}"
        elif isinstance(node, ast.ImportFrom) and node.module:
            root_mod = node.module.split(".")[0]
            if root_mod in _NONDETERMINISTIC_MODULES:
                return f"from_import:{node.module}"
        elif isinstance(node, ast.Attribute):
            if node.attr in _NONDETERMINISTIC_ATTRS:
                return f"attr:{node.attr}"
    return None


def _detect_prompt_leak(prompt: str, reference_answer: Any, forbidden_tokens: Sequence[str] = ()) -> list[str]:
    findings: list[str] = []
    if not prompt:
        return findings

    if isinstance(reference_answer, Mapping):
        ans_str = json.dumps(reference_answer, ensure_ascii=False, sort_keys=True)
    elif reference_answer is None:
        ans_str = ""
    else:
        ans_str = str(reference_answer).strip()

    if len(ans_str) >= 4:
        if ans_str in prompt:
            findings.append("verbatim_reference_in_prompt")
        elif ans_str.lower() in prompt.lower() and not ans_str.isdigit():
            findings.append("casefold_reference_in_prompt")

    # Cek pula nilai-nilai substansial dari jawaban berbentuk dict/test mapping.
    if isinstance(reference_answer, Mapping):
        for val in reference_answer.values():
            sval = str(val).strip()
            if len(sval) >= 5 and sval in prompt:
                findings.append(f"mapping_value_in_prompt:{sval}")

    # Untuk jawaban singkat sekalipun, tangkap label eksplisit "answer: <val>".
    if ans_str:
        for match in _LEAK_LABEL_RE.finditer(prompt):
            captured = match.group(1).strip().strip("'\"")
            if captured == ans_str:
                findings.append("explicit_answer_marker_in_prompt")
                break

    for tok in forbidden_tokens:
        stok = str(tok).strip()
        if stok and stok in prompt:
            findings.append(f"forbidden_token_in_prompt:{stok}")

    return list(dict.fromkeys(findings))


def validate_task(task: Mapping[str, Any], *, repeats: int = 3) -> dict[str, Any]:
    """Validasi satu tugas praktik dan kembalikan daftar temuan cacatnya."""
    task_id = str(task.get("id") or "")
    prompt = str(task.get("prompt") or "")
    issues: list[dict[str, Any]] = []

    if not task_id.strip():
        issues.append({"code": "missing_task_id", "detail": "id tugas wajib tak-kosong"})
    if not prompt.strip():
        issues.append({"code": "missing_prompt", "detail": "prompt tugas wajib tak-kosong"})

    has_ref = "reference_answer" in task or "reference_solution" in task
    ref_answer = task.get("reference_answer", task.get("reference_solution"))
    if not has_ref or ref_answer is None or (isinstance(ref_answer, str) and not ref_answer.strip()):
        issues.append({"code": "missing_reference_answer", "detail": "reference_answer wajib ada"})

    forbidden = task.get("leak_forbidden") or ()
    if has_ref and ref_answer is not None and prompt:
        leak_reasons = _detect_prompt_leak(prompt, ref_answer, forbidden)
        if leak_reasons:
            issues.append(
                {
                    "code": "answer_leak_in_prompt",
                    "detail": ", ".join(leak_reasons),
                }
            )

    eval_src = task.get("evaluator_source")
    if isinstance(eval_src, str) and eval_src.strip():
        nd_reason = _ast_has_nondeterminism(eval_src)
        if nd_reason:
            issues.append(
                {
                    "code": "nondeterministic_evaluator",
                    "detail": f"sumber evaluator terdeteksi tak deterministik ({nd_reason})",
                }
            )

    evaluator = task.get("evaluator")
    if evaluator is None:
        issues.append({"code": "missing_evaluator", "detail": "evaluator wajib ada"})
    elif has_ref and ref_answer is not None:
        try:
            outcomes = [_run_evaluator(evaluator, ref_answer) for _ in range(repeats)]
        except ValueError as exc:
            issues.append({"code": "invalid_evaluator", "detail": str(exc)})
            outcomes = []

        if outcomes:
            if len(set(outcomes)) > 1:
                issues.append(
                    {
                        "code": "nondeterministic_evaluator",
                        "detail": f"keluaran berubah antar pengulangan: {outcomes}",
                    }
                )
            first_ok, first_score = outcomes[0]
            if not first_ok:
                issues.append(
                    {
                        "code": "unsolvable_by_reference",
                        "detail": f"reference_answer gagal lolos evaluator (score={first_score})",
                    }
                )
            else:
                try:
                    wrong_ok, _ = _run_evaluator(evaluator, "__ACE_INVALID_PROBE_9999__")
                    if wrong_ok:
                        issues.append(
                            {
                                "code": "trivial_always_pass_evaluator",
                                "detail": "evaluator meloloskan probe jawaban salah",
                            }
                        )
                except ValueError:
                    pass

    # Validasi test_cases tambahan bila tersedia di objek tugas.
    test_cases = task.get("test_cases")
    if test_cases is not None:
        if not isinstance(test_cases, list) or not test_cases:
            issues.append({"code": "invalid_test_cases", "detail": "test_cases harus daftar tak-kosong"})
        elif isinstance(ref_answer, Mapping):
            for idx, case in enumerate(test_cases):
                if not isinstance(case, Mapping) or "input" not in case or "expected" not in case:
                    issues.append(
                        {"code": "malformed_test_case", "detail": f"test_cases[{idx}] tidak lengkap"}
                    )
                    break
                key = str(case["input"])
                if key not in ref_answer or ref_answer[key] != case["expected"]:
                    issues.append(
                        {
                            "code": "unsolvable_by_reference",
                            "detail": f"reference_answer tidak memenuhi test_cases[{idx}] ({key})",
                        }
                    )
                    break

    return {
        "id": task_id,
        "valid": len(issues) == 0,
        "issue_codes": [item["code"] for item in issues],
        "issues": issues,
    }


def validate_task_pack(tasks: Sequence[Mapping[str, Any]], *, repeats: int = 3) -> dict[str, Any]:
    """Validasi seluruh daftar tugas praktik hasil generator."""
    if not tasks:
        raise ValueError("Paket tugas tidak boleh kosong")
    results = [validate_task(task, repeats=repeats) for task in tasks]
    valid_count = sum(1 for row in results if row["valid"])
    invalid_ids = [row["id"] for row in results if not row["valid"]]
    return {
        "schema": SCHEMA,
        "summary": {
            "total_tasks": len(results),
            "valid_tasks": valid_count,
            "invalid_tasks": len(results) - valid_count,
            "all_valid": len(invalid_ids) == 0,
            "invalid_task_ids": invalid_ids,
        },
        "tasks": results,
    }


def _load_task_pack(path: Path) -> list[dict[str, Any]]:
    raw = Path(path).read_text(encoding="utf-8").strip()
    if not raw:
        raise ValueError(f"Berkas paket tugas kosong: {path}")
    if raw.startswith("["):
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("Paket JSON wajib berupa list")
        return [dict(item) for item in data]
    if raw.startswith("{") and "\n" not in raw:
        obj = json.loads(raw)
        if isinstance(obj, dict) and isinstance(obj.get("tasks"), list):
            return [dict(item) for item in obj["tasks"]]
        return [dict(obj)]
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validasi solvabilitas, determinisme evaluator, dan kebocoran jawaban paket tugas praktik."
    )
    parser.add_argument("--tasks", required=True, help="Path berkas paket tugas JSON/JSONL.")
    parser.add_argument("--repeats", type=int, default=3, help="Jumlah ulang evaluasi determinisme.")
    parser.add_argument("--out", help="Path output JSON opsional (default stdout).")
    args = parser.parse_args(argv)

    try:
        tasks = _load_task_pack(Path(args.tasks))
        report = validate_task_pack(tasks, repeats=args.repeats)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0 if report["summary"]["all_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
