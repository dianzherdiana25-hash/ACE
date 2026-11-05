"""External oracle transaction contract tests using a synthetic trusted backend."""
from __future__ import annotations
from tempfile import TemporaryDirectory
from pathlib import Path
import json
import sqlite3
import unittest
from unittest.mock import Mock

from .receipt_escrow import OracleEscrow,EscrowError,UncertainDispatch
from e14.e14y_study import question
from e14.e14u_primitive import PAIR_SPACE


class EscrowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'receipt.sqlite'
        self.store=OracleEscrow(self.path)
        self.pair=PAIR_SPACE[18]

    def q(self,lo=4,hi=4):return question(self.pair,(lo,hi))
    def backend(self,key,graph):return {'token':key,'label':8,'receipt':'fake-signed-'+key}

    def test_durable_reservation_before_callback(self):
        self.store.reserve('a','req1','qualification',self.q())
        def backend(key,g):
            fresh=OracleEscrow(self.path)
            self.assertEqual(fresh.snapshot('a')['pending'][0]['state'],'DISPATCHED')
            return self.backend(key,g)
        result=self.store.dispatch_once('a','req1',backend)
        self.assertEqual(result['label'],8)
        self.assertEqual(self.store.snapshot('a')['settled'],1)

    def test_at_most_one_invocation_after_success_and_restart(self):
        self.store.reserve('a','req1','qualification',self.q())
        hook=Mock(side_effect=self.backend)
        self.store.dispatch_once('a','req1',hook)
        fresh=OracleEscrow(self.path)
        with self.assertRaises(UncertainDispatch):fresh.dispatch_once('a','req1',hook)
        hook.assert_called_once()
        self.assertEqual(fresh.snapshot('a')['purchased'],1)

    def test_uncertain_backend_error_stays_pending_and_blocks_next(self):
        self.store.reserve('a','req1','qualification',self.q())
        def broken(*args):raise RuntimeError('connection closed after remote success')
        with self.assertRaises(UncertainDispatch):self.store.dispatch_once('a','req1',broken)
        self.assertEqual(self.store.snapshot('a')['pending'][0]['state'],'DISPATCHED')
        with self.assertRaises(UncertainDispatch):self.store.dispatch_once('a','req1',broken)
        with self.assertRaisesRegex(EscrowError,'pending'):
            self.store.reserve('a','req2','repair',self.q(4,5))

    def test_authentic_out_of_band_reconciliation_without_second_call(self):
        self.store.reserve('a','req1','qualification',self.q())
        with self.assertRaises(UncertainDispatch):self.store.dispatch_once('a','req1',lambda *_: (_ for _ in ()).throw(OSError('lost reply')))
        proof=self.backend('req1',self.q())
        checked=[]
        def verify(receipt,query):
            checked.append((receipt,query))
            from e14.e14_integrated_graph import canonical_graph
            return receipt['receipt']=='fake-signed-req1' and query==canonical_graph(self.q())
        self.assertEqual(self.store.reconcile('a','req1',proof,verify)['label'],8)
        self.assertEqual(len(checked),1)
        self.assertEqual(self.store.snapshot('a')['settled'],1)
        with self.assertRaisesRegex(EscrowError,'only dispatched'):
            self.store.reconcile('a','req1',proof,verify)

    def test_bad_proof_does_not_settle_and_allows_later_real_evidence(self):
        self.store.reserve('a','req1','qualification',self.q())
        with self.assertRaises(UncertainDispatch):self.store.dispatch_once('a','req1',lambda *_: 1/0)
        for p in ({'token':'wrong','label':8,'receipt':'fake'},
                  {'token':'req1','label':True,'receipt':'fake'},
                  {'token':'req1','label':8,'receipt':''}):
            with self.assertRaises(EscrowError):self.store.reconcile('a','req1',p,lambda *_:True)
        with self.assertRaises(EscrowError):
            self.store.reconcile('a','req1',self.backend('req1',self.q()),lambda *_:False)
        self.assertEqual(self.store.snapshot('a')['settled'],0)
        self.store.reconcile('a','req1',self.backend('req1',self.q()),lambda *_:True)
        self.assertEqual(self.store.snapshot('a')['settled'],1)

    def test_key_reuse_same_graph_free_but_changing_graph_fails(self):
        self.assertTrue(self.store.reserve('a','req1','qualification',self.q())['charge'])
        self.assertFalse(self.store.reserve('a','req1','qualification',self.q())['charge'])
        with self.assertRaisesRegex(EscrowError,'idempotency'):
            self.store.reserve('a','req1','qualification',self.q(4,5))

    def test_same_graph_second_key_cannot_repuchase(self):
        self.store.reserve('a','req1','qualification',self.q())
        self.store.dispatch_once('a','req1',self.backend)
        with self.assertRaisesRegex(EscrowError,'duplicate graph'):
            self.store.reserve('a','req2','repair',self.q())

    def test_four_label_cap_and_isolated_arms(self):
        for i,xy in enumerate(((4,4),(4,5),(4,6),(4,7))):
            key=f'req{i}'
            self.store.reserve('a',key,'qualification',self.q(*xy))
            self.store.dispatch_once('a',key,self.backend)
        self.assertEqual(self.store.snapshot('a')['remaining'],0)
        with self.assertRaisesRegex(EscrowError,'budget exhausted'):
            self.store.reserve('a','req4','qualification',self.q(4,8))
        self.store.reserve('different','req0','qualification',self.q())
        self.assertEqual(self.store.snapshot('different')['purchased'],1)

    def test_graph_real_cost_rebuilt_and_malformed_graph_rejected(self):
        fake=self.q();fake['edges'][0][-1]=True
        with self.assertRaises(EscrowError):self.store.reserve('a','k1','qualification',fake)
        self.store.reserve('a','req1','qualification',self.q())
        self.assertGreater(self.store.snapshot('a')['query_cost_totals']['events'],0)

    def test_boolean_or_float_metadata_fails_closed(self):
        for name in ('a/b','',True):
            with self.assertRaises(EscrowError):self.store.reserve(name,'key','qualification',self.q())

    def test_sqlite_digest_tampering_detected_on_read(self):
        self.store.reserve('a','req1','qualification',self.q())
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE purchase SET stage='repair' WHERE arm='a'")
        with self.assertRaisesRegex(EscrowError,'integrity digest'):
            self.store.snapshot('a')

    def test_altered_topology_cost_caught_even_if_row_digest_rehashed(self):
        self.store.reserve('a','req1','qualification',self.q())
        with sqlite3.connect(self.path) as db:
            row=db.execute('SELECT arm,key,stage,query,query_sha,cost,status,label,backend_receipt,digest FROM purchase').fetchone()
            from .engine import digest
            obj=dict(zip(('arm','key','stage','query','query_sha','cost','status','label','backend_receipt','digest'),row))
            obj['cost']=json.dumps({'nodes':1,'edges':1,'events':1},separators=(',',':'),sort_keys=True)
            obj['digest']=digest({k:v for k,v in obj.items() if k!='digest'})
            db.execute('UPDATE purchase SET cost=?,digest=? WHERE arm=?',
                       (obj['cost'],obj['digest'],'a'))
        with self.assertRaisesRegex(EscrowError,'forged graph or cost'):
            self.store.snapshot('a')

    def test_symlink_db_refused(self):
        other=Path(self.tmp.name)/'other.sqlite';other.write_bytes(b'dont overwrite')
        link=Path(self.tmp.name)/'link.sqlite';link.symlink_to(other)
        with self.assertRaisesRegex(EscrowError,'symlink'):
            OracleEscrow(link)
        self.assertEqual(other.read_bytes(),b'dont overwrite')


if __name__=='__main__':unittest.main()
