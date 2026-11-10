"""Operational Proof & Verification Suite for ACE Autonomous Code Agent (V0.3).

Verifies the 7 required criteria from Tahap 5:
1. ACE autonomously selects research problems without human prompts per cycle.
2. ACE synthesizes genuine code patches with verifiable AST and diffs.
3. ACE automatically creates git branches and PR metadata with verifiable author identity.
4. Independent evaluator accepts or rejects modifications based on empirical evidence and negative controls.
5. Persistent research state survives process stoppage, reload, and re-execution.
6. Duplicate candidate patches are intercepted and de-duplicated with zero wasted evaluation.
7. Baseline and recovery baselines remain intact and protected from candidate corruption.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ace_code_agent.codebase_reader import CodebaseReader
from ace_code_agent.controller import AutonomousSoftwareResearcher
from ace_code_agent.independent_evaluator import IndependentEvaluator
from ace_code_agent.models import ImprovementHypothesis, ResearchProblem
from ace_code_agent.patch_synthesizer import ModularPatchGenerator
from ace_code_agent.problem_selector import ProblemSelector
from ace_code_agent.worktree_harness import WorktreeHarness


class TestAutonomousCodeAgentOperationalProof(unittest.TestCase):
    """Rigorous unit and integration test suite proving autonomous self-development capabilities."""

    def setUp(self):
        self.temp_repo = Path(tempfile.mkdtemp(prefix="ace_test_agent_"))
        self.code_dir = self.temp_repo / "code" / "ace_self_dev"
        self.code_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir = self.temp_repo / "checkpoints" / "self_dev"
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

        # Create dummy target file
        self.target_file = self.code_dir / "strategy_repair.py"
        self.target_file.write_text("def repair_strategy():\n    return 'linear_mutation'\n", encoding="utf-8")

        # Create baseline state
        self.state_file = self.checkpoints_dir / "v03_researcher_state.json"
        self.immutable_baseline_file = self.checkpoints_dir / "immutable_baseline.json"
        self.immutable_baseline_file.write_text(json.dumps({"root_id": "G0_root", "accuracy": 0.50}), encoding="utf-8")

        self.researcher = AutonomousSoftwareResearcher(self.temp_repo)

    def tearDown(self):
        shutil.rmtree(self.temp_repo, ignore_errors=True)

    def test_criterion_1_autonomous_problem_selection_without_human_prompt(self):
        """Criterion 1: ProblemSelector inspects diagnostics and formulates problem & hypothesis."""
        diagnostics = {
            "cycle_count": 5,
            "stagnation_events": 2,
            "common_rejection_reasons": {"NO_VALIDATION_IMPROVEMENT": 3},
            "task_failure_counts": {"task_k2": 4},
        }
        selector = ProblemSelector()
        problem, hypothesis = selector.select_next_problem(diagnostics)

        self.assertIsInstance(problem, ResearchProblem)
        self.assertIsInstance(hypothesis, ImprovementHypothesis)
        self.assertEqual(problem.category, "REPRESENTATION_BOTTLENECK")
        self.assertEqual(hypothesis.proposed_strategy, "MULTI_TASK_COMPOSITE_DISPATCH")
        self.assertTrue(len(hypothesis.statement) > 10)
        self.assertGreater(hypothesis.expected_metric_gain, 0.0)

    def test_criterion_2_real_source_code_patch_generation(self):
        """Criterion 2: Synthesizer generates genuine unified diff and replacement code snippet."""
        hypothesis = ImprovementHypothesis(
            hypothesis_id="hyp_test_01",
            problem_id="prob_01",
            statement="Expand dispatch predicates to handle multi-task modular invariants.",
            proposed_strategy="MULTI_TASK_COMPOSITE_DISPATCH",
            expected_metric_gain=0.1875,
            target_module="code/ace_self_dev/strategy_repair.py",
            rationale="Single-task search cannot cross the threshold.",
        )
        synthesizer = ModularPatchGenerator()
        orig_source = "def evaluate_mechanism(l, d, s):\n    return l % 3\n"
        patch = synthesizer.generate_patch(hypothesis, orig_source, "code/ace_self_dev/strategy_repair.py")
        self.assertIn("ace_v04_dispatch", patch.replacement_code_snippet)
        self.assertIn("--- a/code/ace_self_dev/strategy_repair.py", patch.diff_content)
        self.assertIn("+++ b/code/ace_self_dev/strategy_repair.py", patch.diff_content)
        self.assertEqual(patch.author_provenance, "ACE_BOUNDED_AST_PATCH_GENERATOR_V04")
        self.assertFalse(patch.generator_metadata.get("external_model_claimed", False))

    def test_criterion_3_worktree_isolation_and_security_blocking(self):
        """Criterion 3 & 7: Harness blocks patches targeting protected governance files or dangerous AST."""
        harness = WorktreeHarness(self.temp_repo)
        synthesizer = ModularPatchGenerator()
        hypothesis = ImprovementHypothesis(
            hypothesis_id="hyp_malicious_01",
            problem_id="prob_malicious",
            statement="Attempt unauthorized modification of immutable baseline.",
            proposed_strategy="UNAUTHORIZED_OVERWRITE",
            expected_metric_gain=0.50,
            target_module="checkpoints/self_dev/immutable_baseline.json",
            rationale="Bypass safety gates.",
        )
        malicious_patch = synthesizer.generate_patch(
            hypothesis,
            "baseline data",
            "checkpoints/self_dev/immutable_baseline.json",
        )

        # Execute in worktree
        result = harness.execute_in_worktree(malicious_patch)
        self.assertEqual(result.decision, "REJECTED")
        self.assertIn("SECURITY VIOLATION", result.rejection_reason)
        # Ensure immutable baseline is completely intact!
        baseline_content = json.loads(self.immutable_baseline_file.read_text(encoding="utf-8"))
        self.assertEqual(baseline_content["accuracy"], 0.50)

    def test_fail_closed_candidate_intake_does_not_execute_untrusted_code(self):
        """A parsable appended function and a purported test must not imply improvement."""
        from ace_code_agent.models import CodePatch
        patch = CodePatch(
            patch_id="staged_only",
            hypothesis_id="hyp_test",
            target_file="code/ace_self_dev/strategy_repair.py",
            diff_content="",
            original_code_snippet="",
            replacement_code_snippet="def unused_candidate(length, density, stride_val):\n    return 1\n",
            patch_type="MULTI_AI_SYNTHESIS",
            author_provenance="EXTERNAL_MODEL_UNTRUSTED",
        )
        # The test command would mutate the host if the harness executed it.
        marker = self.temp_repo / "untrusted_test_ran"
        command = ["python", "-c", f"open({str(marker)!r}, 'w').write('BAD')"]
        result = WorktreeHarness(self.temp_repo).execute_in_worktree(
            patch, test_commands=[command]
        )
        self.assertEqual(result.decision, "INCONCLUSIVE")
        self.assertTrue(result.ast_valid)
        self.assertFalse(result.applied_cleanly)
        self.assertEqual(result.tests_passed, 0)
        self.assertFalse(marker.exists())
        self.assertIn("STAGED_ONLY_NOT_EXECUTED", result.rejection_reason)

    def test_fail_closed_candidate_rejects_path_traversal(self):
        """A crafted target must not escape a worktree or protected paths."""
        from ace_code_agent.models import CodePatch
        patch = CodePatch(
            patch_id="path_traversal",
            hypothesis_id="hyp_test",
            target_file="code/../checkpoints/self_dev/immutable_baseline.json",
            diff_content="",
            original_code_snippet="",
            replacement_code_snippet="def harmless():\n    return 0\n",
            patch_type="MULTI_AI_SYNTHESIS",
            author_provenance="EXTERNAL_MODEL_UNTRUSTED",
        )
        result = WorktreeHarness(self.temp_repo).execute_in_worktree(patch)
        self.assertEqual(result.decision, "REJECTED")
        self.assertIn("SECURITY VIOLATION", result.rejection_reason)

    def test_criterion_4_independent_evaluation_and_negative_control(self):
        """Criterion 4: Evaluator accepts valid functions and rejects trivial constant predictors."""
        evaluator = IndependentEvaluator()

        # Dummy candidate that always predicts 1 (adversarial shortcut)
        trivial_fn = lambda l, d, s: 1
        neg_control_ok = evaluator.evaluate_negative_control(trivial_fn)
        self.assertFalse(neg_control_ok, "Trivial constant predictor must FAIL negative control!")

        # Genuine modular solver for task_k2
        good_fn = lambda l, d, s: 1 if ((s * 2 - d) % 3 == 0) else 0
        neg_control_good = evaluator.evaluate_negative_control(good_fn)
        self.assertTrue(neg_control_good, "Legitimate solver must PASS negative control.")

        score, hits, total = evaluator.evaluate_predicate(good_fn, "task_k2")
        self.assertGreater(score, 0.70)
        self.assertGreaterEqual(hits, 6)

    def test_criterion_5_and_6_state_persistence_and_duplicate_deduplication(self):
        """Criterion 5 & 6: State survives restarts, and duplicates are skipped without evaluator cost."""
        # Run Cycle 1
        res1 = self.researcher.execute_autonomous_cycle(auto_pr=False)
        self.assertEqual(res1["cycle"], 1)
        self.assertEqual(res1["decision"], "INCONCLUSIVE")

        # Reload researcher from disk (simulating restart)
        reloaded_researcher = AutonomousSoftwareResearcher(self.temp_repo)
        state_after_1 = reloaded_researcher.load_researcher_state()
        self.assertEqual(state_after_1["completed_cycles"], 1)

        # Run Cycle 2 with identical hypothesis to verify duplicate de-duplication
        prob1 = ResearchProblem.from_dict(res1["problem"])
        hyp1 = ImprovementHypothesis.from_dict(res1["hypothesis"])
        reloaded_researcher.selector.select_next_problem = lambda diag: (prob1, hyp1)
        res2 = reloaded_researcher.execute_autonomous_cycle(auto_pr=False)
        self.assertEqual(res2["decision"], "DUPLICATE_PATCH_SKIPPED")
        self.assertEqual(res2["evaluator_calls"], 0)

        # Baseline check
        self.assertTrue(self.immutable_baseline_file.exists())

    def test_criterion_autonomous_pr_pipeline_and_safety(self):
        """Criterion: AutonomousPRManager enforces safety namespace and structured verification."""
        from ace_code_agent.pr_manager import AutonomousPRManager
        from ace_code_agent.models import AutonomousPRMetadata, CodePatch, WorktreeExecutionResult

        pr_manager = AutonomousPRManager(self.temp_repo)
        problem = ResearchProblem(
            problem_id="prob_pr_test",
            category="REPRESENTATION_BOTTLENECK",
            title="PR Pipeline Test Problem",
            description="Testing PR metadata generation.",
            target_files=["code/ace_self_dev/strategy_repair.py"],
        )
        hypothesis = ImprovementHypothesis(
            hypothesis_id="hyp_pr_test_01",
            problem_id="prob_pr_test",
            statement="Test statement for PR generation.",
            proposed_strategy="MULTI_TASK_COMPOSITE_DISPATCH",
            expected_metric_gain=0.18,
            target_module="code/ace_self_dev/strategy_repair.py",
            rationale="Test rationale.",
        )
        patch = CodePatch(
            patch_id="patch_test_pr",
            hypothesis_id="hyp_pr_test_01",
            target_file="code/ace_self_dev/strategy_repair.py",
            diff_content="--- a\n+++ b\n",
            original_code_snippet="",
            replacement_code_snippet="def dummy_test(): pass\n",
            patch_type="AST_TRANSFORMATION",
            author_provenance="ACE_BOUNDED_AST_PATCH_GENERATOR_V04",
        )
        exec_res = WorktreeExecutionResult(
            execution_id="exec_test_01",
            patch_id=patch.patch_id,
            hypothesis_id=hypothesis.hypothesis_id,
            worktree_path="",
            applied_cleanly=True,
            ast_valid=True,
            tests_passed=1,
            tests_failed=0,
            test_duration_seconds=0.1,
            decision="ACCEPTED",
            receipt_signature="sig_test_12345",
        )

        pr_meta = pr_manager.prepare_pr_metadata(problem, hypothesis, patch, exec_res)
        self.assertTrue(pr_meta.branch_name.startswith("ace-dev/"))
        self.assertIn("Autonomous Research PR", pr_meta.body_markdown)
        self.assertIn("sig_test_12345", pr_meta.body_markdown)

        # Test safety namespace violation
        unsafe_meta = AutonomousPRMetadata(
            pr_id="unsafe_01",
            branch_name="main-exploit",
            target_branch="main",
            title="Unsafe branch",
            body_markdown="Unsafe",
            commit_sha="",
            hypothesis_id="hyp_unsafe",
            patch_id="patch_unsafe",
            merkle_proof_digest="sig",
            author_identity="ACE",
        )
        ok, msg = pr_manager.create_git_branch_and_commit(unsafe_meta, patch)
        self.assertFalse(ok)
        self.assertIn("SECURITY VIOLATION", msg)

        # Test verification fails closed without PR number/url
        empty_meta = AutonomousPRMetadata(
            pr_id="empty_01",
            branch_name="ace-dev/test",
            target_branch="main",
            title="Empty PR",
            body_markdown="Empty",
            commit_sha="",
            hypothesis_id="hyp_test",
            patch_id="patch_test",
            merkle_proof_digest="sig",
            author_identity="ACE",
        )
        ok_ver, ver_msg, _ = pr_manager.verify_pr_exists(empty_meta)
        self.assertFalse(ok_ver)
        self.assertIn("No PR number or URL", ver_msg)



class TestPublicStaticProbe(unittest.TestCase):
    """Actual AST candidate is probed, but never compiled/executed or promoted."""

    def test_modular_rule_has_real_public_score_and_strong_reference(self):
        from ace_code_agent.static_probe import public_diagnostic
        code = (
            "def ace_ai_synthesized_modular(length: int, density: int, stride_val: int) -> int:\n"
            "    return 1 if (stride_val * 2 - density) % 3 == 0 else 0\n"
        )
        score = public_diagnostic(code)
        self.assertEqual(score["public_probe_count"], 96.0)
        self.assertEqual(score["public_modular_candidate"], 1.0)
        self.assertEqual(score["public_strong_baseline"], 1.0)
        self.assertLess(score["public_parity_candidate"], 1.0)
        self.assertEqual(score["independent_confirmation"], 0.0)
        self.assertEqual(score["connected_to_active_algorithm"], 0.0)
        self.assertEqual(score["candidate_python_executed"], 0.0)

    def test_branching_and_assignments_are_interpreted_without_exec(self):
        from ace_code_agent.static_probe import public_diagnostic
        code = (
            "def ace_ai_synthesized_parity(length, density, stride_val):\n"
            "    if length < 4:\n"
            "        return 0\n"
            "    good = density % 2 == 0\n"
            "    return 1 if good else 0\n"
        )
        score = public_diagnostic(code)
        self.assertEqual(score["public_parity_candidate"], 1.0)
        self.assertEqual(score["candidate_python_executed"], 0.0)

    def test_rejects_untrusted_python_semantics(self):
        from ace_code_agent.static_probe import parse_candidate, UnsafeOrUnsupported
        bad = [
            "import os\n" "def ace_ai_synthesized_bad(length,density,stride_val):\n"
            "    return os.system('echo BAD')\n",
            "def ace_ai_synthesized_bad(length,density,stride_val):\n"
            "    while True: pass\n",
            "def ace_ai_synthesized_bad(length,density,stride_val):\n"
            "    return 2**20000000\n",
            "def ace_ai_synthesized_bad(length,density,stride_val):\n"
            "    return open('/tmp/unsafe', 'w')\n",
            "def ace_ai_synthesized_bad(length,density,stride_val, extra):\n"
            "    return 0\n",
            "def ace_ai_synthesized_bad(length,density,stride_val):\n"
            "    return (lambda x: x)(length)\n",
            "def ace_ai_synthesized_bad(length,density,stride_val):\n"
            "    return 0\n"
            "def second(): return 1\n",
        ]
        for source in bad:
            with self.subTest(source=source[:40]):
                with self.assertRaises(UnsafeOrUnsupported):
                    parse_candidate(source)

    def test_actual_96_style_ai_candidate_runs_in_interpreter_only(self):
        from ace_code_agent.static_probe import public_diagnostic, parse_candidate
        code = (
            "def ace_ai_synthesized_hyp_expand_dispatch_96(length: int, density: int, stride_val: int) -> int:\n"
            "    if stride_val == 0:\n"
            "        return 0\n"
            "    congruent = length % stride_val == density % stride_val\n"
            "    parity_matches = length % 2 == density % 2\n"
            "    return int(congruent and parity_matches)\n"
        )
        self.assertIsNotNone(parse_candidate(code))
        result = public_diagnostic(code)
        self.assertEqual(result["public_probe_count"], 96.0)
        self.assertEqual(result["candidate_python_executed"], 0.0)
        self.assertEqual(result["independent_confirmation"], 0.0)
        self.assertEqual(result["connected_to_active_algorithm"], 0.0)

    def test_only_int_one_positional_arg_is_interpreted(self):
        from ace_code_agent.static_probe import parse_candidate, UnsafeOrUnsupported
        forbidden_calls = (
            "eval('1')", "float(length)", "int()", "int(length, 2)",
            "int(length, base=2)", "int.__call__(length)",
            "int(__import__('os').system('echo bad'))",
            "int([1][0])",
        )
        for expression in forbidden_calls:
            code = (
                "def ace_ai_synthesized_bad(length, density, stride_val):\n"
                f"    return {expression}\n"
            )
            with self.subTest(expression=expression):
                with self.assertRaises(UnsafeOrUnsupported):
                    parse_candidate(code)

    def test_rejects_unbounded_or_nonbinary_evaluation(self):
        from ace_code_agent.static_probe import (
            parse_candidate, interpret, public_diagnostic, UnsafeOrUnsupported
        )
        huge = parse_candidate(
            "def ace_ai_synthesized_big(length,density,stride_val):\n"
            "    return (length * 999999) * 999999\n"
        )
        with self.assertRaises(UnsafeOrUnsupported):
            interpret(huge, 32, 1, 1)
        with self.assertRaises(UnsafeOrUnsupported):
            public_diagnostic(
                "def ace_ai_synthesized_two(length,density,stride_val):\n"
                "    return 2\n"
            )

    def test_public_probe_never_produces_accepted(self):
        from ace_code_agent.models import CodePatch
        from ace_code_agent.worktree_harness import WorktreeHarness
        candidate = CodePatch(
            patch_id="modular_predicate",
            hypothesis_id="hyp_modular",
            target_file="code/ace_self_dev/strategy_repair.py",
            diff_content="",
            original_code_snippet="",
            replacement_code_snippet=(
                "def ace_ai_synthesized_modular(length,density,stride_val):\n"
                "    return 1 if (stride_val * 2 - density) % 3 == 0 else 0\n"
            ),
            patch_type="MULTI_AI_SYNTHESIS",
            author_provenance="EXTERNAL_MODEL_UNTRUSTED",
        )
        result = WorktreeHarness(self.temp_repo if hasattr(self, "temp_repo") else Path(".")).execute_in_worktree(candidate)
        self.assertEqual(result.decision, "INCONCLUSIVE")
        self.assertEqual(result.performance_metrics["public_modular_candidate"], 1.0)
        self.assertEqual(result.performance_metrics["connected_to_active_algorithm"], 0.0)
        self.assertEqual(result.performance_metrics["candidate_python_executed"], 0.0)
        self.assertIn("PUBLIC_PROBE_COMPLETED", result.rejection_reason)


try:
    from tools.ace_ai_diagnostic import audit_consultations
except (ImportError, ModuleNotFoundError):
    import importlib.util
    _tools_path = _REPO_ROOT / "tools" / "ace_ai_diagnostic.py"
    _spec = importlib.util.spec_from_file_location("tools.ace_ai_diagnostic", _tools_path)
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules["tools.ace_ai_diagnostic"] = _mod
    _spec.loader.exec_module(_mod)
    audit_consultations = _mod.audit_consultations


class TestTermuxAiDiagnosticCLI(unittest.TestCase):
    """Read-only reports use the real stored source, not a fabricated AI result."""

    def test_read_only_diagnostics_fail_closed_and_do_not_claim_provider(self):
        from tools.ace_ai_diagnostic import audit_consultations
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "ai_consultations.json"
            records = [
                {
                    "timestamp": "2026-11-09 19:39:57 UTC",
                    "hypothesis_id": "hyp_expand_dispatch_95",
                    "engine": "PowerBrain (GPT-5/4) / Pollinations",
                    "ai_answered": (
                        "def ace_ai_synthesized_test(length,density,stride_val):\n"
                        "    return 1 if (2*stride_val-density)%3==0 else 0\n"
                    ),
                },
                {
                    "timestamp": "2026-11-09 19:41:53 UTC",
                    "hypothesis_id": "hyp_expand_dispatch_96",
                    "engine": "UNVERIFIED_PROVIDER",
                    "ai_answered": (
                        "def ace_ai_synthesized_bad(length,density,stride_val):\n"
                        "    return int(length==density)\n"
                    ),
                },
            ]
            original = json.dumps(records)
            source_path.write_text(original, encoding="utf-8")
            report = audit_consultations(source_path, limit=2)
            self.assertEqual(source_path.read_text(encoding="utf-8"), original)
            self.assertEqual(report["records_scored"], 2)
            self.assertEqual(report["records"][0]["status"], "PUBLIC_DIAGNOSTIC_ONLY")
            self.assertEqual(report["records"][0]["public_diagnostic"]["public_modular_candidate"], 1.0)
            self.assertFalse(report["records"][0]["provider_verified"])
            self.assertFalse(report["records"][0]["candidate_python_executed"])
            self.assertEqual(report["records"][1]["status"], "PUBLIC_DIAGNOSTIC_ONLY")
            self.assertFalse(report["records"][1]["candidate_python_executed"])
            self.assertEqual(report["release_gate"], "BLOCK_RELEASE")
            self.assertEqual(report["scientific_status"], "NOT_ASSESSED")

    def test_rejects_malformed_input_and_unbounded_limit(self):
        from tools.ace_ai_diagnostic import audit_consultations
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "consultations.json"
            path.write_text('{"not": "a list"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                audit_consultations(path)
            with self.assertRaises(ValueError):
                audit_consultations(path, limit=0)

    def test_cycle_95_and_96_are_duplicate_on_public_grid(self):
        from ace_code_agent.static_probe import public_behavior_digest, public_diagnostic
        c95 = (
            "def ace_ai_synthesized_hyp_expand_dispatch_95(length,density,stride_val):\n"
            "    if stride_val == 0:\n"
            "        return 0\n"
            "    congruent = length % stride_val == density % stride_val\n"
            "    run_length_parity = (length - density) % 2 == 0\n"
            "    return 1 if congruent and run_length_parity else 0\n"
        )
        c96 = (
            "def ace_ai_synthesized_hyp_expand_dispatch_96(length,density,stride_val):\n"
            "    if stride_val == 0:\n"
            "        return 0\n"
            "    congruent = length % stride_val == density % stride_val\n"
            "    parity_matches = length % 2 == density % 2\n"
            "    return int(congruent and parity_matches)\n"
        )
        self.assertEqual(public_behavior_digest(c95), public_behavior_digest(c96))
        self.assertEqual(public_diagnostic(c95), public_diagnostic(c96))

    def test_audit_flags_repeated_public_behavior_without_claiming_equivalence(self):
        from tools.ace_ai_diagnostic import audit_consultations
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "consultations.json"
            same_behavior = [
                {"hypothesis_id": "hyp_old",
                 "ai_answered": "def ace_ai_synthesized_first(length,density,stride_val):\n"
                                "    return 1 if length % 2 == 0 else 0\n"},
                {"hypothesis_id": "hyp_new",
                 "ai_answered": "def ace_ai_synthesized_second(length,density,stride_val):\n"
                                "    return int(length % 2 == 0)\n"},
            ]
            path.write_text(json.dumps(same_behavior), encoding="utf-8")
            report = audit_consultations(path, limit=2)
            self.assertEqual(
                report["records"][1]["public_behavior_duplicate_of"], "hyp_old"
            )
            self.assertEqual(report["records"][0]["status"], "PUBLIC_DIAGNOSTIC_ONLY")
            self.assertEqual(report["records"][1]["status"], "PUBLIC_DIAGNOSTIC_ONLY")
            self.assertEqual(report["release_gate"], "BLOCK_RELEASE")
