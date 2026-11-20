"""Tes regresi fixture-only untuk tools.curriculum_ab_report (AG47)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools import curriculum_ab_report


class CurriculumABReportTest(unittest.TestCase):
    def test_compare_fixed_vs_generated_per_family_and_aggregate(self) -> None:
        # Fixed (11 gap):
        # - DYNAMIC_TECH: 1/5 = 0.20
        # - LANGUAGE_SYNTAX: 3/4 = 0.75
        # - BFS_GRAPH: 2/2 = 1.00
        # -> agregat = 6/11 (~0.545455)
        fixed_rows = (
            [{"family": "DYNAMIC_TECH", "status": "RESOLVED"}] * 1
            + [{"family": "DYNAMIC_TECH", "status": "OPEN"}] * 4
            + [{"family": "LANGUAGE_SYNTAX", "status": "RESOLVED"}] * 3
            + [{"family": "LANGUAGE_SYNTAX", "status": "OPEN"}] * 1
            + [{"family": "BFS_GRAPH", "status": "RESOLVED"}] * 2
        )

        # Generated (11 gap):
        # - DYNAMIC_TECH: 4/5 = 0.80 (delta +0.60)
        # - LANGUAGE_SYNTAX: 2/4 = 0.50 (delta -0.25)
        # - BFS_GRAPH: 2/2 = 1.00 (delta 0.00)
        # -> agregat = 8/11 (~0.727273), delta = +2/11 (~+0.181818)
        gen_rows = (
            [{"family": "DYNAMIC_TECH", "closed": True}] * 4
            + [{"family": "DYNAMIC_TECH", "closed": False}] * 1
            + [{"family": "LANGUAGE_SYNTAX", "closed": True}] * 2
            + [{"family": "LANGUAGE_SYNTAX", "closed": False}] * 2
            + [{"family": "BFS_GRAPH", "closed": True}] * 2
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f_path = root / "fixed.jsonl"
            g_path = root / "generated.jsonl"
            o_path = root / "ab.json"
            f_path.write_text(
                "\n".join(json.dumps(r) for r in fixed_rows) + "\n", encoding="utf-8"
            )
            g_path.write_text(
                "\n".join(json.dumps(r) for r in gen_rows) + "\n", encoding="utf-8"
            )

            rc = curriculum_ab_report.main(
                ["--fixed", str(f_path), "--generated", str(g_path), "--out", str(o_path)]
            )
            self.assertEqual(rc, 0)
            rep = json.loads(o_path.read_text(encoding="utf-8"))

        self.assertEqual(rep["schema"], curriculum_ab_report.SCHEMA)
        agg = rep["aggregate"]
        self.assertEqual(agg["fixed_closed"], 6)
        self.assertEqual(agg["fixed_total"], 11)
        self.assertEqual(agg["generated_closed"], 8)
        self.assertEqual(agg["generated_total"], 11)
        self.assertAlmostEqual(agg["closure_rate_delta"], 2 / 11, places=5)
        self.assertEqual(agg["overall_winner"], "generated")
        self.assertEqual(agg["families_improved"], ["DYNAMIC_TECH"])
        self.assertEqual(agg["families_regressed"], ["LANGUAGE_SYNTAX"])
        self.assertEqual(agg["families_tied"], ["BFS_GRAPH"])

        by_fam = rep["by_family"]
        self.assertAlmostEqual(by_fam["DYNAMIC_TECH"]["closure_rate_delta"], 0.6, places=6)
        self.assertAlmostEqual(by_fam["LANGUAGE_SYNTAX"]["closure_rate_delta"], -0.25, places=6)
        self.assertAlmostEqual(by_fam["BFS_GRAPH"]["closure_rate_delta"], 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
