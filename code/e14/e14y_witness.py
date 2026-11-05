"""Postscore counterexample generator for ALL actually accepted wrong E1.4y arms.

Each witness graph is chosen AFTER scoring, is not a target-budget purchase,
and cannot be used to revise locked scores. This diagnoses finite-grammar
false acceptance and missed distinctions; it does not prove OOD detection.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from .e14_shared_budget import BudgetContractError,SharedLabelBudget
from .e14u_primitive import PAIR_SPACE
from .e14w_synthesis import GRID,library as old_library,evaluate as old_eval
from .e14y_bank import build,canonical,digest
from .e14y_induction import grammar,GRID_INDEX,value_at
from .e14y_study import truth_of,source_learn,question,independent_oracle
from .e14y_audit import reconstruct,unpack_costs


def discover_one(row,source,truth):
    if type(row) is not dict or row.get('wrong_accepted')!=1:
        raise BudgetContractError('witness only for false accepted arms')
    pair=PAIR_SPACE[row['target_pair']]
    checked,selected=reconstruct(row,source,truth,pair,include_candidate=True)
    if selected is None:raise BudgetContractError('accepted arm lost candidate')
    used={unpack_costs(r['query'],pair) for r in row['target_journal']['receipts']}
    def predicted(xy):
        if selected[0]=='new':return grammar()[selected[1]][2][GRID_INDEX[xy]]
        return old_eval(old_library(5)[selected[1]],*xy)
    possible=[xy for xy in GRID if xy not in used and predicted(xy)!=value_at(truth,xy)]
    if not possible:raise BudgetContractError('false acceptance has no separating unpurchased query')
    # Prioritize a legal target purchase that the learner could still have bought.
    from .e14y_study import TARGET_QUERY_GRID
    potential=[xy for xy in possible if xy in TARGET_QUERY_GRID]
    witness=potential[0] if potential else possible[0]
    graph=question(pair,witness)
    actual=independent_oracle(graph,pair,truth)
    yhat=predicted(witness)
    if actual==yhat or actual!=value_at(truth,witness):
        raise BudgetContractError('invalid counterexample verification')
    graph_raw=canonical(graph)
    return {'world':row['world'],'mode':row['mode'],'target_pair':row['target_pair'],
            'label_purchases_before_witness':len(used),
            'witness_in_unused_target_query_domain':witness in TARGET_QUERY_GRID,
            'witness_cost_coordinates':list(witness),
            'witness_graph':graph,
            'witness_graph_sha256':hashlib.sha256(graph_raw).hexdigest(),
            'hypothesis_cost':yhat,'oracle_cost':actual,
            'difference':actual-yhat,'counterexample_postscore_only':True,
            'no_frozen_target_label_was_purchased':True}


def collect(paths):
    bank=build();sources={};arms=[]
    for p in paths:
        raw=json.loads(Path(p).read_bytes())
        expected=raw.pop('sha256',None)
        if hashlib.sha256(canonical(raw)).hexdigest()!=expected:
            raise BudgetContractError('tampered input score report')
        if raw['bank_sha256']!=digest(bank):raise BudgetContractError('mismatched locked bank')
        sources.update((x['id'],x) for x in raw['sources'])
        arms.extend(raw['rows'])
    if len(arms)!=400 or len(sources)!=40:
        raise BudgetContractError('missing target arm or source')
    outputs=[];cases_by_mode={}
    with tempfile.TemporaryDirectory(prefix='ace-e14y-witness-') as folder:
        home=Path(folder)
        for row_def in bank['rows']:
            source=source_learn(row_def,home)
            for row in (a for a in arms if a['world']==row_def['id'] and a['wrong_accepted']==1):
                cert=discover_one(row,source,truth_of(row_def));outputs.append(cert)
                cases_by_mode[row['mode']]=cases_by_mode.get(row['mode'],0)+1
    if len(outputs)!=sum(x['wrong_accepted'] for x in arms):
        raise BudgetContractError('some wrong accepted cases have no witness')
    return {'version':1,'status':'POSTSCORE_ADVERSARIAL_COUNTEREXAMPLES',
            'scientific_decision':'NOT_ASSESSED','bank_sha256':digest(bank),
            'wrong_accepts_falsified':len(outputs),
            'target_legal_unused_witnesses':sum(x['witness_in_unused_target_query_domain'] for x in outputs),
            'extra_auditor_oracle_calls':len(outputs),
            'purchased_target_labels_added':0,
            'by_mode':cases_by_mode,'cases':outputs,
            'warning':'hindsight witnesses, not unbiased target actions or a tuned new policy'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reports',nargs='+',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    a=parser.parse_args()
    r=collect(a.reports);r['sha256']=hashlib.sha256(canonical(r)).hexdigest()
    a.output.parent.mkdir(exist_ok=True,parents=True)
    a.output.write_text(json.dumps(r,sort_keys=True,indent=2)+'\n')
    print(json.dumps({k:v for k,v in r.items() if k!='cases'},sort_keys=True))

if __name__=='__main__':main()
