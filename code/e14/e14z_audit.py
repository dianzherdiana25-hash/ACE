"""E1.4z after-score receipt, lineage, drift and semantics audit.

No tuning of E1.4y source or E1.4z pre-score bank. Independently replays
purchased target answers against historical E1.4p DFS cost evaluator and
reconstructs every accepted target program and its full 120-point signature.
Source task raw journals are not score-archived; independent new ledger source
replay reconstructs source label counts and operator identities.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from .e14_shared_budget import BudgetContractError
from .e14y_bank import canonical,digest
from .e14y_study import source_learn,MODES
from .e14y_audit import reconstruct
from .e14y_induction import grammar
from .e14u_primitive import PAIR_SPACE
from .e14z_drift import bank,source_row,target_row,TARGET_PAIRS


def read_scores(paths):
    b=bank();results=[];sources=[];seen=set();digests=[]
    for p in paths:
        raw=json.loads(Path(p).read_bytes())
        recorded=raw.pop('sha256',None)
        if hashlib.sha256(canonical(raw)).hexdigest()!=recorded:
            raise BudgetContractError('score batch digest mismatch')
        if raw['bank_sha256']!=digest(b):
            raise BudgetContractError('wrong prescore drift bank')
        for row in raw['rows']:
            key=(row['source_world'],row['drift_type'],row['target_pair'],row['mode'])
            if key in seen:raise BudgetContractError('duplicate target arm')
            seen.add(key)
        for drift in ('near','far'):
            for mode in MODES:
                group=[r for r in raw['rows'] if r['mode']==mode and r['drift_type']==drift]
                for field in ('accepted','exact','wrong_accepted','abstain','target_labels',
                              'target_replayed','accepted_probes','probe_errors'):
                    if sum(r[field] for r in group)!=raw['summary'][drift][mode][field]:
                        raise BudgetContractError('batch score summary forged')
        results.extend(raw['rows']);sources.extend(raw['sources'])
        digests.append({'name':Path(p).name,'canonical_sha256':recorded})
    if len(results)!=b['expected_arms'] or len(sources)!=len(b['rows']):
        raise BudgetContractError('incomplete prescore arm or source coverage')
    return b,results,sources,digests


def audit(paths):
    b,results,sources,digests=read_scores(paths)
    totals={mode:{drift:{field:0 for field in ('accepted','exact','wrong_accepted','abstain',
                       'target_labels','accepted_probes','probe_errors')}
                  for drift in ('near','far')} for mode in MODES}
    source_total=target_total=accepted_probes=0
    with tempfile.TemporaryDirectory(prefix='ace-e14z-auditor-') as temp:
        root=Path(temp)
        for item in b['rows']:
            match=[s for s in sources if s['source_world']==item['id']]
            if len(match)!=1:raise BudgetContractError('missing/duplicate source lineage')
            src=source_learn(source_row(item),root)
            original=match[0]
            if (src['source_purchased']!=original['source_labels'] or
                sum(x['replay'] for x in src['source'])!=original['source_replayed'] or
                int(src['inferred_id'] is not None)!=original['source_unique']):
                raise BudgetContractError('independent source replay mismatch')
            source_total+=src['source_purchased']
            for drift in ('near','far'):
                truth=target_row(item,drift)
                form=grammar()[truth['program_id']]
                for pair_idx in TARGET_PAIRS:
                    pair=PAIR_SPACE[pair_idx]
                    for mode in MODES:
                        matches=[a for a in results if a['source_world']==item['id'] and
                                 a['drift_type']==drift and a['target_pair']==pair_idx and
                                 a['mode']==mode]
                        if len(matches)!=1:raise BudgetContractError('missing target policy arm')
                        row=matches[0]
                        if (row['world']!=truth['id'] or row['family']!=truth['family'] or
                            row['source_program_id']!=item['source_program_id'] or
                            row['target_program_id']!=truth['program_id'] or
                            row['semantic_signature_disagreements']!=item[f'{drift}_disagreements']):
                            raise BudgetContractError('falsified task drift/lineage metadata')
                        if row['source_label_cost']!=src['source_purchased']:
                            raise BudgetContractError('wrong attached source-label cost')
                        checked=reconstruct(row,src,form,pair)
                        target_total+=checked['target_labels']
                        accepted_probes+=checked['accepted_probes']
                        for key in totals[mode][drift]:totals[mode][drift][key]+=checked[key]
    return {'version':1,'status':'POSTSCORE_NEGATIVE_TRANSFER_INDEPENDENT_AUDIT',
            'scientific_decision':'NOT_ASSESSED','bank_sha256':digest(b),
            'source_operators':len(b['rows']),'arms':len(results),
            'source_labels_independently_recomputed':source_total,
            'target_labels_independently_replayed':target_total,
            'accepted_heldout_predictions_rechecked':accepted_probes,
            'summary':totals,'batch_digests':digests,
            'caveats':['same author selected near/far extreme signature pairs',
                       'source raw original SQLite journals not archived',
                       'independent-from-worker DFS cost oracle but same-author audit',
                       'no full checkout or native Bubblewrap proof']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('reports',nargs='+',type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    r=audit(a.reports);r['sha256']=hashlib.sha256(canonical(r)).hexdigest()
    a.output.parent.mkdir(exist_ok=True,parents=True)
    a.output.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in r.items() if k not in ('summary','batch_digests')},sort_keys=True))

if __name__=='__main__':main()
