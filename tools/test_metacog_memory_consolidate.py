#!/usr/bin/env python3
"""Unit tests for C3: Metacognitive Memory Consolidation (strictly read-only)."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from tools.metacog_memory_consolidate import (
    SCHEMA,
    consolidate_metacognitive_memory,
    render_markdown,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _canonical(val: object) -> str:
    return json.dumps(val, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(val: object) -> str:
    if isinstance(val, (bytes, bytearray)):
        return hashlib.sha256(bytes(val)).hexdigest()
    return hashlib.sha256(_canonical(val).encode("utf-8")).hexdigest()


def _build_memory_log(path: Path) -> bytes:
    ev_dig = _digest(b"skill-receipt")
    events = [
        {"type": "anchor", "digest": ev_dig},
        {
            "type": "record",
            "record": {
                "id": "mem_proc_01",
                "kind": "procedural",
                "content": {"name": "fix_boundary", "class": "skill_verified", "subject": "pricing"},
                "source": {"kind": "evidence", "ref": ev_dig},
                "confidence": 0.9,
                "status": "active",
                "written_seq": 2,
                "outcomes": {},
            },
        },
        {"type": "outcome", "record_id": "mem_proc_01", "context": "shipping", "success": True},
        {"type": "outcome", "record_id": "mem_proc_01", "context": "tax_v2", "success": False},
        {"type": "outcome", "record_id": "mem_proc_01", "context": "tax_v2", "success": False},
        {
            "type": "record",
            "record": {
                "id": "mem_find_01",
                "kind": "episodic",
                "content": {"class": "finding_high_opened", "event": "OPEN: empty_corpus_bypass", "finding_id": "HIGH_01"},
                "source": {"kind": "evidence", "ref": ev_dig},
                "confidence": 0.9,
                "status": "active",
                "written_seq": 6,
                "outcomes": {},
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


class MetacogConsolidateTests(unittest.TestCase):
    def test_consolidates_memory_jsonl_episodes_and_real_metacog_readonly(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem_dir = root / "mem_store"
            mem_dir.mkdir()
            mem_file = mem_dir / "memory.jsonl"
            before = _build_memory_log(mem_file)

            ep_snap = root / "episodes.jsonl"
            ep_snap.write_text(
                "\n".join(
                    [
                        json.dumps({
                            "episode_id": "ep_101",
                            "task_family": "json_parse",
                            "status": "FAIL",
                            "failure_mode": "timeout_backoff",
                            "predicted_prob": 0.85,
                            "context": "groq_burst",
                            "summary": "Worker timed out under burst 101",
                        }),
                        json.dumps({
                            "episode_id": "ep_102",
                            "task_family": "json_parse",
                            "status": "FAIL",
                            "failure_mode": "timeout_backoff",
                            "predicted_prob": 0.80,
                            "context": "groq_burst",
                            "summary": "Worker timed out under burst 102",
                        }),
                        json.dumps({
                            "episode_id": "ep_103",
                            "task_family": "regex_guard",
                            "status": "PASS",
                            "predicted_prob": 0.92,
                            "context": "offline_gate",
                            "summary": "Guard verified cleanly",
                        }),
                        "{broken-json-line",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            real_mc = REPO_ROOT / "checkpoints" / "self_dev" / "metacognitive_memory.json"
            os.chmod(mem_file, 0o444)
            os.chmod(mem_dir, 0o555)
            try:
                r1 = consolidate_metacognitive_memory([mem_dir, ep_snap, real_mc], root=REPO_ROOT)
                r2 = consolidate_metacognitive_memory([mem_dir, ep_snap, real_mc], root=REPO_ROOT)
            finally:
                os.chmod(mem_dir, 0o755)
                os.chmod(mem_file, 0o644)

            self.assertEqual(mem_file.read_bytes(), before)
            self.assertEqual(_canonical(r1), _canonical(r2))
            self.assertEqual(r1["schema"], SCHEMA)
            self.assertTrue(r1["read_only"])
            self.assertEqual(r1["totals"]["skipped_malformed"], 1)
            self.assertEqual(r1["totals"]["open_high_findings"], 1)
            self.assertEqual(len(r1["negative_transfer_alerts"]), 1)
            self.assertEqual(r1["negative_transfer_alerts"][0]["failing_context"], "tax_v2")

            recurring = [c for c in r1["failure_clusters"] if c["recurring"]]
            self.assertGreaterEqual(len(recurring), 2)
            by_key = {c["cluster_key"]: c for c in r1["failure_clusters"]}
            self.assertIn("json_parse::timeout_backoff", by_key)
            jb = by_key["json_parse::timeout_backoff"]
            self.assertEqual(jb["count"], 2)
            self.assertEqual(jb["calibration"]["overconfident_failures"], 2)

            md = render_markdown(r1)
            self.assertIn("Konsolidasi Memori Metakognitif", md)
            self.assertIn("BERULANG", md)

    def test_missing_or_empty_inputs_never_create_store(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            absent = Path(td) / "nonexistent_mem"
            res = consolidate_metacognitive_memory([absent], root=Path(td))
            self.assertFalse(absent.exists())
            self.assertEqual(res["missing_inputs"], ["nonexistent_mem"])
            self.assertEqual(res["totals"]["observations"], 0)
            self.assertEqual(res["failure_clusters"], [])


if __name__ == "__main__":
    unittest.main()
