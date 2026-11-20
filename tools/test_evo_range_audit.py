"""Tes regresi fixture-only untuk tools.evo_range_audit (AG57)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools import evo_range_audit


class EvoRangeAuditTest(unittest.TestCase):
    def test_mini_evo_tree_complete_partial_and_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            handover = root / "handover"
            handover.mkdir(parents=True)
            (root / "evidence" / "evo0017").mkdir(parents=True)
            (root / "evidence" / "evo0018").mkdir(parents=True)

            # EVO 0017: complete — dokumen desain ada dan kedua file bukti ada.
            (root / "evidence" / "evo0017" / "probe.json").write_text("{}", encoding="utf-8")
            (root / "evidence" / "evo0017" / "verdict.json").write_text("{}", encoding="utf-8")
            (handover / "RANCANGAN_EVO_0017.md").write_text(
                "# EVO 0017\n"
                "- Bukti 1: `evidence/evo0017/probe.json`\n"
                "- Bukti 2: [verdict](evidence/evo0017/verdict.json)\n",
                encoding="utf-8",
            )

            # EVO 0018: partial — dokumen desain ada, 1 bukti ada dan 1 bukti hilang.
            (root / "evidence" / "evo0018" / "found.json").write_text("{}", encoding="utf-8")
            (handover / "RANCANGAN_EVO_0018.md").write_text(
                "# EVO 0018\n"
                "- Bukti 1: `evidence/evo0018/found.json`\n"
                "- Bukti 2: `evidence/evo0018/missing_step.json`\n",
                encoding="utf-8",
            )

            # EVO 0019: missing — tidak ada dokumen desain sama sekali.

            out_json = root / "audit.json"
            out_md = root / "audit.md"
            rc = evo_range_audit.main(
                [
                    "--root",
                    str(root),
                    "--start",
                    "0017",
                    "--end",
                    "0019",
                    "--out-json",
                    str(out_json),
                    "--out-md",
                    str(out_md),
                ]
            )
            self.assertEqual(rc, 0)
            rep = json.loads(out_json.read_text(encoding="utf-8"))
            md = out_md.read_text(encoding="utf-8")

        self.assertEqual(rep["schema"], evo_range_audit.SCHEMA)
        self.assertEqual(rep["summary"]["total_evos"], 3)
        self.assertEqual(rep["summary"]["complete_evos"], ["EVO-0017"])
        self.assertEqual(rep["summary"]["partial_evos"], ["EVO-0018"])
        self.assertEqual(rep["summary"]["missing_evos"], ["EVO-0019"])

        by_evo = {row["evo"]: row for row in rep["rows"]}
        self.assertEqual(by_evo["EVO-0017"]["status"], "complete")
        self.assertEqual(by_evo["EVO-0017"]["missing_evidence"], [])

        self.assertEqual(by_evo["EVO-0018"]["status"], "partial")
        self.assertEqual(by_evo["EVO-0018"]["existing_evidence"], ["evidence/evo0018/found.json"])
        self.assertEqual(
            by_evo["EVO-0018"]["missing_evidence"], ["evidence/evo0018/missing_step.json"]
        )

        self.assertEqual(by_evo["EVO-0019"]["status"], "missing")
        self.assertEqual(by_evo["EVO-0019"]["design_docs"], [])

        self.assertIn("# Audit Kelengkapan Rentang EVO 0017–0019", md)
        self.assertIn("| EVO-0017 | complete |", md)
        self.assertIn("| EVO-0018 | partial |", md)
        self.assertIn("| EVO-0019 | missing | - |", md)


if __name__ == "__main__":
    unittest.main()
