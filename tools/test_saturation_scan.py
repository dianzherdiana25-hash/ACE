#!/usr/bin/env python3
"""Tes unit & CLI untuk `tools/saturation_scan.py` (Garis B2)."""
from __future__ import annotations

import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools import saturation_scan as ss


def _write_jsonl(path: Path, rows: list[dict | str]) -> Path:
    lines = [r if isinstance(r, str) else json.dumps(r, ensure_ascii=False) for r in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class TestSaturationScan(unittest.TestCase):
    def test_embedded_saturated_rows_and_group_recommendations(self) -> None:
        # 4 kelompok dengan perilaku kejenuhan berbeda-beda + baris invalid tertanam
        rows = [
            # Kelompok easy_lang: semua pasangan selalu lolos + menumpuk di pita 76-100 (ceiling saturated)
            {"id": "easy-1", "task_kind": "language", "group": "easy_lang", "ratified": True, "score": 92},
            {"id": "easy-1", "task_kind": "language", "group": "easy_lang", "ratified": True, "score": 94},
            {"id": "easy-2", "task_kind": "language", "group": "easy_lang", "ratified": True, "judge_score": 89},
            {"id": "easy-2", "task_kind": "language", "group": "easy_lang", "ratified": True, "judge_score": 90},
            {"id": "easy-3", "task_kind": "language", "group": "easy_lang", "ratified": True, "score": 96},
            {"id": "easy-3", "task_kind": "language", "group": "easy_lang", "ratified": True, "score": 97},
            # Kelompok broken_hard: semua pasangan selalu gagal + menumpuk di pita 0-39 (floor saturated)
            {"id": "hard-1", "task_kind": "code", "group": "broken_hard", "ratified": False, "score": 15},
            {"id": "hard-1", "task_kind": "code", "group": "broken_hard", "ratified": False, "score": 18},
            {"id": "hard-2", "task_kind": "code", "group": "broken_hard", "ratified": False, "score": 22},
            {"id": "hard-2", "task_kind": "code", "group": "broken_hard", "ratified": False, "score": 20},
            # Kelompok hardening_needed: 1 dari 2 always_pass (50%) -> HARDEN
            {"id": "mid-1", "task_kind": "language", "group": "hardening_needed", "ratified": True, "score": 82},
            {"id": "mid-1", "task_kind": "language", "group": "hardening_needed", "ratified": True, "score": 83},
            {"id": "mid-2", "task_kind": "language", "group": "hardening_needed", "ratified": True, "score": 66},
            {"id": "mid-2", "task_kind": "language", "group": "hardening_needed", "ratified": False, "score": 52},
            # Kelompok calibrated_band: pita tengah 45-75 membedakan -> KEEP_CALIBRATED
            {"id": "cal-1", "task_kind": "code", "group": "calibrated_band", "ratified": False, "score": 48},
            {"id": "cal-1", "task_kind": "code", "group": "calibrated_band", "ratified": True, "score": 71},
            {"id": "cal-2", "task_kind": "code", "group": "calibrated_band", "ratified": False, "score": 45},
            {"id": "cal-2", "task_kind": "code", "group": "calibrated_band", "ratified": True, "score": 68},
            # Baris error & score tidak sah wajib masuk invalid_rows
            {"id": "bad-err", "task_kind": "code", "group": "calibrated_band", "ratified": False, "error": "timeout"},
            {"id": "bad-bool-score", "task_kind": "code", "group": "calibrated_band", "ratified": True, "score": True},
            {"id": "bad-oob-score", "task_kind": "code", "group": "calibrated_band", "ratified": True, "score": 105},
            "{not valid json",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_jsonl(Path(tmp) / "screen.jsonl", rows)
            rep = ss.scan_saturation([p], group_by="group")

        summary = rep["summary"]
        self.assertEqual(summary["valid_rows"], 18)
        self.assertEqual(summary["invalid_rows"], 4)
        self.assertEqual(summary["always_pass_tasks"], 4)
        self.assertEqual(summary["always_fail_tasks"], 2)
        self.assertEqual(summary["split_tasks"], 3)

        stopped = {b["band"]: set(b["reasons"]) for b in rep["non_discriminating_bands"]}
        self.assertIn("76-100", stopped)
        self.assertIn("CEILING_SATURATED", stopped["76-100"])
        self.assertIn("0-39", stopped)
        self.assertIn("FLOOR_SATURATED", stopped["0-39"])
        self.assertNotIn("45-75", stopped)

        recs = rep["recommendations_by_group"]
        self.assertEqual(recs["easy_lang"]["action"], "RETIRE_EASY")
        self.assertEqual(recs["broken_hard"]["action"], "RECALIBRATE_OR_RETIRE_FAILING")
        self.assertEqual(recs["hardening_needed"]["action"], "HARDEN")
        self.assertEqual(recs["calibrated_band"]["action"], "KEEP_CALIBRATED")

    def test_gzip_input_and_validator_parsed_fallback(self) -> None:
        rows = [
            {"id": "task-1", "task_kind": "language", "validator": {"parsed": {"accept": True, "score": 88}}},
            {"id": "task-1", "task_kind": "language", "validator": {"parsed": {"accept": True, "score": 90}}},
            {"id": "task-2", "task_kind": "language", "status": "REJECT", "score": 30},
            {"id": "task-2", "task_kind": "language", "status": "REJECT", "score": 32},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            gz = Path(tmp) / "eval.jsonl.gz"
            with gzip.open(gz, "wt", encoding="utf-8") as fp:
                for row in rows:
                    fp.write(json.dumps(row) + "\n")
            rep = ss.scan_saturation([gz], group_by="task_kind")
        self.assertEqual(rep["summary"]["always_pass_tasks"], 1)
        self.assertEqual(rep["summary"]["always_fail_tasks"], 1)
        self.assertIn("language", rep["recommendations_by_group"])

    def test_read_only_scan_on_repo_evo0006_screen_archive(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        sc_code = repo_root / "evidence" / "evo0006" / "screen_code.jsonl"
        sc_lang = repo_root / "evidence" / "evo0006" / "screen_language.jsonl"
        self.assertTrue(sc_code.is_file() and sc_lang.is_file())
        rep = ss.scan_saturation([sc_code, sc_lang], group_by="task_kind")
        self.assertGreater(rep["summary"]["valid_rows"], 0)
        self.assertIn("code", rep["recommendations_by_group"])
        self.assertIn("language", rep["recommendations_by_group"])

    def test_cli_markdown_output_and_error_exit(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            in_path = _write_jsonl(
                Path(tmp) / "in.jsonl",
                [
                    {"id": "x-1", "task_kind": "code", "ratified": True, "score": 91},
                    {"id": "x-1", "task_kind": "code", "ratified": True, "score": 92},
                ],
            )
            md_out = Path(tmp) / "out.md"
            proc = subprocess.run(
                [sys.executable, "-m", "tools.saturation_scan", str(in_path), "--format", "markdown", "--output", str(md_out)],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("# Laporan Analisis Kejenuhan Judge", md_out.read_text(encoding="utf-8"))

            missing = subprocess.run(
                [sys.executable, "-m", "tools.saturation_scan", str(Path(tmp) / "nope.jsonl")],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(missing.returncode, 2)


if __name__ == "__main__":
    unittest.main()
