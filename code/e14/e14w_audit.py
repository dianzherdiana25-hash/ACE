"""Independent E1.4w postscore audit (development, NOT external acceptance).

Reconstructs source and target oracles with the historical DFS graph walker,
interprets expression trees through a separate evaluator, validates complete
SQLite receipt snapshots and recomputes all six graph probes per arm. Never
alters or calibrates original policies based on score results.
"""
from __future__ import annotations
import argparse
from collections import Counter
import glob
import hashlib
import json
from pathlib import Path

from .e14p_graph import paths
from .e14_shared_budget import SharedLabelBudget,BudgetContractError
from .e14_integrated_graph import graph_cost
from .e14u_primitive import PAIR_SPACE
from .e14w_synthesis import library,render,GRID
from .e14w_study import world,MODES,CANARY,NEIGHBOR


def contains(events,motif):
    n=len(motif)
    return any(tuple(events[i:i+n])==tuple(motif) for i in range(len(events)-n+1))


def route_pairs(graph,pair):
    routes=paths(graph)
    return tuple(sorted({(min(c1,c2),max(c1,c2))
                         for i,(e1,c1) in enumerate(routes)
                         for j,(e2,c2) in enumerate(routes)
                         if i!=j and contains(e1,pair[0]) and contains(e2,pair[1])}))


def alternate_eval(tree,lo,hi):
    """Iterative stack interpreter independent of e14w_synthesis.evaluate."""
    stack=[(tree,False)];vals=[]
    while stack:
        node,done=stack.pop();op=node[0]
        if op=='lo':vals.append(lo);continue
        if op=='hi':vals.append(hi);continue
        if op=='const':vals.append(node[1]);continue
        if not done:
            stack.append((node,True));stack.append((node[2],False));stack.append((node[1],False));continue
        b=vals.pop();a=vals.pop()
        if op=='add':vals.append(a+b)
        elif op=='mul':vals.append(a*b)
        elif op=='min':vals.append(min(a,b))
        elif op=='max':vals.append(max(a,b))
        else:raise BudgetContractError('invalid independent expression')
    if len(vals)!=1:raise BudgetContractError('invalid expression stack')
    return vals[0]


def alternate_score(graph,pair,formula):
    if formula=='source-max':fn=max
    elif formula in ('difference','offset-3','saturated-difference','half-hi',
                    'three-lo-two-hi','two-lo-three-hi','square-sum','floor-mean',
                    'gap-parity','switch-gap','quadratic-mix','clamped-sum',
                    'gap-mod3','lo-parity','hi-parity','upper-threshold',
                    'gap-mod4','clamped-product','odd-weighted','piecewise-product'):
        if formula=='difference':fn=lambda a,b:b-a
        elif formula=='offset-3':fn=lambda a,b:a+b+3
        elif formula=='saturated-difference':fn=lambda a,b:min(7,b-a)
        elif formula=='half-hi':fn=lambda a,b:a+b//2
        elif formula=='three-lo-two-hi':fn=lambda a,b:3*a+2*b
        elif formula=='two-lo-three-hi':fn=lambda a,b:2*a+3*b
        elif formula=='square-sum':fn=lambda a,b:a*a+b*b
        elif formula=='floor-mean':fn=lambda a,b:(a+b)//2
        elif formula=='gap-parity':fn=lambda a,b:a+b+((b-a)%2)
        elif formula=='switch-gap':fn=lambda a,b:a+b if b-a<5 else b
        elif formula=='quadratic-mix':fn=lambda a,b:a*b+a*a+1
        elif formula=='clamped-sum':fn=lambda a,b:min(24,a+b)
        elif formula=='gap-mod3':fn=lambda a,b:a+b+((b-a)%3)
        elif formula=='lo-parity':fn=lambda a,b:a+b+(a%2)
        elif formula=='hi-parity':fn=lambda a,b:a+b+(b%2)
        elif formula=='upper-threshold':fn=lambda a,b:a+b+int(b>=15)
        elif formula=='gap-mod4':fn=lambda a,b:a+b+((b-a)%4)
        elif formula=='clamped-product':fn=lambda a,b:min(a*b,200)
        elif formula=='odd-weighted':fn=lambda a,b:a*(1+(b%2))+b
        else:fn=lambda a,b:(a*b if b-a<=4 else a+b)
    else:
        ast=next((p for p in library(5) if render(p)==formula),None)
        if ast is None:raise BudgetContractError('unknown scored grammar formula')
        fn=lambda a,b:alternate_eval(ast,a,b)
    costs=route_pairs(graph,pair)
    return min((fn(lo,hi) for lo,hi in costs),default=None)


def validate_receipts(snapshot,pair,formula):
    book=SharedLabelBudget.from_snapshot(snapshot)
    book.assert_complete()
    calls=0
    for receipt in snapshot['receipts']:
        query=receipt['query']
        if receipt['cost']!=graph_cost(query):
            raise BudgetContractError('forged graph topology cost')
        label=alternate_score(query,pair,formula)
        if type(label) is not type(receipt['label']) or label!=receipt['label']:
            raise BudgetContractError('independent oracle mismatch')
        calls+=1
    return calls


def audit_files(paths):
    reports=[];seen=set();source_calls=target_calls=probe_calls=0
    source_costs=Counter();target_costs=Counter();scores=Counter();by_mode={}
    semantic_disagreements=0
    for path in sorted(paths):
        with open(path,encoding='utf-8') as file:r=json.load(file)
        supplied=r.pop('sha256',None)
        raw=json.dumps(r,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        if supplied!=hashlib.sha256(raw).hexdigest():
            raise BudgetContractError('batch SHA-256 mismatch')
        if r['status']!='PUBLIC_DEVELOPMENT_ONLY' or r['scientific_decision']!='NOT_ASSESSED':
            raise BudgetContractError('invalid evidence state')
        modes=tuple(r.get('modes',MODES))
        if not modes or len(set(modes))!=len(modes) or any(m not in (*MODES,CANARY,NEIGHBOR) for m in modes):
            raise BudgetContractError('invalid claimed strategy set')
        if r['arm_count']!=len(r['rows']) or r['worlds']*len(modes)!=len(r['rows']):
            raise BudgetContractError('incomplete world × policy block')
        source_map={s['index']:s for s in r['sources']}
        for idx,s in source_map.items():
            if idx in seen:raise BudgetContractError('duplicate source pair')
            seen.add(idx)
            observed=validate_receipts(s['source_journal'],PAIR_SPACE[idx],'source-max')
            if observed!=s['source_labels'] or observed!=s['source_replay']:
                raise BudgetContractError('source accounting mismatch')
            if s['correct'] and s['pair_learned'] is None:
                raise BudgetContractError('false source success')
            if s['pair_learned'] is not None and tuple(map(tuple,s['pair_learned']))!=PAIR_SPACE[idx]:
                if s['correct']:raise BudgetContractError('forged claimed lineage')
            source_calls+=observed
            source_costs.update(s['source_journal']['query_cost_totals'])
        group=Counter()
        for row in r['rows']:
            tokens=row['id'].split(':',2)
            if len(tokens)!=3 or int(tokens[1]) not in source_map:
                raise BudgetContractError('unexpected arm linkage')
            idx=int(tokens[1]);formula=tokens[2]
            if row['mode'] not in modes:raise BudgetContractError('unexpected strategy')
            key=(row['id'],row['mode'])
            group[key]+=1
            truth=world(idx, next((i for i,p in enumerate(library(5)) if render(p)==formula),formula))
            if row['in_family']!=truth['in_family']:
                raise BudgetContractError('mislabelled grammar family')
            source=source_map[idx]
            pair=(PAIR_SPACE[idx] if row['mode']=='known-pair-upper' else
                  PAIR_SPACE[(idx+1)%len(PAIR_SPACE)] if row['mode']=='sham-pair' else
                  tuple(map(tuple,source['pair_learned'])) if source['pair_learned'] is not None else None)
            bought=validate_receipts(row['target_journal'],PAIR_SPACE[idx],formula)
            if bought!=row['target_labels'] or bought!=row['target_replays'] or bought>4:
                raise BudgetContractError('target cap/accounting violation')
            target_calls+=bought;target_costs.update(row['target_journal']['query_cost_totals'])
            selected=row['selected_expr']
            accepted=selected is not None
            if row['accepted']!=int(accepted) or row['abstain']!=int(not accepted):
                raise BudgetContractError('accepted/abstention mismatch')
            if selected is not None:
                ast=next((p for p in library(5) if render(p)==selected),None)
                if ast is None:raise BudgetContractError('selected program not in grammar')
                exact=(pair==PAIR_SPACE[idx] and truth['in_family'] and
                       all(alternate_eval(ast,*costs)==alternate_score(
                          # The independent value at each grid point is simply
                          # evaluated via the truth's public DSL program.
                          __fake_graph(pair,costs),PAIR_SPACE[idx],formula) for costs in GRID))
            else:exact=False
            if row['semantic_exact']!=int(exact) or row['wrong_accepted']!=int(accepted and not exact):
                raise BudgetContractError('wrong exactness/false acceptance claim')
            errs=sum(alternate_score(g,pair,selected)!=alternate_score(g,PAIR_SPACE[idx],formula)
                     for g in truth['probes']) if accepted else 0
            probe_calls+=len(truth['probes'])
            if row['accepted_probes']!=6*int(accepted) or row['probe_errors']!=errs:
                raise BudgetContractError('probe-score mismatch')
            scores[row['mode']+':arms']+=1
            scores[row['mode']+':correct']+=int(exact)
            scores[row['mode']+':wrong']+=int(accepted and not exact)
            scores[row['mode']+':covered']+=row['accepted_probes']
            scores[row['mode']+':errors']+=errs
        if len(group)!=len(r['rows']) or any(c!=1 for c in group.values()):
            raise BudgetContractError('duplicate/missing arm')
        reports.append({'path':Path(path).name,'sha256':supplied,'worlds':r['worlds'],'arms':r['arm_count']})
    return {'status':'POSTSCORE_INDEPENDENT_DEVELOPMENT_AUDIT',
            'scientific_decision':'NOT_ASSESSED','batches':len(reports),
            'pair_sources':len(seen),'source_oracle_replay':source_calls,
            'target_oracle_replay':target_calls,'probe_oracle_calls':probe_calls,
            'source_cost':dict(source_costs),'target_cost':dict(target_costs),
            'policy_summary':dict(scores),'files':reports}


def __fake_graph(pair,costs):
    """Construct independent costs via two-route witness, used only for audit."""
    from .e14u_primitive import graph_from_routes
    lo,hi=costs
    return graph_from_routes(pair,(lo-4,hi-4))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('reports',nargs='+')
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    report=audit_files(args.reports)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='files'},sort_keys=True))

if __name__=='__main__':main()
