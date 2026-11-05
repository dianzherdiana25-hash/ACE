"""Postscore E1.4v structural-shift audit: disjoint training -> shared-prefix DAG.

Reruns the already-developed policy with *unchanged* oracle and interventions.
New graph structures are evaluator-owned and never influence candidate choice.
No new scientific GO, no independent confirmatory scoring.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from .e14p_graph import paths
from .e14u_primitive import _matches
from .e14v_study import COEFFICIENTS,OUTSIDERS,MODES,SEED,evaluate,source_evidence,world
from .e14v_operator import graph_score
from .e14v_topology import structurally_new_probes


def independent_cost(graph,pair,semantics):
    """Use a different DFS implementation from the source evaluator."""
    routes=paths(graph)
    a,b=pair
    options=[]
    for i,(ei,ci) in enumerate(routes):
        for j,(ej,cj) in enumerate(routes):
            if i==j or not _matches(ei,a) or not _matches(ej,b):continue
            lo,hi=min(ci,cj),max(ci,cj)
            if isinstance(semantics,tuple):
                x,y=semantics
                value=x*lo+y*hi
            elif semantics=='offset-plus-1':value=lo+hi+1
            elif semantics=='product':value=lo*hi
            else:raise ValueError('unknown semantic kind')
            options.append(value)
    return min(options,default=None)


def audit(*,indices=range(8),operators=None):
    if operators is None:operators=COEFFICIENTS+OUTSIDERS
    records=[];unique_checks=0
    with tempfile.TemporaryDirectory(prefix='ace-e14v-topology-') as home:
        db=Path(home)/'journal.sqlite'
        for idx in indices:
            for kind in operators:
                w=world(idx,kind)
                demos,_=source_evidence(w,db)
                # All modes use the SAME target-independent topology probes.
                probes=structurally_new_probes(SEED+idx*4099+sum(map(ord,str(kind)))*17,count=6)
                truth_outputs=[independent_cost(g,w['pair'],kind) for g in probes]
                for graph,gold in zip(probes,truth_outputs,strict=True):
                    if w['oracle'](graph)!=gold:raise AssertionError('independent oracle disagreement')
                    unique_checks+=1
                for mode in MODES:
                    result=evaluate(w,demos,db,mode,include_program=True)
                    selected=result.pop('selected_program')
                    predicted=[graph_score(g,selected) for g in probes] if selected is not None else []
                    records.append({'id':w['id'],'mode':mode,
                                    'accepted':int(selected is not None),
                                    'exact':result['exact'],
                                    'wrong_exact':result['wrong_accepted'],
                                    'structural_covered':len(predicted),
                                    'structural_errors':sum(p!=gold for p,gold in zip(predicted,truth_outputs)),
                                    'target_labels':result['target_purchased']})
    summary={mode:{k:sum(r[k] for r in records if r['mode']==mode)
                   for k in ('accepted','exact','wrong_exact','structural_covered',
                             'structural_errors','target_labels')}
             for mode in MODES}
    return {'status':'POSTSCORE_STRUCTURAL_INVARIANCE_ONLY',
            'scientific_decision':'NOT_ASSESSED','worlds':unique_checks//6,
            'arm_count':len(records),'unique_independent_oracle_checks':unique_checks,
            'source_topology':'disjoint-branches',
            'probe_topology':'shared-prefix-forward-DAG',
            'summary':summary,'rows':records}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--indices',type=int,default=8)
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    report=audit(indices=range(args.indices))
    digest=hashlib.sha256(json.dumps(report,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps({**report,'sha256':digest},sort_keys=True,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'worlds':report['worlds'],
                      'arm_count':report['arm_count'],'summary':report['summary'],
                      'sha256':digest},sort_keys=True))

if __name__=='__main__':main()
