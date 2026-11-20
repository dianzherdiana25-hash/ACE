"""Tes regresi fixture-only untuk tools.practice_task_validator (AG46)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools import practice_task_validator


class PracticeTaskValidatorTest(unittest.TestCase):
    def test_valid_leaky_unsolvable_and_nondeterministic_fixtures(self) -> None:
        valid_task = {
            "id": "prac-valid-tax",
            "family": "progressive_tax",
            "prompt": "Hitung total pajak progresif atas penghasilan kena pajak Rp 100.000.000.",
            "reference_answer": "10000000",
            "evaluator": {"kind": "exact_match", "expected": "10000000"},
        }
        leaky_task = {
            "id": "prac-leaky-json",
            "family": "json_parser",
            "prompt": 'Ekstrak field "status" (answer: "verified_green_ok") dari objek payload.',
            "reference_answer": "verified_green_ok",
            "evaluator": {"kind": "exact_match", "expected": "verified_green_ok"},
        }
        unsolvable_task = {
            "id": "prac-unsolvable-bfs",
            "family": "bfs",
            "prompt": "Temukan jarak terpendek dari simpul A ke simpul D pada graf berarah.",
            "reference_answer": "99",
            "evaluator": {"kind": "exact_match", "expected": "3"},
        }

        calls = {"n": 0}

        def flaky_eval(_answer: str) -> bool:
            calls["n"] += 1
            return (calls["n"] % 2) == 1

        nondet_task = {
            "id": "prac-nondet-lru",
            "family": "lru",
            "prompt": "Kembalikan urutan kunci paling baru di cache LRU setelah 3 operasi get/put.",
            "reference_answer": "k3,k1",
            "evaluator": flaky_eval,
        }

        report = practice_task_validator.validate_task_pack(
            [valid_task, leaky_task, unsolvable_task, nondet_task]
        )
        self.assertEqual(report["schema"], practice_task_validator.SCHEMA)
        self.assertEqual(report["summary"]["total_tasks"], 4)
        self.assertEqual(report["summary"]["valid_tasks"], 1)
        self.assertEqual(report["summary"]["invalid_tasks"], 3)
        self.assertFalse(report["summary"]["all_valid"])

        by_id = {row["id"]: row for row in report["tasks"]}
        self.assertTrue(by_id["prac-valid-tax"]["valid"])
        self.assertEqual(by_id["prac-valid-tax"]["issue_codes"], [])

        self.assertFalse(by_id["prac-leaky-json"]["valid"])
        self.assertIn("answer_leak_in_prompt", by_id["prac-leaky-json"]["issue_codes"])

        self.assertFalse(by_id["prac-unsolvable-bfs"]["valid"])
        self.assertIn("unsolvable_by_reference", by_id["prac-unsolvable-bfs"]["issue_codes"])

        self.assertFalse(by_id["prac-nondet-lru"]["valid"])
        self.assertIn("nondeterministic_evaluator", by_id["prac-nondet-lru"]["issue_codes"])

    def test_cli_exits_0_when_pack_clean_and_1_when_defective(self) -> None:
        clean_pack = [
            {
                "id": "t-dedup",
                "family": "csv_dedup",
                "prompt": "Hilangkan baris duplikat berdasarkan kolom id sambil mempertahankan urutan.",
                "reference_answer": {"case_1": "a,b"},
                "test_cases": [{"input": "case_1", "expected": "a,b"}],
                "evaluator": {
                    "kind": "test_cases_exact",
                    "cases": [{"input": "case_1", "expected": "a,b"}],
                },
            }
        ]
        bad_pack = [
            {
                "id": "t-rng-source",
                "family": "security_detector",
                "prompt": "Deteksi pola SQL injection tanpa membocorkan kunci.",
                "reference_answer": "DETECTED",
                "evaluator_source": "import random\ndef score(x): return random.choice([True, False])\n",
                "evaluator": {"kind": "exact_match", "expected": "DETECTED"},
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clean_file = root / "clean.jsonl"
            bad_file = root / "bad.jsonl"
            out_file = root / "out.json"
            clean_file.write_text(json.dumps(clean_pack[0]) + "\n", encoding="utf-8")
            bad_file.write_text(json.dumps(bad_pack[0]) + "\n", encoding="utf-8")

            rc_clean = practice_task_validator.main(
                ["--tasks", str(clean_file), "--out", str(out_file)]
            )
            self.assertEqual(rc_clean, 0)
            self.assertTrue(json.loads(out_file.read_text(encoding="utf-8"))["summary"]["all_valid"])

            rc_bad = practice_task_validator.main(
                ["--tasks", str(bad_file), "--out", str(out_file)]
            )
            self.assertEqual(rc_bad, 1)
            bad_rep = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertIn(
                "nondeterministic_evaluator",
                bad_rep["tasks"][0]["issue_codes"],
            )


if __name__ == "__main__":
    unittest.main()
