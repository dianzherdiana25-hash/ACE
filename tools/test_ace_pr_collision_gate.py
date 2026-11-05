"""Adversarial stdlib tests for ACE read-only PR integration preflight."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from tools.ace_pr_collision_gate import AuditError, audit, canonical, live_snapshot, main
except ModuleNotFoundError:
    from ace_pr_collision_gate import AuditError, audit, canonical, live_snapshot, main

REPO = 'dianzherdiana25-hash/ACE'
SHA = 'a' * 40


def pr(n, base, head, files):
    return dict(number=n, base=base, head=head, head_sha=SHA, files=files, title=f'PR{n}')


def snapshot(*records):
    return dict(repository=REPO, pull_requests=list(records))


class CollisionGateTests(unittest.TestCase):
    def test_sibling_source_overlap_blocks(self):
        r = audit(snapshot(pr(26, 'research/e15', 'research/e16', ['code/ace_loop/source_evolution.py']),
                           pr(27, 'research/e15', 'research/e15-source', ['code/ace_loop/source_evolution.py'])))
        self.assertEqual('BLOCK_INTEGRATION', r['decision'])
        self.assertEqual([26, 27], r['overlaps'][0]['prs'])
        self.assertEqual(1, r['blocking_overlap_count'])

    def test_stacked_ancestry_reuse_does_not_block(self):
        r = audit(snapshot(pr(24, 'research/e14aa', 'research/recovery', ['x']),
                           pr(25, 'research/recovery', 'research/e15', ['x']),
                           pr(26, 'research/e15', 'research/e16', ['x'])))
        self.assertEqual('NO_PATH_OVERLAP', r['decision'])
        self.assertEqual(2, len(r['dependencies']))

    def test_cross_stack_overlap_requires_review(self):
        r = audit(snapshot(pr(10, 'main', 'a', ['x']), pr(11, 'other', 'b', ['x'])))
        self.assertEqual('MANUAL_REVIEW_REQUIRED', r['decision'])
        self.assertEqual('REVIEW_CROSS_STACK_OVERLAP', r['overlaps'][0]['severity'])

    def test_disjoint_siblings_safe(self):
        r = audit(snapshot(pr(10, 'main', 'a', ['x']), pr(11, 'main', 'b', ['y'])))
        self.assertEqual('NO_PATH_OVERLAP', r['decision'])

    def test_unstable_input_order_has_same_receipt(self):
        a = pr(10, 'main', 'a', ['x', 'z'])
        b = pr(11, 'main', 'b', ['y', 'x'])
        x, y = audit(snapshot(a, b)), audit(snapshot(b, {**a, 'files': ['z', 'x']}))
        self.assertEqual(canonical(x), canonical(y))

    def test_empty_snapshot_valid_no_false_completeness_claim(self):
        self.assertEqual(0, audit(snapshot())['open_pr_count'])

    def test_duplicate_head_ref_rejected(self):
        with self.assertRaises(AuditError):
            audit(snapshot(pr(1, 'main', 'a', []), pr(2, 'main', 'a', [])))

    def test_duplicate_number_rejected(self):
        with self.assertRaises(AuditError):
            audit(snapshot(pr(1, 'main', 'a', []), pr(1, 'main', 'b', [])))

    def test_missing_file_list_rejected(self):
        record = pr(1, 'main', 'a', [])
        del record['files']
        with self.assertRaises(AuditError):
            audit(snapshot(record))

    def test_invalid_shas_rejected(self):
        record = pr(1, 'main', 'a', [])
        record['head_sha'] = 'short'
        with self.assertRaises(AuditError):
            audit(snapshot(record))

    def test_repo_and_file_path_validation(self):
        with self.assertRaises(AuditError):
            audit({'repository': 'owner/repo/extra', 'pull_requests': []})
        with self.assertRaises(AuditError):
            audit(snapshot(pr(1, 'main', 'a', ['../ESCAPE'])))

    def test_cyclic_dependency_rejected(self):
        with self.assertRaises(AuditError):
            audit(snapshot(pr(1, 'b', 'a', []), pr(2, 'a', 'b', [])))

    def test_github_fetch_pagination_with_mock_http(self):
        calls = []
        class Response:
            def __init__(self, item): self.item = item
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, n=-1): return json.dumps(self.item).encode()
        def opener(request, timeout):
            calls.append((request.full_url, request.get_method()))
            if '/pulls?' in request.full_url:
                return Response([{'number': 1, 'title': 'x',
                                  'head': {'ref': 'b', 'sha': SHA}, 'base': {'ref': 'main'}}])
            if '/pulls/1/files?' in request.full_url:
                return Response([{'filename': 'code/test.py'}])
            raise AssertionError(request.full_url)
        r = live_snapshot(REPO, 'synthetic-test-token', opener)
        self.assertEqual(['code/test.py'], r['pull_requests'][0]['files'])
        self.assertEqual(['GET', 'GET'], [method for _, method in calls])
        self.assertNotIn('synthetic-test-token', ''.join(url for url, _ in calls))

    def test_github_malformed_response_fails_closed(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, n=-1): return b'{"message":"rate limited"}'
        with self.assertRaises(AuditError):
            live_snapshot(REPO, '', lambda *a, **k: Response())

    def test_cli_offline_exit_two_without_mutation(self):
        s = snapshot(pr(26, 'base', 'a', ['x']), pr(27, 'base', 'b', ['x']))
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'data.json'
            p.write_text(json.dumps(s))
            with patch('sys.stdout', new_callable=io.StringIO) as stdout:
                self.assertEqual(2, main(['--repo', REPO, '--snapshot', str(p)]))
                self.assertEqual('BLOCK_INTEGRATION', json.loads(stdout.getvalue())['decision'])
            self.assertEqual(s, json.loads(p.read_text()))

    def test_cli_repo_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'data.json'
            p.write_text(json.dumps(snapshot()))
            with patch('sys.stderr', new_callable=io.StringIO):
                self.assertEqual(1, main(['--repo', 'other/repo', '--snapshot', str(p)]))


if __name__ == '__main__':
    unittest.main()
