"""Tes mode --sqlite read-only pada recall_ablation.py + regresi byte-identik mode fixture (AG28)."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from tools.recall_ablation import load_sqlite_ablation_store, main


class RecallAblationSqliteTests(unittest.TestCase):
    def _seed_operational_db(self, db_path: Path) -> None:
        conn = sqlite3.connect(str(db_path))
        conn.executescript(
            """
            CREATE TABLE receipts (
                receipt_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                passed INTEGER NOT NULL
            );
            CREATE TABLE learning_experiences (
                experience_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                failure_signature TEXT NOT NULL,
                extracted_rule TEXT NOT NULL,
                strategy_after TEXT NOT NULL,
                verification_evidence_json TEXT NOT NULL
            );
            CREATE TABLE skills (
                skill_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                domain TEXT NOT NULL,
                procedure_steps_json TEXT NOT NULL,
                source_task_ids_json TEXT NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE tasks (
                task_id TEXT PRIMARY KEY,
                normalized_goal TEXT NOT NULL,
                next_action TEXT NOT NULL,
                status TEXT NOT NULL
            );
            """
        )
        conn.execute("INSERT INTO receipts VALUES ('rcpt-valid-1', 'task-anchor-ok', 1)")
        conn.execute("INSERT INTO receipts VALUES ('rcpt-fail-2', 'task-unverified', 0)")
        conn.execute(
            "INSERT INTO learning_experiences VALUES "
            "('exp-1', 'task-anchor-ok', 'bracket balance stack', 'use_stack_checker', 'stack_fix', '{\"receipt_id\": \"rcpt-valid-1\"}')"
        )
        conn.execute(
            "INSERT INTO learning_experiences VALUES "
            "('exp-2', 'task-unverified', 'progressive tax decimal', 'use_decimal_tiers', 'decimal_fix', '{\"receipt_id\": \"rcpt-fail-2\"}')"
        )
        conn.commit()
        conn.close()

    def test_sqlite_readonly_mode_maps_records_and_never_modifies_db(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "operational.sqlite3"
            self._seed_operational_db(db_path)
            os.chmod(db_path, 0o444)
            before_sha = hashlib.sha256(db_path.read_bytes()).hexdigest()

            tasks = [
                {"id": "t1", "query": "bracket balance stack", "cold_decision": "cold", "expected": "use_stack_checker"},
                {"id": "t2", "query": "progressive tax decimal", "cold_decision": "cold", "expected": "use_decimal_tiers"},
                {"id": "t3", "query": "unknown unrelated topic", "cold_decision": "cold", "expected": "other"},
            ]
            tasks_path = root / "tasks.json"
            tasks_path.write_text(json.dumps(tasks), encoding="utf-8")

            # Mode standar --sqlite
            out_std = root / "out_std"
            self.assertEqual(
                main(["--sqlite", str(db_path), "--tasks", str(tasks_path), "--seed", "7", "--output-dir", str(out_std)]),
                0,
            )
            std_summary = json.loads((out_std / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(std_summary["scores"], {"active": 2, "off": 0})
            self.assertAlmostEqual(std_summary["delta"], 2 / 3)

            # Mode --anchored --sqlite: t2 pakai receipt gagal (passed=0) -> hanya t1 yang lolos di lengan anchored
            out_anc = root / "out_anc"
            self.assertEqual(
                main([
                    "--sqlite", str(db_path),
                    "--tasks", str(tasks_path),
                    "--seed", "7",
                    "--anchored",
                    "--output-dir", str(out_anc),
                ]),
                0,
            )
            anc_summary = json.loads((out_anc / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(anc_summary["scores"], {"active": 2, "anchored": 1, "off": 0})
            self.assertEqual(hashlib.sha256(db_path.read_bytes()).hexdigest(), before_sha)
            os.chmod(db_path, 0o644)

    def test_missing_sqlite_fails_closed_cleanly(self) -> None:
        with TemporaryDirectory() as tmp:
            missing = Path(tmp) / "tidak_ada.sqlite3"
            with self.assertRaisesRegex(ValueError, "tidak ditemukan"):
                load_sqlite_ablation_store(missing, [{"id": "a", "query": "q"}])


if __name__ == "__main__":
    unittest.main()
