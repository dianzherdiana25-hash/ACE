"""Tes perute antrean proposal director (praktik / riset / payung) — AG35."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.director_queue_router import SCHEMA, route_proposals


SCRIPT = Path(__file__).with_name("director_queue_router.py")


class DirectorQueueRouterTests(unittest.TestCase):
    def test_routes_practice_language_multi_gap_and_research_proposals(self) -> None:
        gap_errors = {
            "gap-tech-1": "DYNAMIC_TECH_PRACTICE_FAILED",
            "gap-lang-1": "LANGUAGE_CURRICULUM_FAILED",
            "gap-lang-2": "LANGUAGE_CURRICULUM_VERIFICATION_TIMEOUT",
            "gap-novel-1": "NOVEL_SYNTHESIS_FAILURE",
        }
        proposals = [
            {"id": "p-tech", "based_on": ["gap-tech-1"]},
            {"id": "p-lang-a", "based_on": ["gap-lang-1"]},
            {"id": "p-lang-b", "based_on": ["gap-lang-2"]},
            {"id": "p-umbrella", "based_on": ["gap-tech-1", "gap-lang-1"]},
            {"id": "p-research-other", "based_on": ["gap-novel-1"]},
            {"id": "p-research-unknown", "based_on": ["gap-absent"]},
        ]
        report = route_proposals(proposals, gap_errors)
        self.assertEqual(report["schema"], SCHEMA)
        self.assertEqual(
            report["summary"],
            {"total_proposals": 6, "praktik": 3, "payung": 1, "riset": 2},
        )
        self.assertEqual(report["queues"], {
            "praktik": ["p-tech", "p-lang-a", "p-lang-b"],
            "payung": ["p-umbrella"],
            "riset": ["p-research-other", "p-research-unknown"],
        })

    def test_cli_sqlite_readonly_routing(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "store.sqlite3"
            conn = sqlite3.connect(str(db))
            conn.executescript("CREATE TABLE gaps (gap_id TEXT PRIMARY KEY, error_type TEXT NOT NULL);")
            conn.execute("INSERT INTO gaps VALUES ('g1', 'DYNAMIC_TECH_PRACTICE_FAILED')")
            conn.execute("INSERT INTO gaps VALUES ('g2', 'LANGUAGE_CURRICULUM_ITEM_3')")
            conn.execute("INSERT INTO gaps VALUES ('g3', 'PARSER_GRAMMAR_MISSING')")
            conn.commit()
            conn.close()

            prop_path = root / "proposals.jsonl"
            prop_path.write_text(
                "".join(
                    json.dumps(p) + "\n"
                    for p in (
                        {"id": "r1", "based_on": ["g1"]},
                        {"id": "r2", "based_on": ["g2"]},
                        {"id": "r3", "based_on": ["g1", "g2"]},
                        {"id": "r4", "based_on": ["g3"]},
                    )
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--proposals", str(prop_path), "--sqlite", str(db)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = json.loads(proc.stdout)
            self.assertEqual(out["queues"], {
                "praktik": ["r1", "r2"],
                "payung": ["r3"],
                "riset": ["r4"],
            })


if __name__ == "__main__":
    unittest.main()
