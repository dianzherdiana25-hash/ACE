"""Tes papan skor kualitas dua organ dengan profil berlawanan (AG71)."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import organ_quality_board


class OrganQualityBoardTest(unittest.TestCase):
    def test_two_contrasting_organs_rates_and_weekly_trend(self) -> None:
        # Organ A ("groq-front"): minggu 1 (2026-W46) 1 ok + 1 fail (0.5),
        # minggu 2 (2026-W47) 2 ok + 0 fail (1.0) -> tren improving, mismatch 0%, gate_block 0%.
        # Organ B ("gemini-alt"): minggu 1 1 ok + 1 fail (0.5),
        # minggu 2 0 ok + 2 fail (0.0) + 2 blocked -> tren degrading, mismatch 75%, gate_block 33.3%.
        receipts = [
            {"task_id": "g-1", "organ": "groq-front", "status": "completed", "at": "2026-11-11T10:00:00Z"},
            {"task_id": "g-2", "organ": "groq-front", "status": "failed", "at": "2026-11-12T10:00:00Z"},
            {"task_id": "g-3", "organ": "groq-front", "status": "completed", "at": "2026-11-18T10:00:00Z"},
            {"task_id": "g-4", "organ": "groq-front", "status": "completed", "at": "2026-11-19T10:00:00Z"},
            {"task_id": "m-1", "organ": "gemini-alt", "status": "completed", "at": "2026-11-11T10:00:00Z"},
            {"task_id": "m-2", "organ": "gemini-alt", "status": "failed", "at": "2026-11-12T10:00:00Z"},
            {"task_id": "m-3", "organ": "gemini-alt", "status": "failed", "at": "2026-11-18T10:00:00Z"},
            {"task_id": "m-4", "organ": "gemini-alt", "status": "failed", "at": "2026-11-19T10:00:00Z"},
            {"task_id": "m-5", "organ": "gemini-alt", "status": "blocked", "gate_reason": "touches_money", "at": "2026-11-19T11:00:00Z"},
            {"task_id": "m-6", "organ": "gemini-alt", "status": "blocked", "gate_reason": "weak_based_on", "at": "2026-11-19T12:00:00Z"},
        ]
        grounding = [
            {"task_id": "g-1", "organ": "groq-front", "grounded": True, "mismatch_count": 0, "at": "2026-11-11T10:00:00Z"},
            {"task_id": "g-2", "organ": "groq-front", "grounded": True, "mismatch_count": 0, "at": "2026-11-12T10:00:00Z"},
            {"task_id": "g-3", "organ": "groq-front", "grounded": True, "mismatch_count": 0, "at": "2026-11-18T10:00:00Z"},
            {"task_id": "g-4", "organ": "groq-front", "grounded": True, "mismatch_count": 0, "at": "2026-11-19T10:00:00Z"},
            {"task_id": "m-1", "organ": "gemini-alt", "grounded": True, "mismatch_count": 0, "at": "2026-11-11T10:00:00Z"},
            {"task_id": "m-2", "organ": "gemini-alt", "grounded": False, "mismatch_count": 2, "at": "2026-11-12T10:00:00Z"},
            {"task_id": "m-3", "organ": "gemini-alt", "grounded": False, "mismatch_count": 1, "at": "2026-11-18T10:00:00Z"},
            {"task_id": "m-4", "organ": "gemini-alt", "grounded": False, "mismatch_count": 3, "at": "2026-11-19T10:00:00Z"},
        ]

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            r_path = root / "receipts.jsonl"
            g_path = root / "grounding.json"
            o_path = root / "board.json"
            r_path.write_text("\n".join(json.dumps(r) for r in receipts) + "\n", encoding="utf-8")
            g_path.write_text(json.dumps({"results": grounding}), encoding="utf-8")

            rc = organ_quality_board.main(
                ["--receipts", str(r_path), "--grounding", str(g_path), "--out", str(o_path)]
            )
            self.assertEqual(rc, 0)
            rep = json.loads(o_path.read_text(encoding="utf-8"))

        self.assertEqual(rep["schema"], organ_quality_board.SCHEMA)
        groq = rep["by_organ"]["groq-front"]
        gemini = rep["by_organ"]["gemini-alt"]

        self.assertAlmostEqual(groq["execution_success_rate"], 0.75, places=6)
        self.assertAlmostEqual(groq["grounding_mismatch_rate"], 0.0, places=6)
        self.assertAlmostEqual(groq["gate_block_rate"], 0.0, places=6)
        self.assertEqual(groq["trend_direction"], "improving")

        self.assertAlmostEqual(gemini["execution_success_rate"], 0.25, places=6)
        self.assertAlmostEqual(gemini["grounding_mismatch_rate"], 0.75, places=6)
        self.assertAlmostEqual(gemini["gate_block_rate"], 2 / 6, places=5)
        self.assertEqual(gemini["trend_direction"], "degrading")

        self.assertGreater(groq["execution_success_rate"], gemini["execution_success_rate"])
        self.assertLess(groq["grounding_mismatch_rate"], gemini["grounding_mismatch_rate"])
        self.assertEqual(len(groq["weekly_trend"]), 2)


if __name__ == "__main__":
    unittest.main()
