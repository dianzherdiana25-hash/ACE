"""Fixture audit bundel lintas paket terpin + catatan cakupan & satuan per pasangan paket (Garis A4 Tranche 2)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.evo_results import compare_metrics, compare_package_matrix
from tools.seal_run import BUNDLE_MATRIX_SCHEMA, audit_bundle_matrix, seal_run


TOOLS = Path(__file__).resolve().parent


class EvoTranche2BundleAndScopeTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def _write(self, rel: str, content: str) -> Path:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    def test_cross_package_bundle_matrix_detects_every_corrupted_copy_mode(self):
        # Pack three distinct package run trees
        specs = []
        (self.root / "bundles").mkdir()
        for pkg in ("EVO_0004", "EVO_0005", "EVO_0006"):
            self._write(f"runs/{pkg}/metrics.json", json.dumps({"package": pkg, "score": 0.75}))
            self._write(f"runs/{pkg}/trace.log", f"{pkg}: done\n")
            packed = seal_run(self.root / f"runs/{pkg}", self.root / f"bundles/{pkg}")
            specs.append({
                "package": pkg,
                "bundle": f"bundles/{pkg}",
                "manifest_sha256": packed["manifest_sha256"],
            })

        clean_report = audit_bundle_matrix(specs, base_dir=self.root)
        self.assertEqual(clean_report["schema"], BUNDLE_MATRIX_SCHEMA)
        self.assertTrue(clean_report["all_valid"])
        self.assertEqual(clean_report["summary"], {"total_bundles": 3, "valid_count": 3, "failed_count": 0})

        # Now copy clean bundles into corrupted variants covering all 4 tamper modes + missing dir
        for idx, pkg in enumerate(("EVO_0004", "EVO_0005", "EVO_0006")):
            shutil.copytree(self.root / f"bundles/{pkg}", self.root / f"corrupt/{pkg}")

        # 1. Bit-flip in payload of EVO_0004
        target = self.root / "corrupt/EVO_0004/metrics.json"
        raw = bytearray(target.read_bytes())
        raw[-2] = ord("9") if raw[-2] != ord("9") else ord("8")
        target.write_bytes(bytes(raw))

        # 2. Tampered manifest.json vs pinned digest in EVO_0005
        mf5 = self.root / "corrupt/EVO_0005/manifest.json"
        mf5.write_bytes(mf5.read_bytes() + b"\n")

        # 3. Extra unmanifested file + missing expected file in EVO_0006
        (self.root / "corrupt/EVO_0006/extra_leak.txt").write_text("rogue\n", encoding="utf-8")
        (self.root / "corrupt/EVO_0006/trace.log").unlink()

        bad_specs = [
            {**specs[0], "bundle": "corrupt/EVO_0004"},
            {**specs[1], "bundle": "corrupt/EVO_0005"},
            {**specs[2], "bundle": "corrupt/EVO_0006"},
            {"package": "EVO_MISSING", "bundle": "corrupt/DOES_NOT_EXIST", "manifest_sha256": "0" * 64},
        ]
        corrupt_report = audit_bundle_matrix(bad_specs, base_dir=self.root)
        self.assertFalse(corrupt_report["all_valid"])
        self.assertEqual(corrupt_report["summary"], {"total_bundles": 4, "valid_count": 0, "failed_count": 4})

        by_pkg = {row["package"]: row for row in corrupt_report["bundles"]}
        self.assertFalse(by_pkg["EVO_0004"]["valid"])
        self.assertEqual(by_pkg["EVO_0004"]["modified"][0]["path"], "metrics.json")
        self.assertEqual(by_pkg["EVO_0005"]["reason"], "manifest_sha256_mismatch")
        self.assertEqual(by_pkg["EVO_0006"]["extra_files"], ["extra_leak.txt"])
        self.assertEqual(by_pkg["EVO_0006"]["missing"], ["trace.log"])
        self.assertEqual(by_pkg["EVO_MISSING"]["reason"], "corrupt_or_unreadable_bundle")

        # Verify CLI exit code 0 on clean matrix and 2 on corrupt matrix
        clean_spec_path = self._write("clean_matrix.json", json.dumps(specs))
        res_ok = subprocess.run(
            [sys.executable, str(TOOLS / "seal_run.py"), "audit-matrix", str(clean_spec_path)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(res_ok.returncode, 0, res_ok.stderr)

        bad_spec_path = self._write("bad_matrix.json", json.dumps(bad_specs))
        res_bad = subprocess.run(
            [sys.executable, str(TOOLS / "seal_run.py"), "audit-matrix", str(bad_spec_path)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(res_bad.returncode, 2)
        self.assertFalse(json.loads(res_bad.stdout)["all_valid"])

    def test_compare_matrix_persists_per_pair_scope_notes_and_guards_unit_mismatch(self):
        self._write(
            "docs/EVO_0004.md",
            "# KONSOLIDASI EVO 0004\n"
            "| total | 6/8 = 0.750 |\n"
            "| rate_pct | 75.0 |\n",
        )
        self._write(
            "docs/EVO_0005.md",
            "# KONSOLIDASI EVO 0005\n"
            "| total | 7/8 = 0.875 |\n"
            "| rate_prop | 0.875 |\n",
        )
        self._write(
            "docs/EVO_0006.md",
            "# KONSOLIDASI EVO 0006\n"
            "| total | 12/16 = 0.750 |\n"
            "| rate_prop | 0.750 |\n",
        )

        spec = [
            {
                "before": "docs/EVO_0004.md",
                "after": "docs/EVO_0005.md",
                "scope_notes": {
                    "population": "N=8 held-out famili S9.1",
                    "caveat": "Rate pada L3 EVO 0004 memakai persen, sedangkan EVO 0005 proporsi.",
                },
                "metrics": [
                    {
                        "name": "pass_proportion",
                        "unit": "proporsi",
                        "before": {"line": 2, "column": 2, "format": "equals_decimal"},
                        "after": {"line": 2, "column": 2, "format": "equals_decimal"},
                        "before_population": "N=8",
                        "after_population": "N=8",
                        "scope_note": "Populasi dan definisi rasio identik (N=8).",
                    },
                    {
                        "name": "rate_unit_mismatch",
                        "unit": "campuran",
                        "before_unit": "persen",
                        "after_unit": "proporsi",
                        "before": {"line": 3, "column": 2},
                        "after": {"line": 3, "column": 2},
                        "scope_note": "Satuan berbeda tidak boleh dikurangi langsung.",
                    },
                ],
            },
            {
                "before": "docs/EVO_0005.md",
                "after": "docs/EVO_0006.md",
                "scope_notes": {
                    "population": "N=8 -> N=16 (famili diperluas)",
                    "caveat": "Denominator berubah dari 8 ke 16; tandai incomparable.",
                },
                "metrics": [
                    {
                        "name": "pass_proportion_cross_pop",
                        "unit": "proporsi",
                        "comparable": False,
                        "before": {"line": 2, "column": 2, "format": "equals_decimal"},
                        "after": {"line": 2, "column": 2, "format": "equals_decimal"},
                        "before_population": "N=8",
                        "after_population": "N=16",
                        "scope_note": "Korpus berbeda; delta sengaja ditahan.",
                    }
                ],
            },
        ]

        matrix_file = self._write("matrix_spec.json", json.dumps(spec))
        cli = subprocess.run(
            [sys.executable, str(TOOLS / "evo_results.py"), "compare-matrix", str(matrix_file)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(cli.returncode, 0, cli.stderr)
        report = json.loads(cli.stdout)
        self.assertEqual(report["schema"], "ace.evo-metric-matrix.v1")
        self.assertEqual(report["pair_count"], 2)

        pair_45 = report["scope_notes_by_pair"]["EVO 0004 -> EVO 0005"]
        self.assertEqual(pair_45["pair_notes"]["population"], "N=8 held-out famili S9.1")
        notes_45 = {item["metric"]: item for item in pair_45["metric_notes"]}
        self.assertTrue(notes_45["pass_proportion"]["comparable"])
        self.assertFalse(notes_45["rate_unit_mismatch"]["comparable"])
        self.assertIn("unit_mismatch", notes_45["rate_unit_mismatch"]["incomparable_reason"])

        comp_by_pair = {item["package_pair"]: item for item in report["comparisons"]}
        metrics_45 = {m["name"]: m for m in comp_by_pair["EVO 0004 -> EVO 0005"]["metrics"]}
        self.assertEqual(metrics_45["pass_proportion"]["delta"], "0.125")
        self.assertIsNone(metrics_45["rate_unit_mismatch"]["delta"])

        metrics_56 = {m["name"]: m for m in comp_by_pair["EVO 0005 -> EVO 0006"]["metrics"]}
        self.assertIsNone(metrics_56["pass_proportion_cross_pop"]["delta"])
        self.assertEqual(
            metrics_56["pass_proportion_cross_pop"]["incomparable_reason"],
            "population_or_scope_mismatch",
        )


if __name__ == "__main__":
    unittest.main()
