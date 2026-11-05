"""Read-only E1.4aa prescore byte-lock verifier; NO scoring and NO CI claim.

Fails closed on path traversal, symlinks, aliases, missing files or hash drift.
A matching self-authored lock is not an independent scientific attestation.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import sys
from pathlib import Path, PurePosixPath

HEX_SHA256 = re.compile(r'[0-9a-f]{64}\Z')
MAX_SOURCE_BYTES = 10 * 1024 * 1024


class PrescoreGateError(RuntimeError):
    pass


def _safe_file(root: Path, name: str):
    if type(name) is not str or not name or '\\' in name or '\x00' in name:
        raise PrescoreGateError('invalid locked relative path')
    posix = PurePosixPath(name)
    if (posix.is_absolute() or '..' in posix.parts or '.' in name.split('/') or
            posix.as_posix() != name):
        raise PrescoreGateError('unsafe locked path')
    target = root
    for component in posix.parts:
        target = target / component
        if target.is_symlink():
            raise PrescoreGateError('symlink in locked path')
    if not target.is_file():
        raise PrescoreGateError('missing locked source file')
    if target.stat().st_size > MAX_SOURCE_BYTES:
        raise PrescoreGateError('oversized locked source file')
    return target


def verify(repo_root, lock_path):
    root = Path(repo_root)
    if root.is_symlink() or not root.is_dir():
        raise PrescoreGateError('invalid repository root')
    lock_file = Path(lock_path)
    if lock_file.is_symlink() or not lock_file.is_file():
        raise PrescoreGateError('untrusted prescore lock file')
    if lock_file.stat().st_size > MAX_SOURCE_BYTES:
        raise PrescoreGateError('oversized lock')
    try:
        lock = json.loads(lock_file.read_bytes())
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise PrescoreGateError('unreadable prescore lock') from exc
    if (type(lock) is not dict or lock.get('status') != 'PRESCORE_LOCK' or
            type(lock.get('version')) is not int or lock['version'] != 1 or
            type(lock.get('base_sha')) is not str or not re.fullmatch(r'[a-f0-9]{40}',lock['base_sha']) or
            type(lock.get('files')) is not dict or not lock['files'] or len(lock['files']) > 64):
        raise PrescoreGateError('invalid lock structure')
    checks = []
    for name, expected in sorted(lock['files'].items()):
        if type(expected) is not str or not HEX_SHA256.fullmatch(expected):
            raise PrescoreGateError('invalid expected source SHA256')
        path = _safe_file(root, name)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if not hmac.compare_digest(actual, expected):
            raise PrescoreGateError('source SHA256 mismatch: ' + name)
        checks.append(name)
    return {'status': 'PRESCORE_LOCAL_HASHES_MATCH', 'files_checked': len(checks),
            'base_sha': lock['base_sha'], 'verified_paths': checks,
            'scientific_decision': 'NOT_ASSESSED', 'scoring_performed': False,
            'independent_custody': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--lock', type=Path, required=True)
    a = p.parse_args()
    try:
        r = verify(a.repo, a.lock)
    except PrescoreGateError as exc:
        print(json.dumps({'status': 'BLOCKED_PRESCORE_LOCK', 'reason': str(exc)}))
        return 3
    print(json.dumps(r, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
