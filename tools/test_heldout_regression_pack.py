"""Paket regresi held-out JSONL (8 tugas + tetangga memory) & integrasi probe AG27 (AG29)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import unittest


FIXTURES = Path(__file__).resolve().parent / "fixtures"
TASKS_PATH = FIXTURES / "heldout_regression_tasks_v1.jsonl"
MEMORY_PATH = FIXTURES / "heldout_regression_memory_v1.jsonl"
PROBE_AVAILABLE = importlib.util.find_spec("tools.recall_delivery_probe") is not None


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class HeldoutRegressionPackTests(unittest.TestCase):
    def test_pack_schema_and_eight_tasks_with_neighbor_and_empty_design(self) -> None:
        tasks = _load_jsonl(TASKS_PATH)
        memories = _load_jsonl(MEMORY_PATH)
        self.assertEqual(len(tasks), 8)
        self.assertEqual(len({t["id"] for t in tasks}), 8)
        self.assertEqual(len(memories), 7)

        mem_tokens = [set(re.findall(r"[a-z0-9_]+", m["text"].lower())) for m in memories]
        neighbor_count = 0
        truly_empty = []
        for task in tasks:
            q_toks = set(re.findall(r"[a-z0-9_]+", task["query"].lower()))
            has_neighbor = any(bool(q_toks & mt) for mt in mem_tokens)
            if has_neighbor:
                neighbor_count += 1
            else:
                truly_empty.append(task["id"])
        self.assertEqual(neighbor_count, 7)
        self.assertEqual(truly_empty, ["ho-08"])

    @unittest.skipUnless(PROBE_AVAILABLE, "Memerlukan tools/recall_delivery_probe.py (AG27) saat digabungkan")
    def test_probe_ag27_flags_exact_designed_zero_record_tasks(self) -> None:
        from tools.recall_delivery_probe import probe_recall_delivery

        tasks = _load_jsonl(TASKS_PATH)
        memories = _load_jsonl(MEMORY_PATH)
        mem_by_domain_idx = {m["id"]: m for m in memories}
        delivered = {
            "ho-06": [mem_by_domain_idx["mem-ho-06"]],
            "ho-07": [mem_by_domain_idx["mem-ho-07"]],
        }
        report = probe_recall_delivery(tasks, {"records": memories, "delivered": delivered})
        expected_flagged = sorted(t["id"] for t in tasks if t["expected_zero_record_flagged"])
        self.assertEqual(sorted(report["flagged_task_ids"]), expected_flagged)
        self.assertEqual(expected_flagged, ["ho-01", "ho-02", "ho-03", "ho-04", "ho-05"])
        self.assertEqual(report["truly_empty_task_ids"], ["ho-08"])
        self.assertEqual(report["delivered_task_ids"], ["ho-06", "ho-07"])


if __name__ == "__main__":
    unittest.main()
