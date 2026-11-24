"""Tool layer v1 tests: operational core, MCP wiring, and thin CLI.

Covers ACE_TOOL_LAYER_PLAN_v1 Phase 1-3 behavior against a throwaway
workspace: task lifecycle through the store's real state machine,
cognitive-memory remember/recall/forget/audit with honest provenance,
gap dedup, skills, work orders that do not self-verify, preimage-hash
guarded file writes, receipt-based verification verdicts, the
operator write opt-in, and the CLI calling the identical core.
"""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest

from ace_mcp.bridge import ACEBridge, json_rpc
from ace_mcp.cli import main as cli_main
from ace_mcp.op_bridge import OperationalBridge


class OperationalBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.op = OperationalBridge(self.ws, allow_writes=True)

    def tearDown(self) -> None:
        self.op.store.close()
        self._tmp.cleanup()

    def test_status_shape(self) -> None:
        out = self.op.call("ace_op_status", {})
        self.assertIn("memory", out)
        self.assertTrue(out["memory"]["chain_ok"])
        self.assertEqual(out["tasks_total"], 0)

    def test_task_lifecycle_and_verify_verdict(self) -> None:
        task = self.op.call("ace_op_task_create", {
            "agent": "test-agent", "title": "Uji tool layer",
            "goal": "Membuktikan siklus tugas lewat tool layer"})
        tid = task["task_id"]
        self.assertEqual(task["status"], "QUEUED")

        moved = self.op.call("ace_op_task_update_status", {
            "task_id": tid, "status": "ACTIVE"})
        self.assertEqual(moved["status"], "ACTIVE")

        with self.assertRaises(ValueError):
            self.op.call("ace_op_task_update_status", {
                "task_id": tid, "status": "QUEUED"})

        got = self.op.call("ace_op_task_get", {"task_id": tid})
        self.assertIn("receipts", got)
        self.assertIn("work_orders", got)

        verdict = self.op.call("ace_op_verify_task", {"task_id": tid})
        self.assertEqual(verdict["verdict"], "NOT_VERIFIED")
        self.assertEqual(verdict["receipts_total"], 0)
        self.assertTrue(verdict["memory_chain_ok"])

    def test_memory_roundtrip_with_provenance_and_forget(self) -> None:
        res = self.op.call("ace_op_memory_remember", {
            "agent": "claude-test", "text": "namaku adalah Tes Percobaan"})
        self.assertTrue(res["stored"])
        rid = res["record_id"]

        audit = self.op.call("ace_op_memory_audit", {})
        self.assertTrue(audit["audit"]["chain_ok"])
        self.assertGreaterEqual(audit["summary"]["active_records"], 1)

        found = self.op.call("ace_op_memory_recall", {"query": "nama"})
        self.assertTrue(any(r["id"] == rid for r in found["results"]))
        rec = next(r for r in found["results"] if r["id"] == rid)
        self.assertEqual(rec["source"]["kind"], "external")
        self.assertEqual(rec["source"]["ref"], "claude-test")

        forgot = self.op.call("ace_op_memory_forget", {"record_id": rid})
        self.assertEqual(forgot["tombstone"]["record_id"], rid)
        after = self.op.call("ace_op_memory_recall", {"query": "nama"})
        self.assertFalse(any(r["id"] == rid for r in after["results"]))

    def test_gap_dedup_skill_and_work_order(self) -> None:
        gap_args = {"error_type": "missing_tool", "missing_skill_or_tool": "pdf_reader",
                    "description": "Tidak ada pembaca PDF", "source_task_id": "t1",
                    "reproduction_ref": "ref-1"}
        first = self.op.call("ace_op_gap_report", gap_args)
        second = self.op.call("ace_op_gap_report", gap_args)
        self.assertTrue(first["created_new"])
        self.assertFalse(second["created_new"])

        skill = self.op.call("ace_op_skill_create", {
            "name": "baca_pdf", "domain": "dokumen",
            "procedure_steps": ["buka berkas", "ekstrak teks"]})
        got = self.op.call("ace_op_skill_get", {"skill_id": skill["skill_id"]})
        self.assertEqual(got["name"], "baca_pdf")

        task = self.op.call("ace_op_task_create", {"title": "Induk", "goal": "g"})
        wo = self.op.call("ace_op_work_order_create", {
            "parent_task_id": task["task_id"], "objective": "kerjakan bagian A",
            "idempotency_key": "k-1"})
        self.assertTrue(wo["created_new"])
        again = self.op.call("ace_op_work_order_create", {
            "parent_task_id": task["task_id"], "objective": "kerjakan bagian A",
            "idempotency_key": "k-1"})
        self.assertFalse(again["created_new"])

        submitted = self.op.call("ace_op_work_order_submit", {
            "work_order_id": wo["work_order"]["work_order_id"],
            "result": {"ringkasan": "selesai"}})
        self.assertEqual(submitted["status"], "SUBMITTED")
        self.assertEqual(submitted["verification_status"], "UNVERIFIED")

    def test_file_write_preimage_guard(self) -> None:
        out = self.op.call("ace_op_file_write", {
            "path": "catatan/uji.txt", "content": "halo",
            "expected_sha256": ""})
        self.assertEqual(out["sha256_before"], "")
        self.assertTrue(out["sha256_after"])

        with self.assertRaises(ValueError):
            self.op.call("ace_op_file_write", {
                "path": "catatan/uji.txt", "content": "timpa",
                "expected_sha256": ""})
        with self.assertRaises(ValueError):
            self.op.call("ace_op_file_write", {
                "path": "../kabur.txt", "content": "x", "expected_sha256": ""})

        out2 = self.op.call("ace_op_file_write", {
            "path": "catatan/uji.txt", "content": "halo dunia",
            "expected_sha256": out["sha256_after"]})
        self.assertEqual(out2["sha256_before"], out["sha256_after"])
        self.assertEqual((self.ws / "catatan" / "uji.txt").read_text(encoding="utf-8"),
                         "halo dunia")


class BridgeWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_operational_tools_listed_only_when_enabled(self) -> None:
        off = ACEBridge(self.ws)
        self.assertFalse(any(t["name"].startswith("ace_op_")
                             for t in off.tools()))
        on = ACEBridge(self.ws, operational=True)
        self.assertTrue(any(t["name"] == "ace_op_status" for t in on.tools()))

    def test_write_gate_is_operator_optin(self) -> None:
        bridge = ACEBridge(self.ws, operational=True)  # allow_writes=False
        resp = json_rpc({"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                         "params": {"name": "ace_op_task_create",
                                    "arguments": {"title": "x", "goal": "y"}}},
                        bridge)
        self.assertTrue(resp["result"]["isError"])
        self.assertIn("disabled", resp["result"]["content"][0]["text"])

        ok = ACEBridge(self.ws, operational=True, allow_writes=True)
        resp2 = json_rpc({"jsonrpc": "2.0", "id": 8, "method": "tools/call",
                          "params": {"name": "ace_op_task_create",
                                     "arguments": {"title": "x", "goal": "y"}}},
                         ok)
        self.assertFalse(resp2["result"]["isError"])


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = str(Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run_cli(self, argv: list[str]) -> tuple[int, dict]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli_main(argv)
        return code, json.loads(buf.getvalue())

    def test_cli_list_and_call_share_the_core(self) -> None:
        code, out = self._run_cli(["--workspace", self.ws, "list"])
        self.assertEqual(code, 0)
        self.assertTrue(any(t["name"] == "ace_op_memory_audit"
                            for t in out["tools"]))

        code, out = self._run_cli(
            ["--workspace", self.ws, "--read-write", "call",
             "ace_op_task_create", '{"title": "lewat CLI", "goal": "uji"}'])
        self.assertEqual(code, 0)
        self.assertEqual(out["status"], "QUEUED")

        code, out = self._run_cli(
            ["--workspace", self.ws, "call",
             "ace_op_task_create", '{"title": "ditolak", "goal": "uji"}'])
        self.assertEqual(code, 1)
        self.assertEqual(out["status"], "ACE_TOOL_ERROR")


class ToolboxBatch1Tests(unittest.TestCase):
    """Batch 1: ACE's own repo tools (tools/) opened to its agents."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.op = OperationalBridge(self.ws, allow_writes=True)
        self.ro = OperationalBridge(self.ws, allow_writes=False)

    def tearDown(self) -> None:
        self.ro.store.close()
        self.op.store.close()
        self._tmp.cleanup()

    def test_toolbox_registered_and_readonly(self) -> None:
        from ace_mcp.op_bridge import ACE_TOOLBOX_SPECS, OP_WRITE_TOOLS
        self.assertEqual(len(ACE_TOOLBOX_SPECS), 12)
        for spec in ACE_TOOLBOX_SPECS:
            self.assertTrue(spec["name"].startswith("ace_op_tool_"))
            self.assertNotIn(spec["name"], OP_WRITE_TOOLS)
            self.assertIn(spec["name"],
                          [s["name"] for s in self.ro.tools()])

    def test_mastery_board_and_curriculum_ab(self) -> None:
        board = self.ro.call("ace_op_tool_mastery_board",
                             {"domains": {"coding": {"closure": 0.5},
                                          "language": {"closure": 1.0}}})
        self.assertIn("summary", board)
        report = self.ro.call(
            "ace_op_tool_curriculum_ab",
            {"fixed": [{"family": "bfs", "status": "COMPLETED"}],
             "generated": [{"family": "bfs", "closed": True}]})
        self.assertIsInstance(report, dict)

    def test_prose_audit_and_practice_lint(self) -> None:
        audit = self.ro.call("ace_op_tool_prose_audit",
                             {"text": "# Laporan\n\nSemua sistem pasti sempurna."})
        self.assertIn("summary", audit)
        lint = self.ro.call("ace_op_tool_practice_lint", {"tasks": [
            {"id": "t1", "title": "Latihan", "prompt": "Buat fungsi f",
             "reference_solution": "def f():\n    return 1",
             "evaluator_code": "def check(fn):\n    return fn() == 1",
             "test_cases": [[]]}]})
        self.assertIn("summary", lint)

    def test_occurrence_outliers_on_live_store(self) -> None:
        out = self.ro.call("ace_op_tool_occurrence_outliers", {})
        self.assertIn("summary", out)

    def test_gap_patterns_defaults_to_store_gaps(self) -> None:
        with self.assertRaises(ValueError):
            self.ro.call("ace_op_tool_gap_patterns", {})
        self.op.call("ace_op_gap_report", {
            "agent": "test-agent", "error_type": "MISSING_SKILL",
            "missing_skill_or_tool": "uji", "description": "gap uji"})
        out = self.ro.call("ace_op_tool_gap_patterns", {})
        self.assertIsInstance(out, dict)

    def test_receipt_chain_and_workspace_escape_guard(self) -> None:
        path = self.ws / "director_exec_receipts.jsonl"
        path.write_text('{"at": "2026-11-24T00:00:00Z"}\n', encoding="utf-8")
        out = self.ro.call("ace_op_tool_receipt_chain",
                           {"path": "director_exec_receipts.jsonl"})
        self.assertIsInstance(out, dict)
        with self.assertRaises(ValueError):
            self.ro.call("ace_op_tool_receipt_chain",
                         {"path": "../outside.jsonl"})


class ToolboxBatch2Tests(unittest.TestCase):
    """Batch 2: memory hygiene/decay, director helpers, factories."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.op = OperationalBridge(self.ws, allow_writes=True)
        self.ro = OperationalBridge(self.ws, allow_writes=False)

    def tearDown(self) -> None:
        self.ro.store.close()
        self.op.store.close()
        self._tmp.cleanup()

    def test_batch2_registration_and_write_gating(self) -> None:
        from ace_mcp.op_bridge import ACE_TOOLBOX2_SPECS, OP_WRITE_TOOLS
        self.assertEqual(len(ACE_TOOLBOX2_SPECS), 10)
        write_names = {s["name"] for s in ACE_TOOLBOX2_SPECS
                       if s["name"] in OP_WRITE_TOOLS}
        self.assertEqual(write_names, {"ace_op_tool_candidate_factory_v2",
                                       "ace_op_tool_discriminating_candidates"})
        with self.assertRaises(PermissionError):
            self.ro.call("ace_op_tool_candidate_factory_v2",
                         {"id_lang_count": 1, "ml_lang_count": 1,
                          "code_count": 1})

    def test_director_helpers(self) -> None:
        proposals = [{"proposal_id": "p1", "title": "Latihan BFS",
                      "rationale": "Ada 3 gap terbuka tentang graf",
                      "based_on": ["gap_1"]}]
        out = self.ro.call("ace_op_tool_director_challenge",
                           {"proposals": proposals,
                            "facts": {"gap_1": {"status": "OPEN"}}})
        self.assertIsInstance(out, dict)
        routed = self.ro.call("ace_op_tool_director_route",
                              {"proposals": proposals,
                               "gap_error_types": {"gap_1": "PRACTICE_ERROR"}})
        self.assertIsInstance(routed, dict)
        grounded = self.ro.call("ace_op_tool_director_grounding",
                                {"proposals": proposals,
                                 "facts": {"open_gaps": 3}})
        self.assertIsInstance(grounded, dict)

    def test_gap_root_causes_on_live_store(self) -> None:
        out = self.ro.call("ace_op_tool_gap_root_causes", {})
        self.assertIsInstance(out, dict)

    def test_discriminating_factory_writes_intake(self) -> None:
        out = self.op.call("ace_op_tool_discriminating_candidates",
                           {"agent": "test-agent", "lang_count": 2,
                            "code_count": 2, "seed": 7,
                            "write_to": "discriminating_intake.jsonl"})
        self.assertTrue(out["written"])
        self.assertTrue((self.ws / "discriminating_intake.jsonl").is_file())

    def test_candidate_factory_v2_bundle(self) -> None:
        out = self.op.call("ace_op_tool_candidate_factory_v2",
                           {"agent": "test-agent", "id_lang_count": 5,
                            "ml_lang_count": 5, "code_count": 5, "seed": 3})
        self.assertIsInstance(out, dict)
        self.assertTrue((self.ws / "candidates_v2").is_dir())


class ToolboxBatch3Tests(unittest.TestCase):
    """Batch 3: organ/observation family, all read-only."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.ro = OperationalBridge(self.ws, allow_writes=False)

    def tearDown(self) -> None:
        self.ro.store.close()
        self._tmp.cleanup()

    def test_batch3_registered_readonly(self) -> None:
        from ace_mcp.op_bridge import ACE_TOOLBOX3_SPECS, OP_WRITE_TOOLS
        self.assertEqual(len(ACE_TOOLBOX3_SPECS), 9)
        for spec in ACE_TOOLBOX3_SPECS:
            self.assertNotIn(spec["name"], OP_WRITE_TOOLS)

    def test_scoreboard_and_idle_report(self) -> None:
        board = self.ro.call("ace_op_tool_organ_scoreboard", {
            "receipts": [{"task_id": "t1", "organ": "front",
                          "at": "2026-11-24T00:00:00Z", "passed": True}],
            "grounding_rows": []})
        self.assertIsInstance(board, dict)
        idle = self.ro.call("ace_op_tool_idle_report", {
            "log_records": [{"ts": "2026-11-24T00:00:00Z", "cycle": 1},
                            {"ts": "2026-11-24T00:05:00Z", "cycle": 2}]})
        self.assertIsInstance(idle, dict)

    def test_recall_delivery_and_verdict_board(self) -> None:
        out = self.ro.call("ace_op_tool_recall_delivery", {
            "tasks": [{"id": "h1", "query": "latihan graf bfs"}],
            "store": {"records": [{"id": "m1", "title": "graf",
                                   "text": "latihan graf bfs"}]}})
        self.assertIsInstance(out, dict)
        board = self.ro.call("ace_op_tool_verdict_board", {"gate_paths": {}})
        self.assertIsInstance(board, dict)


class ToolboxBatch4Tests(unittest.TestCase):
    """Batch 4: agenda/curiosity/report family, all read-only."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.ro = OperationalBridge(self.ws, allow_writes=False)

    def tearDown(self) -> None:
        self.ro.store.close()
        self._tmp.cleanup()

    def test_batch4_registered_readonly(self) -> None:
        from ace_mcp.op_bridge import ACE_TOOLBOX4_SPECS, OP_WRITE_TOOLS
        self.assertEqual(len(ACE_TOOLBOX4_SPECS), 8)
        for spec in ACE_TOOLBOX4_SPECS:
            self.assertNotIn(spec["name"], OP_WRITE_TOOLS)

    def test_plain_data_tools(self) -> None:
        prio = self.ro.call("ace_op_tool_agenda_prioritize", {"items": [{
            "schema": "ace.agenda-proposal.v1", "proposal_id": "p1",
            "brain_of_origin": "claude-agent", "title": "satu",
            "sources": [{"path": "code/ace_mcp/op_bridge.py"}],
            "kind": "failure", "status": "proposal_only",
            "claim_made": False, "requires_human_validation": True}]})
        self.assertIsInstance(prio, list)
        nov = self.ro.call("ace_op_tool_corpus_novelty", {
            "corpus": [{"work_id": "w1", "text": "graf pohon biner"}],
            "candidates": [{"work_id": "c1", "text": "resep rendang sapi"}]})
        self.assertIsInstance(nov, dict)
        cap = self.ro.call("ace_op_tool_capability_report", {
            "gate_board": {"gates": {}}, "store_stats": {"tasks": 3}})
        self.assertIsInstance(cap, dict)
        ver = self.ro.call("ace_op_tool_assessment_verify",
                           {"versions": []})
        self.assertIsInstance(ver, dict)


if __name__ == "__main__":
    unittest.main()
