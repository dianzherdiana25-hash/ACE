"""Candidate-bound regression diagnostics; never authorizes promotion.

Only a fixed target and supervisor-selected tests are supported. Candidate code
and tests execute inside a read-only bubblewrap snapshot with no network.
"""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import re
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

TARGET = 'code/ace_self_dev/strategy_repair.py'
TEST_MODULES = ('ace_self_dev.test_stagnation_detector', 'ace_self_dev.test_anti_stagnation')
MAX_PATCH_BYTES = 16384
SANDBOX_PROFILE = {'cpu_seconds': 25, 'memory_bytes': 536870912,
                   'output_bytes': 1048576, 'file_descriptors': 64,
                   'wall_seconds': 35, 'network': 'unshared',
                   'snapshot': 'read-only', 'environment': 'cleared'}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_receipt(receipt: dict) -> bool:
    """Detect accidental or unsophisticated edits; checksum is not authentication."""
    if type(receipt) is not dict or type(receipt.get('receipt_sha256')) is not str:
        return False
    unsigned = dict(receipt)
    expected = unsigned.pop('receipt_sha256')
    try:
        actual = _sha(json.dumps(unsigned, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(expected, actual)


def _extract_snapshot(repo: Path, destination: Path, commit: str) -> None:
    archive = subprocess.run(['git', 'archive', '--format=tar', commit], cwd=repo,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             timeout=30, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:') as tf:
        # Do not allow repository-controlled links or unusual filesystem entries.
        members = tf.getmembers()
        if any(not (m.isdir() or m.isfile()) for m in members):
            raise ValueError('snapshot contains unsupported filesystem entry')
        tf.extractall(destination, members=members, filter='data')


def _run(snapshot: Path, bwrap: str, prlimit: str) -> dict:
    command = [prlimit, f"--cpu={SANDBOX_PROFILE['cpu_seconds']}",
               f"--as={SANDBOX_PROFILE['memory_bytes']}",
               f"--fsize={SANDBOX_PROFILE['output_bytes']}",
               f"--nofile={SANDBOX_PROFILE['file_descriptors']}", '--',
               bwrap, '--die-with-parent', '--unshare-all', '--new-session', '--clearenv',
               '--setenv', 'PATH', '/usr/bin', '--setenv', 'PYTHONPATH', '/repo/code',
               '--setenv', 'PYTHONDONTWRITEBYTECODE', '1', '--setenv', 'HOME', '/tmp',
               '--ro-bind', '/usr', '/usr', '--ro-bind', '/lib', '/lib',
               '--ro-bind', '/lib64', '/lib64', '--proc', '/proc', '--dev', '/dev',
               '--tmpfs', '/tmp', '--ro-bind', str(snapshot), '/repo', '--chdir', '/repo',
               '/usr/bin/python3', '-m', 'unittest', *TEST_MODULES, '-q']
    with tempfile.TemporaryFile() as out:
        try:
            proc = subprocess.run(command, stdout=out, stderr=subprocess.STDOUT,
                                  timeout=SANDBOX_PROFILE['wall_seconds'], env={'PATH': '/usr/bin:/bin'}, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {'passed': False, 'status': 'BLOCKED_OR_TIMEOUT', 'error': type(exc).__name__}
        out.seek(0)
        data = out.read(SANDBOX_PROFILE['output_bytes'] + 1)
        if len(data) > SANDBOX_PROFILE['output_bytes']:
            return {'passed': False, 'status': 'OUTPUT_LIMIT'}
    # Exit zero alone does not establish that unittest completed: candidate code
    # can call os._exit(0) during import. This is a diagnostic integrity check,
    # not a secure channel: candidate code can still forge in-process output.
    summary = re.search(rb'(?m)^Ran ([1-9][0-9]*) tests? in [0-9.]+s\r?$', data)
    complete = bool(summary and re.search(rb'(?m)^OK\r?$', data))
    passed = proc.returncode == 0 and complete
    return {'passed': passed, 'status': 'PASS' if passed else 'FAIL_OR_BLOCKED',
            'test_count': int(summary.group(1)) if summary else 0,
            'exit_code': proc.returncode, 'output_sha256': _sha(data), 'output_bytes': len(data),
            'output_excerpt': data[-2000:].decode('utf-8', 'replace')}


def evaluate_patch(repo: str | Path, target: str, snippet: str) -> dict:
    """Compare baseline and append-only candidate at committed HEAD; no promotion."""
    if target != TARGET:
        raise ValueError('target is not in the fixed diagnostic allowlist')
    if type(snippet) is not str or not 1 <= len(snippet.encode('utf-8')) <= MAX_PATCH_BYTES:
        raise ValueError('invalid patch size')
    bwrap, prlimit = shutil.which('bwrap'), shutil.which('prlimit')
    if not bwrap or not prlimit:
        raise RuntimeError('BLOCKED_ENVIRONMENT: bwrap and prlimit are required')
    repo = Path(repo).resolve()
    commit = subprocess.check_output(['git', 'rev-parse', '--verify', 'HEAD^{commit}'], cwd=repo, text=True).strip()
    with tempfile.TemporaryDirectory(prefix='ace-patch-diag-') as tmp:
        base, candidate = Path(tmp) / 'base', Path(tmp) / 'candidate'
        base.mkdir(); _extract_snapshot(repo, base, commit)
        shutil.copytree(base, candidate, symlinks=False)
        base_file, candidate_file = base / TARGET, candidate / TARGET
        if not base_file.is_file() or base_file.is_symlink() or candidate_file.is_symlink():
            raise ValueError('target is not a regular file in snapshot')
        original = base_file.read_bytes()
        test_hashes = {}
        for module in TEST_MODULES:
            relpath = 'code/' + module.replace('.', '/') + '.py'
            source = base / relpath
            if not source.is_file() or source.is_symlink():
                raise ValueError('test module is not a regular file in snapshot')
            test_hashes[relpath] = _sha(source.read_bytes())
        patched = original + b'\n' + snippet.encode('utf-8')
        candidate_file.write_bytes(patched)
        baseline = _run(base, bwrap, prlimit)
        # Do not execute a candidate when baseline or containment setup failed.
        result = _run(candidate, bwrap, prlimit) if baseline['passed'] else {'passed': False, 'status': 'NOT_RUN'}
        if result.get('passed') and baseline['test_count'] != result['test_count']:
            result = {**result, 'passed': False, 'status': 'TEST_COUNT_MISMATCH'}
        elif result.get('passed'):
            # Candidate and tests share an interpreter: candidate code can forge
            # unittest output and terminate early. Never promote or mark passed
            # from that self-reported output, even when the summary looks valid.
            result = {**result, 'reported_test_success': True, 'passed': False,
                      'status': 'INCONCLUSIVE', 'reason': 'UNTRUSTED_IN_PROCESS_TEST_RESULT'}
    receipt = {'schema': 'ace.patch-diagnostic.v1', 'base_commit': commit, 'target': target,
               'base_file_sha256': _sha(original), 'patch_sha256': _sha(snippet.encode('utf-8')),
               'candidate_file_sha256': _sha(patched), 'test_modules': list(TEST_MODULES),
               'test_file_sha256': test_hashes, 'sandbox_profile': dict(SANDBOX_PROFILE),
               'baseline': baseline, 'candidate': result, 'promotion_authorized': False,
               'scientific_decision': 'NOT_ASSESSED'}
    receipt['receipt_sha256'] = _sha(json.dumps(receipt, sort_keys=True, separators=(',', ':')).encode())
    return receipt
