#!/usr/bin/env python3
"""Tes unit & CLI untuk `tools/eval_bench.py` (Garis B4)."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools import eval_bench as eb


class TestEvalBenchB4(unittest.TestCase):
    def test_introspective_qa_against_real_handover_requires_valid_pointers(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        handover = repo_root / "handover"
        items = list(eb.DEFAULT_HANDOVER_QA_ITEMS)
        auto_res = eb.evaluate_introspective_qa(items, handover, base_root=repo_root)
        self.assertEqual(auto_res["passed"], len(items))
        self.assertEqual(auto_res["pointer_compliance_rate"], 1.0)

        # Jawaban tanpa pointer berkas sumber atau pointer palsu wajib ditolak
        bad_answers = {
            "qa-evo0006-verdict": {"answer": "Vonisnya INSTRUMEN_TIDAK_CUKUP karena probe set kecil."},
            "qa-evo0005-prereg": {
                "answer": "Preregistrasi #247 dan mesin #246.",
                "source_pointers": ["handover/BERKAS_TIDAK_ADA_PALSU.md"],
            },
            "qa-governance-rules": {
                "answer": "Dicatat 15 November 2026 berisi Dua aturan tetap.",
                "source_pointers": ["handover/EVO_0006_KONSOLIDASI_20261117.md"],  # sumber salah
            },
        }
        bad_res = eb.evaluate_introspective_qa(items, handover, answers_by_id=bad_answers, base_root=repo_root)
        self.assertEqual(bad_res["passed"], 0)
        reasons_by_id = {r["id"]: r["reasons"] for r in bad_res["results"]}
        self.assertIn("MISSING_SOURCE_POINTER", reasons_by_id["qa-evo0006-verdict"])
        self.assertIn("BROKEN_SOURCE_POINTER", reasons_by_id["qa-evo0005-prereg"])
        self.assertIn("WRONG_SOURCE_POINTER", reasons_by_id["qa-governance-rules"])

    def test_cross_organ_consistency_disagreement_report(self) -> None:
        rows = [
            # Tugas t-1: sepakat lulus antar 3 organ, delta skor kecil
            {"id": "t-1", "task_kind": "code", "organ": "front", "ratified": True, "score": 82},
            {"id": "t-1", "task_kind": "code", "organ": "coder", "ratified": True, "score": 85},
            {"id": "t-1", "task_kind": "code", "organ": "gonka", "ratified": True, "score": 80},
            # Tugas t-2: ketidaksepakatan putusan & selisih skor 35 > 15
            {"id": "t-2", "task_kind": "language", "organ": "front", "ratified": True, "score": 78},
            {"id": "t-2", "task_kind": "language", "organ": "gonka", "ratified": False, "score": 43},
            # Tugas t-3: satu organ saja (tidak dibandingkan) + 1 baris rusak
            {"id": "t-3", "task_kind": "code", "organ": "front", "ratified": True, "score": 90},
            {"id": "t-bad", "task_kind": "code", "organ": "front", "error": "timeout"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            res_file = Path(tmp) / "multi_organ.jsonl"
            res_file.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
            co = eb.evaluate_cross_organ_consistency([res_file], score_delta_threshold=15.0)

        self.assertEqual(co["comparable_tasks"], 2)
        self.assertEqual(co["verdict_disagreement_count"], 1)
        self.assertEqual(co["score_disagreement_count"], 1)
        self.assertAlmostEqual(co["overall_verdict_agreement_rate"], 0.5)
        self.assertEqual(co["verdict_disagreements"][0]["id"], "t-2")
        self.assertEqual(co["pairwise_agreement"]["front vs gonka"]["agreed"], 1)
        self.assertEqual(co["pairwise_agreement"]["front vs gonka"]["total"], 2)

    def test_format_regression_clean_baseline_and_detects_drift(self) -> None:
        # 1. Baseline perkakas nyata repo harus 100% CLEAN
        clean = eb.evaluate_format_regression()
        self.assertTrue(clean["all_clean"], clean)
        self.assertGreaterEqual(clean["tools_checked"], 6)

        # 2. Mutasi tak terduga (kunci hilang, bool menggantikan int, schema berubah) wajib terdeteksi
        drifted = eb.evaluate_format_regression(
            [
                {
                    "tool": "tools.broken_sim",
                    "payload": {"schema": "wrong.v2", "total_lines": True},
                    "required_keys": {"schema": "str", "total_lines": "int", "corpora": "list"},
                    "schema_value": "ace.frozen-corpus-registry.v1",
                    "markdown": "no table here",
                    "markdown_contains": ["| Arm |"],
                }
            ]
        )
        self.assertFalse(drifted["all_clean"])
        drifts = drifted["results"][0]["drifts"]
        self.assertIn("MISSING_KEY:corpora", drifts)
        self.assertIn("TYPE_MISMATCH:total_lines:expected_int_got_bool", drifts)
        self.assertIn("SCHEMA_MISMATCH:expected_ace.frozen-corpus-registry.v1_got_wrong.v2", drifts)
        self.assertIn("MARKDOWN_ANCHOR_MISSING:| Arm |", drifts)

    def test_cli_all_benches_end_to_end(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            organ_p = Path(tmp) / "organs.jsonl"
            organ_p.write_text(
                "\n".join(
                    [
                        json.dumps({"id": "e-1", "task_kind": "code", "pair": {"proposer": "coder", "validator": "front"}, "ratified": True, "score": 80}),
                        json.dumps({"id": "e-1", "task_kind": "code", "pair": {"proposer": "coder", "validator": "gonka"}, "ratified": True, "score": 82}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            out_p = Path(tmp) / "bench_report.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tools.eval_bench",
                    "--cross-organ-results",
                    str(organ_p),
                    "--output",
                    str(out_p),
                ],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            report = json.loads(out_p.read_text(encoding="utf-8"))
            self.assertTrue(report["overall_passed"])
            self.assertEqual(report["introspective_qa"]["passed"], 3)
            self.assertEqual(report["cross_organ_consistency"]["verdict_agreed_tasks"], 1)
            self.assertTrue(report["format_regression"]["all_clean"])

            bad_cli = subprocess.run(
                [sys.executable, "-m", "tools.eval_bench", "--handover-dir", str(Path(tmp) / "missing_dir")],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(bad_cli.returncode, 2)


if __name__ == "__main__":
    unittest.main()
