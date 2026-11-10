import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from ace_code_agent.models import CodePatch
from ace_code_agent.models import WorktreeExecutionResult
from ace_code_agent.controller import AutonomousSoftwareResearcher
from ace_code_agent.worktree_harness import WorktreeHarness
from ace_host_controller.boundary import detect_os_sealing, SealingStatus
from ace_smt.dpllt_solver import LinearConstraint, Seq, Assign, Const, While, Lt, Var, Add, Eq, verify_program_satisfies_spec

class AuditRegressions(unittest.TestCase):
    def candidate(self, path, code='x = 1'):
        return CodePatch('p', 'h', path, '', '', code, 'test', 'test')

    def test_paths_cannot_escape(self):
        harness = WorktreeHarness()
        for path in ('/tmp/out.py', 'code/../code/ace_host_controller/a.py'):
            self.assertFalse(harness.validate_patch_security(self.candidate(path))[0])

    def test_candidate_execution_fails_closed(self):
        result = WorktreeHarness().execute_in_worktree(self.candidate('code/test_candidate.py'))
        self.assertIn(result.decision, ('REJECTED', 'INCONCLUSIVE'))
        self.assertNotEqual(result.decision, 'ACCEPTED')
        self.assertTrue(
            'BLOCKED_ENVIRONMENT' in result.rejection_reason
            or 'STAGED_ONLY_NOT_EXECUTED' in result.rejection_reason
        )

    def test_import_success_cannot_trigger_promotion(self):
        with tempfile.TemporaryDirectory() as directory:
            researcher = AutonomousSoftwareResearcher(Path(directory))
            fake = WorktreeExecutionResult(
                execution_id='x', patch_id='p', hypothesis_id='h', worktree_path='',
                applied_cleanly=True, ast_valid=True, tests_passed=1, tests_failed=0,
                test_duration_seconds=0, decision='ACCEPTED')
            with patch.object(researcher.harness, 'execute_in_worktree', return_value=fake), \
                 patch.object(researcher.pr_manager, 'publish_autonomous_pr') as publish:
                result = researcher.execute_autonomous_cycle(auto_pr=True)
            self.assertIn(result['decision'], ('REJECTED', 'INCONCLUSIVE'))
            self.assertNotEqual(result['decision'], 'ACCEPTED')
            self.assertTrue(
                'candidate-bound' in result['execution']['rejection_reason']
                or 'MISSING_INDEPENDENT_EVIDENCE' in result['execution']['rejection_reason']
                or 'STAGED_ONLY_NOT_EXECUTED' in result['execution']['rejection_reason']
            )
            publish.assert_not_called()

    def test_binary_presence_does_not_imply_containment(self):
        with patch('ace_host_controller.boundary.shutil.which', return_value='/usr/bin/bwrap'):
            self.assertEqual(detect_os_sealing(), SealingStatus.NOT_SEALED)

    def test_large_integer_normalization(self):
        n = 2**54 + 3
        self.assertEqual(LinearConstraint.create({'x': 2}, n, 'x').const, n // 2)

    def test_bounded_loop_cannot_prove_universal_claim(self):
        program = Seq([Assign('i', Const(0)), While(Lt(Var('i'), Const(3)), Assign('i', Add(Var('i'), Const(1))), max_unrolls=1)])
        with self.assertRaises(NotImplementedError):
            verify_program_satisfies_spec(program, None, Eq(Var('i'), Const(0)))
