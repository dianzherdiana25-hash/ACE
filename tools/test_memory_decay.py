"""Tes perencana arsip memory_decay tanpa hapus + jejak alasan (AG62)."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import memory_decay


class MemoryDecayArchiveTest(unittest.TestCase):
    def test_active_records_excluded_from_archive_plan_and_source_preserved(self) -> None:
        records = [
            # Aktif karena baru dipakai recall meskipun dibuat agak lama.
            {"id": "rec-active-recalled", "kind": "semantic", "created_at": "2026-07-01T00:00:00Z"},
            # Aktif karena masih baru (baru 5 hari).
            {"id": "rec-active-recent", "kind": "episodic", "created_at": "2026-11-15T00:00:00Z"},
            # Usang: 120 hari idle, 0 recall -> masuk rencana arsip!
            {"id": "rec-stale-unused", "kind": "episodic", "created_at": "2026-07-23T00:00:00Z"},
        ]
        recall_events = [
            {"ts": "2026-11-10T00:00:00Z", "recalled_ids": ["rec-active-recalled"]},
            {"ts": "2026-11-18T12:00:00Z", "recalled_ids": ["rec-active-recalled"]},
        ]

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            mem_path = root / "memory.jsonl"
            recall_path = root / "recall.jsonl"
            out_path = root / "decay_plan.json"
            mem_path.write_text(
                "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
            )
            recall_path.write_text(
                "\n".join(json.dumps(e) for e in recall_events) + "\n", encoding="utf-8"
            )
            before_mem = mem_path.read_bytes()
            before_rec = recall_path.read_bytes()

            rc = memory_decay.main(
                [
                    "--memory",
                    str(mem_path),
                    "--recall-log",
                    str(recall_path),
                    "--as-of",
                    "2026-11-20T00:00:00Z",
                    "--stale-days",
                    "60",
                    "--out",
                    str(out_path),
                ]
            )
            self.assertEqual(rc, 0)
            self.assertEqual(mem_path.read_bytes(), before_mem)
            self.assertEqual(recall_path.read_bytes(), before_rec)
            rep = json.loads(out_path.read_text(encoding="utf-8"))

        self.assertEqual(rep["schema"], memory_decay.SCHEMA)
        self.assertFalse(rep["policy"]["delete_records"])
        self.assertEqual(rep["summary"]["total_evaluated"], 3)
        self.assertEqual(rep["summary"]["archive_candidate_count"], 1)
        self.assertEqual(rep["summary"]["retained_active_count"], 2)

        planned_ids = [item["record_id"] for item in rep["archive_plan"]]
        self.assertEqual(planned_ids, ["rec-stale-unused"])
        self.assertNotIn("rec-active-recalled", planned_ids)
        self.assertNotIn("rec-active-recent", planned_ids)

        stale_item = rep["archive_plan"][0]
        self.assertFalse(stale_item["deleted"])
        self.assertGreater(stale_item["idle_days"], 60)
        self.assertTrue(stale_item["reason_trace"])


if __name__ == "__main__":
    unittest.main()
