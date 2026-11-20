"""Tes pembangkit tugas praktik dari fingerprint kegagalan + validator AG46 (AG65)."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import failure_taskgen, practice_task_validator


class FailureTaskgenTest(unittest.TestCase):
    def test_three_valid_fingerprints_accepted_and_one_defective_rejected(self) -> None:
        fingerprints = [
            {
                "fingerprint_id": "fp-csv-dup",
                "family": "csv_dedup",
                "symptom": "case_folded_key_collision",
                "cases": [
                    {"input": "Alpha,alpha", "expected": "Alpha"},
                    {"input": "b,B,c", "expected": "b,c"},
                ],
            },
            {
                "fingerprint_id": "fp-tax-bracket",
                "family": "progressive_tax",
                "symptom": "top_bracket_overflow",
                "cases": [
                    {"input": "100000000", "expected": 10000000},
                ],
            },
            {
                "fingerprint_id": "fp-bfs-hop",
                "family": "bfs",
                "symptom": "cycle_infinite_loop",
                "expected": "2_hops_reachable",
            },
            # Fingerprint cacat: jawaban acuan tidak memenuhi expected test case (unsolvable!).
            {
                "fingerprint_id": "fp-defective-unsolvable",
                "family": "json_parser",
                "symptom": "contradictory_ground_truth",
                "cases": [{"input": "row1", "expected": "ok"}],
                "override_reference_answer": {"row1": "WRONG_VALUE"},
            },
        ]

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            fp_file = root / "fps.jsonl"
            tasks_out = root / "accepted_tasks.jsonl"
            report_out = root / "report.json"
            fp_file.write_text(
                "\n".join(json.dumps(fp) for fp in fingerprints) + "\n", encoding="utf-8"
            )

            rc = failure_taskgen.main(
                [
                    "--fingerprints",
                    str(fp_file),
                    "--out-tasks",
                    str(tasks_out),
                    "--out",
                    str(report_out),
                ]
            )
            self.assertEqual(rc, 0)
            rep = json.loads(report_out.read_text(encoding="utf-8"))

            # Seluruh tugas yang lolos wajib benar-benar lulus CLI practice_task_validator (exit 0).
            self.assertEqual(
                practice_task_validator.main(["--tasks", str(tasks_out)]),
                0,
            )

        self.assertEqual(rep["schema"], failure_taskgen.SCHEMA)
        self.assertEqual(rep["summary"]["input_fingerprints"], 4)
        self.assertEqual(rep["summary"]["accepted_count"], 3)
        self.assertEqual(rep["summary"]["rejected_count"], 1)

        accepted_ids = [t["fingerprint_id"] for t in rep["accepted_tasks"]]
        self.assertEqual(accepted_ids, ["fp-csv-dup", "fp-tax-bracket", "fp-bfs-hop"])

        rejected = rep["rejected_fingerprints"][0]
        self.assertEqual(rejected["fingerprint_id"], "fp-defective-unsolvable")
        self.assertEqual(rejected["reason"], "failed_practice_task_validator")
        self.assertIn("unsolvable_by_reference", rejected["issue_codes"])


if __name__ == "__main__":
    unittest.main()
