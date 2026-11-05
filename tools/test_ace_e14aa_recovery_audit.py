"""Unit tests: recovery inspection never calls an oracle or edits a journal."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from e14.e14_integrated_graph import DurableGraphBudget, purchase
from e14.e14u_primitive import PAIR_SPACE, graph_from_routes
from tools.ace_e14aa_recovery_audit import inspect, RecoveryAuditError


class E14AARecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.joinpath('journals').mkdir()
        self.arm = 'aa:000:source:0'
        self.db = self.root/'journals'/'source-aa:000-0.sqlite'
        self.budget = DurableGraphBudget(self.db, self.arm)
        self.graph = graph_from_routes(PAIR_SPACE[0], [3, 4])

    def buy(self):
        purchase(self.budget, 'qualification', self.graph, lambda _: 11)

    def test_empty_root_is_not_a_fake_pass(self):
        self.assertEqual(inspect(self.root)['status'], 'INCOMPLETE_NO_AUTORETRY')

    def test_settled_journal_is_safe_to_inspect_not_resume(self):
        self.buy()
        before = self.db.read_bytes()
        report = inspect(self.root)
        self.assertEqual(report['status'], 'INCOMPLETE_NO_AUTORETRY')
        self.assertEqual(report['source_labels'], 1)
        self.assertFalse(report['resume_supported'])
        self.assertFalse(report['oracle_called'])
        self.assertEqual(self.db.read_bytes(), before)

    def test_pending_reservation_blocks_automatic_retry(self):
        self.budget.reserve('qualification', self.graph)
        report = inspect(self.root)
        self.assertEqual(report['status'], 'BLOCKED_PENDING_NO_RETRY')
        self.assertEqual(report['pending'], {self.arm: ['q0001']})

    def test_modified_payload_without_valid_digest_fails(self):
        self.buy()
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE arm_budget SET payload=replace(payload,'settled','pending')")
        with self.assertRaises(RecoveryAuditError):
            inspect(self.root)

    def test_forged_cost_with_recomputed_digest_fails(self):
        self.buy()
        with sqlite3.connect(self.db) as db:
            (payload,) = db.execute('SELECT payload FROM arm_budget').fetchone()
            record = json.loads(payload)
            record['receipts'][0]['cost']['events'] += 1
            record['query_cost_totals']['events'] += 1
            changed = json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
            checksum = hashlib.sha256(changed.encode()).hexdigest()
            db.execute('UPDATE arm_budget SET payload=?,digest=?', (changed, checksum))
        with self.assertRaises(RecoveryAuditError):
            inspect(self.root)

    def test_symlinked_snapshot_directory_rejected(self):
        self.buy()
        self.root.joinpath('snapshots').symlink_to(self.root/'journals', target_is_directory=True)
        with self.assertRaises(RecoveryAuditError):
            inspect(self.root)

    def test_wrong_target_snapshot_fails(self):
        self.buy()
        snapshots = self.root/'snapshots'
        snapshots.mkdir()
        (snapshots/'target-aa:999:18:stable:online-random.json').write_text('{}')
        with self.assertRaises(RecoveryAuditError):
            inspect(self.root)

    def test_corrupted_source_report_fails(self):
        self.buy()
        sources = self.root/'sources'
        sources.mkdir()
        (sources/'aa:000.json').write_text(json.dumps({'id': 'aa:000', 'journals': [
            {'pair_index': 0, 'journal': {}}]}))
        with self.assertRaises(RecoveryAuditError):
            inspect(self.root)

    def test_report_without_digest_fails(self):
        self.buy()
        import gzip
        with gzip.open(self.root/'report.json.gz', 'wb') as f:
            f.write(json.dumps({'status': 'COMPLETE'}).encode())
        with self.assertRaises(RecoveryAuditError):
            inspect(self.root)

    def test_wrong_arm_filename_rejected(self):
        self.buy()
        self.db.rename(self.root/'journals'/'wrong.sqlite')
        with self.assertRaises(RecoveryAuditError):
            inspect(self.root)


if __name__ == '__main__':
    unittest.main()
