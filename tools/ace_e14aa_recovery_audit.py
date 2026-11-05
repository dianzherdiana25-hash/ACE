"""Read-only, fail-closed E1.4aa interrupted-run inspector.

Not a resume runner. Never invokes an oracle, reruns a purchase, edits a journal,
or treats stored provider receipts as independently witnessed truth.

Run: PYTHONPATH=code:. python tools/ace_e14aa_recovery_audit.py --root WORK/e14aa-run
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

from e14.e14_integrated_graph import canonical_graph, graph_cost
from e14.e14_shared_budget import BudgetContractError, SharedLabelBudget

MAX_JSON_BYTES = 64 * 1024 * 1024


class RecoveryAuditError(RuntimeError):
    """Evidence cannot be trusted; never continue purchasing labels."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def read_json(path, *, compressed=False):
    if path.is_symlink() or not path.is_file():
        raise RecoveryAuditError(f'non-regular evidence file: {path}')
    if path.stat().st_size > MAX_JSON_BYTES:
        raise RecoveryAuditError(f'oversized evidence: {path}')
    try:
        if compressed:
            with gzip.open(path, 'rb') as stream:
                data = stream.read(MAX_JSON_BYTES + 1)
        else:
            data = path.read_bytes()
        if len(data) > MAX_JSON_BYTES:
            raise RecoveryAuditError(f'decompressed evidence too large: {path}')
        return json.loads(data)
    except (OSError, EOFError, UnicodeError, ValueError, TypeError) as exc:
        raise RecoveryAuditError(f'unreadable evidence: {path}') from exc


def _checked_receipts(snapshot):
    # Python makes True == 1 and 1.0 == 1; scientific evidence requires exact
    # numeric types even when an older ledger reconstructs equal snapshots.
    if (type(snapshot) is not dict or any(
            type(snapshot.get(key)) is not int
            for key in ('version', 'shared_cap', 'purchased', 'remaining'))):
        raise RecoveryAuditError('noninteger typed budget counter')
    try:
        book = SharedLabelBudget.from_snapshot(snapshot)
        data = book.snapshot()
        for row in data['receipts']:
            graph = row['query']
            if canonical_graph(graph) != graph:
                raise RecoveryAuditError('noncanonical receipt graph')
            if graph_cost(graph) != row['cost']:
                raise RecoveryAuditError('forged graph topology cost')
            label = row['label']
            if label is not None and (type(label) is not int or not 0 <= label <= 960):
                raise RecoveryAuditError('invalid graph oracle label')
        return data
    except (BudgetContractError, TypeError, KeyError, ValueError, OverflowError,
            RecursionError) as exc:
        raise RecoveryAuditError('invalid typed receipt or budget') from exc


def _sqlite_rows(path):
    if path.is_symlink() or not path.is_file():
        raise RecoveryAuditError(f'non-regular SQLite journal: {path}')
    # Explicit read-only URI. No DurableGraphBudget constructor: that creates DBs.
    try:
        with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True,
                             timeout=2) as connection:
            connection.execute('PRAGMA query_only=ON')
            rows = connection.execute('SELECT arm,revision,payload,digest FROM arm_budget ORDER BY arm').fetchall()
    except sqlite3.Error as exc:
        raise RecoveryAuditError(f'cannot read journal: {path}') from exc
    if len(rows) != 1:
        raise RecoveryAuditError(f'expected one arm per journal: {path}')
    arm, revision, payload, checksum = rows[0]
    if type(arm) is not str or not arm or type(revision) is not int or revision < 0:
        raise RecoveryAuditError('invalid journal identity/revision')
    if type(payload) is not str or type(checksum) is not str:
        raise RecoveryAuditError('invalid journal payload/checksum types')
    if hashlib.sha256(payload.encode('utf-8')).hexdigest() != checksum:
        raise RecoveryAuditError('journal SHA256 mismatch')
    try:
        record = json.loads(payload)
        if canonical(record).decode('utf-8') != payload:
            raise RecoveryAuditError('noncanonical stored journal JSON')
    except (ValueError, TypeError, UnicodeError, OverflowError, RecursionError) as exc:
        raise RecoveryAuditError('malformed journal payload') from exc
    return arm, revision, _checked_receipts(record)


def inspect(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise RecoveryAuditError('run root must be a real directory')
    journals_dir = root/'journals'
    if journals_dir.is_symlink():
        raise RecoveryAuditError('journal directory is a symlink')
    journals = {}
    if journals_dir.exists():
        for path in sorted(journals_dir.iterdir()):
            if path.is_symlink() or not path.is_file() or path.suffix != '.sqlite':
                raise RecoveryAuditError(f'unexpected journal directory entry: {path.name}')
            arm, revision, snapshot = _sqlite_rows(path)
            if arm in journals:
                raise RecoveryAuditError(f'duplicate journal arm: {arm}')
            # The fixed task creates these exact arm-relative filenames.
            if arm.startswith('aa:') and ':source:' in arm:
                source_id, pair = arm.split(':source:', 1)
                expected_name = f'source-{source_id}-{pair}.sqlite'
            elif arm.startswith('aa:'):
                expected_name = f'target-{arm}.sqlite'
            else:
                raise RecoveryAuditError(f'unexpected E1.4aa arm ID: {arm}')
            if path.name != expected_name:
                raise RecoveryAuditError(f'journal filename/arm mismatch: {path.name}')
            journals[arm] = {'revision': revision, 'snapshot': snapshot,
                             'pending': [r['id'] for r in snapshot['receipts']
                                         if r['status'] == 'pending']}

    checked_targets = 0
    target_dir = root/'snapshots'
    if target_dir.is_symlink():
        raise RecoveryAuditError('snapshot directory is a symlink')
    if target_dir.exists():
        for path in sorted(target_dir.iterdir()):
            if path.is_symlink() or path.suffix != '.json' or not path.is_file():
                raise RecoveryAuditError(f'unexpected snapshot file: {path}')
            if not path.name.startswith('target-'):
                raise RecoveryAuditError(f'unsupported snapshot identity: {path}')
            arm = path.stem.removeprefix('target-')
            if arm not in journals:
                raise RecoveryAuditError(f'snapshot without journal: {arm}')
            stored = read_json(path)
            if _checked_receipts(stored) != journals[arm]['snapshot']:
                raise RecoveryAuditError(f'snapshot and durable journal disagree: {arm}')
            checked_targets += 1

    checked_sources = 0
    source_dir = root/'sources'
    if source_dir.is_symlink():
        raise RecoveryAuditError('source directory is a symlink')
    if source_dir.exists():
        for path in sorted(source_dir.iterdir()):
            if path.is_symlink() or path.suffix != '.json' or not path.is_file():
                raise RecoveryAuditError(f'unexpected source file: {path}')
            doc = read_json(path)
            if type(doc) is not dict or path.stem != doc.get('id') or not isinstance(doc.get('journals'), list):
                raise RecoveryAuditError('malformed source evidence identity')
            for item in doc['journals']:
                pair_idx = item.get('pair_index') if type(item) is dict else None
                if type(pair_idx) is not int:
                    raise RecoveryAuditError('invalid source pair index')
                arm = f'{doc["id"]}:source:{pair_idx}'
                if arm not in journals:
                    raise RecoveryAuditError('source report without matching journal')
                if _checked_receipts(item['journal']) != journals[arm]['snapshot']:
                    raise RecoveryAuditError(f'source report/journal mismatch: {arm}')
            checked_sources += 1

    progress_path = root/'progress.json'
    progress = read_json(progress_path) if progress_path.exists() else None
    if progress is not None:
        if (type(progress) is not dict or set(progress) !=
                {'status', 'sources', 'arms', 'expected'} or
                progress.get('status') != 'RUNNING' or
                any(type(progress.get(k)) is not int or progress[k] < 0
                    for k in ('sources', 'arms', 'expected')) or
                progress['arms'] > progress['expected']):
            raise RecoveryAuditError('invalid typed progress checkpoint')
    report_path, summary_path = root/'report.json.gz', root/'summary.json'
    report = read_json(report_path, compressed=True) if report_path.exists() else None
    summary = read_json(summary_path) if summary_path.exists() else None
    if report is not None:
        if type(report) is not dict or type(report.get('sha256')) is not str:
            raise RecoveryAuditError('invalid completed report')
        raw = {k:v for k,v in report.items() if k != 'sha256'}
        if hashlib.sha256(canonical(raw)).hexdigest() != report['sha256']:
            raise RecoveryAuditError('completed report digest mismatch')
        if type(report.get('rows')) is not list or type(report.get('sources')) is not list:
            raise RecoveryAuditError('missing complete report row collections')
        if type(report.get('arm_count')) is not int or report['arm_count'] != len(report['rows']):
            raise RecoveryAuditError('report arm count differs from rows')
        if summary is not None:
            without_rows = {k:v for k,v in report.items() if k not in ('rows','sources')}
            if canonical(summary) != canonical(without_rows):
                raise RecoveryAuditError('summary differs from completed report')

    pending = {arm:state['pending'] for arm,state in journals.items()
               if state['pending']}
    bought = sum(s['snapshot']['purchased'] for s in journals.values())
    source_bought = sum(s['snapshot']['purchased'] for k,s in journals.items() if ':source:' in k)
    target_bought = bought - source_bought
    if report is not None and summary is not None and not pending:
        if (type(report.get('target_labels')) is not int or
                type(report.get('source_labels')) is not int or
                report['target_labels'] != target_bought or
                report['source_labels'] != source_bought or
                report.get('arm_count') != checked_targets or
                len(report['sources']) != checked_sources):
            raise RecoveryAuditError('completed report/journal/count mismatch')
        status = 'COMPLETE_CONSISTENT_NOT_ORACLE_VERIFIED'
    elif pending:
        status = 'BLOCKED_PENDING_NO_RETRY'
    elif journals or progress is not None or report is not None or summary is not None:
        status = 'INCOMPLETE_NO_AUTORETRY'
    else:
        status = 'EMPTY'
    return {'status': status, 'journals': len(journals),
            'source_labels': source_bought, 'target_labels': target_bought,
            'pending': pending, 'source_reports_checked': checked_sources,
            'target_snapshots_checked': checked_targets,
            'progress': progress, 'completed_report_present': report is not None,
            'summary_present': summary is not None,
            'resume_supported': False, 'oracle_called': False,
            'scientific_decision': 'NOT_ASSESSED'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = inspect(args.root)
    except RecoveryAuditError as exc:
        print(json.dumps({'status': 'BLOCKED_CORRUPT_OR_UNVERIFIABLE',
                          'reason': str(exc), 'resume_supported': False}, sort_keys=True))
        return 3
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] == 'COMPLETE_CONSISTENT_NOT_ORACLE_VERIFIED' else 2


if __name__ == '__main__':
    sys.exit(main())
