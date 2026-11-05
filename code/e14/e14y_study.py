"""E1.4y: source-acquired AST operator form transferred to new graph tasks.

Four purchased target labels MAXIMUM per arm, each with durable evaluator
receipt. Three source tasks have their own four-label budgets, all counted.
Candidate synthesis and all questions use only observed source/target values;
hidden program and six target probes are accessible to the trusted evaluator.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import random
import tempfile
from pathlib import Path
from .e14_shared_budget import BudgetContractError
from .e14_integrated_graph import graph_routes, DurableGraphBudget, purchase, audit_journal
from .e14p_graph import paths
from .e14u_primitive import PAIR_SPACE, graph_from_routes
from .e14v_operator import pairs_of
from .e14w_synthesis import GRID, library as old_library, evaluate as old_evaluate
from .e14y_induction import (grammar,candidates,choose_query, GRID_INDEX,
                             OUTSIDERS, value_at,old_signatures)
from .e14y_bank import build,canonical,digest,SEED

TARGET_QUERY_GRID=tuple(xy for xy in GRID if xy[1]<=14)
TARGET_PROBE_GRID=tuple(xy for xy in GRID if xy[1]>=15)
MODES=('transfer-direct','transfer-verify2','cold-new','cold-old','sham-transfer')


def source_oracle(graph,pair,form):
    return min((value_at(form, xy) for xy in pairs_of(graph_routes(graph)[0],pair)),default=None)


def independent_oracle(graph,pair,form):
    # Independent traversal of all paths from historical E1.4p oracle.
    routes=paths(graph);hits=[]
    a,b=pair
    for i,(w1,c1) in enumerate(routes):
        for j,(w2,c2) in enumerate(routes):
            if i==j:continue
            if any(tuple(w1[k:k+len(a)])==a for k in range(len(w1)-len(a)+1)) and any(
                tuple(w2[k:k+len(b)])==b for k in range(len(w2)-len(b)+1)):
                hits.append(value_at(form,(min(c1,c2),max(c1,c2))))
    return min(hits,default=None)


def question(pair,xy):
    lo,hi=xy
    return graph_from_routes(pair,(lo-4,hi-4))


def truth_of(row):
    if row['family']=='unrepresented':return ('unknown',row['outsider'])
    return grammar()[row['program_id']]


def source_learn(row,workdir):
    form=truth_of(row);all_seen=[];source=[]
    bank=build()
    for idx in bank['source_pair_indices']:
        pair=PAIR_SPACE[idx]
        journal=DurableGraphBudget(workdir/f'src_{row["id"]}_{idx}.sqlite',f'{row["id"]}:source:{idx}')
        local=[]
        for turn in range(4):
            ids=candidates(all_seen)
            # When unique, purchase one additional independent audit label in
            # a source task if budget remains (same fixed grid order, no truth).
            if len(ids)==1:
                probe=next((xy for xy in GRID if xy not in {v for v,y in all_seen}),None)
            else:
                probe=choose_query(ids,all_seen,seed=SEED+idx*17+turn)
            if probe is None:break
            graph=question(pair,probe)
            receipt,label=purchase(journal,'diagnosis' if turn==0 else 'repair',graph,
                                   lambda g:source_oracle(g,pair,form))
            assert label is not None
            all_seen.append((probe,label));local.append((probe,label))
            # Stop at one validation after unique: additional source labels
            # would be unneeded if that validation is consistent.
            if len(ids)==1:break
        audit=audit_journal(journal.snapshot(),lambda g:independent_oracle(g,pair,form))
        source.append({'pair_index':idx,'labels':len(local),'replay':audit['auditor_oracle_calls'],
                       'graph_cost':journal.snapshot()['query_cost_totals']})
    ids=candidates(all_seen)
    # Source form may be unique only *conditionally inside finite grammar*.
    inferred=ids[0] if len(ids)==1 else None
    return {'observations':all_seen,'survivors':len(ids), 'inferred_id':inferred,
            'source':source,'source_purchased':sum(x['labels'] for x in source)}


def old_candidates(observed):
    return tuple(i for i,tree in enumerate(old_library(5)) if all(old_evaluate(tree,*xy)==y for xy,y in observed))


def old_question(ids,observed):
    if len(ids)<2:return None
    used={xy for xy,_ in observed};offer=[]
    for xy in TARGET_QUERY_GRID:
        if xy in used:continue
        groups=Counter(old_evaluate(old_library(5)[i],*xy) for i in ids)
        if len(groups)<=1:continue
        offer.append(((sum(v*v for v in groups.values()),max(groups.values()),xy),xy))
    return min(offer)[1] if offer else None


def heldout_probes(row,pair_index):
    # No query-policy state or labels needed. Graphed shared-prefix vs
    # disjoint models can be scored with same independent path oracle.
    from .e14v_topology import fork
    pair=PAIR_SPACE[pair_index];seed=SEED+pair_index*103+int(row['id'][2:])*1009
    rng=random.Random(seed)
    chosen=[]
    selected=rng.sample(TARGET_PROBE_GRID,6)
    for i,(lo,hi) in enumerate(selected):
        tolls=(lo-4,hi-4)
        graph=fork(pair,tolls) if i%2 else graph_from_routes(pair,tolls)
        chosen.append(graph)
    return chosen


def run_arm(row,form,source,target_idx,mode,workdir):
    pair=PAIR_SPACE[target_idx]
    journal=DurableGraphBudget(workdir/f'{row["id"]}_{target_idx}_{mode}.sqlite',
                              f'{row["id"]}:{target_idx}:{mode}')
    seen=[];selected=None
    if mode in ('transfer-direct','transfer-verify2','sham-transfer'):
        src_id=source['inferred_id']
        if mode=='sham-transfer' and src_id is not None:
            src_id=(src_id+37)%len(grammar())
        if src_id is not None:
            tree=grammar()[src_id]
            if mode=='transfer-direct':selected=('new',src_id)
            else:
                # Check two deterministic, label-blind target inputs; do not
                # claim a universal safety guarantee from two agreements.
                rng=random.Random(SEED+target_idx*23+int(row['id'][2:])*31)
                probes=rng.sample(TARGET_QUERY_GRID,2)
                agrees=True
                for i,xy in enumerate(probes):
                    graph=question(pair,xy)
                    _,label=purchase(journal,'qualification',graph,
                                     lambda g:source_oracle(g,pair,form))
                    seen.append((xy,label))
                    if label!=tree[2][GRID_INDEX[xy]]:agrees=False
                if agrees:selected=('new',src_id)
    elif mode in ('cold-new','cold-old'):
        for step in range(4):
            ids=candidates(seen) if mode=='cold-new' else old_candidates(seen)
            if len(ids)==1:
                if len(seen)>=3:
                    selected=('new' if mode=='cold-new' else 'old',ids[0])
                    break
                xy=next((p for p in TARGET_QUERY_GRID if p not in {q for q,_ in seen}),None)
            elif not ids:break
            else:
                xy=choose_query(ids,seen,allowed=TARGET_QUERY_GRID) if mode=='cold-new' else old_question(ids,seen)
            if xy is None:break
            graph=question(pair,xy)
            _,label=purchase(journal,'diagnosis' if step==0 else 'qualification',graph,
                             lambda g:source_oracle(g,pair,form))
            seen.append((xy,label))
        else:
            ids=candidates(seen) if mode=='cold-new' else old_candidates(seen)
            if len(ids)==1 and len(seen)>=3:
                selected=('new' if mode=='cold-new' else 'old',ids[0])
    else:raise BudgetContractError('unknown evaluation mode')
    snap=journal.snapshot()
    aud=audit_journal(snap,lambda g:independent_oracle(g,pair,form))
    actual=tuple(value_at(form,xy) for xy in GRID)
    def inferred(xy):
        if selected is None:return None
        name,idx=selected
        return grammar()[idx][2][GRID_INDEX[xy]] if name=='new' else old_evaluate(old_library(5)[idx],*xy)
    exact=selected is not None and tuple(inferred(xy) for xy in GRID)==actual
    probes=heldout_probes(row,target_idx)
    probe_errors=0
    if selected is not None:
        for graph in probes:
            routepairs=pairs_of(graph_routes(graph)[0],pair)
            predicted=min((inferred(xy) for xy in routepairs),default=None)
            gold=independent_oracle(graph,pair,form)
            probe_errors+=int(predicted!=gold)
    return {'world':row['id'],'family':row['family'],'target_pair':target_idx,
            'mode':mode,'accepted':int(selected is not None),
            'exact':int(exact),'wrong_accepted':int(selected is not None and not exact),
            'abstain':int(selected is None),'target_labels':snap['purchased'],
            'target_replayed':aud['auditor_oracle_calls'],
            'accepted_probes':6*int(selected is not None),'probe_errors':probe_errors,
            'source_label_cost':source['source_purchased'],
            'source_unique':int(source['inferred_id'] is not None),
            'oracle_independent':True,
            'target_journal':snap}


def study(bank,*,indices=None):
    if canonical(bank)!=canonical(build()):
        raise BudgetContractError('public bank has been modified')
    if indices is None:indices=range(len(bank['rows']))
    rows=[];sources=[]
    with tempfile.TemporaryDirectory(prefix='ace-e14y-') as tmp:
        home=Path(tmp)
        for pos in indices:
            row=bank['rows'][pos];form=truth_of(row)
            state=source_learn(row,home)
            sources.append({'id':row['id'],'family':row['family'],'source_labels':state['source_purchased'],
                            'source_replayed':sum(x['replay'] for x in state['source']),
                            'source_unique':int(state['inferred_id'] is not None),
                            'source_task_labels':[x['labels'] for x in state['source']]})
            for tid in bank['target_pair_indices']:
                for mode in MODES:
                    rows.append(run_arm(row,form,state,tid,mode,home))
    summary={}
    for mode in MODES:
        group=[r for r in rows if r['mode']==mode]
        summary[mode]={name:sum(r[name] for r in group) for name in
                       ('accepted','exact','wrong_accepted','abstain','target_labels',
                        'target_replayed','accepted_probes','probe_errors')}
        summary[mode]['arms']=len(group)
    strata={}
    for family in ('residual','threshold','unrepresented'):
        group=[r for r in rows if r['family']==family]
        strata[family]={m:{k:sum(v[k] for v in group if v['mode']==m)
                            for k in ('accepted','exact','wrong_accepted','target_labels')}
                        for m in MODES}
    return {'status':'PUBLIC_DEVELOPMENT_NOT_SCIENCE','scientific_decision':'NOT_ASSESSED',
            'bank_sha256':digest(bank),'programs_in_grammar':len(grammar()),
            'source_tasks_per_operator':3,'source_labels':sum(x['source_labels'] for x in sources),
            'source_replay':sum(x['source_replayed'] for x in sources),
            'operator_worlds':len(sources),'target_worlds':len(sources)*2,
            'arms':len(rows),'summary':summary,'strata':strata,'sources':sources,'rows':rows,
            'limitations':['researcher-authored finite AST grammar and public bank',
                           'not an independently learned grammar primitive',
                           'target motif pairs supplied and source tasks share truth function',
                           'more source labels in transfer arms; compare total resource cost',
                           'native Bubblewrap not verified']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bank',required=True,type=Path)
    parser.add_argument('--start',default=0,type=int)
    parser.add_argument('--end',default=40,type=int)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    bank=json.loads(args.bank.read_bytes())
    if not 0<=args.start<args.end<=len(bank['rows']):raise SystemExit('invalid interval')
    result=study(bank,indices=range(args.start,args.end))
    raw=canonical(result)
    result['sha256']=hashlib.sha256(raw).hexdigest()
    args.output.parent.mkdir(exist_ok=True,parents=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('sources','rows')},sort_keys=True))

if __name__=='__main__':main()
