"""Tes pemindai outlier occurrence gap tanpa kemajuan belajar (AG31)."""
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

from tools.occurrence_outlier_scan import SCHEMA, scan_occurrence_outliers


SCRIPT = Path(__file__).with_name("occurrence_outlier_scan.py")


class OccurrenceOutlierScanTests(unittest.TestCase):
    def _seed_db(self, db_path: Path) -> None:
        conn = sqlite3.connect(str(db_path))
        conn.executescript(
            """
            CREATE TABLE gaps (
                gap_id TEXT PRIMARY KEY,
                error_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                linked_learning_task_id TEXT NOT NULL DEFAULT '',
                occurrence_count INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE tasks (
                task_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                stagnation_score REAL NOT NULL DEFAULT 0.0,
                updated_at TEXT NOT NULL DEFAULT ''
            );
            """
        )
        # Outlier 1526 dengan tugas gagal/mandek -> wajib tertandai
        conn.execute("INSERT INTO tasks VALUES ('lt-fail', 'FAILED_WITH_RECOVERY_STATE', 12, 1.0, '2026-11-19T02:00:00Z')")
        conn.execute(
            "INSERT INTO gaps VALUES ('gap-outlier-1526', 'LANGUAGE_CURRICULUM_FAILED', 'OPEN', 'lt-fail', 1526, '2026-11-19T02:00:00Z')"
        )
        # Gap dengan occurrence 250 tetapi punya tugas belajar aktif yang bergerak -> TIDAK boleh tertandai
        conn.execute("INSERT INTO tasks VALUES ('lt-active', 'LEARNING', 2, 0.1, '2026-11-19T03:00:00Z')")
        conn.execute(
            "INSERT INTO gaps VALUES ('gap-active-progress', 'DYNAMIC_TECH_PRACTICE_FAILED', 'OPEN', 'lt-active', 250, '2026-11-19T03:00:00Z')"
        )
        # Gap wajar di bawah ambang meskipun belum ada kemajuan -> TIDAK tertandai pada ambang 100
        conn.execute(
            "INSERT INTO gaps VALUES ('gap-low-normal', 'DYNAMIC_TECH_PRACTICE_FAILED', 'OPEN', '', 12, '2026-11-19T03:00:00Z')"
        )
        # Gap tak tertaut yang melewati ambang -> tertandai
        conn.execute(
            "INSERT INTO gaps VALUES ('gap-unlinked-high', 'PARSER_ERROR', 'OPEN', '', 140, '2026-11-19T03:00:00Z')"
        )
        conn.commit()
        conn.close()

    def test_flags_outlier_1526_and_skips_active_progress_and_respects_threshold(self) -> None:
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "store.sqlite3"
            self._seed_db(db_path)
            os.chmod(db_path, 0o444)
            before_sha = hashlib.sha256(db_path.read_bytes()).hexdigest()

            rep100 = scan_occurrence_outliers(db_path, threshold=100)
            self.assertEqual(rep100["schema"], SCHEMA)
            self.assertTrue(rep100["read_only"])
            self.assertEqual(rep100["outlier_gap_ids"], ["gap-outlier-1526", "gap-unlinked-high"])
            self.assertNotIn("gap-active-progress", rep100["outlier_gap_ids"])
            self.assertNotIn("gap-low-normal", rep100["outlier_gap_ids"])
            self.assertEqual(rep100["skipped_with_progress_gap_ids"], ["gap-active-progress"])

            # Mengatur ambang lebih tinggi ke 1000 menyisakan hanya 1526
            rep1000 = scan_occurrence_outliers(db_path, threshold=1000)
            self.assertEqual(rep1000["outlier_gap_ids"], ["gap-outlier-1526"])

            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--sqlite", str(db_path), "--threshold", "100"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["outlier_gap_ids"], ["gap-outlier-1526", "gap-unlinked-high"])
            self.assertEqual(hashlib.sha256(db_path.read_bytes()).hexdigest(), before_sha)
            os.chmod(db_path, 0o644)


if __name__ == "__main__":
    unittest.main()
