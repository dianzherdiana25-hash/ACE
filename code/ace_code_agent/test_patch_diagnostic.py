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
        self.assertTrue(d.verify_receipt(result))
        result['promotion_authorized'] = True
        self.assertFalse(d.verify_receipt(result))

    def test_checksum_is_not_authentication(self):
        import json
        receipt = {'promotion_authorized': True}
        receipt['receipt_sha256'] = d._sha(json.dumps(receipt, sort_keys=True, separators=(',', ':')).encode())
        # A checksum can be recomputed; acceptance policy must remain separate.
        self.assertTrue(d.verify_receipt(receipt))

if __name__ == '__main__': unittest.main()
