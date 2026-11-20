"""Tes regresi fixture-only untuk tools.gap_pattern_report (AG4)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools import gap_pattern_report


class GapPatternReportTest(unittest.TestCase):
    def test_triage_fixture_11_gaps_with_1526_outlier_and_orphan_proposal(self) -> None:
        gaps = [
            {
                "gap_id": f"gap-tech-{i:02d}",
                "kind": "DYNAMIC_TECH_PRACTICE_FAILED",
                "occurrence": i,
                "status": "OPEN",
            }
            for i in range(1, 11)
        ]
        gaps.append(
            {
                "gap_id": "gap-lang-outlier",
                "kind": "LANGUAGE",
                "occurrence": 1526,
                "status": "OPEN",
            }
        )
        proposals = [
            {"proposal_id": "prop-valid", "checkpoint": {"gap_id": "gap-tech-01"}},
            {"proposal_id": "prop-orphan", "checkpoint": {"gap_id": "gap-orphan-999"}},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gaps_path = root / "gaps.jsonl"
            props_path = root / "proposals.jsonl"
            out1 = root / "report1.json"
            out2 = root / "report2.json"

            gaps_path.write_text(
                "\n".join(json.dumps(g) for g in gaps) + "\n", encoding="utf-8"
            )
            props_path.write_text(
                "\n".join(json.dumps(p) for p in proposals) + "\n", encoding="utf-8"
            )

            self.assertEqual(
                gap_pattern_report.main(
                    ["--gaps", str(gaps_path), "--proposals", str(props_path), "--out", str(out1)]
                ),
                0,
            )
            self.assertEqual(
                gap_pattern_report.main(
                    ["--gaps", str(gaps_path), "--proposals", str(props_path), "--out", str(out2)]
                ),
                0,
            )
            raw1 = out1.read_text(encoding="utf-8")
            raw2 = out2.read_text(encoding="utf-8")
            self.assertEqual(raw1, raw2)
            rep = json.loads(raw1)

        self.assertEqual(rep["schema"], gap_pattern_report.SCHEMA)
        self.assertEqual(rep["summary"]["total_gaps"], 11)
        self.assertEqual(rep["dominant_family"]["kind"], "DYNAMIC_TECH_PRACTICE_FAILED")
        self.assertEqual(rep["dominant_family"]["count"], 10)
        self.assertEqual(rep["by_kind"]["DYNAMIC_TECH_PRACTICE_FAILED"]["count"], 10)
        self.assertEqual(rep["by_kind"]["LANGUAGE"]["max_occurrence"], 1526)
        self.assertEqual(
            rep["highest_occurrence"],
            {
                "gap_id": "gap-lang-outlier",
                "kind": "LANGUAGE",
                "occurrence": 1526,
                "status": "OPEN",
            },
        )
        self.assertEqual(
            rep["orphan_gaps"],
            [{"gap_id": "gap-orphan-999", "referenced_by": ["prop-orphan"]}],
        )


if __name__ == "__main__":
    unittest.main()
