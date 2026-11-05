"""ACE E1.4w public *development* lineage + grammar-synthesis experiment.

A predecessor learns a 3-event motif pair using MAX semantics; a different
successor task searches expression *trees* for an unfamiliar cost function.
Both tasks buy labels separately and store durable receipts. The grammar and
world generator are authored by the researcher; no scientific GO follows.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import tempfile

from .e14_integrated_graph import DurableGraphBudget,audit_journal,purchase
from .e14u_primitive import PAIR_SPACE, program, oracle as source_oracle, fit, select_query
from .e14w_synthesis import (library,render,GRID,candidate_ids,select_fast,
                              target_for,outsider_for,motif_query,evaluate)
from .e14v_topology import fork

SEED=202611052026
PAIR_INDICES=tuple(range(12))
IN_FAMILY_EXPRESSIONS=(7,8,20,21,22,23,24,25,27,31,35,57)
OUT_FAMILY=('difference','offset-3','saturated-difference','half-hi')
ADV_OUTSIDERS=('three-lo-two-hi','two-lo-three-hi','square-sum','floor-mean',
              'gap-parity','switch-gap','quadratic-mix','clamped-sum')
NOVEL_OUTSIDERS=('gap-mod3','lo-parity','hi-parity','upper-threshold',
               'gap-mod4','clamped-product','odd-weighted','piecewise-product')
MODES=('synthesis-safe','synthesis-eager','compact-safe','random-safe',
       'known-pair-upper','sham-pair')
CANARY='synthesis-canary'
NEIGHBOR='synthesis-neighbor'


def source_acquire(pair_index, db, cap=4):
    """Source predecessor uses MAX, never target operator or target labels."""
    truth_pair=PAIR_SPACE[pair_index]
    oracle=lambda g:source_oracle(g,program('branch-pair',truth_pair))
    journal=DurableGraphBudget(db,f'source:{pair_index}')
    observed=[]; candidates=[program('branch-pair',p) for p in PAIR_SPACE]
    for step in range(cap):
        if len(candidates)<=1:break
        proposal=select_query(candidates,[g for g,y in observed],mode='active',seed=SEED+step)
        if proposal is None:break
        rid,y=purchase(journal,'diagnosis' if step==0 else 'repair',proposal,oracle)
        observed.append((proposal,y))
        candidates=fit([{'input':g,'output':y} for g,y in observed],extended=True)['candidates']
    audit=audit_journal(journal.snapshot(),oracle)
    learned=candidates[0][1] if len(candidates)==1 else None
    return {'index':pair_index,'observations':len(observed),'candidates':len(candidates),
            'pair_learned':learned,'correct':learned==truth_pair,
            'source_labels':journal.snapshot()['purchased'],
            'source_replay':audit['auditor_oracle_calls'],
            'source_graph_cost':journal.snapshot()['query_cost_totals'],
            'source_journal':journal.snapshot()}


def world(pair_index,kind):
    pair=PAIR_SPACE[pair_index]
    if type(kind) is int and kind in IN_FAMILY_EXPRESSIONS:
        tree=library(5)[kind]
        oracle=target_for(pair,tree)
        formula=render(tree)
        in_family=True
    elif kind in OUT_FAMILY+ADV_OUTSIDERS+NOVEL_OUTSIDERS:
        oracle=outsider_for(pair,kind)
        formula=kind
        in_family=False
    else:raise ValueError('unknown development target')
    rng=random.Random(SEED+pair_index*4099+sum(ord(x) for x in formula)*19)
    probes=[]; used=set()
    while len(probes)<6:
        tolls=tuple(rng.randrange(15) for _ in range(2))
        g=fork(pair,tolls)
        key=tuple(sorted(map(tuple,g['edges'])))
        if key not in used:probes.append(g);used.add(key)
    return {'id':f'w:{pair_index}:{formula}','pair_index':pair_index,
            'kind':formula,'in_family':in_family,'pair':pair,
            'oracle':oracle,'probes':probes}


def evaluate_arm(w,source,mode,db):
    if mode not in (*MODES,CANARY,NEIGHBOR):raise ValueError('unknown strategy')
    learned=source['pair_learned']
    pair=(w['pair'] if mode=='known-pair-upper' else
          PAIR_SPACE[(w['pair_index']+1)%len(PAIR_SPACE)] if mode=='sham-pair' else learned)
    journal=DurableGraphBudget(db,w['id']+':'+mode)
    observations=[]
    chosen=None
    size=3 if mode=='compact-safe' else 5
    question_mode='random' if mode=='random-safe' else 'active'
    min_labels=1 if mode=='synthesis-eager' else 3
    if pair is not None:
        for turn in range(4):
            ids=candidate_ids(observations,size)
            if not ids:break
            if len(ids)==1 and len(observations)>=min_labels:
                chosen=library(size)[ids[0]]
                break
            if len(ids)==1:
                # Predefined disconfirming points; none selected from hidden truth.
                used={costs for costs,_ in observations}
                control=next((t for t in ((0,14),(14,0),(1,9),(6,13),(8,2))
                              if (4+min(t),4+max(t)) not in used),None)
                question=control
            else:
                question=select_fast(ids,observations,size,question_mode,
                                     seed=SEED+w['pair_index']*101+turn)
            if question is None:break
            a,b=question; graph=motif_query(pair,a,b)
            receipt,y=purchase(journal,'diagnosis' if turn==0 else 'qualification',graph,w['oracle'])
            if turn==0:journal.reuse(receipt,'repair')
            # Failed pair artifact: no corresponding route -> paid negative None.
            if y is None:break
            observations.append(((4+min(a,b),4+max(a,b)),y))
        else:
            ids=candidate_ids(observations,size)
            if len(ids)==1 and len(observations)>=min_labels:
                chosen=library(size)[ids[0]]
    if mode in (CANARY,NEIGHBOR) and chosen is not None:
        remaining=journal.snapshot()['remaining']
        if not remaining:
            chosen=None  # no unpurchased evidence: abstain visibly
        else:
            # Predeclared unsupervised canary: maximize distance from observed
            # input-cost pairs, not error or hidden truth. Exact truth unknown.
            used={costs for costs,_ in observations}
            available=[(lo,hi) for lo in range(4,19) for hi in range(lo,19)
                       if (lo,hi) not in used]
            if mode==CANARY:
                costs=max(available,key=lambda x:(min(abs(x[0]-y[0])+abs(x[1]-y[1])
                                                       for y in used),x[1],x[0]))
            else:
                # Postscore local-perturbation test (not a precommitted policy):
                # a neighboring input rather than the farthest input.
                costs=min(available,key=lambda x:(min(abs(x[0]-y[0])+abs(x[1]-y[1])
                                                       for y in used),x[0],x[1]))
            graph=motif_query(pair,costs[0]-4,costs[1]-4)
            _,answer=purchase(journal,'qualification',graph,w['oracle'])
            if answer is None or answer!=evaluate(chosen,*costs):
                chosen=None
    snap=journal.snapshot()
    replay=audit_journal(snap,w['oracle'])
    pred_oracle=target_for(pair,chosen) if chosen is not None else None
    accepted=chosen is not None
    exact=accepted and pair==w['pair'] and w['in_family'] and all(
        evaluate(chosen,*x)==w['oracle'](motif_query(w['pair'],x[0]-4,x[1]-4))
        for x in GRID)
    probe_errors=(sum(pred_oracle(g)!=w['oracle'](g) for g in w['probes'])
                  if accepted else 0)
    return {'id':w['id'],'mode':mode,'source_success':source['correct'],
            'in_family':w['in_family'],'formula':w['kind'],
            'accepted':int(accepted),'semantic_exact':int(exact),
            'wrong_accepted':int(accepted and not exact),
            'abstain':int(not accepted),'target_labels':snap['purchased'],
            'target_replays':replay['auditor_oracle_calls'],
            'target_graph_cost':snap['query_cost_totals'],
            'target_journal':snap,
            'accepted_probes':6*int(accepted),'probe_errors':probe_errors,
            'candidate_count':len(candidate_ids(observations,size)) if pair is not None else None,
            'observations':len(observations),
            'selected_expr':render(chosen) if chosen is not None else None}


def run(*,pair_indices=PAIR_INDICES,kinds=IN_FAMILY_EXPRESSIONS+OUT_FAMILY,
        modes=MODES):
    rows=[];sources=[]
    with tempfile.TemporaryDirectory(prefix='ace-e14w-experiment-') as home:
        db=Path(home)/'e14w.sqlite'
        for i in pair_indices:
            s=source_acquire(i,db)
            sources.append(s)
            for kind in kinds:
                w=world(i,kind)
                for mode in modes:
                    rows.append(evaluate_arm(w,s,mode,db))
    stats={}
    for mode in modes:
        group=[r for r in rows if r['mode']==mode]
        stats[mode]={key:sum(r[key] for r in group) for key in (
            'accepted','semantic_exact','wrong_accepted','abstain',
            'target_labels','target_replays','accepted_probes','probe_errors')}
        stats[mode]['arms']=len(group)
    return {'version':1,'status':'PUBLIC_DEVELOPMENT_ONLY',
            'scientific_decision':'NOT_ASSESSED',
            'family':'bottom-up AST 5 nodes, supplied motif artifact',
            'source_semantics':'separate predecessor task with MAX route-pair',
            'source_labels':sum(s['source_labels'] for s in sources),
            'source_successes':sum(s['correct'] for s in sources),
            'source_arms':len(sources),'worlds':len(sources)*len(kinds),
            'arm_count':len(rows),'modes':list(modes),'summary':stats,'sources':sources,'rows':rows}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--start',type=int,default=0)
    p.add_argument('--end',type=int,default=12)
    p.add_argument('--output',type=Path)
    p.add_argument('--stress',action='store_true',help='run separate postdevelopment OOD challenge suite')
    p.add_argument('--canary',action='store_true',help='run one additional canary policy on both public and stress worlds')
    p.add_argument('--neighbor',action='store_true',help='postscore local-perturbation check, no scientific GO')
    p.add_argument('--novel',action='store_true',help='exploratory new-family metamorphic stress, no confirmatory GO')
    args=p.parse_args()
    if not 0<=args.start<args.end<=12 or (int(args.canary)+int(args.neighbor)+int(args.novel)>1):
        raise SystemExit('invalid disjoint batch or conflicting modes')
    r=run(pair_indices=range(args.start,args.end),
          kinds=(NOVEL_OUTSIDERS if args.novel else
                 IN_FAMILY_EXPRESSIONS+OUT_FAMILY+ADV_OUTSIDERS if args.canary or args.neighbor else
                 ADV_OUTSIDERS if args.stress else IN_FAMILY_EXPRESSIONS+OUT_FAMILY),
          modes=('synthesis-safe',CANARY,NEIGHBOR) if args.novel else
                (CANARY,) if args.canary else (NEIGHBOR,) if args.neighbor else MODES)
    raw=json.dumps(r,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    digest=hashlib.sha256(raw).hexdigest()
    if args.output:
        args.output.parent.mkdir(exist_ok=True,parents=True)
        args.output.write_text(json.dumps({**r,'sha256':digest},indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':r['status'],'worlds':r['worlds'],
          'arm_count':r['arm_count'],'source_successes':r['source_successes'],
          'source_labels':r['source_labels'],'summary':r['summary'],'sha256':digest},sort_keys=True))

if __name__=='__main__':main()
