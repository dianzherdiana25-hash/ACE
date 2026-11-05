"""E1.4w namespaces-worker integration experiment (NOT native Bubblewrap).

A policy subprocess receives only a typed predecessor artifact and purchased
public observations. Hidden truth, oracle, and held-out probes stay evaluator-
side. Fresh worker for every action. Compare deterministic results with the
in-process reference on separately purchased but identically bounded labels.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import tempfile

from .e14_integrated_graph import DurableGraphBudget,audit_journal,purchase
from .e14_shared_budget import BudgetContractError
from .e14t_sandbox import isolation_canary,sandbox_call
from .e14w_study import SEED,IN_FAMILY_EXPRESSIONS,OUT_FAMILY,ADV_OUTSIDERS,\
    source_acquire,world,evaluate_arm
from .e14w_synthesis import library,render,motif_query,target_for

WORKER=Path(__file__).with_name('e14w_worker.py')
MODES=('synthesis-safe','synthesis-eager','compact-safe','random-safe')


def worker_arm(w,source,mode,journal_path):
    if mode not in MODES:raise BudgetContractError('unknown isolated mode')
    pair=source['pair_learned']
    if pair is None:
        return {'status':'source_abstain','id':w['id'],'mode':mode,
                'accepted':0,'exact':0,'wrong_accepted':0,
                'target_labels':0,'target_replays':0,'probe_errors':0,
                'worker_calls':0,'cpu_us':0,'rss_kib_max':0}
    journal=DurableGraphBudget(journal_path,w['id']+':'+mode)
    receipts=[];action=None;worker_calls=cpu_us=rss_peak=0
    chosen=None
    for turn in range(8):
        current=journal.snapshot()
        packet={'pair':[list(word) for word in pair],
                'observations':receipts,
                'remaining':current['remaining'],
                'mode':mode,'seed':SEED+w['pair_index']*101+len(receipts)}
        output=sandbox_call(packet,timeout=8,worker=WORKER)
        cpu=output.pop('cpu_us',None);rss=output.pop('rss_kib',None)
        if type(cpu) is not int or type(rss) is not int or not 0<=cpu<=3_000_000 or not 0<rss<=512*1024:
            raise BudgetContractError('invalid isolated resource metering')
        worker_calls+=1;cpu_us+=cpu;rss_peak=max(rss_peak,rss)
        op=output['action']
        if op=='query':
            if set(output)!= {'action','tolls'}:
                raise BudgetContractError('invalid worker question packet')
            tolls=output['tolls']
            if type(tolls) is not list or len(tolls)!=2 or any(type(v) is not int or not 0<=v<=14 for v in tolls):
                raise BudgetContractError('invalid worker toll vector')
            if current['remaining']<=0:raise BudgetContractError('worker exceeded shared cap')
            graph=motif_query(pair,*tolls)
            receipt,label=purchase(journal,'diagnosis' if turn==0 else 'qualification',graph,w['oracle'])
            if turn==0:journal.reuse(receipt,'repair')
            receipts.append({'costs':[4+min(tolls),4+max(tolls)],'label':label})
        elif op=='accept':
            if set(output)!= {'action','expression'}:
                raise BudgetContractError('invalid worker acceptance packet')
            expression=output['expression']
            allowed=library(3 if mode=='compact-safe' else 5)
            chosen=next((p for p in allowed if render(p)==expression),None)
            if chosen is None:raise BudgetContractError('unrecognized worker expression')
            if len(receipts)<(1 if mode=='synthesis-eager' else 3):
                raise BudgetContractError('acceptance before evidence threshold')
            break
        elif op=='abstain':
            if set(output)!= {'action'}:raise BudgetContractError('invalid abstention packet')
            break
        else:raise BudgetContractError('invalid worker action')
    else:raise BudgetContractError('worker action cap exhausted')
    snapshot=journal.snapshot()
    audit=audit_journal(snapshot,w['oracle'])
    accepted=chosen is not None
    if accepted:
        from .e14w_synthesis import evaluate,GRID
        exact=bool(w['in_family'] and pair==w['pair'] and
                   all(evaluate(chosen,*costs)==w['oracle'](
                         motif_query(w['pair'],costs[0]-4,costs[1]-4)) for costs in GRID))
    else:
        exact=False
    predicted=target_for(pair,chosen) if accepted else None
    errors=(sum(predicted(g)!=w['oracle'](g) for g in w['probes'])
            if accepted else 0)
    return {'status':'isolated_development','id':w['id'],'mode':mode,
            'accepted':int(accepted),'exact':int(exact),
            'wrong_accepted':int(accepted and not exact),
            'target_labels':snapshot['purchased'],
            'target_replays':audit['auditor_oracle_calls'],
            'probe_errors':errors,'worker_calls':worker_calls,
            'cpu_us':cpu_us,'rss_kib_max':rss_peak,
            'selected_expr':render(chosen) if accepted else None,
            'target_graph_cost':snapshot['query_cost_totals']}


def run_batch(indices,kinds=IN_FAMILY_EXPRESSIONS+OUT_FAMILY):
    checks=isolation_canary()
    rows=[];sources=[]
    with tempfile.TemporaryDirectory(prefix='ace-e14w-isolated-') as home:
        root=Path(home)
        for i in indices:
            source=source_acquire(i,root/'source.sqlite')
            sources.append({'index':i,'correct':source['correct'],
                            'purchased':source['source_labels']})
            for kind in kinds:
                w=world(i,kind)
                for mode in MODES:
                    isolated=worker_arm(w,source,mode,root/'isolated.sqlite')
                    reference=evaluate_arm(w,source,mode,root/'reference.sqlite')
                    for key,other in (('accepted','accepted'),('exact','semantic_exact'),
                                      ('wrong_accepted','wrong_accepted'),
                                      ('target_labels','target_labels'),
                                      ('probe_errors','probe_errors'),
                                      ('selected_expr','selected_expr')):
                        if isolated.get(key)!=reference.get(other):
                            raise RuntimeError(f'worker/reference disagreement {w["id"]} {mode} {key}: '
                                               f'{isolated.get(key)!r} != {reference.get(other)!r}')
                    rows.append(isolated)
    summary={mode:{k:sum(r[k] for r in rows if r['mode']==mode)
                   for k in ('accepted','exact','wrong_accepted','target_labels',
                             'target_replays','probe_errors','worker_calls','cpu_us')}
             for mode in MODES}
    return {'status':'ISOLATED_NAMESPACE_DEVELOPMENT_REPLAY',
            'scientific_decision':'NOT_ASSESSED',
            'native_bubblewrap_certified':False,'canaries':checks,
            'source_purchases':sum(r['purchased'] for r in sources),
            'worlds':len(rows)//len(MODES),'arms':len(rows),
            'summary':summary,'sources':sources,'rows':rows}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--start',type=int,default=0)
    p.add_argument('--end',type=int,default=1)
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    if not 0<=args.start<args.end<=12:raise SystemExit('invalid disjoint batch')
    result=run_batch(range(args.start,args.end))
    raw=json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    digest=hashlib.sha256(raw).hexdigest()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps({**result,'sha256':digest},indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':result['status'],'worlds':result['worlds'],
          'arms':result['arms'],'source_purchases':result['source_purchases'],
          'summary':result['summary'],'sha256':digest},sort_keys=True))

if __name__=='__main__':main()
