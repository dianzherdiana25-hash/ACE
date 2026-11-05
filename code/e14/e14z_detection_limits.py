"""Exact random-query miss probabilities for near/far semantic drift.

This is a postscore analytical diagnostic, not a new scored policy and not a
claim of transfer safety. The distribution is finite uniform sampling without
replacement from the original fixed 66-point legal intervention domain.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from math import comb
from pathlib import Path
from .e14_shared_budget import BudgetContractError
from .e14y_bank import canonical,digest
from .e14y_induction import grammar,GRID_INDEX
from .e14y_study import TARGET_QUERY_GRID
from .e14z_drift import bank
from .e14z_audit import read_scores


def miss_probability(disagreements,purchases,domain=66):
    if (any(type(x) is not int for x in (disagreements,purchases,domain)) or
        not 0<=disagreements<=domain or not 0<=purchases<=domain):
        raise BudgetContractError('invalid hypergeometric parameters')
    if domain-disagreements<purchases:return 0.0
    return comb(domain-disagreements,purchases)/comb(domain,purchases)


def limits(paths):
    b,rows,sources,_=read_scores(paths)
    by_key={(r['source_world'],r['drift_type'],r['target_pair'],r['mode']):r for r in rows}
    summaries={}
    cases=[]
    for drift in ('near','far'):
        results={'source_operator_count':len(b['rows']),
                 'target_worlds':len(b['rows'])*2,
                 'expected_false_accepts_random_2':0.0,
                 'expected_false_accepts_random_4':0.0,
                 'actual_false_accepts_random_2':0,
                 'legal_query_disagreement_points_min':999,
                 'legal_query_disagreement_points_max':0,
                 'target_worlds_with_no_query_distinction':0}
        for x in b['rows']:
            a=grammar()[x['source_program_id']][2]
            t=grammar()[x[f'{drift}_target_program_id']][2]
            mismatch=sum(a[GRID_INDEX[xy]]!=t[GRID_INDEX[xy]] for xy in TARGET_QUERY_GRID)
            results['legal_query_disagreement_points_min']=min(results['legal_query_disagreement_points_min'],mismatch)
            results['legal_query_disagreement_points_max']=max(results['legal_query_disagreement_points_max'],mismatch)
            results['target_worlds_with_no_query_distinction']+=2*int(mismatch==0)
            for target_idx in b['target_pair_indices']:
                r=by_key[(x['id'],drift,target_idx,'transfer-verify2')]
                results['expected_false_accepts_random_2']+=miss_probability(mismatch,2)
                results['expected_false_accepts_random_4']+=miss_probability(mismatch,4)
                results['actual_false_accepts_random_2']+=r['wrong_accepted']
                cases.append({'source_world':x['id'],'drift':drift,'target_pair':target_idx,
                              'disagreement_points':mismatch,
                              'miss_probability_two_random_queries':miss_probability(mismatch,2),
                              'miss_probability_four_random_queries':miss_probability(mismatch,4),
                              'actual_wrong_accept':r['wrong_accepted']})
        summaries[drift]=results
    return {'version':1,'status':'POSTSCORE_HYPERGEOMETRIC_MISS_ANALYSIS',
            'scientific_decision':'NOT_ASSESSED','bank_sha256':digest(b),
            'target_query_domain_size':len(TARGET_QUERY_GRID),
            'summary':summaries,'cases':cases,
            'warning':'expectations assume uniform random draws, not deterministic future experiment or OOD guarantee'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('reports',nargs='+',type=Path)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    r=limits(a.reports);r['sha256']=hashlib.sha256(canonical(r)).hexdigest()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in r.items() if k!='cases'},sort_keys=True))

if __name__=='__main__':main()
