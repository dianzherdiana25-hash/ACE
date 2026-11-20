"""Tes audit anchor batch proposal: campuran anchored, partial, dangling, dan tanpa based_on.

Kenapa: memastikan proposal tanpa based_on tertandai eksplisit (bukan lolos
diam-diam) dan hitungan ringkasan cocok dengan vonis per proposal.
"""
from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from contextlib import redirect_stdout

from tools.memory_anchor_audit import (
    VerifiedRefSet,
    audit_proposals,
    load_verified_store,
    main,
)


class MemoryAnchorBatchAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = VerifiedRefSet(["ref-ok-1", "ref-ok-2"])
        self.proposals = [
            {"task_id": "p-anchored", "based_on": ["ref-ok-1", "ref-ok-2"]},
            {"task_id": "p-partial", "based_on": ["ref-ok-1", "ref-hilang"]},
            {"task_id": "p-dangling", "based_on": ["ref-hilang-1", "ref-hilang-2"]},
            {"task_id": "p-no-based-on"},
            {"task_id": "p-empty-based-on", "based_on": []},
        ]

    def test_mixed_batch_verdicts_and_explicit_missing_based_on(self) -> None:
        report = audit_proposals(self.proposals, self.store)
        self.assertEqual(report["total_proposals"], 5)
        self.assertEqual(
            report["counts"],
            {
                "anchored": 1,
                "partial": 1,
                "dangling": 1,
                "missing_based_on": 2,
            },
        )
        by_id = {row["task_id"]: row for row in report["proposals"]}
        self.assertEqual(by_id["p-anchored"]["verdict"], "anchored")
        self.assertEqual(by_id["p-anchored"]["score"], 1.0)
        self.assertEqual(by_id["p-partial"]["verdict"], "partial")
        self.assertEqual(by_id["p-partial"]["score"], 0.5)
        self.assertEqual(by_id["p-dangling"]["verdict"], "dangling")
        self.assertEqual(by_id["p-dangling"]["score"], 0.0)
        for missing_id in ("p-no-based-on", "p-empty-based-on"):
            self.assertEqual(by_id[missing_id]["verdict"], "missing_based_on")
            self.assertEqual(by_id[missing_id]["reason"], "based_on_missing_or_empty")
            self.assertNotEqual(by_id[missing_id]["verdict"], "anchored")

    def test_cli_reads_jsonl_and_verified_refs_file_read_only(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            prop_path = root / "proposals.jsonl"
            store_path = root / "store.json"
            prop_bytes = "".join(json.dumps(p) + "\n" for p in self.proposals).encode("utf-8")
            store_bytes = json.dumps({"verified_refs": ["ref-ok-1", "ref-ok-2"]}).encode("utf-8")
            prop_path.write_bytes(prop_bytes)
            store_path.write_bytes(store_bytes)

            buf = StringIO()
            with redirect_stdout(buf):
                code = main(["--proposals", str(prop_path), "--store", str(store_path)])
            self.assertEqual(code, 0)
            parsed = json.loads(buf.getvalue())
            self.assertEqual(parsed["counts"]["anchored"], 1)
            self.assertEqual(parsed["counts"]["partial"], 1)
            self.assertEqual(parsed["counts"]["dangling"], 1)
            self.assertEqual(parsed["counts"]["missing_based_on"], 2)
            # Murni baca: berkas masukan tidak berubah
            self.assertEqual(prop_path.read_bytes(), prop_bytes)
            self.assertEqual(store_path.read_bytes(), store_bytes)

    def test_duplicate_task_id_and_bad_store_rejected(self) -> None:
        with self.assertRaises(ValueError):
            audit_proposals(
                [{"task_id": "dup", "based_on": ["ref-ok-1"]}, {"task_id": "dup", "based_on": ["ref-ok-1"]}],
                self.store,
            )
        with TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text('{"verified_refs": [""]}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_verified_store(bad)


if __name__ == "__main__":
    unittest.main()
