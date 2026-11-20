"""Pipa tempa perkakas terisolasi dari spesifikasi JSON hingga paket adopsi (AG81).

Membentuk modul implementasi serta berkas tesnya di dalam direktori tempa
terisolasi berdasarkan spesifikasi JSON (``name``, ``origin_gap``, ``io_contract``),
menjalankan audit statis AST terhadap impor/panggilan terlarang, mengeksekusi
tes terisolasi hanya jika audit statis bersih, lalu mengeluarkan paket adopsi
berstatus ``approved`` atau ``rejected`` beserta alasannya.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Sequence


SCHEMA = "ace.tool-forge.v1"
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        "subprocess",
        "socket",
        "http",
        "urllib",
        "requests",
        "ctypes",
        "importlib",
        "autonomous_engine",
        "secrets",
        "shutil",
    }
)
FORBIDDEN_CALLS = frozenset({"eval", "exec", "compile", "__import__", "system", "popen"})


def static_audit_source(source: str) -> list[str]:
    """Periksa kode Python dengan AST untuk mendeteksi impor atau panggilan terlarang."""
    findings: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"syntax_error:{exc.msg}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in FORBIDDEN_IMPORT_ROOTS or "autonomous_engine" in alias.name:
                    findings.append(f"forbidden_import:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            root = mod.split(".")[0]
            if root in FORBIDDEN_IMPORT_ROOTS or "autonomous_engine" in mod:
                findings.append(f"forbidden_import:{mod}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                findings.append(f"forbidden_call:{node.func.id}")
            elif isinstance(node.func, ast.Attribute) and node.func.attr in FORBIDDEN_CALLS:
                findings.append(f"forbidden_call:{node.func.attr}")
    return list(dict.fromkeys(findings))


def _render_module_source(spec: Mapping[str, Any]) -> str:
    name = str(spec["name"])
    origin_gap = str(spec["origin_gap"])
    extra_imports = spec.get("imports") or []
    import_lines = "\n".join(f"import {m}" for m in extra_imports)
    body = spec.get("body_code") or (
        "def run(payload):\n"
        "    if isinstance(payload, dict):\n"
        "        return {k: (v.strip().lower() if isinstance(v, str) else v) for k, v in sorted(payload.items())}\n"
        "    if isinstance(payload, str):\n"
        "        return payload.strip().lower()\n"
        "    return payload\n"
    )
    return (
        f'"""Perkakas tempaan {name} (asal gap: {origin_gap})."""\n\n'
        + (import_lines + "\n\n" if import_lines else "")
        + body.rstrip()
        + "\n"
    )


def _render_test_source(name: str, cases: Sequence[Mapping[str, Any]]) -> str:
    rendered_cases = json.dumps(list(cases), ensure_ascii=False)
    return (
        "import json\n"
        "import unittest\n"
        f"from {name} import run\n\n"
        f"_CASES = json.loads({rendered_cases!r})\n\n"
        "class ForgedToolTests(unittest.TestCase):\n"
        "    def test_io_contract_cases(self):\n"
        "        for case in _CASES:\n"
        "            self.assertEqual(run(case['input']), case['expected'])\n\n"
        "if __name__ == '__main__':\n"
        "    unittest.main()\n"
    )


def forge_tool(spec: Mapping[str, Any], *, forge_root: Path | None = None) -> dict[str, Any]:
    """Tempa perkakas dalam direktori terisolasi, audit statis + tes, dan keluarkan paket adopsi."""
    if not isinstance(spec, Mapping):
        raise ValueError("Spesifikasi tempa wajib berupa objek JSON")
    name = spec.get("name")
    origin_gap = spec.get("origin_gap")
    io_contract = spec.get("io_contract")
    if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
        raise ValueError(f"Nama perkakas tidak sah (wajib [a-z][a-z0-9_]{{1,40}}): {name!r}")
    if not isinstance(origin_gap, str) or not origin_gap.strip():
        raise ValueError("origin_gap wajib tak-kosong")
    if not isinstance(io_contract, Mapping) or not io_contract.get("inputs") or "output" not in io_contract:
        raise ValueError("io_contract wajib memuat 'inputs' dan 'output'")

    cases = spec.get("test_cases") or [{"input": {"Raw": " Hallo "}, "expected": {"Raw": "hallo"}}]
    module_src = _render_module_source(spec)
    test_src = _render_test_source(name, cases)

    def _run_in_dir(work_dir: Path) -> dict[str, Any]:
        isolated = work_dir / name
        isolated.mkdir(parents=True, exist_ok=True)
        mod_path = isolated / f"{name}.py"
        tst_path = isolated / f"test_{name}.py"
        mod_path.write_text(module_src, encoding="utf-8")
        tst_path.write_text(test_src, encoding="utf-8")

        audit_findings = static_audit_source(module_src)
        static_passed = len(audit_findings) == 0

        tests_executed = False
        tests_passed = False
        test_tail = ""
        reasons: list[str] = []

        if not static_passed:
            reasons.extend(audit_findings)
        else:
            tests_executed = True
            env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(isolated)}
            proc = subprocess.run(
                [sys.executable, "-m", "unittest", tst_path.name],
                cwd=str(isolated),
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
            )
            combined = (proc.stdout + "\n" + proc.stderr).strip()
            test_tail = combined.splitlines()[-1] if combined else ""
            tests_passed = proc.returncode == 0
            if not tests_passed:
                reasons.append(f"unit_tests_failed:returncode={proc.returncode}")

        approved = static_passed and tests_passed
        return {
            "schema": SCHEMA,
            "tool_name": name,
            "origin_gap": origin_gap.strip(),
            "io_contract": dict(io_contract),
            "static_audit": {
                "passed": static_passed,
                "findings": audit_findings,
            },
            "unit_tests": {
                "executed": tests_executed,
                "passed": tests_passed,
                "tail": test_tail,
            },
            "adoption_verdict": "approved" if approved else "rejected",
            "reasons": reasons if reasons else ["all_static_and_unit_checks_passed"],
            "artifacts": {
                "module_file": mod_path.name,
                "module_sha256": hashlib.sha256(module_src.encode("utf-8")).hexdigest(),
                "test_file": tst_path.name,
                "test_sha256": hashlib.sha256(test_src.encode("utf-8")).hexdigest(),
            },
        }

    if forge_root is not None:
        return _run_in_dir(Path(forge_root))
    with TemporaryDirectory(prefix="ace_tool_forge_") as tmp:
        return _run_in_dir(Path(tmp))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Tempa kerangka modul + tes di direktori terisolasi lalu audit paket adopsi."
    )
    parser.add_argument("--spec", required=True, help="Path spesifikasi perkakas JSON.")
    parser.add_argument("--forge-dir", help="Direktori terisolasi opsional untuk menulis artefak.")
    parser.add_argument("--out", help="Path output paket adopsi JSON.")
    args = parser.parse_args(argv)

    try:
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        bundle = forge_tool(spec, forge_root=Path(args.forge_dir) if args.forge_dir else None)
    except (OSError, json.JSONDecodeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        op = Path(args.out)
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0 if bundle["adoption_verdict"] == "approved" else 1


if __name__ == "__main__":
    raise SystemExit(main())
