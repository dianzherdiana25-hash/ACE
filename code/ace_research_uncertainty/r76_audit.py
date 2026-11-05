"""JSON-only R7.6 result auditor. Does not import or rerun the evaluator."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

FAMILIES=('stable','swap','reverse','new01','new23','all_null','correlated','near_boundary')
SEEDS=(20261112,20261113,20261114,20261115)
CAPS=(0,6,12,18,24)
METHODS=('narrow6','full12','broad6','adaptive10','random6','abstain6')

def audit(raw:bytes)->dict:
    x=json.loads(raw)
    errors=[];checks=0;arms=0
    def ck(v,reason):
        nonlocal checks
        checks+=1
        if not v: errors.append(reason)
    ck(x.get('classification')=='PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY','class')
    ck(x.get('protocol')=='R76_PROTOCOL.md','protocol')
    ck(x.get('offline_train_labels')==1296,'offline cost')
    ck(tuple(x.get('seeds',()))==SEEDS,'seed set')
    ck(set(x.get('results',()))==set(FAMILIES),'family set')
    ck(set(x.get('split_id_hashes',()))==set(FAMILIES),'manifest')
    manifest=[]
    for family in FAMILIES:
        ck(set(x['results'][family])=={str(s) for s in SEEDS},f'{family} seeds')
        ck(set(x['split_id_hashes'][family])=={str(s) for s in SEEDS},f'{family} manifest')
        for seed in SEEDS:
            manifest.append(x['split_id_hashes'][family][str(seed)])
            per_seed=x['results'][family][str(seed)]
            ck(set(per_seed)=={str(c) for c in CAPS},f'{family}/{seed} caps')
            for cap in CAPS:
                rows=per_seed[str(cap)]
                ck(set(rows)==set(METHODS),f'{family}/{seed}/{cap} methods')
                for method in METHODS:
                    r=rows[method];arms+=1
                    prefix=f'{family}/{seed}/{cap}/{method}'
                    ck(r['tasks']==20 and r['cap']==cap,prefix+' metadata')
                    ck(type(r['purchases']) is int and 0<=r['purchases']<=20*cap,prefix+' cap')
                    ck(all(type(r[k]) is int and r[k]>=0 for k in ('true_accepts','false_accepts','abstentions')),prefix+' outcomes')
                    ck(r['true_accepts']+r['false_accepts']+r['abstentions']==120,prefix+' disjoint')
                    ck(r['certified_tasks']==r['true_accepts']+r['false_accepts'] and r['certified_tasks']<=20,prefix+' certificate')
                    ck(r['diagnostic_labels']+r['certificate_labels']==r['purchases'],prefix+' purchases')
                    ck(r['utility']==20*r['true_accepts']-60*r['false_accepts']-2*r['abstentions']-r['purchases'],prefix+' utility')
                    ck(0<=r['ece']<=1 and 0<=r['brier']<=1,prefix+' score bounds')
                    accepted=r['true_accepts']+r['false_accepts']
                    ck(r['false_acceptance_rate'] == (round(r['false_accepts']/accepted,6) if accepted else None),prefix+' false rate')
                    ck(r['correct_per_100_labels']==(round(100*r['true_accepts']/r['purchases'],6) if r['purchases'] else None),prefix+' efficiency')
                    ck(set(r['selected_groups'])=={str(g) for g in range(6)},prefix+' histogram')
                    ck(sum(r['selected_groups'].values())<=20,prefix+' selected cap')
                    if cap==0:
                        ck(r['purchases']==0 and accepted==0,prefix+' zero cap')
                    if method=='abstain6':
                        ck(accepted==0 and r['purchases']==20*min(cap,6),prefix+' abstain control')
                    if method=='adaptive10' and cap>=10:
                        ck(r['diagnostic_labels']==20*10,prefix+' adaptive diagnostic cost')
                    if method=='narrow6' and cap>=6:
                        ck(r['diagnostic_labels']==20*6,prefix+' narrow diagnostic cost')
                    if method=='full12' and cap>=12:
                        ck(r['diagnostic_labels']==20*12,prefix+' full diagnostic cost')
    ck(len(manifest)==len(set(manifest)),'split disjoint hashes')
    ck(all(x['oracle_ceiling_eval_only'][f][str(s)]==0 for f in ('all_null',) for s in SEEDS),'null ceiling')
    def sumf(f,m,k):return sum(x['results'][f][str(s)]['24'][m][k] for s in SEEDS)
    core=('stable','swap','reverse','new01','new23')
    risk=core+('all_null','near_boundary')
    computed={
        'new23_exceeds_narrow':sumf('new23','adaptive10','true_accepts')>sumf('new23','narrow6','true_accepts'),
        'stable_coverage_and_safety':sumf('stable','adaptive10','true_accepts')>=.8*sumf('stable','full12','true_accepts') and sumf('stable','adaptive10','false_accepts')<=sumf('stable','full12','false_accepts'),
        'risk_not_higher':sum(sumf(f,'adaptive10','false_accepts') for f in risk)<=sum(sumf(f,'full12','false_accepts') for f in risk),
        'utility_at_least_full':sum(sumf(f,'adaptive10','utility') for f in core)>=sum(sumf(f,'full12','utility') for f in core),
        'utility_at_least_broad':sum(sumf(f,'adaptive10','utility') for f in core)>=sum(sumf(f,'broad6','utility') for f in core),
        'budget_and_certificate':all(x['results'][f][str(s)][str(c)][m]['purchases']<=c*20 and x['results'][f][str(s)][str(c)][m]['certified_tasks']<=20 for f in FAMILIES for s in SEEDS for c in CAPS for m in METHODS),
    }
    ck(computed==x['gate'],'locked gate replay')
    ck(x['gate_pass']==all(computed.values()),'pass status')
    totals={m:{k:sum(sumf(f,m,k) for f in core) for k in ('true_accepts','false_accepts','purchases','utility')} for m in METHODS}
    return {'status':'PASS' if not errors else 'FAIL','failed':len(errors),'errors':errors[:30],
            'checks':checks,'arms':arms,'sha256':hashlib.sha256(raw).hexdigest(),
            'bytes':len(raw),'gate':computed,'core_totals':totals,'scoring_rerun':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('path',type=Path);a=p.parse_args()
    result=audit(a.path.read_bytes())
    print(json.dumps(result,indent=2,sort_keys=True))
    raise SystemExit(0 if result['status']=='PASS' else 2)

if __name__=='__main__':main()
