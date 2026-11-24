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


class ToolboxBatch5Tests(unittest.TestCase):
    """Batch 5: audit/agreement family, all read-only."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.ro = OperationalBridge(self.ws, allow_writes=False)

    def tearDown(self) -> None:
        self.ro.store.close()
        self._tmp.cleanup()

    def test_batch5_registered_readonly(self) -> None:
        from ace_mcp.op_bridge import ACE_TOOLBOX5_SPECS, OP_WRITE_TOOLS
        self.assertEqual(len(ACE_TOOLBOX5_SPECS), 8)
        for spec in ACE_TOOLBOX5_SPECS:
            self.assertNotIn(spec["name"], OP_WRITE_TOOLS)

    def test_plain_data_tools(self) -> None:
        inv = self.ro.call("ace_op_tool_execution_invariants",
                           {"receipts": [], "executions": []})
        self.assertIsInstance(inv, dict)
        snap = {"responses": [{"prompt_id": "p1", "category": "gaya",
                               "response": "jawaban", "response_sha256": "a" * 64}]}
        diff = self.ro.call("ace_op_tool_fingerprint_diff",
                            {"baseline": snap, "candidate": snap})
        self.assertIsInstance(diff, dict)
        val = self.ro.call("ace_op_tool_organ_registry_validate",
                           {"data": {}})
        self.assertIsInstance(val, dict)
        story = self.ro.call("ace_op_tool_story_consistency", {
            "story_state": {}, "chapter_draft": {"chapter_id": "c1"}})
        self.assertIsInstance(story, dict)


class ToolboxBatch6Tests(unittest.TestCase):
    """Batch 6: simulation/design family, all read-only."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.ro = OperationalBridge(self.ws, allow_writes=False)

    def tearDown(self) -> None:
        self.ro.store.close()
        self._tmp.cleanup()

    def test_batch6_registered_readonly(self) -> None:
        from ace_mcp.op_bridge import ACE_TOOLBOX6_SPECS, OP_WRITE_TOOLS
        self.assertEqual(len(ACE_TOOLBOX6_SPECS), 7)
        for spec in ACE_TOOLBOX6_SPECS:
            self.assertNotIn(spec["name"], OP_WRITE_TOOLS)

    def test_simulators_and_diagnose(self) -> None:
        plan = self.ro.call("ace_op_tool_cycle_plan_sim", {
            "world_model": {"house_state": "healthy"},
            "steps": [{"step_id": "s1", "role": "front",
                       "critical": False, "cost": 1}]})
        self.assertIsInstance(plan, dict)
        sim = self.ro.call("ace_op_tool_failover_sim", {
            "budget_state": {"roles": {"front": {"remaining": 3}}},
            "steps": [{"role": "front", "cost": 1, "critical": False}]})
        self.assertIsInstance(sim, dict)
        diag = self.ro.call("ace_op_tool_writeback_diagnose", {})
        self.assertIsInstance(diag, dict)


class ToolboxBatch7Tests(unittest.TestCase):
    """Batch 7: triage class A probes/checks, all read-only."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.ro = OperationalBridge(self.ws, allow_writes=False)

    def tearDown(self) -> None:
        self.ro.store.close()
        self._tmp.cleanup()

    def test_batch7_registered_readonly(self) -> None:
        from ace_mcp.op_bridge import ACE_TOOLBOX7_SPECS, OP_WRITE_TOOLS
        self.assertEqual(len(ACE_TOOLBOX7_SPECS), 6)
        for spec in ACE_TOOLBOX7_SPECS:
            self.assertNotIn(spec["name"], OP_WRITE_TOOLS)

    def test_forensics_and_autobiography(self) -> None:
        out = self.ro.call("ace_op_tool_organ_forensics", {
            "lines": ["2026-11-24T00:00:00Z INFO siklus mulai",
                      "2026-11-24T00:01:00Z ERROR organ front timeout"]})
        self.assertIsInstance(out, dict)
        suite = self.ro.call("ace_op_tool_autobiography_suite", {
            "history": [{"decision_id": "d1", "decision": "uji segel",
                         "date": "2026-11-01", "reason": "uji",
                         "outcome": "lulus"}]})
        self.assertIsInstance(suite, dict)


class ToolboxBatch8Tests(unittest.TestCase):
    """Batch 8: curriculum lab + first code/ packages, read-only."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.ro = OperationalBridge(self.ws, allow_writes=False)

    def tearDown(self) -> None:
        self.ro.store.close()
        self._tmp.cleanup()

    def test_batch8_registered_readonly(self) -> None:
        from ace_mcp.op_bridge import ACE_TOOLBOX8_SPECS, OP_WRITE_TOOLS
        self.assertEqual(len(ACE_TOOLBOX8_SPECS), 6)
        for spec in ACE_TOOLBOX8_SPECS:
            self.assertNotIn(spec["name"], OP_WRITE_TOOLS)

    def test_numeric_packages(self) -> None:
        q = self.ro.call("ace_op_tool_conformal_quantile",
                         {"scores": [0.1, 0.2, 0.3, 0.4], "alpha": 0.1})
        self.assertIsInstance(q, float)
        bounds = self.ro.call("ace_op_tool_pac_bayes_bounds", {
            "empirical_risk": 0.1, "kl_div": 2.0, "m": 100})
        self.assertEqual(sorted(bounds),
                         ["catoni", "mcallester", "seeger_maurer"])
        gap = self.ro.call("ace_op_tool_nash_gap", {
            "payoff_matrix": [[1, -1], [-1, 1]],
            "p": [0.5, 0.5], "q": [0.5, 0.5]})
        self.assertIsInstance(gap, float)
        self.assertAlmostEqual(gap, 0.0, places=6)

    def test_indo_nlp(self) -> None:
        out = self.ro.call("ace_op_tool_indo_meaning_query",
                           {"text": "apa arti kata swastamita?"})
        self.assertIsInstance(out, dict)


class ToolboxBatch9Tests(unittest.TestCase):
    """Batch 9: causal/epistemic/selfmodel/report packages."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.ro = OperationalBridge(self.ws, allow_writes=False)

    def tearDown(self) -> None:
        self.ro.store.close()
        self._tmp.cleanup()

    def test_batch9_registered_readonly(self) -> None:
        from ace_mcp.op_bridge import ACE_TOOLBOX9_SPECS, OP_WRITE_TOOLS
        self.assertEqual(len(ACE_TOOLBOX9_SPECS), 4)
        for spec in ACE_TOOLBOX9_SPECS:
            self.assertNotIn(spec["name"], OP_WRITE_TOOLS)

    def test_causal_and_entropy(self) -> None:
        dag = {"A": ["B"], "B": ["C"], "C": []}
        open_path = self.ro.call("ace_op_tool_d_separation", {
            "graph": dag, "x": "A", "y": "C", "z": []})
        self.assertEqual(open_path, {"d_separated": False})
        blocked = self.ro.call("ace_op_tool_d_separation", {
            "graph": dag, "x": "A", "y": "C", "z": ["B"]})
        self.assertEqual(blocked, {"d_separated": True})
        ent = self.ro.call("ace_op_tool_entropy", {"probs": [0.5, 0.5]})
        self.assertIsInstance(ent, float)
        self.assertGreater(ent, 0.0)

    def test_calibration(self) -> None:
        out = self.ro.call("ace_op_tool_calibration_metrics", {
            "records": [[0.9, True, True], [0.1, False, True]]})
        self.assertIsInstance(out, dict)


class ToolboxBatch10Tests(unittest.TestCase):
    """Batch 10: ace_evaluator family."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.ro = OperationalBridge(self.ws, allow_writes=False)

    def tearDown(self) -> None:
        self.ro.store.close()
        self._tmp.cleanup()

    def test_batch10_registered_readonly(self) -> None:
        from ace_mcp.op_bridge import ACE_TOOLBOX10_SPECS, OP_WRITE_TOOLS
        self.assertEqual(len(ACE_TOOLBOX10_SPECS), 3)
        for spec in ACE_TOOLBOX10_SPECS:
            self.assertNotIn(spec["name"], OP_WRITE_TOOLS)

    def test_evaluator_tools(self) -> None:
        verdict = self.ro.call("ace_op_tool_candidate_integrity", {
            "code": "def solve(x):\n    return x > 0\n"})
        self.assertIsInstance(verdict, dict)
        seed = self.ro.call("ace_op_tool_evaluation_seed", {})
        self.assertIsInstance(seed, dict)
        inst = self.ro.call("ace_op_tool_task_family_instances", {
            "family": "parity", "seed": 7, "count": 4})
        self.assertEqual(len(inst["instances"]), 4)


class ToolboxBatch11Tests(unittest.TestCase):
    """Batch 11: mission/code-agent/self-dev packages."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.ro = OperationalBridge(self.ws, allow_writes=False)

    def tearDown(self) -> None:
        self.ro.store.close()
        self._tmp.cleanup()

    def test_batch11_registered_readonly(self) -> None:
        from ace_mcp.op_bridge import ACE_TOOLBOX11_SPECS, OP_WRITE_TOOLS
        self.assertEqual(len(ACE_TOOLBOX11_SPECS), 4)
        for spec in ACE_TOOLBOX11_SPECS:
            self.assertNotIn(spec["name"], OP_WRITE_TOOLS)

    def test_scorers(self) -> None:
        brier = self.ro.call("ace_op_tool_brier_score", {
            "predictions": [0.9, 0.1], "outcomes": [True, False]})
        self.assertIsInstance(brier, float)
        self.assertLess(brier, 0.05)
        ece = self.ro.call("ace_op_tool_calibration_error", {
            "predictions": [0.9, 0.1], "outcomes": [True, False]})
        self.assertIsInstance(ece, float)
        verdict = self.ro.call("ace_op_tool_receipt_verify",
                               {"receipt": {"bogus": True}})
        self.assertEqual(verdict, {"valid": False})


class ToolboxBatch12Tests(unittest.TestCase):
    """Batch 12: host controller + research discovery."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.ro = OperationalBridge(self.ws, allow_writes=False)

    def tearDown(self) -> None:
        self.ro.store.close()
        self._tmp.cleanup()

    def test_batch12_registered_readonly(self) -> None:
        from ace_mcp.op_bridge import ACE_TOOLBOX12_SPECS, OP_WRITE_TOOLS
        self.assertEqual(len(ACE_TOOLBOX12_SPECS), 3)
        for spec in ACE_TOOLBOX12_SPECS:
            self.assertNotIn(spec["name"], OP_WRITE_TOOLS)

    def test_host_and_partition(self) -> None:
        sealing = self.ro.call("ace_op_tool_os_sealing", {})
        self.assertIn("sealing", sealing)
        audit = self.ro.call("ace_op_tool_candidate_ast_audit",
                             {"code": "def f(x):\n    return x + 1\n"})
        self.assertEqual(audit, {"passed": True})
        part = self.ro.call("ace_op_tool_prefix_partition", {
            "train": [["kata", True], ["buku", False]],
            "validation": [["meja", True]]})
        self.assertIn("train_rt", part)
        self.assertIn("val_rt", part)


class ToolboxBatch13Tests(unittest.TestCase):
    """Batch 13: ace_software_factory anchored evaluators."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.ro = OperationalBridge(self.ws, allow_writes=False)

    def tearDown(self) -> None:
        self.ro.store.close()
        self._tmp.cleanup()

    def test_batch13_registered_readonly(self) -> None:
        from ace_mcp.op_bridge import ACE_TOOLBOX13_SPECS, OP_WRITE_TOOLS
        self.assertEqual(len(ACE_TOOLBOX13_SPECS), 5)
        for spec in ACE_TOOLBOX13_SPECS:
            self.assertNotIn(spec["name"], OP_WRITE_TOOLS)

    def test_factory_flag_and_payment(self) -> None:
        flag_plan = {
            "schema": "ace.factory-flag-plan.v1", "product_id": "demo",
            "source_ref": "test:flags",
            "attributes": [{"id": "tier", "values": ["free", "pro"]}],
            "flags": [{"id": "beta", "start": None, "end": None,
                       "enabled": True, "salt": "s1", "rollout_bp": 10000,
                       "segments": [], "source_ref": "test:flag"}]}
        out = self.ro.call("ace_op_tool_factory_flag_eval", {
            "plan": flag_plan,
            "request": {"flag": "beta", "subject": "user-1",
                        "at": "2026-01-01T00:00:00Z", "attributes": {}}})
        self.assertEqual(out["reason"], "inside_rollout")
        self.assertTrue(out["enabled"])
        unknown = self.ro.call("ace_op_tool_factory_flag_eval", {
            "plan": flag_plan,
            "request": {"flag": "nope", "subject": "user-1",
                        "at": "2026-01-01T00:00:00Z", "attributes": {}}})
        self.assertEqual(unknown["reason"], "unknown_flag")

        pay_plan = {
            "schema": "ace.factory-payment-sandbox.v1",
            "source_ref": "test:pay",
            "fixture_accounts": [{"id": "acct", "units": 100}],
            "events": [{"id": "e1", "kind": "authorize",
                        "account": "acct", "units": 40},
                       {"id": "e2", "kind": "capture",
                        "authorization": "e1", "units": 40}],
            "expected_receipts": [{"status": "accepted", "reason": None},
                                  {"status": "accepted", "reason": None}]}
        sim = self.ro.call("ace_op_tool_factory_payment_sim",
                           {"plan": pay_plan})
        self.assertEqual(sim["status"], "verified_fixture")
        self.assertTrue(sim["reconciliation"]["acct"]["conserved"])

    def test_factory_acceptance_trend_uptime(self) -> None:
        from ace_software_factory._contracts import identity
        spec = {
            "schema": "ace.factory-product-spec.v1",
            "brief_sha256": "0" * 64, "product_id": "demo",
            "name": "Demo", "surface": "cli", "objective": "Demo.",
            "objective_ref": "test:obj",
            "requirements": [{"id": "req1", "statement": "Works.",
                              "source_ref": "test:req",
                              "acceptance": [{"statement": "Answer is 4.",
                                              "source_ref": "test:crit"}]}],
            "constraints": [], "non_goals": [], "pending": [],
            "status": "ready"}
        contract = {
            "schema": "ace.factory-acceptance-contract.v1",
            "spec_sha256": identity(spec), "source_ref": "test:contract",
            "rules": [{"id": "r1", "criterion_ref": "test:crit",
                       "operator": "equals", "expected": 4,
                       "source_ref": "test:rule"}]}
        observations = {
            "schema": "ace.factory-observations.v1",
            "product_id": "demo", "contract_sha256": identity(contract),
            "artifact_sha256": "a" * 64,
            "records": [{"id": "r1", "value": 4,
                         "source_ref": "test:obs"}]}
        verdict = self.ro.call("ace_op_tool_factory_acceptance", {
            "spec": spec, "contract": contract,
            "observations": observations})
        self.assertEqual(verdict["status"], "passed")
        self.assertEqual(verdict["counts"]["passed"], 1)

        bench = {
            "schema": "ace.factory-bench-report.v1",
            "plan_sha256": "b" * 64, "source_ref": "test:bench",
            "product_count": 1, "passed": 1, "status": "passed",
            "products": [{"product_id": "demo", "surface": "cli",
                          "artifact_sha256": "a" * 64,
                          "acceptance": "test:acc",
                          "counts": {"passed": 1, "failed": 0,
                                     "missing_rule": 0,
                                     "missing_observation": 0},
                          "status": "passed"}]}
        history = {
            "schema": "ace.factory-trend-history.v1",
            "source_ref": "test:history",
            "runs": [{"id": "run1", "at": "2026-01-01T00:00:00Z",
                      "ref": "test:run", "bench_sha256": identity(bench),
                      "bench": bench}]}
        trend = self.ro.call("ace_op_tool_factory_trend",
                             {"history": history})
        self.assertEqual(trend["run_count"], 1)
        self.assertEqual(trend["by_surface"]["cli"]["passed"], 1)

        up_plan = {
            "schema": "ace.factory-uptime-plan.v1",
            "source_ref": "test:uptime",
            "from": "2026-01-01T00:00:00Z",
            "until": "2026-01-01T00:03:00Z", "cadence_seconds": 60,
            "max_delay_seconds": 10,
            "components": [{"id": "web", "port": 8080, "path": "/health",
                            "ok_status": 200, "source_ref": "test:comp"}]}
        up_obs = {
            "schema": "ace.factory-uptime-observations.v1",
            "plan_sha256": identity(up_plan),
            "rows": [{"component": "web", "at": "2026-01-01T00:00:00Z",
                      "state": "up", "source_ref": "test:probe"}]}
        report = self.ro.call("ace_op_tool_factory_uptime", {
            "plan": up_plan, "observations": up_obs})
        comp = report["components"][0]
        self.assertEqual(comp["up"], 1)
        self.assertEqual(comp["unknown"], 2)
        self.assertEqual(comp["uptime_lower_bound"]["denominator"], 3)


class ToolboxBatch14Tests(unittest.TestCase):
    """Batch 14: more ace_software_factory anchored tools."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.ro = OperationalBridge(self.ws, allow_writes=False)

    def tearDown(self) -> None:
        self.ro.store.close()
        self._tmp.cleanup()

    def test_batch14_registered_readonly(self) -> None:
        from ace_mcp.op_bridge import ACE_TOOLBOX14_SPECS, OP_WRITE_TOOLS
        self.assertEqual(len(ACE_TOOLBOX14_SPECS), 4)
        for spec in ACE_TOOLBOX14_SPECS:
            self.assertNotIn(spec["name"], OP_WRITE_TOOLS)

    def test_factory_schema_and_dependencies(self) -> None:
        from ace_software_factory._contracts import identity
        model = {
            "schema": "ace.factory-relational-model.v1",
            "model_ref": "test:model",
            "entities": [{"name": "item", "source_ref": "test:item",
                          "columns": [
                              {"name": "id", "kind": "integer",
                               "nullable": False, "default": None},
                              {"name": "label", "kind": "text",
                               "nullable": False, "default": None}],
                          "primary_key": ["id"], "unique": [],
                          "foreign_keys": [], "indexes": []}]}
        ddl = self.ro.call("ace_op_tool_factory_schema_design",
                           {"model": model})
        self.assertIn("CREATE TABLE", ddl["sql"])
        self.assertIn("item", ddl["entities"][0]["name"])

        catalog = {
            "schema": "ace.factory-package-catalog.v1",
            "ref": "test:catalog",
            "packages": [{"name": "demo-pkg", "releases": [
                {"version": "1.0.0", "sha256": "c" * 64,
                 "yanked": False}]}]}
        advisories = {"schema": "ace.factory-package-advisories.v1",
                      "ref": "test:adv", "advisories": []}
        plan = {
            "schema": "ace.factory-dependency-plan.v1",
            "source_ref": "test:plan",
            "catalog_sha256": identity(catalog),
            "advisories_sha256": identity(advisories),
            "pins": [{"name": "demo-pkg", "version": "1.0.0",
                      "sha256": "c" * 64,
                      "allowed": {"min_inclusive": "1.0.0",
                                  "max_exclusive": "2.0.0"},
                      "source_ref": "test:pin"}]}
        report = self.ro.call("ace_op_tool_factory_dependency_check", {
            "plan": plan, "catalog": catalog, "advisories": advisories})
        self.assertEqual(report["status"], "snapshot_checks_passed")
        self.assertEqual(report["pins"][0]["issues"], [])

    def test_factory_release_gate_and_audit(self) -> None:
        from ace_software_factory._contracts import identity
        from ace_software_factory import auditlog_builder
        files = [{"path": "mod.py", "sha256": "d" * 64}]
        artifact = identity(files)
        acceptance = {
            "schema": "ace.factory-acceptance-report.v1",
            "status": "passed", "artifact_sha256": artifact,
            "counts": {"passed": 1, "failed": 0, "missing_rule": 0,
                       "missing_observation": 0}}
        coverage = {
            "schema": "ace.factory-coverage-report.v1",
            "status": "measured", "files": files, "skipped": 0,
            "modules": [{"path": "mod.py", "sha256": "d" * 64,
                         "ratio_bp": 10000}]}
        scan = {
            "schema": "ace.factory-sast-report.v1",
            "status": "no_rule_matches", "findings": [], "unscanned": [],
            "sources": [{"path": "mod.py", "parse_ok": True,
                         "sha256": "d" * 64}]}
        archive = {
            "schema": "ace.factory-release-verification.v1",
            "status": "verified", "zip_sha256": "b" * 64,
            "manifest_sha256": "e" * 64, "verified_files": 1}
        evidence = {"acceptance": acceptance, "coverage": coverage,
                    "scan": scan, "archive": archive}
        policy = {
            "schema": "ace.factory-release-gate-policy.v1",
            "source_ref": "test:policy", "artifact_sha256": artifact,
            "zip_sha256": "b" * 64, "zip_manifest_sha256": "e" * 64,
            "expected_criteria": 1,
            "required_modules": [{"path": "mod.py", "min_bp": 5000,
                                  "source_ref": "test:req"}],
            "evidence_sha256": {k: identity(v)
                                for k, v in evidence.items()}}
        gate = self.ro.call("ace_op_tool_factory_release_gate", {
            "policy": policy, "evidence": evidence})
        self.assertEqual(gate["status"], "ready_for_review")
        self.assertEqual(gate["blockers"], [])

        audit_policy = {
            "schema": "ace.factory-audit-policy.v1", "id": "demo",
            "source_ref": "test:audit",
            "operations": [{"id": "login", "source_ref": "test:op"}]}
        empty = self.ro.call("ace_op_tool_factory_audit_verify", {
            "policy": audit_policy, "log_text": ""})
        self.assertEqual(empty["status"], "verified")
        self.assertEqual(empty["events"], 0)
        snapshot, built = auditlog_builder.extend(
            b"", audit_policy, identity(audit_policy), "0" * 64,
            [{"id": "ev1", "at": "2026-01-01T00:00:00Z",
              "actor_ref": "actor1", "operation": "login",
              "target_ref": "target1", "status": "allowed",
              "evidence_ref": "evref1"}])
        chained = self.ro.call("ace_op_tool_factory_audit_verify", {
            "policy": audit_policy, "log_text": snapshot.decode(),
            "tail_sha256": built["tail_sha256"]})
        self.assertEqual(chained["events"], 1)
        self.assertEqual(chained["by_status"]["allowed"], 1)


class ToolboxBatch15Tests(unittest.TestCase):
    """Batch 15: ace_guardian + ace_presence + ace_deliberation."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.ro = OperationalBridge(self.ws, allow_writes=False)

    def tearDown(self) -> None:
        self.ro.store.close()
        self._tmp.cleanup()

    def test_batch15_registered_readonly(self) -> None:
        from ace_mcp.op_bridge import ACE_TOOLBOX15_SPECS, OP_WRITE_TOOLS
        self.assertEqual(len(ACE_TOOLBOX15_SPECS), 6)
        for spec in ACE_TOOLBOX15_SPECS:
            self.assertNotIn(spec["name"], OP_WRITE_TOOLS)

    def test_guardian_tools(self) -> None:
        abstention = {
            "schema": "ace.guardian.abstention-calibration.v1",
            "samples": [{"id": "s1", "confidence_bp": 9000,
                         "correct": True},
                        {"id": "s2", "confidence_bp": 9000,
                         "correct": True},
                        {"id": "s3", "confidence_bp": 1000,
                         "correct": False}],
            "thresholds": [5000], "max_error_bp": 1000,
            "minimum_accepted": 1}
        out = self.ro.call("ace_op_tool_guardian_abstention",
                           {"plan": abstention})
        self.assertEqual(out["chosen_threshold_bp"], 5000)
        self.assertEqual(out["sample_count"], 3)

        calibration = {
            "schema": "ace.guardian.calibration.v1",
            "rows": [{"id": "p1", "domain": "d", "confidence_bp": 10000,
                      "observed": True, "resolved_ref": "f" * 64}],
            "bins": 10, "minimum": 1}
        scored = self.ro.call("ace_op_tool_guardian_calibration",
                              {"plan": calibration})
        self.assertEqual(scored["domains"]["d"]["ece"], "0")
        self.assertEqual(scored["domains"]["d"]["brier"], "0")

        def action(key, units):
            return {"id": key, "kind": "read", "actor": "a1",
                    "units": units, "source": "e" * 64}
        anomaly = {
            "schema": "ace.guardian.action-anomalies.v1",
            "baseline": [action("b1", 10), action("b2", 10),
                         action("b3", 10)],
            "observed": [action("o1", 500)],
            "minimum_count": 2, "mad_multiplier": 3}
        flagged = self.ro.call("ace_op_tool_guardian_action_anomaly",
                               {"plan": anomaly})
        self.assertEqual(len(flagged["findings"]), 1)
        self.assertIn("unit_outlier", flagged["findings"][0]["flags"])

    def test_presence_and_deliberation_tools(self) -> None:
        collision = {
            "schema": "ace.presence.deadline-collisions.v1",
            "working": [{"start": "2026-01-01T09:00:00Z",
                         "end": "2026-01-01T10:00:00Z"}],
            "tasks": [{"id": "t1", "available_at": "2026-01-01T09:00:00Z",
                       "due_at": "2026-01-01T10:00:00Z", "minutes": 90,
                       "source": "test:task"}]}
        out = self.ro.call("ace_op_tool_presence_deadline_collision",
                           {"plan": collision})
        self.assertFalse(out["can_fit_preemptive"])
        self.assertEqual(out["collisions"][0]["deficit_minutes"], 30)

        duration = {
            "schema": "ace.presence.duration-plan.v1", "kind": "report",
            "complexity": 3, "minimum_samples": 2,
            "history": [{"kind": "report", "complexity": 3,
                         "minutes": 30, "source": "test:h1"},
                        {"kind": "report", "complexity": 3,
                         "minutes": 50, "source": "test:h2"},
                        {"kind": "report", "complexity": 3,
                         "minutes": 70, "source": "test:h4"},
                        {"kind": "other", "complexity": 3,
                         "minutes": 999, "source": "test:h3"}]}
        estimate = self.ro.call("ace_op_tool_presence_duration_estimate",
                                {"plan": duration})
        self.assertEqual(estimate["samples"], 3)
        self.assertEqual(estimate["median_minutes"], 50)

        circular = {
            "claims": [{"id": "x", "source_ref": "test:x"},
                       {"id": "y", "source_ref": "test:y"}],
            "foundations": [],
            "rules": [{"id": "r1", "conclusion": "x", "premises": ["y"],
                       "source_ref": "test:r1"},
                      {"id": "r2", "conclusion": "y", "premises": ["x"],
                       "source_ref": "test:r2"}]}
        verdict = self.ro.call("ace_op_tool_deliberation_circular",
                               {"record": circular})
        self.assertEqual(len(verdict["cycles"]), 1)
        self.assertEqual(sorted(verdict["cycles"][0]["claims"]),
                         ["x", "y"])
        self.assertEqual(verdict["grounded"], [])


class ToolboxBatch16Tests(unittest.TestCase):
    """Batch 16: more deliberation checkers + anchored evaluators."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.ro = OperationalBridge(self.ws, allow_writes=False)

    def tearDown(self) -> None:
        self.ro.store.close()
        self._tmp.cleanup()

    def test_batch16_registered_readonly(self) -> None:
        from ace_mcp.op_bridge import ACE_TOOLBOX16_SPECS, OP_WRITE_TOOLS
        self.assertEqual(len(ACE_TOOLBOX16_SPECS), 4)
        for spec in ACE_TOOLBOX16_SPECS:
            self.assertNotIn(spec["name"], OP_WRITE_TOOLS)

    def test_deliberation_brier_and_fallacy(self) -> None:
        record = {
            "cutoff": "2026-01-01T00:00:00+00:00",
            "as_of": "2026-02-01T00:00:00+00:00",
            "history": [{"question_id": "h1", "outcome": 1,
                         "resolved_at": "2025-12-01T00:00:00+00:00",
                         "resolution_ref": "test:hist"}],
            "forecasts": [{"question_id": "q1", "probability": "0.5",
                           "forecast_at": "2026-01-15T00:00:00+00:00",
                           "forecast_ref": "test:fc"}],
            "resolutions": [{"question_id": "q1", "outcome": 1,
                             "resolved_at": "2026-01-20T00:00:00+00:00",
                             "resolution_ref": "test:res"}]}
        scored = self.ro.call("ace_op_tool_deliberation_brier",
                              {"record": record})
        # Fractions cross the bridge as numerator/denominator pairs.
        self.assertEqual(scored["brier"],
                         {"numerator": 1, "denominator": 4})
        self.assertEqual(scored["baseline_brier"],
                         {"numerator": 0, "denominator": 1})
        self.assertEqual(scored["verdict"], "worse")

        argument = {
            "premises": [
                {"formula": {"op": "implies",
                             "args": [{"atom": "P"}, {"atom": "Q"}]},
                 "source_ref": "test:p1"},
                {"formula": {"atom": "Q"}, "source_ref": "test:p2"}],
            "conclusion": {"formula": {"atom": "P"},
                           "source_ref": "test:c"}}
        checked = self.ro.call("ace_op_tool_deliberation_fallacy",
                               {"record": argument})
        self.assertEqual(checked["status"], "counterexample")
        codes = [row["code"] for row in checked["findings"]]
        self.assertIn("affirming_consequent", codes)

    def test_guardian_leak_and_presence_commitments(self) -> None:
        leak = {
            "schema": "ace.guardian.rss-leak.v1",
            "samples": [{"instance": "proc", "at": f"2026-01-01T0{h}:00:00Z",
                         "rss_mib": 100 * (h + 1), "source": "test:rss"}
                        for h in range(4)],
            "minimum": 3, "growth_mib_per_hour": 50, "min_total_mib": 100}
        report = self.ro.call("ace_op_tool_guardian_leak", {"plan": leak})
        instance = report["instances"][0]
        self.assertEqual(instance["status"], "suspected_leak")
        self.assertEqual(instance["gain_mib"], 300)

        commitments = {
            "schema": "ace.presence.commitments.v1",
            "as_of": "2026-01-10", "alert_days": 3,
            "promises": [{"id": "p1", "due_on": "2026-01-12",
                          "action": "Kirim laporan", "source": "test:p"},
                         {"id": "p2", "due_on": "2026-01-05",
                          "action": "Tugas lama", "source": "test:p"}],
            "resolutions": [{"id": "p2", "at": "2026-01-04",
                             "source": "test:done"}]}
        tracked = self.ro.call("ace_op_tool_presence_commitments",
                               {"plan": commitments})
        by_id = {row["id"]: row for row in tracked["commitments"]}
        self.assertEqual(by_id["p1"]["status"], "due_soon")
        self.assertEqual(by_id["p1"]["days_left"], 2)
        self.assertEqual(by_id["p2"]["status"], "fulfilled")


class ToolboxBatch17Tests(unittest.TestCase):
    """Batch 17: institute hypothesis + deliberation VOI/weigher."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.ro = OperationalBridge(self.ws, allow_writes=False)

    def tearDown(self) -> None:
        self.ro.store.close()
        self._tmp.cleanup()

    def test_batch17_registered_readonly(self) -> None:
        from ace_mcp.op_bridge import ACE_TOOLBOX17_SPECS, OP_WRITE_TOOLS
        self.assertEqual(len(ACE_TOOLBOX17_SPECS), 3)
        for spec in ACE_TOOLBOX17_SPECS:
            self.assertNotIn(spec["name"], OP_WRITE_TOOLS)

    def test_institute_hypothesis(self) -> None:
        plan = {
            "schema": "ace.institute.hypothesis-plan.v1",
            "hypothesis": "Kelompok A lebih sering berhasil.",
            "method": "fisher", "alternative": "two_sided",
            "alpha": "0.05",
            "assumptions": {
                "independent_observations": {
                    "declared": True, "source_ref": "test:a1"},
                "fixed_margins": {"declared": True,
                                  "source_ref": "test:a2"}},
            "data": {"a": 3, "b": 1, "c": 1, "d": 3}}
        result = self.ro.call("ace_op_tool_institute_hypothesis",
                              {"plan": plan})
        self.assertEqual(result["status"], "fail_to_reject")
        self.assertEqual(result["p_value_exact"], [17, 35])
        held = dict(plan)
        held["assumptions"] = {
            "independent_observations": {
                "declared": False, "source_ref": "test:a1"},
            "fixed_margins": {"declared": True, "source_ref": "test:a2"}}
        held_result = self.ro.call("ace_op_tool_institute_hypothesis",
                                   {"plan": held})
        self.assertEqual(held_result["status"], "held_assumption")
        self.assertIsNone(held_result["p_value_exact"])

    def test_deliberation_voi_and_weigher(self) -> None:
        def frac(n, d):
            return {"numerator": n, "denominator": d}
        voi = {
            "prior": {"rain": frac(1, 2), "shine": frac(1, 2)},
            "utility": {"umbrella": {"rain": 10, "shine": 0},
                        "no_umbrella": {"rain": -10, "shine": 10}},
            "experiments": [{"id": "forecast", "source_ref": "test:fc",
                             "cost": 1,
                             "outcomes": {
                                 "pos": {"rain": frac(9, 10),
                                         "shine": frac(1, 10)},
                                 "neg": {"rain": frac(1, 10),
                                         "shine": frac(9, 10)}}}],
            "budget": 10, "min_net_value": 0}
        compared = self.ro.call("ace_op_tool_deliberation_voi",
                                {"record": voi})
        self.assertEqual(compared["status"], "continue")
        self.assertEqual(compared["recommended_experiment"], "forecast")
        self.assertEqual(compared["perfect_information_bound"],
                         {"numerator": 5, "denominator": 1})

        weigh = {
            "claims": ["c1"],
            "sources": [{"id": "s1", "family": "famA",
                         "source_ref": "test:s1", "credibility": "0.5",
                         "verified": True}],
            "evidence": [{"id": "e1", "claim": "c1", "source": "s1",
                          "evidence_ref": "test:e1", "stance": "support",
                          "strength": "0.5"}]}
        weighed = self.ro.call("ace_op_tool_deliberation_evidence_weigh",
                               {"record": weigh})
        claim = weighed["claims"][0]
        self.assertEqual(claim["support"],
                         {"numerator": 1, "denominator": 4})
        self.assertEqual(claim["evidence"][0]["state"], "counted")


class ToolboxBatch18Tests(unittest.TestCase):
    """Batch 18: guardian gate ledger + coverage + compliance."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.ro = OperationalBridge(self.ws, allow_writes=False)

    def tearDown(self) -> None:
        self.ro.store.close()
        self._tmp.cleanup()

    def test_batch18_registered_readonly(self) -> None:
        from ace_mcp.op_bridge import ACE_TOOLBOX18_SPECS, OP_WRITE_TOOLS
        self.assertEqual(len(ACE_TOOLBOX18_SPECS), 4)
        for spec in ACE_TOOLBOX18_SPECS:
            self.assertNotIn(spec["name"], OP_WRITE_TOOLS)

    def test_guardian_gate_chain_and_consumers(self) -> None:
        from ace_guardian._contracts import identity
        from ace_guardian.rule_compiler import compile_rules
        policy = {
            "schema": "ace.guardian.compile-rules.v1", "revision": "r1",
            "actions": [{"kind": "read", "fields": {}}],
            "lines": ["allow rule_read read"]}
        compiled = compile_rules(policy, identity(policy))
        decision = {
            "action_id": "act1", "kind": "read", "outcome": "allow",
            "reason": "ok", "matched_rules": ["rule_read"],
            "request_sha256": "a" * 64,
            "policy_sha256": compiled["compiled_sha256"]}
        appended = self.ro.call("ace_op_tool_guardian_gate_append", {
            "plan": {"schema": "ace.guardian.gate-receipt.v1",
                     "prior": [], "decision": decision,
                     "at": "2026-01-01T10:00:00Z"}})
        self.assertFalse(appended["replay"])
        receipt = appended["receipt"]
        self.assertEqual(appended["head_sha256"], receipt["sha256"])
        replayed = self.ro.call("ace_op_tool_guardian_gate_append", {
            "plan": {"schema": "ace.guardian.gate-receipt.v1",
                     "prior": [receipt], "decision": decision,
                     "at": "2026-01-01T10:00:00Z"}})
        self.assertTrue(replayed["replay"])

        verified = self.ro.call("ace_op_tool_guardian_gate_verify",
                                {"receipts": [receipt]})
        self.assertEqual(verified["head_sha256"], receipt["sha256"])
        self.assertEqual(verified["action_ids"], ["act1"])

        coverage = self.ro.call("ace_op_tool_guardian_coverage", {
            "plan": {"schema": "ace.guardian.policy-coverage.v1",
                     "policy": policy,
                     "classes": [{"kind": "read",
                                  "expected_outcomes": ["allow"]}],
                     "ledger": [receipt]}})
        self.assertTrue(coverage["complete"])
        self.assertEqual(coverage["coverage"][0]["classification"],
                         "covered")

        compliance = self.ro.call("ace_op_tool_guardian_compliance", {
            "plan": {"schema": "ace.guardian.compliance-report.v1",
                     "from": "2026-01-01T00:00:00Z",
                     "until": "2026-01-02T00:00:00Z",
                     "ledger": [receipt],
                     "actions": [{"id": "act1",
                                  "request_sha256": "a" * 64,
                                  "at": "2026-01-01T10:00:00Z"}]}})
        self.assertEqual(compliance["matched_receipts"], 1)
        self.assertEqual(compliance["coverage"], "1")
        self.assertEqual(compliance["per_rule"],
                         {"rule_read": {"allow": 1}})


if __name__ == "__main__":
    unittest.main()
