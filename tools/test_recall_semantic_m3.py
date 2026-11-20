"""Tes EVO 0017 M3 — lengan semantik recall_ablation (top-k kosinus).

Memakai embedder stub deterministik: kasus parafrase (query tanpa token
bersama dengan skill yang benar) harus tertangkap kolam semantik
sementara kolam leksikal kosong.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.recall_ablation import load_sqlite_ablation_store


def _seed(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE receipts (receipt_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, passed INTEGER NOT NULL);
        CREATE TABLE learning_experiences (experience_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
            failure_signature TEXT NOT NULL, extracted_rule TEXT NOT NULL, strategy_after TEXT NOT NULL,
            verification_evidence_json TEXT NOT NULL);
        CREATE TABLE skills (skill_id TEXT PRIMARY KEY, name TEXT NOT NULL, domain TEXT NOT NULL,
            procedure_steps_json TEXT NOT NULL, source_task_ids_json TEXT NOT NULL, status TEXT NOT NULL);
        CREATE TABLE tasks (task_id TEXT PRIMARY KEY, normalized_goal TEXT NOT NULL,
            next_action TEXT NOT NULL, status TEXT NOT NULL);
        """
    )
    conn.execute("INSERT INTO skills VALUES ('sk-graph', 'dijkstra shortest path graph', 'algorithms', '[\"relax edges\"]', '[]', 'ACTIVE')")
    conn.execute("INSERT INTO skills VALUES ('sk-tax', 'progressive tax tiers decimal', 'finance', '[\"apply tiers\"]', '[]', 'ACTIVE')")
    conn.commit()
    conn.close()


# Vektor buatan: query parafrase dekat ke skill graf, jauh dari pajak.
_VECTORS = {
    "temukan rute tercepat antar simpul": [1.0, 0.0],
    "dijkstra shortest path graph algorithms relax edges": [0.9, 0.1],
    "progressive tax tiers decimal finance apply tiers": [0.0, 1.0],
}


def _stub_embedder(text: str):
    if text in _VECTORS:
        return _VECTORS[text]
    # haystack skill digabung loader sebagai "name domain steps"
    for key, vec in _VECTORS.items():
        if text.startswith(key.split(" finance")[0].split(" algorithms")[0]):
            return vec
    return [0.5, 0.5]


TASKS = [{"id": "t1", "query": "temukan rute tercepat antar simpul",
          "cold_decision": "cold", "expected": "dijkstra shortest path graph"}]


class RecallSemanticM3Tests(unittest.TestCase):
    def test_paraphrase_caught_by_semantic_not_lexical(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "store.sqlite3"
            _seed(db)
            lexical = load_sqlite_ablation_store(db, TASKS, pool_cleanup=True)
            self.assertEqual(lexical[TASKS[0]["query"]], [])
            semantic = load_sqlite_ablation_store(
                db, TASKS, pool_cleanup=True, semantic=True,
                embedder=_stub_embedder, top_k=1)
            self.assertEqual(semantic[TASKS[0]["query"]],
                             ["dijkstra shortest path graph"])

    def test_semantic_requires_embedder(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "store.sqlite3"
            _seed(db)
            with self.assertRaises(ValueError):
                load_sqlite_ablation_store(db, TASKS, semantic=True)

    def test_top_k_bounds_pool(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "store.sqlite3"
            _seed(db)
            store = load_sqlite_ablation_store(
                db, TASKS, anchored=True, pool_cleanup=True, semantic=True,
                embedder=_stub_embedder, top_k=1)
            records = store["records"][TASKS[0]["query"]]
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["decision"], "dijkstra shortest path graph")


if __name__ == "__main__":
    unittest.main()
