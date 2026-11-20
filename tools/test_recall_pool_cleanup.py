"""Regresi EVO 0017 M2: pool_cleanup mengeluarkan kandidat riwayat
tugas COMPLETED dari kolam keputusan ablas recall."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.recall_ablation import load_sqlite_ablation_store

TASKS = [{"query": "bagaimana menganalisis morfologi imbuhan bahasa"}]


def _build_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE skills (skill_id TEXT, name TEXT, domain TEXT,
                             procedure_steps_json TEXT, source_task_ids_json TEXT,
                             status TEXT);
        CREATE TABLE tasks (task_id TEXT, normalized_goal TEXT,
                            next_action TEXT, status TEXT);
        CREATE TABLE learning_experiences (experience_id TEXT, task_id TEXT,
                            failure_signature TEXT, extracted_rule TEXT,
                            strategy_after TEXT, verification_evidence_json TEXT);
        CREATE TABLE receipts (receipt_id TEXT, task_id TEXT, passed INTEGER);
        """
    )
    conn.execute(
        "INSERT INTO skills VALUES ('sk1', 'analisis_morfologi_imbuhan_id', "
        "'bahasa', '[\"morfologi imbuhan analisis\"]', '[]', 'ACTIVE')")
    # Tugas COMPLETED dengan next_action generik yang tumpang-tindih
    # tokennya dengan kueri — pencemar kolam pada M1.
    conn.execute(
        "INSERT INTO tasks VALUES ('t1', 'menganalisis morfologi imbuhan bahasa', "
        "'mulai_eksekusi', 'COMPLETED')")
    conn.commit()
    conn.close()


class PoolCleanupTests(unittest.TestCase):
    def test_task_history_pollutes_without_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "store.db"
            _build_db(db)
            store = load_sqlite_ablation_store(db, TASKS)
            decisions = store[TASKS[0]["query"]]
            self.assertIn("mulai_eksekusi", decisions)

    def test_pool_cleanup_excludes_task_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "store.db"
            _build_db(db)
            store = load_sqlite_ablation_store(db, TASKS, pool_cleanup=True)
            decisions = store[TASKS[0]["query"]]
            self.assertNotIn("mulai_eksekusi", decisions)
            self.assertIn("analisis_morfologi_imbuhan_id", decisions)


if __name__ == "__main__":
    unittest.main()
