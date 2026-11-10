"""Candidate-bound regression diagnostic safety tests."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ace_code_agent import patch_diagnostic as d

class PatchDiagnosticTests(unittest.TestCase):
    def test_target_and_size_are_bounded(self):
        for target, snippet in [('../outside.py', 'x=1'), (d.TARGET, ''), (d.TARGET, 'x' * (d.MAX_PATCH_BYTES + 1))]:
            with self.assertRaises(ValueError): d.evaluate_patch('.', target, snippet)

    def test_missing_sandbox_blocks(self):
        with patch.object(d.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'BLOCKED_ENVIRONMENT'):
                d.evaluate_patch('.', d.TARGET, '# candidate')

    def test_baseline_failure_skips_candidate_and_records_hashes(self):
        def fixture(repo, dst, commit):
            target = dst / d.TARGET
            target.parent.mkdir(parents=True)
            target.write_text('value = 1\n')
            for module in d.TEST_MODULES:
                test_file = dst / 'code' / (module.replace('.', '/') + '.py')
                test_file.parent.mkdir(parents=True, exist_ok=True)
                test_file.write_text('# test fixture\n')
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(d.shutil, 'which', return_value='/usr/bin/example'), \
             patch.object(d.subprocess, 'check_output', return_value='a'*40+'\n'), \
             patch.object(d, '_extract_snapshot', side_effect=fixture), \
             patch.object(d, '_run', return_value={'passed':False,'status':'FAIL_OR_BLOCKED'}) as runner:
            result = d.evaluate_patch(temp, d.TARGET, 'value = 2')
        self.assertEqual(runner.call_count, 1)
        self.assertEqual(result['candidate']['status'], 'NOT_RUN')
        self.assertNotEqual(result['base_file_sha256'], result['candidate_file_sha256'])
        self.assertFalse(result['promotion_authorized'])
        self.assertEqual(len(result['receipt_sha256']), 64)
        self.assertEqual(len(result['test_file_sha256']), len(d.TEST_MODULES))
        self.assertTrue(d.verify_receipt(result))
        result['promotion_authorized'] = True
        self.assertFalse(d.verify_receipt(result))

    def test_checksum_is_not_authentication(self):
        import json
        receipt = {'promotion_authorized': True}
        receipt['receipt_sha256'] = d._sha(json.dumps(receipt, sort_keys=True, separators=(',', ':')).encode())
        # A checksum can be recomputed; acceptance policy must remain separate.
        self.assertTrue(d.verify_receipt(receipt))

    def test_exit_zero_without_completed_tests_fails_closed(self):
        from types import SimpleNamespace
        with patch.object(d.subprocess, 'run', return_value=SimpleNamespace(returncode=0)):
            result = d._run(Path('/tmp/fake'), '/usr/bin/bwrap', '/usr/bin/prlimit')
        self.assertFalse(result['passed'])
        self.assertEqual(result['test_count'], 0)

    def test_completed_unittest_output_and_limits_are_bound(self):
        from types import SimpleNamespace
        def fake_run(command, **kwargs):
            kwargs['stdout'].write(b'----------------------------------------------------------------------\nRan 5 tests in 0.123s\n\nOK\n')
            self.assertIn('--unshare-all', command)
            self.assertIn('--clearenv', command)
            return SimpleNamespace(returncode=0)
        with patch.object(d.subprocess, 'run', side_effect=fake_run):
            result = d._run(Path('/tmp/fake'), '/usr/bin/bwrap', '/usr/bin/prlimit')
        self.assertTrue(result['passed'])
        self.assertEqual(result['test_count'], 5)

    def test_spoofed_success_never_marks_candidate_as_passed(self):
        def fixture(repo, dst, commit):
            target = dst / d.TARGET
            target.parent.mkdir(parents=True)
            target.write_text('value = 1\n')
            for module in d.TEST_MODULES:
                file = dst / 'code' / (module.replace('.', '/') + '.py')
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text('# pinned test\n')
        fake_run = {'passed': True, 'status': 'PASS', 'test_count': 20}
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(d.shutil, 'which', return_value='/usr/bin/example'), \
             patch.object(d.subprocess, 'check_output', return_value='a'*40+'\n'), \
             patch.object(d, '_extract_snapshot', side_effect=fixture), \
             patch.object(d, '_run', return_value=fake_run):
            result = d.evaluate_patch(temp, d.TARGET, "import os\nos._exit(0)")
        self.assertEqual(result['candidate']['status'], 'INCONCLUSIVE')
        self.assertTrue(result['candidate']['reported_test_success'])
        self.assertFalse(result['candidate']['passed'])
        self.assertFalse(result['promotion_authorized'])

if __name__ == '__main__': unittest.main()
