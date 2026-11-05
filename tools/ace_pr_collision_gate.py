#!/usr/bin/env python3
"""Read-only ACE pull-request integration gate.

Never merges, fetches source code, or makes a mutating GitHub request. Its only
hard block is overlapping changed paths between *sibling* PRs with an identical
base ref; other independent overlaps require review. Transitive stacked PRs
are expected to reuse paths and are not reported as collisions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = 'https://api.github.com'
REPO_RE = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
MAX_PAGES = 30


class AuditError(Exception):
    """Malformed or incomplete data: fail closed, no verdict."""


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def _require_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise AuditError(f'invalid {field}')
    return value


def validate_snapshot(snapshot: object) -> dict:
    if not isinstance(snapshot, dict):
        raise AuditError('snapshot must be a JSON object')
    repo = _require_string(snapshot.get('repository'), 'repository')
    if not REPO_RE.fullmatch(repo):
        raise AuditError('repository must be owner/name')
    prs = snapshot.get('pull_requests')
    if not isinstance(prs, list):
        raise AuditError('pull_requests must be a list (not partial/absent)')
    result = []
    numbers, heads = set(), set()
    for p in prs:
        if not isinstance(p, dict):
            raise AuditError('PR record is not an object')
        number = p.get('number')
        if type(number) is not int or number < 1 or number in numbers:
            raise AuditError('duplicate or invalid PR number')
        numbers.add(number)
        head = _require_string(p.get('head'), f'PR #{number} head')
        base = _require_string(p.get('base'), f'PR #{number} base')
        head_sha = _require_string(p.get('head_sha'), f'PR #{number} SHA')
        if not re.fullmatch(r'[a-fA-F0-9]{40}', head_sha):
            raise AuditError(f'PR #{number} invalid HEAD SHA')
        if head in heads:
            raise AuditError(f'duplicate PR head ref: {head}')
        if head == base:
            raise AuditError(f'PR #{number} has self-referential base')
        heads.add(head)
        paths = p.get('files')
        if not isinstance(paths, list):
            raise AuditError(f'PR #{number} missing complete files list')
        normalized_paths = set()
        for file in paths:
            file = _require_string(file, f'PR #{number} file')
            if file.startswith('/') or '\\' in file or any(part in ('', '.', '..') for part in file.split('/')):
                raise AuditError(f'PR #{number} unsafe file path')
            if file in normalized_paths:
                raise AuditError(f'PR #{number} duplicate path')
            normalized_paths.add(file)
        result.append(dict(number=number, title=str(p.get('title', '')),
                           head=head, base=base, head_sha=head_sha,
                           files=sorted(normalized_paths)))
    result.sort(key=lambda p: p['number'])
    return {'repository': repo, 'pull_requests': result}


def audit(snapshot: object) -> dict:
    snapshot = validate_snapshot(snapshot)
    prs = snapshot['pull_requests']
    by_head = {p['head']: p for p in prs}
    parents = {p['number']: by_head[p['base']]['number']
               for p in prs if p['base'] in by_head}

    def is_ancestor(a: int, b: int) -> bool:
        seen = set()
        while b in parents:
            b = parents[b]
            if b == a:
                return True
            if b in seen:
                raise AuditError('cyclic PR dependency graph')
            seen.add(b)
        return False

    for p in prs:
        cursor = p['number']
        seen = {cursor}
        while cursor in parents:
            cursor = parents[cursor]
            if cursor in seen:
                raise AuditError('cyclic PR dependency graph')
            seen.add(cursor)
    overlaps = []
    for i, a in enumerate(prs):
        for b in prs[i + 1:]:
            if is_ancestor(a['number'], b['number']) or is_ancestor(b['number'], a['number']):
                continue
            shared = sorted(set(a['files']) & set(b['files']))
            if not shared:
                continue
            severity = 'BLOCK_SIBLING_OVERLAP' if a['base'] == b['base'] else 'REVIEW_CROSS_STACK_OVERLAP'
            overlaps.append({'prs': [a['number'], b['number']], 'severity': severity,
                             'base_refs': [a['base'], b['base']], 'shared_paths': shared})
    blocked = any(x['severity'] == 'BLOCK_SIBLING_OVERLAP' for x in overlaps)
    review = bool(overlaps)
    evidence_digest = hashlib.sha256(canonical(snapshot)).hexdigest()
    return {'schema_version': 1, 'repository': snapshot['repository'],
            'snapshot_sha256': evidence_digest, 'open_pr_count': len(prs),
            'dependencies': [{'pr': n, 'depends_on_pr': parents[n]} for n in sorted(parents)],
            'overlaps': overlaps, 'blocking_overlap_count': sum(x['severity'] == 'BLOCK_SIBLING_OVERLAP' for x in overlaps),
            'review_overlap_count': sum(x['severity'] == 'REVIEW_CROSS_STACK_OVERLAP' for x in overlaps),
            'decision': 'BLOCK_INTEGRATION' if blocked else ('MANUAL_REVIEW_REQUIRED' if review else 'NO_PATH_OVERLAP'),
            'disclaimer': 'Path-level preflight only; no semantic conflict, SHA ancestry, CI or mergeability verification.'}


def get_json(url: str, token: str, opener=urllib.request.urlopen) -> object:
    if not url.startswith(API + '/repos/'):
        raise AuditError('refusing non-GitHub repository API URL')
    req = urllib.request.Request(url, headers={
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'ACE-pr-collision-gate/1',
        **({'Authorization': 'Bearer ' + token} if token else {}),
    }, method='GET')
    try:
        with opener(req, timeout=20) as response:
            data = response.read(10 * 1024 * 1024 + 1)
            if len(data) > 10 * 1024 * 1024:
                raise AuditError('GitHub response too large')
            return json.loads(data)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise AuditError(f'GitHub request or JSON failed: {type(exc).__name__}') from exc


def all_pages(repo: str, suffix: str, token: str, opener=urllib.request.urlopen) -> list:
    records = []
    for page in range(1, MAX_PAGES + 1):
        url = f'{API}/repos/{repo}/{suffix}?state=open&per_page=100&page={page}' if suffix == 'pulls' else \
              f'{API}/repos/{repo}/{suffix}?per_page=100&page={page}'
        batch = get_json(url, token, opener)
        if not isinstance(batch, list):
            raise AuditError('GitHub paginated endpoint returned non-list')
        if len(batch) > 100:
            raise AuditError('GitHub page exceeded 100 records')
        records.extend(batch)
        if len(batch) < 100:
            return records
    raise AuditError('pagination limit reached; refuse incomplete snapshot')


def live_snapshot(repo: str, token: str, opener=urllib.request.urlopen) -> dict:
    if not REPO_RE.fullmatch(repo):
        raise AuditError('repository must be owner/name')
    pulls = all_pages(repo, 'pulls', token, opener)
    records = []
    for p in pulls:
        try:
            n = p['number']
            files = all_pages(repo, f'pulls/{n}/files', token, opener)
            names = [f['filename'] for f in files]
            records.append({'number': n, 'title': p.get('title', ''),
                            'head': p['head']['ref'], 'head_sha': p['head']['sha'],
                            'base': p['base']['ref'], 'files': names})
        except (TypeError, KeyError) as exc:
            raise AuditError('incomplete GitHub pull request response') from exc
    # A multi-page read is not atomic: concurrent agents can change HEAD, base,
    # open/close PRs, or add a PR while we are reading its changed-file pages.
    # A second read prevents issuing an apparently safe stale-snapshot verdict.
    # It cannot guarantee future stability after this command returns.
    refreshed = all_pages(repo, 'pulls', token, opener)

    def identity(pulls):
        result = {}
        for p in pulls:
            try:
                number = p['number']
                value = (p['head']['ref'], p['head']['sha'], p['base']['ref'])
                if type(number) is not int or number in result:
                    raise AuditError('invalid/duplicate GitHub PR identity')
                result[number] = value
            except (TypeError, KeyError) as exc:
                raise AuditError('incomplete GitHub PR identity') from exc
        return result

    if identity(pulls) != identity(refreshed):
        raise AuditError('GitHub PR set, branch or HEAD changed during snapshot; retry from scratch')
    return validate_snapshot({'repository': repo, 'pull_requests': records})



RACE_ERROR = 'GitHub PR set, branch or HEAD changed during snapshot; retry from scratch'


def stable_live_snapshot(repo: str, token: str, opener=urllib.request.urlopen,
                         max_attempts: int = 3) -> dict:
    """Retry a TOCTOU failure only, always starting a *new* entire snapshot.

    No partial changed-file pages or stale snapshots are reused. Other GitHub
    failures are never retried here. Exhaustion raises AuditError, never PASS.
    """
    if type(max_attempts) is not int or not 1 <= max_attempts <= 3:
        raise AuditError('max_attempts must be an integer between 1 and 3')
    for _ in range(max_attempts):
        try:
            return live_snapshot(repo, token, opener)
        except AuditError as exc:
            if str(exc) != RACE_ERROR:
                raise
    raise AuditError(f'GitHub PR set remained unstable through {max_attempts} full captures; HALT')



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, help='owner/name; validated against offline snapshot if supplied')
    parser.add_argument('--snapshot', type=Path, help='existing offline JSON snapshot (no GitHub access)')
    parser.add_argument('--require-pr', type=int, action='append', default=[], metavar='NUMBER',
                        help='fail closed when this PR number is missing; repeatable')
    args = parser.parse_args(argv)
    try:
        if args.snapshot:
            snapshot = json.loads(args.snapshot.read_text(encoding='utf-8'))
            if snapshot.get('repository') != args.repo:
                raise AuditError('--repo differs from snapshot.repository')
        else:
            snapshot = stable_live_snapshot(args.repo, os.getenv('GITHUB_TOKEN', ''))
        report = audit(snapshot)
        if any(type(n) is not int or n < 1 for n in args.require_pr):
            raise AuditError('--require-pr values must be positive integers')
        observed = {p['number'] for p in snapshot['pull_requests']}
        missing = sorted(set(args.require_pr) - observed)
        if missing:
            raise AuditError(f'required PRs absent from snapshot: {missing}')
        report['capture_method'] = ('OFFLINE_SNAPSHOT_NOT_PROVEN_COMPLETE' if args.snapshot
                                    else 'LIVE_DOUBLE_READ_STABLE_AT_CAPTURE')
        print(json.dumps(report, sort_keys=True, indent=2))
        return 2 if report['decision'] == 'BLOCK_INTEGRATION' else 0
    except (AuditError, OSError, ValueError, AttributeError) as exc:
        print(json.dumps({'decision': 'UNKNOWN_INCOMPLETE_EVIDENCE', 'error': str(exc)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
