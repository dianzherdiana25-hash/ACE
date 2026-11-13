"""Recheck this path inventory using Git metadata only; never import ACE code.

Run from a checkout containing the pinned commits:
    python3 evidence/audit_20261113_legacy_prs/verify_inventory.py
An optional first argument selects an alternative JSON snapshot for review.
Live GitHub metadata and scientific/test outcomes are outside this verifier.
"""
import collections
import json
import os
from pathlib import Path
import subprocess
import sys


def git(*args):
    return subprocess.run(
        ['git', '--no-optional-locks', *args], check=False, capture_output=True,
        text=True, env={**os.environ, 'GIT_NO_LAZY_FETCH': '1'},
    )


def checked_git(*args):
    result = git(*args)
    if result.returncode:
        raise ValueError(f'git {args!r}: {result.stderr.strip()}')
    return result.stdout.strip()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def tree(commit):
    entries = {}
    for line in checked_git('ls-tree', '-r', '--full-tree', commit).splitlines():
        metadata, path = line.split('\t', 1)
        mode, kind, oid = metadata.split()
        entries[path] = dict(mode=mode, type=kind, oid=oid)
    return entries


def classify(path):
    p = Path(path)
    if path.startswith('evidence/'):
        return 'evidence'
    if path.startswith('.github/workflows/'):
        return 'workflow'
    if p.suffix == '.py':
        return ('python_test' if p.name.startswith('test_') or p.name.endswith('_test.py')
                else 'python_non_test')
    if p.suffix.lower() == '.md':
        return 'documentation'
    return 'design_data' if path.startswith('design/') else 'other'


def verify(snapshot):
    require(snapshot['schema'] == 'ace.audit.legacy_pr_paths.v1', 'schema')
    main = tree(snapshot['main_sha'])
    pulls = snapshot['pulls']
    require(len({p['number'] for p in pulls}) == len(pulls), 'duplicate PR')
    all_files, shared = [], collections.defaultdict(list)
    for p in pulls:
        label = f"PR {p['number']}"
        merge_base = checked_git('merge-base', p['base_sha'], p['head_sha'])
        require(merge_base == p['git_merge_base'], label + ': merge base')
        ancestor = git('merge-base', '--is-ancestor', p['head_sha'], snapshot['main_sha'])
        require(ancestor.returncode in (0, 1), label + ': ancestry command failed')
        require((ancestor.returncode == 0) == p['head_is_ancestor_of_main'], label + ': ancestry')
        actual = [line.split('\t') for line in checked_git(
            'diff', '--no-renames', '--name-status', merge_base, p['head_sha']).splitlines()]
        require(actual == [[r['change'], r['path']] for r in p['files']], label + ': diff')
        paths = [r['path'] for r in p['files']]
        require(sorted(paths) == sorted(p['api_filenames']), label + ': API path snapshot')
        require(p['git_api_changed_paths_equal'] is True, label + ': equality flag')
        require(len(paths) == p['file_count'], label + ': count')
        head = tree(p['head_sha'])
        for row in p['files']:
            path = row['path']
            require(row['category'] == classify(path), label + ': category ' + path)
            require(row['head_entry'] == head.get(path), label + ': head entry ' + path)
            require(row['main_entry'] == main.get(path), label + ': main entry ' + path)
            relation = ('absent_at_same_path' if path not in main else
                        'identical_tree_entry' if main[path] == head.get(path) else
                        'different_tree_entry')
            require(row['main_relation'] == relation, label + ': relation ' + path)
            shared[path].append(p['number'])
        counts = collections.Counter(r['category'] for r in p['files'])
        require(dict(counts) == {k: v for k, v in p['category_counts'].items() if v}, label + ': categories')
        require(dict(collections.Counter(r['main_relation'] for r in p['files'])) ==
                p['main_relation_counts'], label + ': relation counts')
        # This frozen inventory's selected PRs all change non-test Python.
        require(counts['python_non_test'] > 0, label + ': expected Python delta')
        expected_class = ('python_non_test_with_test_file_changes' if counts['python_test'] else
                          'python_non_test_without_test_file_changes')
        require(p['classification'] == expected_class, label + ': classification')
        all_files.extend(p['files'])
    actual_summary = dict(
        pr_count=len(pulls),
        all_open_draft=all(p['state'] == 'open' and p['draft'] is True for p in pulls),
        git_api_changed_paths_match_count=len(pulls),
        heads_ancestor_of_main_count=sum(p['head_is_ancestor_of_main'] for p in pulls),
        classification_counts=dict(collections.Counter(p['classification'] for p in pulls)),
        file_occurrences=len(all_files), unique_paths=len(shared),
        category_occurrence_counts=dict(collections.Counter(r['category'] for r in all_files)),
    )
    require(actual_summary == snapshot['summary'], 'summary')
    require({k: v for k, v in shared.items() if k.endswith('.py') and len(v) > 1} ==
            snapshot['shared_python_paths'], 'shared Python paths')
    return actual_summary


if __name__ == '__main__':
    try:
        path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('path_inventory.json')
        result = verify(json.loads(path.read_text()))
    except (KeyError, TypeError, ValueError, OSError) as exc:
        print(f'INVENTORY_MISMATCH: {exc}', file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps({'verification': 'PATH_INVENTORY_MATCH', 'summary': result}, sort_keys=True))
