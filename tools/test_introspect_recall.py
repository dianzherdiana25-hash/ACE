#!/usr/bin/env python3
"""Unit tests for C4: Introspect & Recall Q&A CLI (strictly read-only)."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from tools.introspect_recall import (
    SCHEMA,
    query_introspection,
    render_markdown,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _canonical(val: object) -> str:
    return json.dumps(val, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(val: object) -> str:
    if isinstance(val, (bytes, bytearray)):
        return hashlib.sha256(bytes(val)).hexdigest()
    return hashlib.sha256(_canonical(val).encode("utf-8")).hexdigest()


def _write_test_mem(path: Path) -> bytes:
    ev_dig = _digest(b"lineage-verdict")
    events = [
        {"type": "anchor", "digest": ev_dig},
        {
            "type": "record",
            "record": {
                "id": "mem_old_01",
                "kind": "semantic",
                "content": {"event": "Status lama router v1 pending", "subject": "router", "object": "pending"},
                "source": {"kind": "evidence", "ref": ev_dig},
                "confidence": 0.9,
                "status": "active",
                "written_seq": 2,
            },
        },
        {
            "type": "record",
            "record": {
                "id": "mem_new_02",
                "kind": "semantic",
                "content": {"event": "Status router v1 adopted secara resmi", "subject": "router", "object": "adopted"},
                "source": {"kind": "evidence", "ref": ev_dig},
                "confidence": 0.95,
                "status": "active",
                "written_seq": 3,
            },
        },
        {"type": "supersede", "record_id": "mem_old_01", "by": "mem_new_02"},
        {
            "type": "record",
            "record": {
                "id": "mem_guess_03",
                "kind": "semantic",
                "content": {"event": "Tebakan model mengenai jalur nebula"},
                "source": {"kind": "model", "ref": None},
                "confidence": 0.3,
                "status": "active",
                "written_seq": 5,
            },
        },
    ]
    prev = "GENESIS"
    lines = []
    for seq, ev in enumerate(events, start=1):
        entry = {"seq": seq, "prev": prev, "event": ev, "hash": _digest({"prev": prev, "event": ev})}
        prev = entry["hash"]
        lines.append(_canonical(entry))
    raw = ("\n".join(lines) + "\n").encode("utf-8")
    path.write_bytes(raw)
    return raw


class IntrospectRecallTests(unittest.TestCase):
    def test_real_repo_qa_returns_verified_source_pointers(self) -> None:
        r_guard = query_introspection("LINEAGE_GUARD_CONFIRMATION_VERDICT lineage guard", root=REPO_ROOT, scope="handover")
        self.assertEqual(r_guard["schema"], SCHEMA)
        self.assertTrue(r_guard["read_only"])
        self.assertEqual(r_guard["status"], "VERIFIED_ANSWER")
        self.assertTrue(len(r_guard["citations"]) >= 1)
        self.assertTrue(any("LINEAGE_GUARD" in c["path"] for c in r_guard["citations"]))
        for c in r_guard["citations"]:
            fpath = REPO_ROOT / c["path"]
            self.assertTrue(fpath.is_file())
            self.assertEqual(len(c["sha256"]), 64)

        r_seed = query_introspection("bahasa utama komunikasi ACE", root=REPO_ROOT, scope="memory")
        self.assertEqual(r_seed["status"], "VERIFIED_ANSWER")
        self.assertEqual(r_seed["citations"][0]["path"], "data/ace_seed_snapshot.json")

        md = render_markdown(r_guard)
        self.assertIn("VERIFIED_ANSWER", md)
        self.assertIn("sumber=", md)

    def test_memory_jsonl_readonly_provenance_superseded_and_guess_flags(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mem_dir = Path(td) / "mem"
            mem_dir.mkdir()
            mem_log = mem_dir / "memory.jsonl"
            before = _write_test_mem(mem_log)
            os.chmod(mem_log, 0o444)
            os.chmod(mem_dir, 0o555)
            try:
                res_router = query_introspection("Status router adopted", root=REPO_ROOT, memory_paths=[mem_dir], scope="memory")
                res_sup = query_introspection(
                    "Status lama router pending",
                    root=REPO_ROOT,
                    memory_paths=[mem_dir],
                    scope="memory",
                    include_superseded=True,
                )
                res_guess = query_introspection("jalur nebula", root=REPO_ROOT, memory_paths=[mem_dir], scope="memory")
            finally:
                os.chmod(mem_dir, 0o755)
                os.chmod(mem_log, 0o644)

            self.assertEqual(mem_log.read_bytes(), before)
            self.assertEqual(res_router["status"], "VERIFIED_ANSWER")
            self.assertEqual(res_router["hits"][0]["record_id"], "mem_new_02")
            self.assertIn("mem_old_01", [h["record_id"] for h in res_sup["hits"]])
            self.assertEqual(res_guess["status"], "GUESS_ONLY_UNVERIFIED")
            self.assertTrue(res_guess["guess_only"])

    def test_abstains_honestly_on_unanswerable_query(self) -> None:
        res = query_introspection("xyzzy quantum_unicorn_zxqv99", root=REPO_ROOT)
        self.assertEqual(res["status"], "NO_VERIFIED_EVIDENCE")
        self.assertEqual(res["hits"], [])
        self.assertEqual(res["citations"], [])
        self.assertIn("Abstain", res["answer"])


if __name__ == "__main__":
    unittest.main()
