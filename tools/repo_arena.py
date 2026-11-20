"""Arena praktik repo multi-berkas untuk simulasi latihan & verifikasi patch (AG67).

Membentuk repo fixture multi-berkas di direktori sementara terisolasi,
menerapkan patch referensi secara opsional (``mode=verify`` vs ``mode=practice``
tanpa patch), menjalankan setiap berkas tes secara terpisah, dan melaporkan
lulus/gagal per berkas tes dalam bentuk struktur laporan yang identik.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Sequence


SCHEMA = "ace.repo-arena.v1"
_RAN_RE = re.compile(r"Ran\s+(\d+)\s+tests?")


def default_arena_spec() -> dict[str, Any]:
    """Spesifikasi repo fixture multi-berkas mini bawaan (2 modul + 2 berkas tes)."""
    return {
        "arena_id": "mini-ledger-math-v1",
        "files": {
            "pkg/__init__.py": "",
            "pkg/dedup.py": (
                "def dedup_keys(items):\n"
                "    # Bug awal: lupa normalisasi huruf kecil/spasi sehingga duplikat terlewat.\n"
                "    return list(dict.fromkeys(items))\n"
            ),
            "pkg/tax.py": (
                "def compute_flat_fee(amount):\n"
                "    return int(round(amount * 0.05))\n"
            ),
            "tests/__init__.py": "",
            "tests/test_dedup.py": (
                "import unittest\n"
                "from pkg.dedup import dedup_keys\n\n"
                "class DedupTest(unittest.TestCase):\n"
                "    def test_case_insensitive_trim_dedup(self):\n"
                "        self.assertEqual(dedup_keys(['A', ' a ', 'B']), ['a', 'b'])\n"
            ),
            "tests/test_tax.py": (
                "import unittest\n"
                "from pkg.tax import compute_flat_fee\n\n"
                "class TaxTest(unittest.TestCase):\n"
                "    def test_fee(self):\n"
                "        self.assertEqual(compute_flat_fee(1000), 50)\n"
            ),
        },
        "reference_patch": {
            "pkg/dedup.py": (
                "def dedup_keys(items):\n"
                "    seen = []\n"
                "    for raw in items:\n"
                "        norm = raw.strip().lower()\n"
                "        if norm not in seen:\n"
                "            seen.append(norm)\n"
                "    return seen\n"
            )
        },
        "test_files": ["tests/test_dedup.py", "tests/test_tax.py"],
    }


def _safe_rel_path(root: Path, rel: str) -> Path:
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts or not p.parts:
        raise ValueError(f"Path relatif arena tidak aman: {rel!r}")
    resolved_root = root.resolve()
    target = (resolved_root / p).resolve()
    if not target.is_relative_to(resolved_root):
        raise ValueError(f"Path arena keluar dari root: {rel!r}")
    return target


def _apply_patch_map(repo_dir: Path, patch_spec: Any) -> None:
    if isinstance(patch_spec, Mapping):
        for rel, body in patch_spec.items():
            dest = _safe_rel_path(repo_dir, str(rel))
            dest.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(body, str):
                dest.write_text(body, encoding="utf-8")
            elif isinstance(body, Mapping) and "old" in body and "new" in body:
                cur = dest.read_text(encoding="utf-8")
                old = str(body["old"])
                if old not in cur:
                    raise ValueError(f"Patch substring tidak ditemukan di {rel}")
                dest.write_text(cur.replace(old, str(body["new"]), 1), encoding="utf-8")
            else:
                raise ValueError(f"Format patch tidak sah pada {rel!r}")
    else:
        raise ValueError("reference_patch wajib berupa mapping path -> isi/operasi")


def run_arena(
    spec: Mapping[str, Any],
    *,
    apply_patch: bool = True,
    timeout_s: int = 15,
) -> dict[str, Any]:
    """Bangun repo fixture, terapkan patch (bila verify), dan jalankan suite per file tes."""
    arena_id = str(spec.get("arena_id") or "arena-fixture")
    files = spec.get("files")
    test_files = spec.get("test_files")
    if not isinstance(files, Mapping) or not files:
        raise ValueError("Spesifikasi arena wajib memiliki mapping 'files'")
    if not isinstance(test_files, list) or not test_files:
        raise ValueError("Spesifikasi arena wajib memiliki daftar 'test_files'")

    with TemporaryDirectory(prefix="ace_repo_arena_") as tmp:
        repo_dir = Path(tmp)
        for rel, content in files.items():
            dest = _safe_rel_path(repo_dir, str(rel))
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(str(content), encoding="utf-8")

        if apply_patch:
            ref_patch = spec.get("reference_patch")
            if ref_patch is None:
                raise ValueError("Mode verify memerlukan 'reference_patch'")
            _apply_patch_map(repo_dir, ref_patch)

        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(repo_dir)}
        results: list[dict[str, Any]] = []
        passed_files = 0

        for rel_test in test_files:
            rel_str = str(rel_test)
            _safe_rel_path(repo_dir, rel_str)
            proc = subprocess.run(
                [sys.executable, "-m", "unittest", rel_str],
                cwd=str(repo_dir),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            combined_out = (proc.stdout + "\n" + proc.stderr).strip()
            m = _RAN_RE.search(combined_out)
            tests_ran = int(m.group(1)) if m else 0
            ok = proc.returncode == 0
            if ok:
                passed_files += 1
            results.append(
                {
                    "file": rel_str,
                    "passed": ok,
                    "status": "PASS" if ok else "FAIL",
                    "returncode": proc.returncode,
                    "tests_ran": tests_ran,
                    "output_tail": combined_out.splitlines()[-1] if combined_out else "",
                }
            )

    total_files = len(results)
    return {
        "schema": SCHEMA,
        "arena_id": arena_id,
        "mode": "verify" if apply_patch else "practice",
        "patch_applied": apply_patch,
        "all_passed": passed_files == total_files,
        "summary": {
            "total_test_files": total_files,
            "passed_files": passed_files,
            "failed_files": total_files - passed_files,
            "pass_rate": round(passed_files / total_files, 6),
        },
        "test_files": results,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Jalankan arena praktik repo multi-berkas dalam mode verify atau practice."
    )
    parser.add_argument("--spec", help="Path JSON spesifikasi repo arena opsional (default: fixture bawaan).")
    parser.add_argument(
        "--mode",
        choices=("verify", "practice"),
        default="verify",
        help="verify: terapkan patch referensi; practice: jalankan tanpa patch.",
    )
    parser.add_argument("--out", help="Path output JSON opsional (default stdout).")
    args = parser.parse_args(argv)

    try:
        spec = (
            json.loads(Path(args.spec).read_text(encoding="utf-8"))
            if args.spec
            else default_arena_spec()
        )
        report = run_arena(spec, apply_patch=(args.mode == "verify"))
    except (OSError, json.JSONDecodeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        op = Path(args.out)
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
