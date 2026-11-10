"""Opt-in local sandbox diagnostic. Never a release or promotion gate."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

# Public synthetic fixture: this is not an independent scientific holdout.
BANK = (("", True), ("a", False), ("ab", True), ("bbb", False), ("aabb", True), ("aaaaa", False))


def evaluate(source: str) -> dict:
    if type(source) is not str or not 1 <= len(source.encode('utf-8')) <= 4096:
        raise ValueError('source must be UTF-8 text of 1 to 4096 bytes')
    bwrap, prlimit = shutil.which('bwrap'), shutil.which('prlimit')
    if not bwrap or not prlimit:
        raise RuntimeError('BLOCKED_ENVIRONMENT: bwrap and prlimit are required')
    worker = Path(__file__).resolve().parents[1] / 'ace_host_controller' / 'isolated_worker.py'
    if not worker.is_file() or not Path('/usr/bin/python3').is_file():
        raise RuntimeError('BLOCKED_ENVIRONMENT: sandbox runtime missing')
    cmd = [prlimit, '--cpu=2', '--as=268435456', '--fsize=1048576', '--nofile=32', '--',
           bwrap, '--die-with-parent', '--unshare-all', '--new-session', '--clearenv',
           '--setenv', 'PATH', '/usr/bin', '--ro-bind', '/usr', '/usr',
           '--ro-bind', '/lib', '/lib', '--ro-bind', '/lib64', '/lib64',
           '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
           '--ro-bind', str(worker), '/worker.py', '--chdir', '/tmp',
           '/usr/bin/python3', '-I', '/worker.py']
    identity = hashlib.sha256(source.encode('utf-8')).hexdigest()
    payload = {'candidate_id': identity, 'source_code': source,
               'inputs_by_task': {'parity': [word for word, _ in BANK]}}
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        try:
            proc = subprocess.run(cmd, input=json.dumps(payload).encode(), stdout=out, stderr=err,
                                  timeout=4, env={'PATH': '/usr/bin:/bin'}, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError('BLOCKED_ENVIRONMENT: sandbox execution failed or timed out') from exc
        if proc.returncode:
            # Includes sandbox startup, CPU limit, and worker failures. Fail closed.
            raise RuntimeError('BLOCKED_OR_REJECTED: sandbox or candidate failed')
        out.seek(0)
        try:
            data = json.loads(out.read(65537))
            pred = data['predictions_by_task']['parity']
            if data['candidate_id'] != identity or type(pred) is not list or len(pred) != len(BANK) or any(type(x) is not bool for x in pred):
                raise ValueError('invalid predictions')
        except (ValueError, KeyError, TypeError) as exc:
            raise RuntimeError('REJECTED: invalid worker output') from exc
    correct = sum(actual == expected for actual, (_, expected) in zip(pred, BANK))
    return {'schema': 'ace.code-diagnostic.v1', 'source_sha256': identity,
            'fixture_sha256': hashlib.sha256(json.dumps(BANK, separators=(',', ':')).encode()).hexdigest(),
            'correct': correct, 'total': len(BANK), 'baseline_correct': 3,
            'diagnostic_pass': correct == len(BANK), 'promotion_authorized': False,
            'scientific_decision': 'NOT_ASSESSED'}
