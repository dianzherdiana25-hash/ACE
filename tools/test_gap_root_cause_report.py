"""Tes laporan akar masalah gap pada fixture DB OperationalStore read-only (AG30)."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.gap_root_cause_report import SCHEMA, analyze_gap_root_causes, render_markdown


SCRIPT = Path(__file__).with_name("gap_root_cause_report.py")


class GapRootCauseReportTests(unittest.TestCase):
    def _seed_realistic_store(self, db_path: Path) -> None:
        conn = sqlite3.connect(str(db_path))
        conn.executescript(
            """
            CREATE TABLE gaps (
                gap_id TEXT PRIMARY KEY,
                fingerprint TEXT UNIQUE NOT NULL,
                source_task_id TEXT NOT NULL,
                error_type TEXT NOT NULL,
                missing_skill_or_tool TEXT NOT NULL,
                description_id TEXT NOT NULL,
                reproduction_ref TEXT NOT NULL DEFAULT '',
                resolution_strategy TEXT NOT NULL DEFAULT 'micro_experiment',
                status TEXT NOT NULL DEFAULT 'OPEN',
                linked_learning_task_id TEXT NOT NULL DEFAULT '',
                occurrence_count INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE tasks (
                task_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                title_id TEXT NOT NULL,
                user_request TEXT NOT NULL,
                normalized_goal TEXT NOT NULL,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                stagnation_score REAL NOT NULL DEFAULT 0.0,
                error_summary TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        # 10 gap DYNAMIC_TECH_PRACTICE_FAILED meniru keadaan nyata (sebagian besar gagal belajar)
        for i in range(1, 11):
            lt_id = f"learn-tech-{i}"
            lt_status = "FAILED_WITH_RECOVERY_STATE" if i <= 8 else "LEARNING"
            day = f"2026-11-{10 + (i % 3):02d}T10:00:00Z"
            conn.execute(
                "INSERT INTO tasks (task_id, conversation_id, kind, status, title_id, user_request, "
                "normalized_goal, attempt_count, stagnation_score, created_at, updated_at) "
                "VALUES (?, 'c1', 'learning', ?, 'Latih', 'req', 'goal', 3, 0.8, ?, ?)",
                (lt_id, lt_status, day, day),
            )
            conn.execute(
                "INSERT INTO gaps (gap_id, fingerprint, source_task_id, error_type, missing_skill_or_tool, "
                "description_id, status, linked_learning_task_id, occurrence_count, created_at, updated_at) "
                "VALUES (?, ?, ?, 'DYNAMIC_TECH_PRACTICE_FAILED', 'python', 'desc', 'OPEN', ?, ?, ?, ?)",
                (f"gap-tech-{i}", f"fp-tech-{i}", f"src-{i}", lt_id, 2 + i, day, day),
            )

        # 1 gap LANGUAGE dengan occurrence 1526 dan tugas belajar mandek
        conn.execute(
            "INSERT INTO tasks (task_id, conversation_id, kind, status, title_id, user_request, "
            "normalized_goal, attempt_count, stagnation_score, created_at, updated_at) "
            "VALUES ('learn-lang-1', 'c1', 'learning', 'FAILED_WITH_RECOVERY_STATE', 'Bahasa', 'req', "
            "'goal', 9, 1.0, '2026-11-18T01:00:00Z', '2026-11-19T02:00:00Z')"
        )
        conn.execute(
            "INSERT INTO gaps (gap_id, fingerprint, source_task_id, error_type, missing_skill_or_tool, "
            "description_id, status, linked_learning_task_id, occurrence_count, created_at, updated_at) "
            "VALUES ('gap-lang-1526', 'fp-lang-1', 'src-lang', 'LANGUAGE_CURRICULUM_FAILED', 'bahasa_id', "
            "'Outlier berulang', 'OPEN', 'learn-lang-1', 1526, '2026-11-18T01:00:00Z', '2026-11-19T02:00:00Z')"
        )
        conn.commit()
        conn.close()

    def test_groups_10_tech_plus_1_language_1526_readonly(self) -> None:
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "ace_operational.sqlite3"
            self._seed_realistic_store(db_path)
            os.chmod(db_path, 0o444)
            before_sha = hashlib.sha256(db_path.read_bytes()).hexdigest()

            report = analyze_gap_root_causes(db_path)
            self.assertEqual(report["schema"], SCHEMA)
            self.assertTrue(report["read_only"])
            self.assertEqual(report["summary"]["total_gaps"], 11)
            self.assertEqual(report["summary"]["error_type_count"], 2)

            by_type = {g["error_type"]: g for g in report["groups"]}
            lang = by_type["LANGUAGE_CURRICULUM_FAILED"]
            self.assertEqual(lang["gap_count"], 1)
            self.assertEqual(lang["max_occurrence"], 1526)
            self.assertEqual(lang["learning_task_outcomes"], {"FAILED_WITH_RECOVERY_STATE": 1})
            self.assertIn("outlier", lang["root_cause_candidate"])

            tech = by_type["DYNAMIC_TECH_PRACTICE_FAILED"]
            self.assertEqual(tech["gap_count"], 10)
            self.assertEqual(tech["open_gap_count"], 10)
            self.assertEqual(tech["learning_task_outcomes"], {"FAILED_WITH_RECOVERY_STATE": 8, "LEARNING": 2})
            self.assertIn("systemic_practice_evaluator_or_skill_gap", tech["root_cause_candidate"])
            self.assertGreaterEqual(len(tech["occurrence_trend_by_day"]), 2)

            md = render_markdown(report)
            self.assertIn("DYNAMIC_TECH_PRACTICE_FAILED", md)
            self.assertIn("1526", md)

            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--sqlite", str(db_path), "--format", "json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["summary"]["total_gaps"], 11)
            self.assertEqual(hashlib.sha256(db_path.read_bytes()).hexdigest(), before_sha)
            os.chmod(db_path, 0o644)


if __name__ == "__main__":
    unittest.main()
