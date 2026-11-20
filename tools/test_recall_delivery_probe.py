"""Tes probe keteririman recall pada 8 tugas held-out (7 bertetangga + 1 benar-benar kosong) — AG27."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.recall_delivery_probe import SCHEMA, probe_recall_delivery


SCRIPT = Path(__file__).with_name("recall_delivery_probe.py")


class RecallDeliveryProbeTests(unittest.TestCase):
    def test_eight_heldout_tasks_flags_only_neighbor_zero_records_not_truly_empty(self) -> None:
        # 7 tugas punya tetangga di memori (4 mengalami 0-record terkirim, 3 terkirim normal);
        # 1 tugas ('t8-empty') benar-benar tidak punya tetangga di memori.
        tasks = [
            {"id": "t1-missed", "query": "kurung seimbang tumpukan parser"},
            {"id": "t2-missed", "query": "pajak progresif pembulatan decimal"},
            {"id": "t3-missed", "query": "lintas batas symlink traversal"},
            {"id": "t4-missed", "query": "backoff eksponensial spool relai"},
            {"id": "t5-delivered", "query": "validasi skema jsonl tanpa duplikat"},
            {"id": "t6-delivered", "query": "graf bfs lintasan terpendek"},
            {"id": "t7-delivered", "query": "cache lru eviksi kapasitas"},
            {"id": "t8-empty", "query": "kueri asing kuantum fotosintesis"},
        ]
        records = [
            {"id": "mem-1", "text": "Catatan pola stack kurung seimbang pada parser ekspresi."},
            {"id": "mem-2", "text": "Aturan tarif pajak progresif memakai pembulatan decimal akurat."},
            {"id": "mem-3", "text": "Pencegahan traversal symlink melewati batas root."},
            {"id": "mem-4", "text": "Strategi backoff eksponensial saat menguras spool relai."},
            {"id": "mem-5", "text": "Pemeriksa skema jsonl menolak kunci duplikat."},
            {"id": "mem-6", "text": "Algoritma bfs mencari lintasan terpendek pada graf."},
            {"id": "mem-7", "text": "Struktur cache lru untuk eviksi saat kapasitas penuh."},
        ]
        store = {
            "records": records,
            "delivered": {
                "t5-delivered": [records[4]],
                "t6-delivered": [records[5]],
                "t7-delivered": [records[6]],
            },
        }
        report = probe_recall_delivery(tasks, store)
        self.assertEqual(report["schema"], SCHEMA)
        self.assertEqual(report["summary"], {
            "total_tasks": 8,
            "delivered_tasks": 3,
            "zero_record_tasks": 5,
            "flagged_missed_with_neighbors": 4,
            "truly_empty_unflagged": 1,
        })
        self.assertEqual(report["flagged_task_ids"], ["t1-missed", "t2-missed", "t3-missed", "t4-missed"])
        self.assertEqual(report["truly_empty_task_ids"], ["t8-empty"])

        by_id = {row["task_id"]: row for row in report["tasks"]}
        self.assertFalse(by_id["t8-empty"]["missed_with_neighbors"])
        self.assertEqual(by_id["t8-empty"]["neighbor_count"], 0)
        self.assertEqual(by_id["t8-empty"]["status"], "zero_record_truly_empty")

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks_path = root / "tasks.json"
            store_path = root / "store.json"
            tasks_path.write_text(json.dumps(tasks), encoding="utf-8")
            store_path.write_text(json.dumps(store), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--tasks", str(tasks_path), "--store", str(store_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["flagged_task_ids"], report["flagged_task_ids"])


if __name__ == "__main__":
    unittest.main()
