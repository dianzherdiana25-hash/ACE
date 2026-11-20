"""Tes regresi fixture-only untuk tools.verdict_board (AG56)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools import verdict_board


class VerdictBoardTest(unittest.TestCase):
    def test_complete_board_renders_all_five_gates_without_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ev_dir = Path(tmp) / "evidence"
            ev_dir.mkdir()
            for gate in ("G1", "G2", "G3", "G4", "G5"):
                (ev_dir / f"{gate}.json").write_text(
                    json.dumps(
                        {
                            "gate": gate,
                            "status": "PASS",
                            "evidence_pointer": f"evidence/{gate.lower()}_verified.json",
                            "measured_date": "2026-11-20",
                        }
                    ),
                    encoding="utf-8",
                )

            out_md = Path(tmp) / "board.md"
            out_json = Path(tmp) / "board.json"
            rc = verdict_board.main(
                [
                    "--evidence-dir",
                    str(ev_dir),
                    "--out-md",
                    str(out_md),
                    "--out-json",
                    str(out_json),
                ]
            )
            self.assertEqual(rc, 0)
            board = json.loads(out_json.read_text(encoding="utf-8"))
            md = out_md.read_text(encoding="utf-8")

        self.assertEqual(board["schema"], verdict_board.SCHEMA)
        self.assertEqual(board["summary"]["board_verdict"], "PASS")
        self.assertEqual(board["summary"]["known_gates"], 5)
        self.assertEqual(board["summary"]["missing_gates"], [])
        self.assertTrue(board["summary"]["all_gates_measured"])
        self.assertNotIn(verdict_board.UNKNOWN, md)
        self.assertIn("| G1 | PASS | evidence/g1_verified.json | 2026-11-20 |", md)

    def test_board_with_two_missing_gates_emits_belum_diketahui_never_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ev_dir = Path(tmp) / "partial_ev"
            ev_dir.mkdir()
            # Hanya G1, G3, G5 ada (G2 absen total, G4 mengklaim PASS tanpa evidence_pointer -> ditolak sebagai belum diketahui).
            (ev_dir / "G1.json").write_text(
                json.dumps(
                    {
                        "gate": "G1",
                        "status": "PASS",
                        "evidence_pointer": "evidence/g1_ok.json",
                        "measured_date": "2026-11-20",
                    }
                ),
                encoding="utf-8",
            )
            (ev_dir / "G3.json").write_text(
                json.dumps(
                    {
                        "gate": "G3",
                        "status": "HOLD",
                        "evidence_pointer": "evidence/g3_hold.json",
                        "measured_date": "2026-11-19",
                    }
                ),
                encoding="utf-8",
            )
            (ev_dir / "G4.json").write_text(
                json.dumps(
                    {
                        "gate": "G4",
                        "status": "PASS",
                        "evidence_pointer": "",
                        "measured_date": "2026-11-20",
                    }
                ),
                encoding="utf-8",
            )
            (ev_dir / "G5.json").write_text(
                json.dumps(
                    {
                        "gate": "G5",
                        "status": "PASS",
                        "evidence_pointer": "evidence/g5_ok.json",
                        "measured_date": "2026-11-18",
                    }
                ),
                encoding="utf-8",
            )

            paths = verdict_board.discover_gate_files(ev_dir)
            board = verdict_board.assemble_verdict_board(paths)
            md = verdict_board.render_verdict_board_markdown(board)

        self.assertEqual(board["summary"]["board_verdict"], "INCOMPLETE")
        self.assertNotEqual(board["summary"]["board_verdict"], "PASS")
        self.assertEqual(board["summary"]["missing_gates"], ["G2", "G4"])
        self.assertFalse(board["summary"]["all_gates_measured"])

        by_gate = {row["gate"]: row for row in board["gates"]}
        self.assertEqual(by_gate["G2"]["status"], verdict_board.UNKNOWN)
        self.assertEqual(by_gate["G2"]["evidence_pointer"], verdict_board.UNKNOWN)
        self.assertEqual(by_gate["G4"]["status"], verdict_board.UNKNOWN)
        self.assertIn("| G2 | belum diketahui | belum diketahui | belum diketahui |", md)
        self.assertIn("| G4 | belum diketahui | belum diketahui | 2026-11-20 |", md)


if __name__ == "__main__":
    unittest.main()
