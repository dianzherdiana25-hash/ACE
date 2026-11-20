"""Tes regresi fixture-only untuk tools.capability_report (AG40)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools import capability_report


class CapabilityReportTest(unittest.TestCase):
    def test_complete_fixture_renders_markdown_and_json(self) -> None:
        gate_board = {
            "subject": "ace-main-fixture",
            "measured_at": "2026-11-20",
            "gates": {
                "G1": {
                    "status": "PASS",
                    "evidence": "evidence/g1_fix.json",
                    "measured_at": "2026-11-19",
                },
                "G2": {
                    "status": "PASS",
                    "evidence": "evidence/g2_fix.json",
                    "measured_at": "2026-11-20",
                },
                "G3": {
                    "status": "WARN",
                    "evidence": "evidence/g3_fix.json",
                    "measured_at": "2026-11-20",
                },
                "G4": {
                    "status": "PASS",
                    "evidence": "evidence/g4_fix.json",
                    "measured_at": "2026-11-18",
                },
                "G5": {
                    "status": "HOLD",
                    "evidence": "evidence/g5_fix.json",
                    "measured_at": "2026-11-20",
                },
            },
        }
        store_stats = {
            "gaps": {"open": 2, "closed": 8, "total": 10},
            "execution": {"executed": 20, "succeeded": 17, "failed": 3},
        }

        report = capability_report.build_capability_report(gate_board, store_stats)
        self.assertEqual(report["schema"], capability_report.SCHEMA)
        self.assertTrue(report["completeness"]["all_known"])
        self.assertEqual(report["completeness"]["unknown_count"], 0)
        self.assertEqual(report["gaps"], {"open": 2, "closed": 8, "total": 10})
        self.assertEqual(report["execution"]["execution_rate"], 0.85)
        self.assertNotIn(capability_report.UNKNOWN, json.dumps(report))

        md = capability_report.render_markdown(report)
        self.assertIn("# Laporan Kapabilitas ACE", md)
        self.assertIn("| G1 | PASS | evidence/g1_fix.json | 2026-11-19 |", md)
        self.assertIn("85.0% (0.85)", md)
        self.assertNotIn(capability_report.UNKNOWN, md)

    def test_incomplete_fixture_marks_missing_fields_belum_diketahui(self) -> None:
        gate_board = {
            "gates": {
                "G1": {"status": "PASS", "evidence": "evidence/g1_only.json"},
                "G2": {"status": "FAIL"},  # evidence hilang
                "G3": {},  # status & evidence hilang
                # G4 & G5 absen total
            }
        }
        # gaps.open dan gaps.total hilang, execution_rate tidak bisa dihitung
        store_stats = {
            "gaps": {"closed": 0},
            "execution": {"executed": 0, "failed": 0},
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            board_path = root / "board.json"
            stats_path = root / "stats.json"
            out_json = root / "cap.json"
            out_md = root / "cap.md"
            board_path.write_text(json.dumps(gate_board), encoding="utf-8")
            stats_path.write_text(json.dumps(store_stats), encoding="utf-8")

            rc = capability_report.main(
                [
                    "--gate-board",
                    str(board_path),
                    "--store-stats",
                    str(stats_path),
                    "--out-json",
                    str(out_json),
                    "--out-md",
                    str(out_md),
                ]
            )
            self.assertEqual(rc, 0)

            report = json.loads(out_json.read_text(encoding="utf-8"))
            md = out_md.read_text(encoding="utf-8")

        gates_by_id = {row["gate"]: row for row in report["gates"]}
        self.assertEqual(gates_by_id["G1"]["status"], "PASS")
        self.assertEqual(gates_by_id["G2"]["evidence"], capability_report.UNKNOWN)
        self.assertEqual(gates_by_id["G3"]["status"], capability_report.UNKNOWN)
        self.assertEqual(gates_by_id["G4"]["status"], capability_report.UNKNOWN)
        self.assertEqual(gates_by_id["G5"]["evidence"], capability_report.UNKNOWN)

        self.assertEqual(report["gaps"]["closed"], 0)
        self.assertEqual(report["gaps"]["open"], capability_report.UNKNOWN)
        self.assertEqual(report["gaps"]["total"], capability_report.UNKNOWN)
        self.assertEqual(report["execution"]["executed"], 0)
        self.assertEqual(report["execution"]["succeeded"], capability_report.UNKNOWN)
        self.assertEqual(report["execution"]["execution_rate"], capability_report.UNKNOWN)
        self.assertFalse(report["completeness"]["all_known"])
        self.assertIn("execution.execution_rate", report["unknown_fields"])
        self.assertIn("gaps.open", report["unknown_fields"])
        self.assertIn(capability_report.UNKNOWN, md)
        self.assertNotIn("0.0%", md)


if __name__ == "__main__":
    unittest.main()
