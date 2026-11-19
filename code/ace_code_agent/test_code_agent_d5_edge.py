"""Ekspansi tes tepi D5 untuk paket code/ace_code_agent (tes saja, tanpa mengubah modul).

Catatan: paket `code/ace_code_agent` memiliki cakupan awal 95.7% (22/23 simbol),
lebih tinggi daripada `code/ace_real_world` (50.0%, 7/14 simbol), sehingga dikerjakan
pada PR kedua setelah `gravity/edge-tests-real-world`. Suite ini menutup simbol `cli.main`
(0% -> 100%) dan menguji batas/tepi pemanggil nyata di seluruh komponen agent.
"""
from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from ace_code_agent import cli as agent_cli
from ace_code_agent.ai_advisor import MultiAIFleetAdvisor
from ace_code_agent.codebase_reader import CodebaseReader
from ace_code_agent.controller import AutonomousSoftwareResearcher
from ace_code_agent.independent_evaluator import IndependentEvaluator
from ace_code_agent.models import (
    AutonomousPRMetadata,
    CodePatch,
    ImprovementHypothesis,
    ResearchProblem,
    WorktreeExecutionResult,
)
from ace_code_agent.patch_diagnostic import (
    MAX_PATCH_BYTES,
    TARGET as DIAGNOSTIC_TARGET,
    evaluate_patch,
    verify_receipt,
)
from ace_code_agent.patch_synthesizer import ModularPatchGenerator
from ace_code_agent.pr_manager import ALLOWED_BRANCH_PREFIXES, AutonomousPRManager
from ace_code_agent.problem_selector import ProblemSelector
from ace_code_agent.repo_retrieval import BoundedRepositoryRetriever
from ace_code_agent.worktree_harness import WorktreeHarness


def _make_sample_objects(hyp_id: str = "hyp-v1 beta/99") -> tuple[
    ResearchProblem,
    ImprovementHypothesis,
    CodePatch,
    WorktreeExecutionResult,
]:
    prob = ResearchProblem(
        problem_id="prob_1",
        category="ALGORITHMIC_GAP",
        title="Edge test problem",
        description="Edge scenario",
        target_files=["code/ace_self_dev/strategy_repair.py"],
    )
    hyp = ImprovementHypothesis(
        hypothesis_id=hyp_id,
        problem_id="prob_1",
        statement="Hypothesis statement for edge test.",
        proposed_strategy="LIBRARY_PRIMITIVE_SYNTHESIS",
        expected_metric_gain=0.16,
        target_module="code/ace_self_dev/strategy_repair.py",
        rationale="Edge test rationale",
    )
    patch = CodePatch(
        patch_id="patch_1",
        hypothesis_id=hyp_id,
        target_file="code/ace_self_dev/strategy_repair.py",
        diff_content="--- a/x\n+++ b/x\n@@ -1 +1 @@\n+x = 1\n",
        original_code_snippet="",
        replacement_code_snippet="def f(x: int) -> int:\n    return x\n",
        patch_type="AST_TRANSFORMATION",
        author_provenance="TEST",
    )
    exec_res = WorktreeExecutionResult(
        execution_id="exec_1",
        patch_id="patch_1",
        hypothesis_id=hyp_id,
        worktree_path="",
        applied_cleanly=False,
        ast_valid=True,
        tests_passed=0,
        tests_failed=0,
        test_duration_seconds=0.01,
        decision="INCONCLUSIVE",
        receipt_signature="deadbeef",
    )
    return prob, hyp, patch, exec_res


class TestCodeAgentD5Edge(unittest.TestCase):
    """Minimal 25 kasus tepi bermakna melintasi modul code/ace_code_agent."""

    # --- cli.py ---

    def test_01_cli_max_cycles_zero_is_noop(self) -> None:
        fake_researcher = MagicMock()
        buf = io.StringIO()
        with patch.object(agent_cli, "AutonomousSoftwareResearcher", return_value=fake_researcher), \
             patch.object(sys, "argv", ["ace-code-agent", "--max-cycles", "0"]), \
             contextlib.redirect_stdout(buf):
            rc = agent_cli.main()
        self.assertEqual(rc, 0)
        fake_researcher.execute_autonomous_cycle.assert_not_called()
        self.assertEqual(buf.getvalue(), "")

    def test_02_cli_negative_max_cycles_is_noop(self) -> None:
        fake_researcher = MagicMock()
        buf = io.StringIO()
        with patch.object(agent_cli, "AutonomousSoftwareResearcher", return_value=fake_researcher), \
             patch.object(sys, "argv", ["ace-code-agent", "--max-cycles", "-3"]), \
             contextlib.redirect_stdout(buf):
            rc = agent_cli.main()
        self.assertEqual(rc, 0)
        fake_researcher.execute_autonomous_cycle.assert_not_called()

    def test_03_cli_auto_pr_prints_pr_fields_when_present_and_omits_when_absent(self) -> None:
        fake_researcher = MagicMock()
        fake_researcher.execute_autonomous_cycle.side_effect = [
            {
                "problem": {"title": "P1"},
                "hypothesis": {"statement": "H1"},
                "decision": "INCONCLUSIVE",
                "pr_metadata": {
                    "branch_name": "ace-dev/hyp_1",
                    "commit_sha": "abc123",
                    "pr_url": "https://example.invalid/pr/42",
                    "pr_number": 42,
                },
            },
            {
                "problem": {"title": "P2"},
                "hypothesis": {"statement": "H2"},
                "decision": "DUPLICATE_PATCH_SKIPPED",
                "pr_metadata": None,
            },
        ]
        buf = io.StringIO()
        with patch.object(agent_cli, "AutonomousSoftwareResearcher", return_value=fake_researcher), \
             patch.object(sys, "argv", ["ace-code-agent", "--autonomous", "--max-cycles", "2", "--auto-pr"]), \
             contextlib.redirect_stdout(buf):
            rc = agent_cli.main()
        out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertEqual(fake_researcher.execute_autonomous_cycle.call_count, 2)
        fake_researcher.execute_autonomous_cycle.assert_called_with(auto_pr=True)
        self.assertIn("Cycle 1/2", out)
        self.assertIn("Cycle 2/2", out)
        self.assertIn("PR Branch Created: ace-dev/hyp_1", out)
        self.assertIn("GitHub PR Number: #42", out)
        self.assertEqual(out.count("Commit SHA:"), 1)

    # --- controller.py ---

    def test_04_controller_corrupt_json_state_falls_back_and_writes_atomic_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            researcher = AutonomousSoftwareResearcher(repo_root=root, use_ai_fleet=False)
            researcher.state_file.write_text("{corrupt json", encoding="utf-8")
            result = researcher.execute_autonomous_cycle(auto_pr=False)
            self.assertEqual(result["cycle"], 1)
            self.assertIn(result["decision"], ("INCONCLUSIVE", "REJECTED"))
            saved = json.loads(researcher.state_file.read_text(encoding="utf-8"))
            self.assertEqual(saved["completed_cycles"], 1)
            self.assertEqual(len(saved["history"]), 1)
            self.assertFalse(researcher.state_file.with_suffix(".tmp").exists())

    def test_05_controller_duplicate_patch_sha_short_circuits_without_advancing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            researcher = AutonomousSoftwareResearcher(repo_root=root, use_ai_fleet=False)
            prob, hyp, code_patch, _ = _make_sample_objects(hyp_id="hyp_dup")
            with patch.object(researcher.selector, "select_next_problem", return_value=(prob, hyp)), \
                 patch.object(researcher.synthesizer, "generate_patch", return_value=code_patch):
                first = researcher.execute_autonomous_cycle(auto_pr=False)
                saved = json.loads(researcher.state_file.read_text(encoding="utf-8"))
                self.assertEqual(saved["completed_cycles"], 1)
                second = researcher.execute_autonomous_cycle(auto_pr=False)
            self.assertEqual(second["decision"], "DUPLICATE_PATCH_SKIPPED")
            self.assertEqual(second["evaluator_calls"], 0)
            saved_after = json.loads(researcher.state_file.read_text(encoding="utf-8"))
            self.assertEqual(saved_after["completed_cycles"], 1)
            self.assertEqual(first["patch"]["patch_sha256"], saved_after["history"][0]["patch_sha"])

    def test_06_controller_empty_target_files_fallback_and_blocks_accepted_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            researcher = AutonomousSoftwareResearcher(repo_root=root, use_ai_fleet=False)
            prob, hyp, _, exec_res = _make_sample_objects()
            prob.target_files = []
            exec_res.decision = "ACCEPTED"
            with patch.object(researcher.selector, "select_next_problem", return_value=(prob, hyp)), \
                 patch.object(researcher.harness, "execute_in_worktree", return_value=exec_res), \
                 patch.object(researcher.pr_manager, "publish_autonomous_pr") as pub_mock:
                result = researcher.execute_autonomous_cycle(auto_pr=True)
            self.assertEqual(result["decision"], "INCONCLUSIVE")
            self.assertIn("MISSING_INDEPENDENT_EVIDENCE", result["execution"]["rejection_reason"])
            self.assertEqual(result["patch"]["target_file"], "code/ace_self_dev/strategy_repair.py")
            pub_mock.assert_not_called()

    def test_07_controller_wrong_shape_json_state_bug(self) -> None:
        # Bug yang sudah diperbaiki (2026-11-20): load_researcher_state() kini
        # memvalidasi bentuk state — JSON sah berbentuk [] diperlakukan sebagai
        # state awal, bukan memicu TypeError di execute_autonomous_cycle().
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            researcher = AutonomousSoftwareResearcher(repo_root=root, use_ai_fleet=False)
            researcher.state_file.write_text("[]", encoding="utf-8")
            result = researcher.execute_autonomous_cycle(auto_pr=False)
            self.assertEqual(result["cycle"], 1)

    # --- pr_manager.py ---

    def test_08_pr_manager_prepare_metadata_sanitizes_id_and_detached_head(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mgr = AutonomousPRManager(repo_root=Path(tmp))
            prob, hyp, code_patch, exec_res = _make_sample_objects(hyp_id="hyp v1/beta:99!")
            detached = subprocess.CompletedProcess(["git"], 0, stdout="\n", stderr="")
            with patch("ace_code_agent.pr_manager.subprocess.run", return_value=detached):
                meta = mgr.prepare_pr_metadata(prob, hyp, code_patch, exec_res)
            self.assertEqual(meta.branch_name, "ace-dev/hyp_v1_beta_99_")
            self.assertEqual(meta.target_branch, "main")
            self.assertTrue(any(meta.branch_name.startswith(p) for p in ALLOWED_BRANCH_PREFIXES))

    def test_09_pr_manager_get_current_branch_timeout_falls_back_to_main(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mgr = AutonomousPRManager(repo_root=Path(tmp))
            with patch(
                "ace_code_agent.pr_manager.subprocess.run",
                side_effect=subprocess.TimeoutExpired(["git"], 10),
            ):
                self.assertEqual(mgr.get_current_branch(), "main")

    def test_10_pr_manager_create_git_branch_rejects_disallowed_prefixes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mgr = AutonomousPRManager(repo_root=Path(tmp))
            prob, hyp, code_patch, exec_res = _make_sample_objects()
            for bad_branch in ("main", "gravity/bad", "ace-dev", "feature/x", "../escape"):
                meta = mgr.prepare_pr_metadata(prob, hyp, code_patch, exec_res, target_branch="main")
                meta.branch_name = bad_branch
                ok, msg = mgr.create_git_branch_and_commit(meta, code_patch)
                self.assertFalse(ok)
                self.assertIn("SECURITY VIOLATION", msg)

    def test_11_pr_manager_create_git_branch_fail_closed_for_allowed_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mgr = AutonomousPRManager(repo_root=Path(tmp))
            prob, hyp, code_patch, exec_res = _make_sample_objects()
            meta = mgr.prepare_pr_metadata(prob, hyp, code_patch, exec_res, target_branch="main")
            ok, msg = mgr.create_git_branch_and_commit(meta, code_patch)
            self.assertFalse(ok)
            self.assertIn("BLOCKED", msg)

    def test_12_pr_manager_open_github_pr_malformed_probe_and_already_exists_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mgr = AutonomousPRManager(repo_root=Path(tmp))
            prob, hyp, code_patch, exec_res = _make_sample_objects()
            meta = mgr.prepare_pr_metadata(prob, hyp, code_patch, exec_res, target_branch="main")
            responses = [
                subprocess.CompletedProcess(["gh"], 0, stdout="{not json", stderr=""),
                subprocess.CompletedProcess(["gh"], 1, stdout="", stderr="a pull request already exists"),
                subprocess.CompletedProcess(
                    ["gh"], 0,
                    stdout='{"number": 88, "url": "https://example.invalid/pr/88", "state": "OPEN"}',
                    stderr="",
                ),
            ]
            with patch("ace_code_agent.pr_manager.subprocess.run", side_effect=responses):
                ok, msg, num, url = mgr.open_github_pr(meta)
            self.assertTrue(ok)
            self.assertEqual(num, 88)
            self.assertEqual(url, "https://example.invalid/pr/88")
            self.assertEqual(meta.pr_number, 88)
            self.assertIn("existing", msg.lower())

    def test_13_pr_manager_open_github_pr_corrupt_race_view_json_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mgr = AutonomousPRManager(repo_root=Path(tmp))
            prob, hyp, code_patch, exec_res = _make_sample_objects()
            meta = mgr.prepare_pr_metadata(prob, hyp, code_patch, exec_res, target_branch="main")
            responses = [
                subprocess.CompletedProcess(["gh"], 1, stdout="", stderr="not found"),
                subprocess.CompletedProcess(["gh"], 1, stdout="", stderr="already exists"),
                subprocess.CompletedProcess(["gh"], 0, stdout="{broken", stderr=""),
            ]
            with patch("ace_code_agent.pr_manager.subprocess.run", side_effect=responses):
                ok, msg, num, url = mgr.open_github_pr(meta)
            self.assertFalse(ok)
            self.assertIn("exception", msg.lower())
            self.assertIsNone(num)
            self.assertIsNone(url)

    def test_14_pr_manager_verify_pr_exists_negative_and_open_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mgr = AutonomousPRManager(repo_root=Path(tmp))
            prob, hyp, code_patch, exec_res = _make_sample_objects()
            meta = mgr.prepare_pr_metadata(prob, hyp, code_patch, exec_res, target_branch="main")

            ok, _, _ = mgr.verify_pr_exists(meta)
            self.assertFalse(ok)

            meta.pr_number = 91
            closed = subprocess.CompletedProcess(
                ["gh"], 0, stdout='{"number": 91, "url": "u", "state": "CLOSED"}', stderr=""
            )
            with patch("ace_code_agent.pr_manager.subprocess.run", return_value=closed):
                ok_closed, msg_closed, _ = mgr.verify_pr_exists(meta)
            self.assertFalse(ok_closed)
            self.assertIn("CLOSED", msg_closed)

            opened = subprocess.CompletedProcess(
                ["gh"], 0, stdout='{"number": 91, "url": "https://example.invalid/91", "state": "open"}', stderr=""
            )
            with patch("ace_code_agent.pr_manager.subprocess.run", return_value=opened):
                ok_open, _, data = mgr.verify_pr_exists(meta)
            self.assertTrue(ok_open)
            self.assertEqual(data["number"], 91)

    def test_15_pr_manager_publish_autonomous_pr_halts_before_push(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mgr = AutonomousPRManager(repo_root=Path(tmp))
            prob, hyp, code_patch, exec_res = _make_sample_objects()
            meta = mgr.prepare_pr_metadata(prob, hyp, code_patch, exec_res, target_branch="main")
            with patch.object(mgr, "push_remote_branch") as push_m, \
                 patch.object(mgr, "open_github_pr") as open_m, \
                 patch.object(mgr, "verify_pr_exists") as ver_m:
                ok, msg = mgr.publish_autonomous_pr(meta, code_patch)
            self.assertFalse(ok)
            self.assertIn("Branch & commit step failed", msg)
            push_m.assert_not_called()
            open_m.assert_not_called()
            ver_m.assert_not_called()

    # --- independent_evaluator.py ---

    def test_16_independent_evaluator_raising_and_non_int_candidates_score_zero(self) -> None:
        ev = IndependentEvaluator()
        score_err, hits_err, total_err = ev.evaluate_predicate(
            lambda l, d, s: 1 // 0, task_id="task_k2"
        )
        self.assertEqual((score_err, hits_err, total_err), (0.0, 0, 16))
        score_bad, hits_bad, total_bad = ev.evaluate_predicate(
            lambda l, d, s: "not_an_int", task_id="unknown_task"  # type: ignore[arg-type]
        )
        self.assertEqual((score_bad, hits_bad, total_bad), (0.0, 0, 16))

    def test_17_independent_evaluator_negative_control_rejects_const1_and_crashing(self) -> None:
        ev = IndependentEvaluator()
        self.assertFalse(ev.evaluate_negative_control(lambda l, d, s: 1))
        self.assertFalse(ev.evaluate_negative_control(lambda l, d, s: (_ for _ in ()).throw(RuntimeError())))
        self.assertTrue(ev.evaluate_negative_control(lambda l, d, s: 0))

    def test_18_independent_evaluator_meta_productivity_edges_and_zero_latency_clamp(self) -> None:
        ev = IndependentEvaluator()
        self.assertEqual(ev.compute_meta_productivity(0, 5, [1.0])["meta_productivity_index"], 0.0)
        self.assertEqual(ev.compute_meta_productivity(5, 5, [])["meta_productivity_index"], 0.0)
        clamped = ev.compute_meta_productivity(4, 2, [0.0, 0.0])
        self.assertEqual(clamped["novelty_rate"], 0.5)
        self.assertEqual(clamped["mean_latency_s"], 0.0)
        self.assertEqual(clamped["meta_productivity_index"], 500.0)

    # --- ai_advisor.py ---

    def test_19_ai_advisor_extract_code_fences_unfenced_and_missing(self) -> None:
        adv = MultiAIFleetAdvisor(ask_ai_bin="/nonexistent/ask-ai")
        self.assertEqual(adv._extract_code("```python\ndef a(x):\n    return x\n```"), "def a(x):\n    return x")
        self.assertEqual(adv._extract_code("```\ndef b():\n    return 1\n```"), "def b():\n    return 1")
        self.assertEqual(adv._extract_code("Penjelasan:\ndef c():\n    return 2\n```"), "def c():\n    return 2")
        self.assertIsNone(adv._extract_code("Tidak ada fungsi di sini."))

    def test_20_ai_advisor_validate_pure_ast_rejects_unsafe_constructs(self) -> None:
        adv = MultiAIFleetAdvisor(ask_ai_bin="/nonexistent/ask-ai")
        self.assertTrue(adv.validate_pure_ast("def f(a: int, b: int) -> int:\n    return (a + b) % 2\n"))
        unsafe = [
            "def f(:",
            "import math\ndef f(): return 1",
            "from os import path\ndef f(): return 1",
            "def f():\n    global g\n    return 1",
            "def f():\n    x = 1\n    del x",
            "async def f():\n    return 1",
            "def f():\n    yield 1",
            "def f(): return eval('1')",
            "def f(x): return getattr(x, 'y')",
            "def f(x): return x.open()",
        ]
        for snippet in unsafe:
            self.assertFalse(adv.validate_pure_ast(snippet), f"Should reject: {snippet!r}")

    def test_21_ai_advisor_consult_failure_modes_and_log_window_30(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_bin = Path(tmp) / "ask-ai"
            fake_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_bin.chmod(0o755)
            adv = MultiAIFleetAdvisor(ask_ai_bin=str(fake_bin))
            adv.dialogue_file = Path(tmp) / "consult.json"
            adv.dialogue_file.write_text("{corrupt", encoding="utf-8")

            # Corrupt history recovered and capped at 30 entries
            for i in range(35):
                adv._log_consultation({"idx": i})
            hist = json.loads(adv.dialogue_file.read_text(encoding="utf-8"))
            self.assertEqual(len(hist), 30)
            self.assertEqual(hist[0]["idx"], 5)
            self.assertEqual(hist[-1]["idx"], 34)

            # Unavailable binary returns None
            self.assertIsNone(MultiAIFleetAdvisor(ask_ai_bin=str(Path(tmp) / "missing")).consult_code_patch(
                "h", "s", "st", "t.py", "id", 1
            ))
            # Timeout / nonzero / unsafe AST return None
            for side in (
                subprocess.TimeoutExpired(["ask-ai"], 1),
                subprocess.CompletedProcess(["ask-ai"], 1, stdout="def f(): return 1", stderr="err"),
                subprocess.CompletedProcess(["ask-ai"], 0, stdout="   \n", stderr=""),
                subprocess.CompletedProcess(["ask-ai"], 0, stdout="```python\nimport os\n```", stderr=""),
            ):
                with patch("ace_code_agent.ai_advisor.subprocess.run", side_effect=[side]):
                    self.assertIsNone(adv.consult_code_patch("h", "s", "st", "t.py", "id", 1))

    # --- patch_synthesizer.py ---

    def test_22_patch_synthesizer_all_strategies_and_external_fallback_valid_ast(self) -> None:
        with patch.object(MultiAIFleetAdvisor, "is_available", return_value=False):
            gen = ModularPatchGenerator(use_external_model=True)
        strategies = (
            "MULTI_TASK_COMPOSITE_DISPATCH",
            "LIBRARY_PRIMITIVE_SYNTHESIS",
            "EVOLUTIONARY_SEARCH_SYNTHESIS",
            "LSTAR_AUTOMATA_SYNTHESIS",
            "UNKNOWN_FALLBACK_STRATEGY",
        )
        for idx, strat in enumerate(strategies, start=1):
            _, hyp, _, _ = _make_sample_objects(hyp_id=f"hyp_{idx}")
            hyp.proposed_strategy = strat
            patch_obj = gen.generate_patch(hyp, "BASELINE = 1\n", "code/ace_self_dev/strategy_repair.py")
            ast.parse(patch_obj.replacement_code_snippet)
            self.assertEqual(patch_obj.patch_type, "AST_TRANSFORMATION")
            self.assertEqual(patch_obj.generator_metadata["marginal_cost_usd"], 0.0)

    # --- patch_diagnostic.py ---

    def test_23_patch_diagnostic_verify_receipt_rejects_nan_nondict_tampered(self) -> None:
        self.assertFalse(verify_receipt("not-a-dict"))  # type: ignore[arg-type]
        self.assertFalse(verify_receipt({"receipt_sha256": 123}))
        base = {"status": "PASS", "exit_code": 0}
        digest = hashlib.sha256(json.dumps(base, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        valid = {**base, "receipt_sha256": digest}
        self.assertTrue(verify_receipt(valid))
        self.assertFalse(verify_receipt({**valid, "exit_code": 1}))
        self.assertFalse(verify_receipt({"val": float("nan"), "receipt_sha256": digest}))

    def test_24_patch_diagnostic_evaluate_patch_bounds_and_multibyte_utf8(self) -> None:
        with self.assertRaises(ValueError):
            evaluate_patch(".", "code/other.py", "x = 1")
        with self.assertRaises(ValueError):
            evaluate_patch(".", DIAGNOSTIC_TARGET, "")
        # 4097 x 4-byte emoji = 16388 UTF-8 bytes (> MAX_PATCH_BYTES=16384 meski len < 16384)
        oversized = "🔥" * (MAX_PATCH_BYTES // 4 + 1)
        self.assertLess(len(oversized), MAX_PATCH_BYTES)
        with self.assertRaises(ValueError):
            evaluate_patch(".", DIAGNOSTIC_TARGET, oversized)
        with patch("ace_code_agent.patch_diagnostic.shutil.which", return_value=None):
            with self.assertRaises(RuntimeError):
                evaluate_patch(".", DIAGNOSTIC_TARGET, "def ok(): return 1\n")

    # --- worktree_harness.py ---

    def test_25_worktree_harness_from_import_os_bypass_bug(self) -> None:
        # Bypass yang sudah ditutup (2026-11-20): pemeriksaan ImportFrom kini
        # memeriksa node.module, sehingga `from os import system` ditolak
        # validate_patch_security() seperti halnya `import os`.
        harness = WorktreeHarness()
        _, _, patch, _ = _make_sample_objects()
        patch.replacement_code_snippet = "from os import system\n"
        allowed, _ = harness.validate_patch_security(patch)
        self.assertFalse(allowed)

    # --- repo_retrieval.py ---

    def test_26_repo_retrieval_bounds_and_search_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for kwargs in (
                {"max_depth": -1},
                {"max_depth": 33},
                {"max_files": 0},
                {"max_files": 10001},
                {"max_file_bytes": 127},
                {"time_budget_seconds": 0.05},
            ):
                with self.assertRaises(ValueError):
                    BoundedRepositoryRetriever(root, **kwargs)

            retriever = BoundedRepositoryRetriever(root)
            with self.assertRaises(subprocess.CalledProcessError):
                retriever.build_index()
            empty_index = {"files": []}
            with self.assertRaises(ValueError):
                retriever.search(empty_index, "q", mode="semantic")
            with self.assertRaises(ValueError):
                retriever.search(empty_index, "   ")
            with self.assertRaises(ValueError):
                retriever.search(empty_index, "x" * 257)
            with self.assertRaises(ValueError):
                retriever.search(empty_index, "ok", limit=0)
            self.assertEqual(retriever.search(empty_index, "---"), [])

    # --- codebase_reader.py / problem_selector.py / models.py ---

    def test_27_codebase_reader_syntax_error_and_selector_default_and_models_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "code" / "demo"
            pkg.mkdir(parents=True)
            (pkg / "good.py").write_text("class A:\n    pass\n", encoding="utf-8")
            (pkg / "broken.py").write_text("def broken(:\n", encoding="utf-8")
            reader = CodebaseReader(root)
            scanned = reader.scan_python_modules("code/demo")
            self.assertTrue(scanned["code/demo/good.py"]["ast_valid"])
            self.assertFalse(scanned["code/demo/broken.py"]["ast_valid"])
            self.assertIn("parse_error", scanned["code/demo/broken.py"])

            state_path = root / "checkpoints" / "self_dev" / "research_state.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text("{corrupt", encoding="utf-8")
            diag = reader.read_failure_history()
            self.assertFalse(diag["state_available"])

            selector = ProblemSelector()
            prob, hyp = selector.select_next_problem({"cycle_count": 7, "unaddressed_tasks": []})
            self.assertEqual(prob.category, "LATENCY_INEFFICIENCY")
            self.assertEqual(hyp.proposed_strategy, "CONSTRAINT_PRUNING")

            _, _, p1, _ = _make_sample_objects()
            p2 = CodePatch(
                patch_id="different_id",
                hypothesis_id="different_hyp",
                target_file=p1.target_file,
                diff_content=p1.diff_content,
                original_code_snippet="",
                replacement_code_snippet=p1.replacement_code_snippet,
                patch_type=p1.patch_type,
                author_provenance="OTHER",
            )
            self.assertEqual(p1.patch_sha256, p2.patch_sha256)
            self.assertEqual(CodePatch.from_dict(p1.to_dict()).patch_sha256, p1.patch_sha256)


if __name__ == "__main__":
    unittest.main()
