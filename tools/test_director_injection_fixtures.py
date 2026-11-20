"""Tes adversarial fixture untuk director_classes + memory_anchor (AG52)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools import director_injection_fixtures


class DirectorInjectionFixturesTest(unittest.TestCase):
    def test_zero_class_a_and_every_attack_stopped_by_named_guard(self) -> None:
        report = director_injection_fixtures.evaluate_injection_suite()
        self.assertEqual(report["schema"], director_injection_fixtures.SCHEMA)

        summary = report["summary"]
        self.assertGreaterEqual(summary["total_adversarial_proposals"], 4)
        self.assertEqual(summary["admitted_class_a_count"], 0)
        self.assertEqual(summary["admitted_class_a_ids"], [])
        self.assertTrue(summary["all_stopped"])

        vectors_seen = {row["attack_vector"] for row in report["results"]}
        self.assertEqual(
            vectors_seen,
            {
                "fake_evidence_claims",
                "fabricated_based_on",
                "hidden_instructions_in_rationale",
                "invented_gap_counts",
            },
        )

        for row in report["results"]:
            self.assertNotEqual(row["effective_class"], "A", msg=row["id"])
            self.assertTrue(row["stopped"], msg=row["id"])
            expected_guard = row["expected_stopped_by"]
            self.assertIn(
                expected_guard,
                row["guards_triggered"],
                msg=f"{row['id']} tidak dihentikan oleh guard {expected_guard!r}: {row['guards_triggered']}",
            )

    def test_cli_writes_fixtures_and_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_jsonl = root / "adversarial.jsonl"
            report_json = root / "report.json"

            rc = director_injection_fixtures.main(
                ["--out-fixtures", str(fixtures_jsonl), "--out", str(report_json)]
            )
            self.assertEqual(rc, 0)
            lines = [json.loads(ln) for ln in fixtures_jsonl.read_text(encoding="utf-8").splitlines() if ln.strip()]
            rep = json.loads(report_json.read_text(encoding="utf-8"))

        self.assertEqual(len(lines), rep["summary"]["total_adversarial_proposals"])
        self.assertEqual(rep["summary"]["admitted_class_a_count"], 0)


if __name__ == "__main__":
    unittest.main()
