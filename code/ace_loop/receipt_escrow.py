"""E1.6 evaluator-owned at-most-once dispatch and reconciliation for E1.4 graphs.

Only a trusted evaluator may hold the SQLite DB and oracle callback. A paid
reservation is committed *before* any external call. Dispatch is durably claimed
before invocation; after a crash or uncertain reply the call is NEVER retried.
An operator must obtain a separate authentic backend receipt, call reconcile
with a trusted verifier, or abandon the charged label. This does NOT provide
true distributed exactly-once delivery without backend idempotency guarantees.
"""
from __future__ import annotations

from contextlib import closing
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from e14.e14_integrated_graph import canonical_graph, graph_cost
from e14.e14_shared_budget import STAGES, SHARED_CAP
from .engine import ResearchIntegrityError, canonical


class EscrowError(ResearchIntegrityError):
    pass


class UncertainDispatch(EscrowError):
    """The oracle may have been called. NEVER retry; reconcile out of band."""


def _valid_name(name):
    return type(name) is str and re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',name) is not None


def _hash(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _canonical_graph(graph):
    try:
        value=canonical_graph(deepcopy(graph))
        cost=graph_cost(value)
    except (ValueError,TypeError,KeyError,OverflowError,RecursionError) as exc:
        raise EscrowError('invalid typed graph') from exc
    return value,cost


def _valid_label(label):
    return label is None or (type(label) is int and 0<=label<=960)


def _validate_proof(proof,token):
    if (type(proof) is not dict or set(proof)!= {'token','label','receipt'} or
        proof['token']!=token or type(proof['receipt']) is not str or
        not 1<=len(proof['receipt'])<=256 or not _valid_label(proof['label'])):
        raise EscrowError('invalid backend receipt proof')
    return proof


class OracleEscrow:
    """Four-label transactional ledger with provider-independent receipt identity.

    One escrow DB may have many arms, but each arm has at most four distinct
    actual graph purchases. This class does NOT run untrusted candidate code.
    """
    def __init__(self,path):
        self.path=Path(path)
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise EscrowError('symlink SQLite path')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with closing(self._connect()) as db:
            db.execute('CREATE TABLE IF NOT EXISTS purchase ('
                       'arm TEXT NOT NULL,key TEXT NOT NULL,stage TEXT NOT NULL,'
                       'query TEXT NOT NULL,query_sha TEXT NOT NULL,cost TEXT NOT NULL,'
                       'status TEXT NOT NULL,label TEXT,backend_receipt TEXT,'
                       'digest TEXT NOT NULL,PRIMARY KEY(arm,key),UNIQUE(arm,query_sha))')

    def _connect(self):
        db=sqlite3.connect(str(self.path),timeout=15,isolation_level=None)
        db.execute('PRAGMA busy_timeout=15000')
        db.execute('PRAGMA synchronous=FULL')
        return db

    @staticmethod
    def _read(db,arm=None):
        if arm is None:
            rows=db.execute('SELECT arm,key,stage,query,query_sha,cost,status,label,'
                            'backend_receipt,digest FROM purchase ORDER BY arm,rowid').fetchall()
        else:
            rows=db.execute('SELECT arm,key,stage,query,query_sha,cost,status,label,'
                            'backend_receipt,digest FROM purchase WHERE arm=? ORDER BY rowid',
                            (arm,)).fetchall()
        records=[]
        for row in rows:
            keys=('arm','key','stage','query','query_sha','cost','status','label',
                  'backend_receipt','digest')
            item=dict(zip(keys,row))
            if not _valid_name(item['arm']) or not _valid_name(item['key']) or item['stage'] not in STAGES:
                raise EscrowError('invalid receipt identity/stage')
            raw=item['query'];raw_cost=item['cost']
            try:
                query=json.loads(raw);cost=json.loads(raw_cost)
                if canonical(query).decode()!=raw or canonical(cost).decode()!=raw_cost:
                    raise EscrowError('noncanonical graph/cost')
                graph,real_cost=_canonical_graph(query)
                if graph!=query or real_cost!=cost:
                    raise EscrowError('forged graph or cost')
                if _hash(graph)!=item['query_sha']:
                    raise EscrowError('query digest mismatch')
            except (ValueError,TypeError,OverflowError) as exc:
                raise EscrowError('malformed receipt content') from exc
            if item['status'] not in ('RESERVED','DISPATCHED','SETTLED'):
                raise EscrowError('unknown receipt state')
            if item['status']=='SETTLED':
                try:label=json.loads(item['label'])
                except (TypeError,ValueError) as exc:
                    raise EscrowError('invalid stored label') from exc
                if not _valid_label(label) or canonical(label).decode()!=item['label'] or (
                    type(item['backend_receipt']) is not str or not item['backend_receipt']):
                    raise EscrowError('invalid settled evidence')
            elif item['label'] is not None or item['backend_receipt'] is not None:
                raise EscrowError('pending receipt contains unsupported label')
            expected=_hash({k:item[k] for k in keys if k!='digest'})
            if expected!=item['digest']:
                raise EscrowError('receipt integrity digest mismatch')
            records.append(item)
        return records

    @staticmethod
    def _store(db,item):
        item['digest']=_hash({k:v for k,v in item.items() if k!='digest'})
        db.execute('UPDATE purchase SET status=?,label=?,backend_receipt=?,digest=? '
                   'WHERE arm=? AND key=?',
                   (item['status'],item['label'],item['backend_receipt'],item['digest'],
                    item['arm'],item['key']))

    def reserve(self,arm,key,stage,graph):
        if not _valid_name(arm) or not _valid_name(key) or stage not in STAGES:
            raise EscrowError('invalid request identity or stage')
        query,cost=_canonical_graph(graph)
        with closing(self._connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                rows=self._read(db,arm)
                same=next((x for x in rows if x['key']==key),None)
                if same:
                    if (same['query_sha']!=_hash(query) or same['stage']!=stage):
                        raise EscrowError('idempotency key reused for different request')
                    db.execute('COMMIT')
                    return {'key':key,'status':same['status'],'charge':False}
                if len(rows)>=SHARED_CAP:
                    raise EscrowError('four-label budget exhausted')
                if any(x['status']!='SETTLED' for x in rows):
                    raise EscrowError('unreconciled pending purchase blocks new purchase')
                if any(x['query_sha']==_hash(query) for x in rows):
                    raise EscrowError('duplicate graph requires receipt reuse, not repurchase')
                item={'arm':arm,'key':key,'stage':stage,'query':canonical(query).decode(),
                      'query_sha':_hash(query),'cost':canonical(cost).decode(),
                      'status':'RESERVED','label':None,'backend_receipt':None}
                item['digest']=_hash(item)
                db.execute('INSERT INTO purchase VALUES (?,?,?,?,?,?,?,?,?,?)',
                           tuple(item[x] for x in ('arm','key','stage','query','query_sha',
                                                   'cost','status','label','backend_receipt','digest')))
                db.execute('COMMIT')
                return {'key':key,'status':'RESERVED','charge':True}
            except BaseException:
                db.execute('ROLLBACK')
                raise

    def _claim(self,arm,key):
        with closing(self._connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                row=next((r for r in self._read(db,arm) if r['key']==key),None)
                if row is None:raise EscrowError('missing reserved request')
                if row['status']!='RESERVED':
                    raise UncertainDispatch('dispatch not available; DO NOT RETRY')
                row['status']='DISPATCHED';self._store(db,row)
                db.execute('COMMIT')
                return json.loads(row['query'])
            except BaseException:
                db.execute('ROLLBACK');raise

    def dispatch_once(self,arm,key,backend):
        """Invoke a trusted backend ONCE after durable claim; no fallback retry."""
        if not callable(backend):raise EscrowError('trusted callable backend required')
        query=self._claim(arm,key)
        try:
            proof=backend(key,deepcopy(query))
            _validate_proof(proof,key)
            self._finish(arm,key,proof)
            return deepcopy(proof)
        except BaseException as exc:
            # Dispatch is irrevocably claimed even if callback never started.
            raise UncertainDispatch('uncertain remote outcome; reconcile, never retry') from exc

    def _finish(self,arm,key,proof):
        with closing(self._connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                row=next((r for r in self._read(db,arm) if r['key']==key),None)
                if row is None or row['status']!='DISPATCHED':
                    raise EscrowError('cannot settle non-dispatched request')
                row['status']='SETTLED';row['label']=canonical(proof['label']).decode()
                row['backend_receipt']=proof['receipt']
                self._store(db,row);db.execute('COMMIT')
            except BaseException:
                db.execute('ROLLBACK');raise

    def reconcile(self,arm,key,proof,verify):
        """Reconcile only after a trusted verifier authenticates out-of-band proof.

        No oracle is called here. An app integration must implement `verify` as
        a cryptographic/provider-side receipt check, not a mere equality test.
        """
        _validate_proof(proof,key)
        if not callable(verify):raise EscrowError('trusted receipt verifier required')
        with closing(self._connect()) as db:
            row=next((r for r in self._read(db,arm) if r['key']==key),None)
        if row is None or row['status']!='DISPATCHED':
            raise EscrowError('only dispatched pending calls can reconcile')
        query=json.loads(row['query'])
        if verify(deepcopy(proof),deepcopy(query)) is not True:
            raise EscrowError('backend receipt could not be authenticated')
        self._finish(arm,key,proof)
        return deepcopy(proof)

    def snapshot(self,arm):
        if not _valid_name(arm):raise EscrowError('invalid arm')
        with closing(self._connect()) as db:
            rows=self._read(db,arm)
        pending=[{'key':r['key'],'state':r['status']} for r in rows
                 if r['status']!='SETTLED']
        return {'arm':arm,'purchased':len(rows),'remaining':SHARED_CAP-len(rows),
                'pending':pending,'settled':len(rows)-len(pending),
                'query_cost_totals':{k:sum(json.loads(x['cost'])[k] for x in rows)
                                     for k in ('nodes','edges','events')},
                'safe_to_dispatch_new':not pending and len(rows)<SHARED_CAP,
                'semantics':'at-most-once attempted dispatch; not distributed exactly-once',
                'scientific_decision':'NOT_ASSESSED'}
