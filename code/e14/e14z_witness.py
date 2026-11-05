"""Hindsight legal graph witnesses for negative transfer under semantic drift.

No intervention is purchased in the original E1.4z target ledger: all graphs
are postscore auditor counterfactuals. Do not report them as online policy.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from .e14_shared_budget import BudgetContractError
from .e14y_bank import canonical,digest
from .e14y_induction import grammar
from .e14y_study import source_learn
from .e14y_witness import discover_one
from .e14z_drift import bank,source_row,target_row
from .e14z_audit import read_scores


def collect(paths):
    b,results,_,_=read_scores(paths)
    witnesses=[]
    with tempfile.TemporaryDirectory(prefix='ace-e14z-witness-') as tmp:
        folder=Path(tmp)
        for item in b['rows']:
            source=source_learn(source_row(item),folder)
            for drift in ('near','far'):
                target=target_row(item,drift)
                truth=grammar()[target['program_id']]
                for row in results:
                    if row['source_world']==item['id'] and row['drift_type']==drift and row['wrong_accepted']==1:
                        witness=discover_one(row,source,truth)
                        witness['drift_type']=drift
                        witness['source_program_id']=item['source_program_id']
                        witness['target_program_id']=target['program_id']
                        witnesses.append(witness)
    if len(witnesses)!=sum(row['wrong_accepted'] for row in results):
        raise BudgetContractError('not all false acceptances were falsified')
    summary={drift:{'false_acceptance_witnesses':sum(x['drift_type']==drift for x in witnesses),
                    'unused_target_query_witnesses':sum(x['drift_type']==drift and x['witness_in_unused_target_query_domain'] for x in witnesses)}
             for drift in ('near','far')}
    return {'version':1,'status':'POSTSCORE_DRIFT_COUNTEREXAMPLES',
            'scientific_decision':'NOT_ASSESSED','bank_sha256':digest(b),
            'false_acceptances_proved':len(witnesses),
            'additional_auditor_oracle_calls':len(witnesses),
            'additional_purchased_target_labels':0,
            'summary':summary,'cases':witnesses,
            'warning':'hindsight adversarial oracle probes, NOT online detection or new target labels'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('reports',nargs='+',type=Path)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    r=collect(a.reports)
    r['sha256']=hashlib.sha256(canonical(r)).hexdigest()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in r.items() if k!='cases'},sort_keys=True))

if __name__=='__main__':main()
