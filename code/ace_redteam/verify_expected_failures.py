"""Strict red-team result gate: expected failures are not automatic evidence.

Do not treat unittest's `OK (expected failures=N)` as sufficient. This verifier
pins the source under test and checks the exact failure signatures of all
known open defects, so unrelated crashes cannot silently count as findings.

Run: PYTHONPATH=code:. python -m ace_redteam.verify_expected_failures
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import re
import sys
import unittest

SUITES = (
    'ace_redteam.test_adversarial',
    'ace_redteam.test_adversarial_v2',
    'ace_redteam.test_portfolio_redteam',
    'ace_redteam.test_adversarial_v3',
)
EXPECTED_SOURCE_BLOBS = {
    'ace_loop/engine.py': '4ebef377e730e2e403c1d437903e04a202ac0bea',
    'ace_loop/source_evolution.py': '8a8c2c729db3072612830c03d7bd1eb0a2371ce9',
    'ace_loop/portfolio.py': '274fb494e127a25c7b5ecf4523e246fdf0f23501',
}
# Full-match patterns refer to the terminal exception line, not a broad keyword.
KNOWN_OPEN_FAILURES = {
    'test_rt01_ledger_path_swap_after_lock_must_not_ack_lost_receipt': r'AssertionError: 1 != 2',
    'test_rt02_replay_must_reject_two_unpaired_trials': r'AssertionError: ResearchIntegrityError not raised',
    'test_rt03_ancestor_symlink_must_not_redirect_run_root': r'AssertionError: ResearchIntegrityError not raised',
    'test_rt04_mutated_holdout_bank_must_halt_before_terminal_receipt': r'AssertionError: ResearchIntegrityError not raised',
    'test_rt05_interpreter_must_reject_unvalidated_operation': r'AssertionError: ResearchIntegrityError not raised',
    'test_rt06_same_object_thread_race_must_not_corrupt_journal': r'AssertionError: 1 != 0',
    'test_rt07_valid_prefix_rollback_must_not_repeat_holdout': r'AssertionError: 4 != 2',
    'test_rt08_staged_fifo_must_reject_without_hanging': r'AssertionError: True is not false : reader hung on attacker-supplied FIFO',
    'test_rt09_generic_type_params_must_be_rejected_by_parser': r'AssertionError: ResearchIntegrityError not raised',
    'test_rt10_no_gain_allocation_is_idempotent_on_resume': r'ace_loop\.engine\.ResearchIntegrityError: unknown allocated track',
    'test_rt11_rehashed_float_and_bool_evidence_must_be_rejected': r'AssertionError: ResearchIntegrityError not raised',
    'test_rt12_overlap_validation_holdout_must_fail_before_experiment': r'AssertionError: ResearchIntegrityError not raised',
    'test_rt13_corrupt_allocation_schema_must_raise_typed_integrity_error': r"TypeError: 'NoneType' object is not iterable",
}
TOTAL_TESTS = 28


def git_blob_sha(path: Path) -> str:
    content = path.read_bytes()
    return hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()


def verify() -> dict:
    source_root = Path(__file__).resolve().parents[1]
    actual = {path: git_blob_sha(source_root / path) for path in EXPECTED_SOURCE_BLOBS}
    errors = []
    if actual != EXPECTED_SOURCE_BLOBS:
        errors.append('SOURCE_BLOB_DRIFT: baseline changed; revalidate findings against new head')

    buffer = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromNames(SUITES)
    result = unittest.TextTestRunner(stream=buffer, verbosity=2).run(suite)
    outcomes = {}
    for test, traceback in result.expectedFailures:
        name = test.id().rsplit('.', 1)[-1]
        tail = traceback.rstrip().splitlines()[-1]
        if name in outcomes:
            errors.append('DUPLICATE_FAILURE_ID:' + name)
        outcomes[name] = tail
    if result.testsRun != TOTAL_TESTS:
        errors.append('TEST_COUNT_MISMATCH')
    if result.failures or result.errors or result.unexpectedSuccesses or result.skipped:
        errors.append('UNEXPECTED_TEST_OUTCOME')
    if set(outcomes) != set(KNOWN_OPEN_FAILURES):
        errors.append('EXPECTED_FAILURE_SET_CHANGED')
    for name, pattern in KNOWN_OPEN_FAILURES.items():
        if name in outcomes and re.fullmatch(pattern, outcomes[name]) is None:
            errors.append('FAILURE_SIGNATURE_CHANGED:' + name)
    report = {
        'schema': 'ace-redteam-strict-gate-v1',
        'baseline_pr27_head': '965640786cbf2f8adcd89eb1d980945f78c2da77',
        'python': sys.version.split()[0],
        'tests_run': result.testsRun,
        'positive_controls': result.testsRun - len(result.expectedFailures),
        'open_defect_signatures': outcomes,
        'failures': len(result.failures),
        'errors': len(result.errors),
        'unexpected_successes': len(result.unexpectedSuccesses),
        'skipped': len(result.skipped),
        'source_git_blob_sha1': actual,
        'gate': 'PASS_EXPECTED_FAILURES_VERIFIED' if not errors else 'FAIL',
        'gate_errors': errors,
    }
    return report


def main() -> int:
    receipt = verify()
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt['gate'] == 'PASS_EXPECTED_FAILURES_VERIFIED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
