"""E1.4v public development: source-cost-aware affine operator induction.

A priori finite structural family, numerically inferred parameters; DOES NOT
infer arbitrary semantic primitives. Same public motif pairs as E1.4u, new
source acquisition queries and candidate cost operators. No scientific GO.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import tempfile
from collections import Counter
from pathlib import Path

from .e14_integrated_graph import DurableGraphBudget, audit_journal, graph_routes, purchase
from .e14_shared_budget import BudgetContractError
from .e14u_primitive import PAIR_SPACE, graph_from_routes, query_pool, _matches
from .e14v_operator import ALL, LEGACY, graph_score, pool, predict, proof, select, survivor_ids

SEED = 2026110515
MODES = ('affine-naive','affine-verified','affine-challenge','legacy')
COEFFICIENTS = ((0,1),(1,0),(1,1),(2,1),(1,2),(3,1),(1,3),(2,3),(3,2))
OUTSIDERS = ('offset-plus-1','product')


def unknown_score(graph,pair,kind):
    routes=graph_routes(graph)[0]
    from .e14v_operator import pairs_of
    values=pairs_of(routes,pair)
    if kind=='offset-plus-1':
        return min((lo+hi+1 for lo,hi in values),default=None)
    if kind=='product':
        return min((lo*hi for lo,hi in values),default=None)
    raise ValueError('unknown stress kind')


def world(index, operator):
    if type(index) is not int or not 0 <= index < len(PAIR_SPACE):
        raise ValueError('invalid world index')
    pair=PAIR_SPACE[index]
    if type(operator) is tuple and operator in COEFFICIENTS:
        truth=('pair-affine',pair,operator)
        oracle=lambda graph:graph_score(graph,truth)
        label=f'affine:{operator[0]}:{operator[1]}'
    elif operator in OUTSIDERS:
        truth=('unrepresented',pair,operator)
        oracle=lambda graph:unknown_score(graph,pair,operator)
        label=operator
    else:raise ValueError('unsupported operator')
    rng=random.Random(SEED+index*1123+sum(map(ord,label))*13)
    # Probes are disjoint in graph identity from the public 70-graph selector.
    base=set(pool()[2]);probes=[];trials=0
    words=tuple(w for w in pair)
    while len(probes)<6 and trials<200:
        trials+=1
        extras=tuple(rng.sample([w for w in __import__('e14.e14u_primitive',fromlist=['PAIR_WORDS']).PAIR_WORDS if w not in words],2))
        g=graph_from_routes((*words,*extras),[rng.randrange(10) for _ in range(4)])
        key=tuple(sorted(map(tuple,g['edges'])))
        if key not in base:
            probes.append(g);base.add(key)
    if len(probes)!=6:raise RuntimeError('could not make novel probes')
    return {'id':f'v:{index}:{label}','truth':truth,'oracle':oracle,
            'pair':pair,'kind':label,'probes':probes}


def source_evidence(w,db,*,limit=4):
    """Acquire source observations actively WITHOUT knowing target parameters."""
    journal=DurableGraphBudget(db,w['id']+':source')
    known=[]
    for turn in range(limit):
        ids=survivor_ids(known)
        if len(ids)==1:
            candidate=ALL[ids[0]]
            if proof(candidate,known)['status'] == 'underidentified':
                question=challenge(candidate,[g for g,_ in known])
            else:break
        else:
            question=select(ids,[g for g,_ in known],mode='active',seed=SEED+turn)
        if question is None:break
        receipt,answer=purchase(journal,'diagnosis' if turn==0 else 'repair',question,w['oracle'])
        known.append((question,answer))
    snap=journal.snapshot()
    audit=audit_journal(snap,w['oracle'])
    return known,{'source_purchased':snap['purchased'],
                  'source_replayed':audit['auditor_oracle_calls'],
                  'source_graph_cost':snap['query_cost_totals']}


def challenge(candidate,seen):
    if candidate[0]=='pair-affine':
        route_words=candidate[1]
        for tolls in ((0,8),(7,1),(2,10),(11,0)):
            g=graph_from_routes(route_words,tolls)
            if all(tuple(sorted(map(tuple,g['edges']))) != tuple(sorted(map(tuple,q['edges']))) for q in seen):
                return g
    else:
        for toll in (9,2,10):
            g=graph_from_routes([candidate[1][0]],[toll])
            if all(tuple(sorted(map(tuple,g['edges']))) != tuple(sorted(map(tuple,q['edges']))) for q in seen):
                return g
    return None


def evaluate(w,source,db,mode,*,include_program=False):
    allowed=None if mode!='legacy' else tuple(ALL.index(c) for c in LEGACY)
    journal=DurableGraphBudget(db,w['id']+':'+mode)
    known=list(source)
    selected=None
    challenge_pass=None
    for turn in range(4):
        ids=survivor_ids(known,allowed)
        if not ids:break
        if len(ids)==1:
            candidate=ALL[ids[0]]
            if (mode in ('affine-verified','affine-challenge') and
                    proof(candidate,known)['status']=='underidentified'):
                question=challenge(candidate,[g for g,_ in known])
            else:break
        else:
            question=select(ids,[g for g,_ in known],mode='active',seed=SEED+turn)
        if question is None:break
        receipt,answer=purchase(journal,'diagnosis' if turn==0 else 'qualification',question,w['oracle'])
        if turn==0:journal.reuse(receipt,'repair')
        known.append((question,answer))
    ids=survivor_ids(known,allowed)
    if len(ids)==1:
        chosen=ALL[ids[0]]
        proved=proof(chosen,known)['status']!='underidentified'
        if mode in ('affine-naive','legacy') or proved:
            if mode=='affine-challenge':
                if journal.snapshot()['remaining']>0:
                    query=challenge(chosen,[g for g,_ in known])
                    if query is not None:
                        _,y=purchase(journal,'qualification',query,w['oracle'])
                        known.append((query,y))
                        challenge_pass=(graph_score(query,chosen)==y)
                        if challenge_pass:selected=chosen
                # Deliberate abstention if challenge cannot be bought.
            else:selected=chosen
    snap=journal.snapshot()
    replay=audit_journal(snap,w['oracle'])
    # Predict only on the candidate set; if challenge falsified, do not rescue
    # score by taking a new version space on held-out probes.
    models=[ALL[i] for i in ids]
    # Distinguish diagnostic consensus from *accepted* prediction coverage.
    # An abstained world contributes ZERO accepted predictions even if an
    # underidentified version space happens to agree on its probes.
    consensus_coverage=consensus_errors=0
    for graph in w['probes']:
        outputs={graph_score(graph,c) for c in models}
        if len(outputs)==1 and models:
            consensus_coverage+=1
            consensus_errors+=int(next(iter(outputs))!=w['oracle'](graph))
    coverage=6 if selected is not None else 0
    wrong_probes=(sum(graph_score(g,selected)!=w['oracle'](g)
                      for g in w['probes']) if selected is not None else 0)
    exact=selected==w['truth']
    result={'id':w['id'],'mode':mode,'kind':w['kind'],
            'initial_source_labels':len(source),'target_purchased':snap['purchased'],
            'target_replayed':replay['auditor_oracle_calls'],
            'target_graph_cost':snap['query_cost_totals'],
            'survivors':len(ids),'accepted':int(selected is not None),
            'exact':int(bool(exact and selected is not None)),
            'wrong_accepted':int(selected is not None and not exact),
            'covered':coverage,'probe_errors':wrong_probes,
            'diagnostic_consensus_covered':consensus_coverage,
            'diagnostic_consensus_errors':consensus_errors,
            'challenge_pass':challenge_pass}
    if include_program:
        result['selected_program']=selected
    return result


def study(*,indices=(0,1,2,3,4,5,6,7),operators=None):
    if operators is None:operators=COEFFICIENTS+OUTSIDERS
    rows=[];sources=[]
    with tempfile.TemporaryDirectory(prefix='ace-e14v-development-') as temp:
        db=Path(temp)/'journals.sqlite'
        for index in indices:
            for op in operators:
                w=world(index,op)
                known,source_cost=source_evidence(w,db)
                sources.append({'id':w['id'],**source_cost})
                for mode in MODES:
                    rows.append(evaluate(w,known,db,mode))
    summary={}
    for mode in MODES:
        selected=[r for r in rows if r['mode']==mode]
        summary[mode]={k:sum(row[k] for row in selected) for k in
                      ('initial_source_labels','target_purchased','target_replayed',
                       'accepted','exact','wrong_accepted','covered','probe_errors')}
        summary[mode]['arms']=len(selected)
    return {'status':'E14V_PUBLIC_EXPLORATORY_ONLY',
            'scientific_decision':'NOT_ASSESSED','seed':SEED,
            'operator_formula':'a*min + b*max, a,b inferred, integers 0..3',
            'scope':'historical motif pairs; source cost recorded; oracle in process',
            'worlds':len(sources),'arms':len(rows),'summary':summary,
            'source':sources,'rows':rows}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--indices',type=int,default=8)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    report=study(indices=range(a.indices))
    encoded=json.dumps(report,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    digest=hashlib.sha256(encoded).hexdigest()
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps({**report,'sha256':digest},sort_keys=True,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'worlds':report['worlds'],
                      'arms':report['arms'],'summary':report['summary'],'sha256':digest},sort_keys=True))

if __name__=='__main__':main()
