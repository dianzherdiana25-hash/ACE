"""Tests for Zero-Infra Browser Copy-Paste Relay (`ace_mcp.relay`) supporting tool_requests loop & revision gates."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from ace_mcp.bridge import ACEBridge
from ace_mcp.relay import build_relay_prompt, ingest_relay_reply


class RelayTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ace-relay-")
        self.ws = Path(self._tmp.name) / "ws"
        self.bridge = ACEBridge(self.ws, allow_writes=True, operational=True, tool_profile="core")

    def tearDown(self) -> None:
        if self.bridge._op_bridge is not None:
            self.bridge._op_bridge.store.close()
        self._tmp.cleanup()

    def test_tool_requests_roundtrip_and_submission_revision_loop(self) -> None:
        goal = self.bridge.call("ace_op_goal_create", {
            "title": "Reels Tips Coding",
            "user_request": "Riset klaim & buat skrip Reels berkualitas tinggi",
            "domain": "video_reels",
            "min_quality_score_bp": 8500,
        })
        wo_id = goal["stages"][0]["work_order_id"]

        exported = build_relay_prompt(
            self.bridge,
            vendor="muse.ai",
            work_order_id=wo_id,
        )
        self.assertIn("Muse.ai Web", exported["prompt"])
        self.assertIn("ace.relay_reply.v1", exported["prompt"])

        # Round 1: Web AI sends fenced JSON tool_requests
        reply1 = """Berikut permintaan tool saya:
```json
{
  "schema": "ace.relay_reply.v1",
  "type": "tool_requests",
  "requests": [
    {"tool": "ace_op_tool_search", "arguments": {"query": "reels"}},
    {"tool": "ace_op_status", "arguments": {}}
  ]
}
```"""
        r1 = ingest_relay_reply(self.bridge, reply1, vendor="muse.ai", work_order_id=wo_id)
        self.assertEqual(r1["mode"], "tool_requests")
        self.assertEqual(len(r1["tool_results"]), 2)
        self.assertTrue(r1["tool_results"][0]["ok"])
        self.assertTrue(r1["tool_results"][1]["ok"])
        self.assertIn("Hasil Eksekusi Tool ACE", r1["continuation_prompt"])

        # Round 2: Ungrounded submission gets REJECTED with revision_prompt
        bad_reply = json.dumps({
            "schema": "ace.relay_reply.v1",
            "type": "submission",
            "work_order_id": wo_id,
            "result": {
                "claims": ["70% penonton suka hook cepat"],  # ungrounded raw string!
                "sources": [],
            },
        })
        r2 = ingest_relay_reply(self.bridge, bad_reply, vendor="muse.ai", work_order_id=wo_id)
        self.assertFalse(r2["verification"]["passed"])
        self.assertIn("DITOLAK QUALITY GATE ACE", r2["revision_prompt"])

        # Round 3: Grounded high-bar submission passes and records external memory provenance
        good_reply = json.dumps({
            "schema": "ace.relay_reply.v1",
            "type": "submission",
            "work_order_id": wo_id,
            "result": {
                "claims": [{"claim": "Hook 3 detik menaikkan penyelesaian tontonan", "source_ref": "src_meta_reels"}],
                "sources": [{
                    "id": "src_meta_reels",
                    "observed_at": "2026-11-20T00:00:00Z",
                    "content": "Laporan performa video pendek vertikal mencatat hook tiga detik pertama dan aksi visual meningkatkan penyelesaian tontonan audiens.",
                }],
            },
            "new_memories": ["Audiens merespons positif hook 3 detik"],
        })
        r3 = ingest_relay_reply(self.bridge, good_reply, vendor="muse.ai", work_order_id=wo_id)
        self.assertTrue(r3["verification"]["passed"])
        self.assertEqual(r3["memories_saved"], 1)
        self.assertEqual(r3["revision_prompt"], "")

    def test_relay_blocks_pasted_secrets_and_enforces_write_opt_in(self) -> None:
        with self.assertRaisesRegex(ValueError, "pola kredensial"):
            ingest_relay_reply(self.bridge, '{"type":"tool_requests","token":"EAAG1234567890ABCDEFGHIJK"}')

        ro_bridge = ACEBridge(self.ws, allow_writes=False, operational=True)
        res = ingest_relay_reply(
            ro_bridge,
            json.dumps({
                "schema": "ace.relay_reply.v1",
                "type": "tool_requests",
                "requests": [{"tool": "ace_op_task_create", "arguments": {"title": "x", "goal": "y"}}],
            }),
            vendor="chatgpt",
        )
        self.assertFalse(res["tool_results"][0]["ok"])
        self.assertIn("disabled", res["tool_results"][0]["error"])


if __name__ == "__main__":
    unittest.main()
