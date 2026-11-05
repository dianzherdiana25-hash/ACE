"""Fail-closed historical test coverage audit regression (no network)."""
from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

try:
    from tools.ace_historical_coverage import (CoverageError, audit, main,
        module_path, parse_declared_tests, write_atomic)
except ModuleNotFoundError:
    from ace_historical_coverage import (CoverageError, audit, main,
        module_path, parse_declared_tests, write_atomic)

SHA = 'a' * 40
RUNNER = "TESTS={'u':['e14.test_one','e14.test_missing'],'tooling':['tools.test_local']}\n"

class ManifestTests(unittest.TestCase):
    def test_static_manifest_only_no_imports(self):
        groups = parse_declared_tests(RUNNER.encode())
        self.assertEqual(('e14.test_one', 'e14.test_missing'), groups['u'])
        self.assertEqual(('tools.test_local',), groups['tooling'])

    def test_malicious_expression_rejected_without_execution(self):
        source = b"TESTS=__import__('os').system('touch /tmp/should-never-be-created')\n"
        with self.assertRaisesRegex(CoverageError, 'literal dictionary'):
            parse_declared_tests(source)

    def test_duplicate_group_rejected(self):
        with self.assertRaisesRegex(CoverageError, 'duplicate test group'):
            parse_declared_tests(b"TESTS={'u':['e14.test_one'],'u':['e14.test_two']}\n")

    def test_duplicate_module_rejected(self):
        with self.assertRaisesRegex(CoverageError, 'duplicate module'):
            parse_declared_tests(b"TESTS={'u':['e14.test_one'],'t':['e14.test_one']}\n")

    def test_invalid_group_and_module_rejected(self):
        for text in (b"TESTS={'UPPER':['e14.test_one']}",
                     b"TESTS={'good':['e14.test_one/../escape']}",
                     b"TESTS={'good':[]}", b"TESTS={'good':[123]}"):
            with self.subTest(text=text), self.assertRaises(CoverageError):
                parse_declared_tests(text)

    def test_redefinition_rejected(self):
        with self.assertRaisesRegex(CoverageError, 'exactly one'):
            parse_declared_tests(b"TESTS={'a':['e14.test_one']}\nTESTS={'b':['e14.test_two']}\n")

    def test_safe_relative_module_path(self):
        self.assertEqual('code/e14/test_one.py', module_path('e14.test_one').as_posix())
        self.assertEqual('tools/test_local.py', module_path('tools.test_local').as_posix())
        with self.assertRaises(CoverageError):
            module_path('other.file')


class CheckoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(['git', '-C', str(self.root), 'init', '-q'], check=True, capture_output=True)
        subprocess.run(['git', '-C', str(self.root), 'config', 'user.email', 'test@example.invalid'], check=True)
        subprocess.run(['git', '-C', str(self.root), 'config', 'user.name', 'ACE Test'], check=True)
        (self.root / 'tools').mkdir()
        (self.root / 'tools' / 'ace_e15_regression.py').write_text(RUNNER)
        (self.root / 'tools' / 'test_local.py').write_text('')
        (self.root / 'code' / 'e14').mkdir(parents=True)
        (self.root / 'code' / 'e14' / 'test_one.py').write_text('')
        self.commit()

    def commit(self):
        subprocess.run(['git', '-C', str(self.root), 'add', '-A'], check=True, capture_output=True)
        subprocess.run(['git', '-C', str(self.root), 'commit', '-qm', 'synthetic fixture', '--allow-empty'], check=True)
        self.sha = subprocess.check_output(['git', '-C', str(self.root), 'rev-parse', 'HEAD'], text=True).strip()

    def test_exact_head_and_explicit_missing(self):
        report = audit(self.root, expected_head=self.sha)
        self.assertEqual('INCOMPLETE_HISTORICAL_COVERAGE', report['status'])
        self.assertEqual(3, report['declared_test_module_count'])
        self.assertEqual(1, report['missing_test_source_count'])
        self.assertEqual([{'module': 'e14.test_missing', 'path': 'code/e14/test_missing.py'}],
                         next(g for g in report['groups'] if g['group'] == 'u')['missing'])
        self.assertEqual(0, report['historical_tests_executed'])
        self.assertEqual(0, report['historical_tests_passed'])

    def test_missing_source_fixed_does_not_claim_test_pass(self):
        (self.root / 'code' / 'e14' / 'test_missing.py').write_text('')
        self.commit()
        report = audit(self.root, expected_head=self.sha)
        self.assertEqual('SOURCE_INVENTORY_COMPLETE_TESTS_NOT_RUN', report['status'])
        self.assertEqual(0, report['missing_test_source_count'])
        self.assertTrue(all(row['status'] == 'SOURCE_PRESENT_NOT_EXECUTED' for row in report['groups']))
        self.assertEqual(0, report['historical_tests_passed'])

    def test_wrong_commit_fails_closed(self):
        with self.assertRaisesRegex(CoverageError, 'CHECKOUT_HEAD_MISMATCH'):
            audit(self.root, expected_head=SHA)

    def test_uncommitted_manifest_change_rejected(self):
        (self.root / 'tools' / 'ace_e15_regression.py').write_text(
            "TESTS={'u':['e14.test_one'], 'tooling':['tools.test_local']}\n")
        with self.assertRaisesRegex(CoverageError, 'TRACKED_CHECKOUT_DIRTY'):
            audit(self.root, expected_head=self.sha)

    def test_untracked_test_source_does_not_fake_coverage(self):
        (self.root / 'code' / 'e14' / 'test_missing.py').write_text('')
        report = audit(self.root, expected_head=self.sha)
        self.assertEqual(1, report['missing_test_source_count'])
        self.assertEqual('INCOMPLETE_HISTORICAL_COVERAGE', report['status'])

    def test_symlinked_module_detected(self):
        (self.root / 'code' / 'e14' / 'test_missing.py').symlink_to(self.root / 'tools' / 'test_local.py')
        with self.assertRaisesRegex(CoverageError, 'symlink path forbidden'):
            audit(self.root, expected_head=self.sha)

    def test_cli_reports_incomplete_exit_two_and_durable_bytes(self):
        output = self.root / 'results' / 'coverage.json'
        with patch('sys.stdout', new_callable=io.StringIO) as stdout:
            result = main(['--root', str(self.root), '--expected-head', self.sha,
                           '--output', str(output)])
        self.assertEqual(2, result)
        self.assertEqual(json.loads(stdout.getvalue()), json.loads(output.read_text()))
        original = output.read_bytes()
        with patch('sys.stderr', new_callable=io.StringIO):
            self.assertEqual(1, main(['--root', str(self.root), '--expected-head', self.sha,
                                      '--output', str(output)]))
        self.assertEqual(original, output.read_bytes())

    def test_unknown_group_rejected(self):
        with self.assertRaisesRegex(CoverageError, 'unknown required groups'):
            audit(self.root, expected_head=self.sha, require_groups=('does-not-exist',))

    def test_deterministic_report(self):
        a = audit(self.root, expected_head=self.sha)
        b = audit(self.root, expected_head=self.sha)
        self.assertEqual(a, b)


if __name__ == '__main__':
    unittest.main()
