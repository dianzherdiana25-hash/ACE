"""Evaluator-side E1.4t bounded public engineering study.

Always use independently staged worker calls. No scientific GO claimed until the
frozen bank, independent isolation acceptance, and strong controls are reviewed.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sqlite3
import tempfile
import time
from pathlib import Path
from contextlib import closing

from .e14_integrated_graph import DurableGraphBudget, audit_journal, graph_oracle, graph_routes, purchase
from .e14t_bank import SEED, STRATA, audit_bank, build, public_packet, sha
from .e14t_sandbox import sandbox_call, isolation_canary, IsolationUnavailable

MODES=('integrated','fixed','exhaustive','no-inheritance','sham')
FILES=('code/e14/e14t_bank.py','code/e14/e14t_worker.py','code/e14/e14t_sandbox.py',
       'code/e14/e14t_run.py','code/e14/e14_integrated_graph.py',
       'code/e14/e14_shared_budget.py', 'code/e14/e14t_audit.py',
       'code/e14/test_e14t.py', 'code/e14/test_e14t_audit.py',
       'design/e1.4/E14T_PROTOCOL_v1.md')


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def load_locked(repo,lockfile,bankfile):
    lock=json.loads(Path(lockfile).read_text())
    if set(lock)!={'version','seed','per_stratum','files_sha256','bank_sha256'} or lock['version']!=1:
        raise ValueError('invalid bank lock')
    for path,digest in lock['files_sha256'].items():
        with open(Path(repo)/path,'rb') as f:
            raw=f.read()
        if hashlib.sha256(raw).hexdigest()!=digest:
            raise ValueError('changed source after lock: '+path)
    data=gzip.decompress(Path(bankfile).read_bytes())
    bank=json.loads(data)
    if sha(bank)!=lock['bank_sha256'] or bank!=build(lock['seed'],lock['per_stratum']):
        raise ValueError('bank mismatch or non-deterministic generator')
    audit_bank(bank)
    return bank,lock


def freeze(repo,lockfile,bankfile,*,seed=SEED,per_stratum=12):
    if Path(bankfile).exists() or Path(lockfile).exists():
        raise FileExistsError('refuse to overwrite a locked bank')
    bank=build(seed,per_stratum)
    audited=audit_bank(bank)
    files={p:hashlib.sha256((Path(repo)/p).read_bytes()).hexdigest() for p in FILES}
    lock={'version':1,'seed':seed,'per_stratum':per_stratum,
          'files_sha256':files,'bank_sha256':sha(bank)}
    Path(bankfile).write_bytes(gzip.compress(encoded(bank),mtime=0))
    Path(lockfile).write_text(json.dumps(lock,indent=2,sort_keys=True)+'\n')
    return {**audited,'lock_sha256':hashlib.sha256(encoded(lock)).hexdigest()}




def _open_trace(sqlite_path):
    db=sqlite3.connect(str(sqlite_path),timeout=15)
    db.execute('PRAGMA busy_timeout=15000')
    db.execute('CREATE TABLE IF NOT EXISTS e14t_step ('
               'arm TEXT NOT NULL, step INTEGER NOT NULL, body TEXT NOT NULL, digest TEXT NOT NULL, '
               'PRIMARY KEY (arm,step))')
    db.execute('CREATE TABLE IF NOT EXISTS e14t_terminal ('
               'arm TEXT PRIMARY KEY, body TEXT NOT NULL, digest TEXT NOT NULL)')
    db.commit()
    return db


def _trace_read(sqlite_path,arm):
    with closing(_open_trace(sqlite_path)) as db:
        records=[]
        for step,raw,digest in db.execute('SELECT step,body,digest FROM e14t_step WHERE arm=? ORDER BY step',(arm,)):
            if hashlib.sha256(raw.encode()).hexdigest()!=digest or step!=len(records):
                raise ValueError('corrupt/missing durable action trace')
            records.append(json.loads(raw))
        terminal=db.execute('SELECT body,digest FROM e14t_terminal WHERE arm=?',(arm,)).fetchone()
        if terminal is not None:
            if hashlib.sha256(terminal[0].encode()).hexdigest()!=terminal[1]:
                raise ValueError('corrupt terminal decision')
            terminal=json.loads(terminal[0])
    return records,terminal


def _trace_append(sqlite_path,arm,row):
    raw=encoded(row).decode()
    with closing(_open_trace(sqlite_path)) as db:
        db.execute('INSERT INTO e14t_step VALUES (?,?,?,?)',
                   (arm,row['step'],raw,hashlib.sha256(raw.encode()).hexdigest()))
        db.commit()


def _terminal_commit(sqlite_path,arm,result):
    raw=encoded(result).decode()
    with closing(_open_trace(sqlite_path)) as db:
        db.execute('INSERT INTO e14t_terminal VALUES (?,?,?)',
                   (arm,raw,hashlib.sha256(raw.encode()).hexdigest()))
        db.commit()


def _public_receipts(book):
    return [{'id':r['id'],'stage':r['stage'],'query':r['query'],
             'label':r['label'],'status':r['status'],'reused_in':r['reused_in']}
            for r in book.snapshot()['receipts']]


def _ensure_action(a):
    if type(a) is not dict or a.get('action') not in ('query','reuse','accept','abstain'):
        raise ValueError('invalid worker proposal')
    if type(a.get('trigger')) is not bool or type(a.get('base_survivors')) is not int:
        raise ValueError('missing worker explanatory fields')
    return a


def evaluate_arm(world,mode,db_path, *, invoker=sandbox_call,max_steps=12):
    """One arm with resumable purchased labels; STOP on any pending receipt.

    A fresh scorer must pass the same DB path only after trusted reconciliation.
    This driver never retries UNKNOWN oracle results and never refunds labels.
    """
    arm=world['id']+':'+mode
    book=DurableGraphBudget(db_path,arm)
    truth=tuple(world['target'])
    oracle=lambda g:graph_oracle(g,truth)
    calls,terminal=_trace_read(db_path,arm)
    snap=book.snapshot()
    if terminal is not None:
        if terminal.get('receipt_sha256')!=sha(snap):
            raise ValueError('terminal result diverged from durable receipt')
        return terminal
    # If a crash happened AFTER label settlement but BEFORE writing its step,
    # do not silently lose accounting or repeat a purchase.
    logged=sum(row['action']=='query' for row in calls)
    if logged!=snap['purchased'] and not book.pending():
        return {'status':'BLOCKED_RECONCILE_TRACE','arm':arm,'purchased':snap['purchased'],
                'logged_purchases':logged}
    if book.pending():
        return {'status':'BLOCKED_UNKNOWN_PENDING','arm':arm,'purchased':book.snapshot()['purchased']}
    p=public_packet(world,mode)
    last=None
    for step in range(len(calls),max_steps):
        packet={**p,'receipts':_public_receipts(book),'remaining':book.snapshot()['remaining']}
        started=time.perf_counter_ns()
        action=_ensure_action(invoker(packet))
        wall_us=(time.perf_counter_ns()-started)//1000
        kind=action['action']
        # Never forward any source or target labels to the worker that are not
        # part of the provided demonstrations and paid receipts.
        extra={k:v for k,v in action.items() if k not in ('graph',)}
        line={'step':step,'action':kind,'worker_wall_us':wall_us,'metadata':extra}
        if kind=='query':
            if set(action)!=set(('action','stage','graph','trigger','base_survivors','extended_survivors','candidate_fits','representation')):
                raise ValueError('unexpected candidate query payload')
            if action['stage'] not in ('diagnosis','repair','qualification','inheritance'):
                raise ValueError('unknown query stage')
            try:
                rid,y=purchase(book,action['stage'],action['graph'],oracle)
            except BaseException:
                # Durable budget has already reserved if oracle failed; mark
                # interruption via the saved journal for manual reconciliation.
                raise
            line['receipt_id']=rid;line['label']=y
            line['query_costs']=next(r['cost'] for r in book.snapshot()['receipts'] if r['id']==rid)
        elif kind=='reuse':
            if set(action)!=set(('action','stage','receipt_id','trigger','base_survivors','extended_survivors','candidate_fits','representation')):
                raise ValueError('unexpected reuse fields')
            book.reuse(action['receipt_id'],action['stage'])
            line['receipt_id']=action['receipt_id']
        elif kind=='accept':
            if type(action.get('word')) is not list or not 5<=len(action['word'])<=9:
                raise ValueError('illegal candidate')
            # An accept must have settled qualification evidence with a
            # predicted non-blank label on its own graph.
            qual=[r for r in book.snapshot()['receipts'] if r['stage']=='qualification']
            if not qual or qual[-1]['label'] is None:
                raise ValueError('unguarded acceptance')
            hypothesis=tuple(action['word'])
            for r in book.snapshot()['receipts']:
                if graph_oracle(r['query'],hypothesis)!=r['label']:
                    raise ValueError('accepted candidate contradicts receipt')
            last=action;_trace_append(db_path,arm,line);calls.append(line);break
        else:
            last=action;_trace_append(db_path,arm,line);calls.append(line);break
        _trace_append(db_path,arm,line)
        calls.append(line)
        if book.pending():
            raise ValueError('pending oracle receipt after step')
    if last is None:
        raise ValueError('worker exceeded max step count')
    book.assert_complete()
    snapshot=book.snapshot()
    audited=audit_journal(snapshot,oracle)
    selected=tuple(last['word']) if last['action']=='accept' else None
    gold=[oracle(g) for g in world['probes']]
    predicted=[graph_oracle(g,selected) for g in world['probes']] if selected else []
    correct=sum(a==b for a,b in zip(predicted,gold)) if selected else 0
    wrong=sum(a!=b for a,b in zip(predicted,gold)) if selected else 0
    result={'status':'COMPLETE','arm':arm,'stratum':world['stratum'],'mode':mode,
            'truth_sha256':sha(list(truth)), 'final_action':last['action'],
            'word_correct':int(selected==truth) if selected else 0,
            'covered':len(predicted),'correct':correct,'errors':wrong,
            'false_accept':int(wrong>0), 'purchased':audited['purchased'],
            'auditor_calls':audited['auditor_oracle_calls'],
            'demo_labels':len(world['demos']), 'probe_labels':len(world['probes']),
            'resource_costs':audited['resource_totals'],
            'worker_calls':len(calls), 'worker_wall_us':sum(row['worker_wall_us'] for row in calls),
            'trace':calls,'receipt_sha256':sha(snapshot),
            'source_origin':world['source_origin']}
    _terminal_commit(db_path,arm,result)
    return result


def report_from_rows(rows):
    cells={}
    for stratum in STRATA:
        cells[stratum]={}
        for mode in MODES:
            sel=[r for r in rows if r['stratum']==stratum and r['mode']==mode]
            cells[stratum][mode]={k:sum(int(r[k]) for r in sel) for k in
                ('purchased','auditor_calls','demo_labels','probe_labels',
                 'word_correct','covered','correct','errors','false_accept','worker_calls','worker_wall_us')}
            cells[stratum][mode]['worlds']=len(sel)
    reachable=cells['reachable'];integrated=reachable['integrated']
    comparators=('fixed','exhaustive','no-inheritance','sham')
    # Strict one-piece GO gate intentionally hard. This is *diagnostic* until
    # independent isolation and pre-score protocol acceptance.
    gate=(integrated['word_correct']>=10
          and integrated['word_correct']>=max(reachable[m]['word_correct'] for m in comparators)+3
          and not any(cells[s]['integrated']['false_accept'] for s in ('rare','out-of-grammar')))
    return {'status':'ENGINEERING_PUBLIC_DEVELOPMENT','scientific_decision':'NOT_ASSESSED',
            'diagnostic_gate':'ELIGIBLE_FOR_REVIEW' if gate else 'HOLD',
            'worlds':len(rows)//len(MODES), 'arms':len(rows), 'cells':cells,
            'total_target_intervention_labels':sum(r['purchased'] for r in rows),
            'total_auditor_oracle_calls':sum(r['auditor_calls'] for r in rows),
            'total_demo_label_calls':sum(r['demo_labels'] for r in rows),
            'total_probe_label_calls':sum(r['probe_labels'] for r in rows)}


def run(repo,lockfile,bankfile,ledgerfile,output):
    bank,lock=load_locked(repo,lockfile,bankfile)
    boundary=isolation_canary()
    rows=[]
    for world in bank['worlds']:
        for mode in MODES:
            row=evaluate_arm(world,mode,ledgerfile)
            if row['status']!='COMPLETE':
                raise RuntimeError('unresolved arm '+row['arm'])
            rows.append(row)
    report={'status':'COMPLETE','version':1,'bank_sha256':lock['bank_sha256'],
            'boundary_preflight':boundary,'summary':report_from_rows(rows),'rows':rows}
    dest=Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
    temporary=dest.with_name(dest.name+'.tmp')
    temporary.write_bytes(gzip.compress(encoded(report),mtime=0))
    os.replace(temporary,dest)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('freeze','run'))
    parser.add_argument('--repo',default='.')
    parser.add_argument('--lock',required=True)
    parser.add_argument('--bank',required=True)
    parser.add_argument('--ledger')
    parser.add_argument('--output')
    parser.add_argument('--seed',type=int,default=SEED)
    parser.add_argument('--per-stratum',type=int,default=12)
    args=parser.parse_args()
    if args.mode=='freeze':
        result=freeze(args.repo,args.lock,args.bank,seed=args.seed,per_stratum=args.per_stratum)
    else:
        if args.ledger is None or args.output is None:
            raise ValueError('run requires ledger and output')
        result=run(args.repo,args.lock,args.bank,args.ledger,args.output)['summary']
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    main()
