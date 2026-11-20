"""Tes pembangun konteks receipt director per organ + semantik robek AG11 (AG69)."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_operational.director_receipt_context import (
    SCHEMA,
    TORN_SENTINEL,
    build_receipt_context,
)


class _FixtureOriginStore:
    def __init__(self, meta: dict[str, dict]) -> None:
        self._meta = meta

    def get_proposal_meta(self, task_id: str):
        return self._meta.get(task_id)


class DirectorReceiptContextTests(unittest.TestCase):
    def test_aggregates_per_organ_and_tolerates_ag11_torn_tail(self) -> None:
        store = _FixtureOriginStore(
            {
                "t1": {"organ": "groq"},
                "t2": {"organ": "groq"},
                "t3": {"organ": "gemini"},
            }
        )
        rows = [
            {"task_id": "t1", "status": "started", "at": "2026-11-20T01:00:00+00:00"},
            {"task_id": "t1", "status": "completed", "at": "2026-11-20T01:01:00+00:00"},
            {"task_id": "t2", "status": "started", "at": "2026-11-20T01:02:00+00:00"},
            {
                "task_id": "t2",
                "status": "failed",
                "at": "2026-11-20T01:03:00+00:00",
                "gate_reason": "untethered_anchor",
                "undo_executed": True,
            },
            {"task_id": "t3", "status": "started", "at": "2026-11-20T01:04:00+00:00"},
            {
                "task_id": "t3",
                "status": "blocked",
                "at": "2026-11-20T01:05:00+00:00",
                "gate_reason": "touches_money",
            },
        ]

        with TemporaryDirectory() as tmp:
            rec_path = Path(tmp) / "receipts.jsonl"
            # Akhiri dengan baris terakhir robek tanpa newline untuk menguji toleransi AG11.
            rec_path.write_text(
                "\n".join(json.dumps(r) for r in rows) + "\n" + '{"task_id": "t4", "status": "star',
                encoding="utf-8",
            )
            ctx = build_receipt_context(rec_path, store)

        self.assertEqual(ctx["schema"], SCHEMA)
        self.assertTrue(ctx["torn_tail"])
        self.assertIn(TORN_SENTINEL, ctx["pending_tasks"])

        groq = ctx["by_organ"]["groq"]
        self.assertEqual(groq["completed"], 1)
        self.assertEqual(groq["failed"], 1)
        self.assertEqual(groq["undo"], 1)
        self.assertEqual(groq["gate_reasons"], {"untethered_anchor": 1})

        gemini = ctx["by_organ"]["gemini"]
        self.assertEqual(gemini["completed"], 0)
        self.assertEqual(gemini["failed"], 0)
        self.assertEqual(gemini["gate_reasons"], {"touches_money": 1})

        self.assertIn("untethered_anchor=1", ctx["context_block"])
        self.assertIn("PERINGATAN: baris receipt terakhir robek", ctx["context_block"])

    def test_corrupt_middle_line_raises_value_error(self) -> None:
        with TemporaryDirectory() as tmp:
            rec_path = Path(tmp) / "bad_mid.jsonl"
            rec_path.write_text(
                json.dumps({"task_id": "t1", "status": "started", "at": "2026-11-20T01:00:00+00:00"})
                + "\n{broken-middle\n"
                + json.dumps({"task_id": "t1", "status": "completed", "at": "2026-11-20T01:01:00+00:00"})
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                build_receipt_context(rec_path)

    def test_no_engine_imports(self) -> None:
        src = (Path(__file__).resolve().parent / "director_receipt_context.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn("autonomous_engine", node.module)


if __name__ == "__main__":
    unittest.main()
