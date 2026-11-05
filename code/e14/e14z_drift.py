"""ACE E1.4z: prospective negative-transfer stress without changing E1.4y.

Source operator is learned from THREE other motif-pair tasks; target operator
has changed, by minimal vs maximal semantic-signature distance. The runner
uses identical E1.4y policy code, budgets and heldout-query split. This is a
public same-author precommitted development study, not independent science.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import random
import tempfile
from pathlib import Path
from .e14_shared_budget import BudgetContractError
from .e14y_bank import build as prior_bank,canonical,digest
from .e14y_induction import grammar
from .e14y_study import source_learn,run_arm,MODES

SEED=202611051639
TARGET_PAIRS=(18,22)


def mismatches(a,b):
    return sum(x!=y for x,y in zip(grammar()[a][2],grammar()[b][2]))


def bank():
    old={r['program_id'] for r in prior_bank()['rows'] if r['program_id'] is not None}
    g=grammar();rng=random.Random(SEED)
    residuals=[i for i,item in enumerate(g) if item[0]=='residual' and i not in old]
    thresholds=[i for i,item in enumerate(g) if item[0]=='threshold' and i not in old]
    chosen=sorted(rng.sample(residuals,10))+sorted(rng.sample(thresholds,10))
    rows=[]
    for j,i in enumerate(chosen):
        others=[k for k in range(len(g)) if k!=i]
        near=min(others,key=lambda k:(mismatches(i,k),k))
        far=max(others,key=lambda k:(mismatches(i,k),-k))
        rows.append({'id':f'z:{j:03d}','source_program_id':i,
                     'near_target_program_id':near,'far_target_program_id':far,
                     'near_disagreements':mismatches(i,near),
                     'far_disagreements':mismatches(i,far)})
    return {'version':1,'status':'PUBLIC_PRESCORE_NEGATIVE_TRANSFER',
            'seed':SEED,'previous_score_operator_ids_excluded':True,
            'source_pair_indices':(0,5,10),'target_pair_indices':TARGET_PAIRS,
            'drift_types':('near','far'),'modes':MODES,
            'rows':rows,'expected_arms':len(rows)*2*2*len(MODES)}


def source_row(entry):
    src=entry['source_program_id']
    return {'id':entry['id'],'family':grammar()[src][0],
            'program_id':src,'outsider':None}


def target_row(entry,drift):
    if drift not in ('near','far'):raise BudgetContractError('invalid drift mode')
    idx=entry[f'{drift}_target_program_id']
    # run_arm derives deterministic IDs from row['id'][2:] and scopes journal
    # with row['id']; use stable digits and mutually distinct identifiers.
    serial=int(entry['id'][2:])*2+int(drift=='far')
    return {'id':f'z:{serial:04d}','family':grammar()[idx][0],
            'program_id':idx,'outsider':None}


def study(b,*,indices=None):
    if canonical(b)!=canonical(bank()):raise BudgetContractError('prescore drift bank changed')
    if indices is None:indices=range(len(b['rows']))
    sources=[];arms=[]
    with tempfile.TemporaryDirectory(prefix='ace-e14z-drift-') as temp:
        root=Path(temp)
        for n in indices:
            item=b['rows'][n]
            src=source_learn(source_row(item),root)
            sources.append({'source_world':item['id'],'source_program_id':item['source_program_id'],
                            'source_labels':src['source_purchased'],
                            'source_replayed':sum(x['replay'] for x in src['source']),
                            'source_unique':int(src['inferred_id'] is not None)})
            for drift in ('near','far'):
                target=target_row(item,drift);truth=grammar()[target['program_id']]
                for pair_idx in TARGET_PAIRS:
                    for mode in MODES:
                        row=run_arm(target,truth,src,pair_idx,mode,root)
                        row.update({'drift_type':drift,'source_world':item['id'],
                                    'source_program_id':item['source_program_id'],
                                    'target_program_id':target['program_id'],
                                    'semantic_signature_disagreements':item[f'{drift}_disagreements']})
                        arms.append(row)
    summary={}
    for drift in ('near','far'):
        summary[drift]={}
        for mode in MODES:
            group=[r for r in arms if r['mode']==mode and r['drift_type']==drift]
            summary[drift][mode]={k:sum(r[k] for r in group) for k in
                ('accepted','exact','wrong_accepted','abstain','target_labels',
                 'target_replayed','accepted_probes','probe_errors')}
            summary[drift][mode]['arms']=len(group)
    return {'version':1,'status':'PUBLIC_NEGATIVE_TRANSFER_POSTPRESCORE',
            'scientific_decision':'NOT_ASSESSED',
            'bank_sha256':digest(b),'source_operator_count':len(sources),
            'target_worlds':len(sources)*len(TARGET_PAIRS)*2,
            'arm_count':len(arms),
            'source_labels':sum(s['source_labels'] for s in sources),
            'source_replayed':sum(s['source_replayed'] for s in sources),
            'summary':summary,'sources':sources,'rows':arms,
            'scope_limitations':['same-author synthetic grammar and prescore bank',
            'the operator drift is purposely introduced by researcher',
            'transfer source labels counted and reused across four target tasks',
            'no model-level autonomous semantic novelty or native Bubblewrap certification']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bank',type=Path,required=True)
    p.add_argument('--start',type=int,default=0)
    p.add_argument('--end',type=int,default=20)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    raw=json.loads(args.bank.read_text())
    if not 0<=args.start<args.end<=len(raw['rows']):raise SystemExit('invalid batch range')
    result=study(raw,indices=range(args.start,args.end))
    result['sha256']=hashlib.sha256(canonical(result)).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','sources')},sort_keys=True))

if __name__=='__main__':main()
