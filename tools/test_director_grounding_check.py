"""Tes pemeriksa keterjangkaran klaim kuantitatif rationale proposal director (AG33)."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.director_grounding_check import SCHEMA, check_proposal_grounding, main


SCRIPT = Path(__file__).with_name("director_grounding_check.py")


class DirectorGroundingCheckTests(unittest.TestCase):
    def test_twelve_claimed_open_gaps_vs_eleven_fact_flags_factual_mismatch(self) -> None:
        facts = {
            "open_gaps": 11,
            "total_gaps": 15,
            "dynamic_tech_practice_failed_gaps": 10,
            "max_occurrence": 1526,
            "active_skills": 4,
        }
        proposals = [
            {
                "id": "prop-mismatch",
                "rationale": "Saat ini terdapat 12 gap terbuka sehingga prioritas penanganan mendesak.",
            },
            {
                "id": "prop-grounded",
                "rationale": (
                    "Terdapat 11 gap terbuka, termasuk 10 gap DYNAMIC_TECH_PRACTICE_FAILED "
                    "serta outlier 1526 occurrence."
                ),
            },
        ]
        report = check_proposal_grounding(proposals, facts)
        self.assertEqual(report["schema"], SCHEMA)
        self.assertFalse(report["all_grounded"])
        self.assertEqual(report["summary"]["mismatched_claims"], 1)
        self.assertEqual(report["summary"]["matched_claims"], 3)

        by_id = {p["id"]: p for p in report["proposals"]}
        self.assertEqual(by_id["prop-mismatch"]["status"], "factual_mismatch")
        self.assertEqual(
            by_id["prop-mismatch"]["claims"],
            [
                {
                    "metric": "open_gaps",
                    "claimed": 12,
                    "actual": 11,
                    "status": "factual_mismatch",
                    "snippet": "12 gap terbuka",
                }
            ],
        )
        self.assertEqual(by_id["prop-grounded"]["status"], "grounded")
        self.assertEqual(
            [c["status"] for c in by_id["prop-grounded"]["claims"]],
            ["match", "match", "match"],
        )

    def test_cli_with_facts_json_and_sqlite_readonly(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "store.sqlite3"
            conn = sqlite3.connect(str(db))
            conn.executescript("CREATE TABLE gaps (gap_id TEXT, error_type TEXT, status TEXT, occurrence_count INT);")
            for i in range(11):
                conn.execute(
                    "INSERT INTO gaps VALUES (?, ?, 'OPEN', ?)",
                    (f"g-{i}", "DYNAMIC_TECH_PRACTICE_FAILED" if i < 10 else "LANGUAGE_CURRICULUM_FAILED", 1526 if i == 10 else 2),
                )
            conn.commit()
            conn.close()

            prop_ok = root / "ok.jsonl"
            prop_ok.write_text(
                json.dumps({"id": "ok-1", "rationale": "Ada 11 gap terbuka dan 1526 occurrence."}) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(main(["--proposals", str(prop_ok), "--sqlite", str(db)]), 0)

            prop_bad = root / "bad.jsonl"
            prop_bad.write_text(
                json.dumps({"id": "bad-1", "rationale": "Ada 12 gap terbuka di store."}) + "\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--proposals", str(prop_bad), "--sqlite", str(db)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(json.loads(proc.stdout)["proposals"][0]["claims"][0]["status"], "factual_mismatch")


if __name__ == "__main__":
    unittest.main()
