"""Adversarial summary corruption tests against receipt-derived facts."""
from copy import deepcopy
import hashlib
import unittest
from .benchmark import bank
from .journal import events
from .model import Grammar, Limits, IntegrityError, canonical, digest
from .verify_results import _verify_record


class SummaryBindingTests(unittest.TestCase):
    def setUp(self):
        self.rows = []
        previous = '0'*64
        for i, (kind, payload) in enumerate(events(Grammar(), Limits(max_candidates=5),
                                                   *bank('difference'), 'beam')):
            row = {'seq':i, 'prev':previous, 'kind':kind, 'payload':payload}
            row['sha256'] = digest(row)
            previous = row['sha256']
            self.rows.append(row)
        self.content = b''.join(canonical(r)+b'\n' for r in self.rows)
        self.record = {'budget':'tight', 'task':'difference', 'mode':'beam',
                       'result':deepcopy(self.rows[-1]['payload']),
                       'search':deepcopy(next(r['payload'] for r in self.rows if r['kind']=='search_stop')),
                       'frozen_candidate':deepcopy(next(r['payload'] for r in self.rows if r['kind']=='freeze')),
                       'chain_head':previous, 'journal_sha256':hashlib.sha256(self.content).hexdigest(),
                       'timing':{'cpu_seconds':0.1, 'wall_seconds':0.2}}

    def check(self, record):
        _verify_record(record,self.rows,self.content)

    def test_genuine_summary_passes(self):
        self.check(self.record)

    def test_forged_search_cost_rejected(self):
        self.record['search']['search_work'] += 999
        with self.assertRaisesRegex(IntegrityError,'search'):
            self.check(self.record)

    def test_forged_frozen_ast_and_decision_rejected(self):
        for field, value in (('ast',['const',20,[]]), ('id','a'*64), ('decisions',[])):
            record = deepcopy(self.record)
            record['frozen_candidate'][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(IntegrityError,'frozen_candidate'):
                self.check(record)

    def test_bool_integer_alias_rejected(self):
        # This substitution passed the old nested-dict equality check.
        self.assertEqual(False, 0)
        self.record['result']['candidate_promoted'] = 0
        with self.assertRaisesRegex(IntegrityError,'result'):
            self.check(self.record)

    def test_changed_final_result_rejected(self):
        self.record['result']['total_work'] += 1
        with self.assertRaisesRegex(IntegrityError,'result'):
            self.check(self.record)

    def test_changed_chain_or_content_digest_rejected(self):
        for field in ('chain_head','journal_sha256'):
            record = deepcopy(self.record)
            record[field] = 'f'*64
            with self.subTest(field=field), self.assertRaisesRegex(IntegrityError,field):
                self.check(record)

    def test_missing_or_extra_summary_field_rejected(self):
        missing = deepcopy(self.record)
        del missing['frozen_candidate']
        extra = dict(self.record,unverified_claim='passed')
        for record in (missing,extra):
            with self.assertRaisesRegex(IntegrityError,'schema'):
                self.check(record)

    def test_invalid_timing_rejected(self):
        for timing in ({}, {'cpu_seconds':0.1,'wall_seconds':0.2,'extra':1},
                       {'cpu_seconds':True,'wall_seconds':1.0},
                       {'cpu_seconds':-0.1,'wall_seconds':1.0},
                       {'cpu_seconds':float('nan'),'wall_seconds':1.0},
                       {'cpu_seconds':float('inf'),'wall_seconds':1.0},
                       {'cpu_seconds':10**1000,'wall_seconds':1.0}):
            record = deepcopy(self.record)
            record['timing'] = timing
            with self.subTest(timing=str(timing)[:60]), self.assertRaises(IntegrityError):
                self.check(record)

    def test_timing_is_structural_not_historical_attestation(self):
        self.record['timing'] = {'cpu_seconds':2.5,'wall_seconds':3.0}
        self.check(self.record)

    def test_no_candidate_has_no_frozen_ast(self):
        rows = []
        for i,(kind,payload) in enumerate(events(Grammar(),Limits(max_depth=0),*bank('difference'),'fixed')):
            row = {'seq':i,'prev':'0'*64 if not rows else rows[-1]['sha256'], 'kind':kind,'payload':payload}
            row['sha256'] = digest(row)
            rows.append(row)
        content = b''.join(canonical(r)+b'\n' for r in rows)
        record = dict(self.record, result=rows[-1]['payload'], frozen_candidate=None,
                      search=next(r['payload'] for r in rows if r['kind']=='search_stop'),
                      chain_head=rows[-1]['sha256'],journal_sha256=hashlib.sha256(content).hexdigest())
        _verify_record(record,rows,content)
        record['frozen_candidate'] = self.record['frozen_candidate']
        with self.assertRaisesRegex(IntegrityError,'frozen_candidate'):
            _verify_record(record,rows,content)


if __name__ == '__main__':
    unittest.main()
