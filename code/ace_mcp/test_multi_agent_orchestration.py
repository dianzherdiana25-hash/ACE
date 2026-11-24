"""Tests for Orchestrator v3: Multi-Agent Registry, Fenced Leases, Directive Orientation, Profiles, & Verified Skill Absorption."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from ace_mcp.bridge import ACEBridge, json_rpc
from ace_mcp.op_bridge import OperationalBridge
from ace_operational.agent_director import absorb_verified_skill, orient_agent, search_tools
from ace_operational.connectors.vault import SecretVault
from ace_self_dev.fenced_store import LeaseRejected
from ace_web_operator._contracts import canonical, identity


class MultiAgentOrchestrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ace-v3-orch-")
        self.ws = Path(self._tmp.name) / "ws"
        self.op = OperationalBridge(self.ws, allow_writes=True)

    def tearDown(self) -> None:
        self.op.store.close()
        self._tmp.cleanup()

    def test_agent_registry_and_cross_vendor_selection(self) -> None:
        a1 = self.op.call("ace_op_agent_register", {
            "agent_id": "antigravity-coder",
            "vendor": "antigravity",
            "roles": ["coder", "brain"],
            "transport": "mcp_stdio",
        })
        a2 = self.op.call("ace_op_agent_register", {
            "agent_id": "gemini-critic",
            "vendor": "gemini",
            "roles": ["critic", "researcher"],
            "transport": "local_cli",
        })
        self.assertEqual(a1["vendor"], "antigravity")
        self.assertEqual(a2["vendor"], "gemini")

        picked = self.op.store.select_agent_for_role(
            "critic",
            exclude_agents=("antigravity-coder",),
            exclude_vendors=("antigravity",),
        )
        self.assertIsNotNone(picked)
        self.assertEqual(picked["agent_id"], "gemini-critic")

    def test_fenced_work_order_claim_prevents_double_claim_until_release(self) -> None:
        task = self.op.call("ace_op_task_create", {"title": "Build X", "goal": "Create X cleanly"})
        wo_res = self.op.call("ace_op_work_order_create", {
            "parent_task_id": task["task_id"],
            "objective": "Implement X",
            "idempotency_key": "wo-claim-1",
            "required_role": "coder",
            "payload": {"target": "x.py"},
        })
        wo_id = wo_res["work_order"]["work_order_id"]

        claimed = self.op.call("ace_op_work_order_claim", {
            "work_order_id": wo_id,
            "agent_id": "agent-alpha",
            "ttl_sec": 300,
        })
        self.assertEqual(claimed["status"], "CLAIMED")
        self.assertTrue(claimed["lease_token"])
        self.assertGreater(claimed["lease_epoch"], 0)

        with self.assertRaises(LeaseRejected):
            self.op.call("ace_op_work_order_claim", {
                "work_order_id": wo_id,
                "agent_id": "agent-beta",
            })

        released = self.op.call("ace_op_work_order_release", {
            "work_order_id": wo_id,
            "agent_id": "agent-alpha",
            "lease_token": claimed["lease_token"],
        })
        self.assertEqual(released["status"], "PENDING")

        reclaimed = self.op.call("ace_op_work_order_claim", {
            "work_order_id": wo_id,
            "agent_id": "agent-beta",
        })
        self.assertEqual(reclaimed["claimed_by"], "agent-beta")

    def test_orient_agent_redacts_secrets_hides_private_memories_and_shows_revision_feedback(self) -> None:
        vault = SecretVault(self.ws)
        vault.set_venue_credentials("facebook", {"page_id": "pg_123", "page_access_token": "EAAGSecretTokenValue999999"})

        self.op.call("ace_op_memory_remember", {
            "agent": "owner",
            "text": "Gunakan rasio 9:16 untuk Reels produk EAAGSecretTokenValue999999",
            "sensitivity": "internal",
        })
        self.op.call("ace_op_memory_remember", {
            "agent": "owner",
            "text": "PIN bank rahasia 998877",
            "sensitivity": "private",
        })
        self.op.call("ace_op_skill_create", {
            "name": "reels_hook_builder",
            "domain": "video_reels",
            "procedure_steps": ["Buat hook pertanyaan <5 detik", "Verifikasi fakta sumber"],
        })

        goal = self.op.call("ace_op_goal_create", {
            "title": "Reels Promo Mei",
            "user_request": "Buat strategi video Reels produk",
            "domain": "video_reels",
            "min_quality_score_bp": 8800,
        })
        wo_id = goal["stages"][0]["work_order_id"]
        self.op.store.update_work_order(
            wo_id,
            revision_count=1,
            quality_score_bp=6100,
            payload={"revision_feedback": ["Hook terlalu lambat di scene sc_1"]},
        )

        packet = orient_agent(
            self.op.store,
            self.op.memory,
            agent_id="muse-worker",
            vendor="muse.ai",
            work_order_id=wo_id,
        )
        dumped = json.dumps(packet, ensure_ascii=False)
        self.assertNotIn("EAAGSecretTokenValue999999", dumped)
        self.assertNotIn("PIN bank rahasia 998877", dumped)
        self.assertEqual(packet["quality_contract"]["min_score_bp"], 8800)
        self.assertEqual(packet["assignment"]["revision_history"]["revision_count"], 1)
        self.assertIn("Hook terlalu lambat", packet["assignment"]["revision_history"]["revision_feedback"][0])
        self.assertTrue(any(s["name"] == "reels_hook_builder" for s in packet["skills"]))
        self.assertGreaterEqual(len(packet["recommended_tools"]), 1)

    def test_tool_profile_core_uses_search_and_invoke(self) -> None:
        core_bridge = ACEBridge(self.ws, allow_writes=True, operational=True, tool_profile="core")
        full_bridge = ACEBridge(self.ws, allow_writes=True, operational=True, tool_profile="full")
        self.assertLess(len(core_bridge.tools()), len(full_bridge.tools()))

        search_res = core_bridge.call("ace_op_tool_search", {"query": "kbm", "limit": 10})
        self.assertTrue(any(t["name"] == "ace_op_tool_kbm_arc_rubric" for t in search_res["tools"]))

        inv_res = core_bridge.call("ace_op_tool_invoke", {
            "tool": "ace_op_tool_kbm_arc_rubric",
            "arguments": {"pack": {"pack_id": "p1", "chapters": [{"chapter_id": "b1", "text": "Budi? Tidak! Namun akhirnya Budi pergi."}]}},
        })
        self.assertIn("overall", inv_res)

        # Read-only bridge still blocks invoking write tool through ace_op_tool_invoke.
        ro_bridge = ACEBridge(self.ws, allow_writes=False, operational=True, tool_profile="core")
        with self.assertRaises(PermissionError):
            ro_bridge.call("ace_op_tool_invoke", {
                "tool": "ace_op_task_create",
                "arguments": {"title": "Blocked", "goal": "Should fail"},
            })

    def test_skill_absorption_and_auto_suspend_unreliable(self) -> None:
        with self.assertRaises(ValueError):
            absorb_verified_skill(
                self.op.store,
                name="tanpa_bukti",
                domain="general",
                procedure_steps=["langkah 1"],
                source_refs=(),
                checks_passed=("check_1",),
            )
        low_res = absorb_verified_skill(
            self.op.store,
            name="skor_rendah",
            domain="general",
            procedure_steps=["langkah 1"],
            source_refs=("src/doc.md",),
            checks_passed=("test_1",),
            verified_score_bp=6500,
            min_score_bp=8500,
        )
        self.assertFalse(low_res["accepted"])

        # Test source_quality_gate full absorption bridge on local files.
        src_root = self.ws / "absorb_src"
        src_root.mkdir(parents=True, exist_ok=True)
        src_file = src_root / "guide.md"
        src_body = "Hook tiga detik memicu rasa penasaran dan retensi penonton secara nyata dalam video pendek vertikal."
        src_file.write_text(src_body + "\n", encoding="utf-8")
        src_sha = sha256(src_file.read_bytes()).hexdigest()
        heldout = {"skill": "reels_copy", "cases": [{"id": "h1"}]}
        curriculum = {
            "schema": "ace.web.skill-absorb-plan.v1",
            "id": "reels_copy",
            "cluster": "media",
            "version": 1,
            "source_ref": "doc/reels",
            "heldout_sha256": identity(heldout),
            "sources": [{
                "id": "src_one",
                "path": "guide.md",
                "sha256": src_sha,
                "license": "MIT",
                "license_ref": "repo/LICENSE",
                "source_ref": "doc/reels",
            }],
            "objectives": [{"id": "obj_hook", "statement": "Menulis hook pembuka 3 detik", "source_ref": "doc/reels"}],
            "lessons": [{
                "id": "les_1",
                "source": "src_one",
                "first_line": 1,
                "last_line": 1,
                "objectives": ["obj_hook"],
                "source_ref": "doc/reels#L1",
            }],
            "practice": [{
                "id": "pr_1",
                "objective": "obj_hook",
                "prompt": "Berapa detik durasi hook pembuka?",
                "op": "int_exact",
                "expected": 3,
                "source_ref": "doc/reels#L1",
            }],
        }
        policy = {
            "schema": "ace.web.source-quality-policy.v1",
            "source_ref": "policy/default",
            "curriculum_sha256": identity(curriculum),
            "as_of": "2026-11-24T00:00:00Z",
            "rules": [{
                "source": "src_one",
                "source_ref": "policy/rule1",
                "observed_at": "2026-11-23T00:00:00Z",
                "max_age_days": 30,
                "min_words": 8,
                "max_duplicate_bp": 5000,
                "topics": [{"id": "top_hook", "phrase": "hook tiga detik", "source_ref": "doc/reels"}],
            }],
        }
        ok = absorb_verified_skill(
            self.op.store,
            self.op.memory,
            name="Reels Hook Pattern",
            domain="video_reels",
            procedure_steps=["Buka dengan pertanyaan hook 3 detik", "Lanjutkan aksi visual"],
            source_refs=("doc/reels",),
            checks_passed=("source_quality_gate:eligible",),
            verified_score_bp=9000,
            absorption_root=src_root,
            quality_policy=policy,
            curriculum=curriculum,
        )
        self.assertTrue(ok["accepted"])
        sid = ok["skill"]["skill_id"]

        # Record 2 negative transfers -> skill auto-suspended.
        self.op.call("ace_op_skill_record_outcome", {"skill_id": sid, "success": False, "negative_transfer": True})
        after = self.op.call("ace_op_skill_record_outcome", {"skill_id": sid, "success": False, "negative_transfer": True})
        self.assertEqual(after["status"], "SUSPENDED")


if __name__ == "__main__":
    unittest.main()
