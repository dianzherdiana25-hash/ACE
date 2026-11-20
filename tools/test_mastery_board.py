"""Tes papan penguasaan tiga domain (lengkap, parsial, kosong) (AG68)."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import mastery_board


class MasteryBoardTest(unittest.TestCase):
    def test_three_domains_complete_partial_and_empty_emit_belum_diketahui(self) -> None:
        fixture = {
            "coding": {
                "closure": 0.9,
                "transfer": 0.8,
                "retention": 0.85,
            },
            "language": {
                "closure": 0.8,
                "transfer": 0.7,
                # retention sengaja hilang!
            },
            "architecture": {},  # kosong total
        }

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            in_path = root / "domains.json"
            out_json = root / "mastery.json"
            out_md = root / "mastery.md"
            in_path.write_text(json.dumps(fixture), encoding="utf-8")

            rc = mastery_board.main(
                [
                    "--input",
                    str(in_path),
                    "--out-json",
                    str(out_json),
                    "--out-md",
                    str(out_md),
                ]
            )
            self.assertEqual(rc, 0)
            rep = json.loads(out_json.read_text(encoding="utf-8"))
            md = out_md.read_text(encoding="utf-8")

        self.assertEqual(rep["schema"], mastery_board.SCHEMA)
        self.assertEqual(rep["summary"]["complete_domains"], ["coding"])
        self.assertEqual(rep["summary"]["partial_domains"], ["language"])
        self.assertEqual(rep["summary"]["empty_domains"], ["architecture"])
        self.assertEqual(rep["summary"]["aggregate_mastery"], mastery_board.UNKNOWN)

        by_dom = {row["domain"]: row for row in rep["domains"]}
        self.assertAlmostEqual(by_dom["coding"]["mastery_score"], 0.855, places=6)
        self.assertEqual(by_dom["coding"]["missing_components"], [])

        # Domain parsial dan kosong MUST tampil "belum diketahui", BUKAN nol!
        self.assertEqual(by_dom["language"]["mastery_score"], mastery_board.UNKNOWN)
        self.assertNotEqual(by_dom["language"]["mastery_score"], 0)
        self.assertEqual(by_dom["language"]["missing_components"], ["retention"])

        self.assertEqual(by_dom["architecture"]["mastery_score"], mastery_board.UNKNOWN)
        self.assertEqual(
            by_dom["architecture"]["missing_components"],
            ["closure", "transfer", "retention"],
        )
        self.assertIn("| language | partial | belum diketahui | 0.8 | 0.7 | belum diketahui |", md)
        self.assertIn("| architecture | empty | belum diketahui |", md)


if __name__ == "__main__":
    unittest.main()
