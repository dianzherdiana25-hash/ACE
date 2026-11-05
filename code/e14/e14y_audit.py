"""Postscore E1.4y independent receipt and semantic-claim audit.

Reconstructs accepted candidate from raw, durable target receipts, independently
replays all oracle labels with E1.4p DFS paths, and re-derives 120-grid semantic
correctness, probe errors and every summary. A fresh separate source-learning
replay checks source aggregate counts; raw source receipts were not archived.
Do not mistake this for independent scientific blind review.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from .e14_shared_budget import BudgetContractError, SharedLabelBudget
from .e14_integrated_graph import audit_journal
from .e14u_primitive import PAIR_SPACE
from .e14v_operator import pairs_of
from .e14p_graph import paths
from .e14w_synthesis import GRID,library as old_library,evaluate as old_eval
from .e14y_induction import grammar,candidates,GRID_INDEX,value_at
from .e14y_study import (truth_of,independent_oracle,source_learn,heldout_probes,
                         old_candidates,TARGET_QUERY_GRID,MODES)
from .e14y_bank import build,digest,canonical


def unpack_costs(graph,pair):
    routes=paths(graph);a,b=pair;found=set()
    for i,(ei,ci) in enumerate(routes):
        for j,(ej,cj) in enumerate(routes):
            if i!=j and a in tuple(ei[k:k+len(a)] for k in range(len(ei)-len(a)+1)) and b in tuple(
                ej[k:k+len(b)] for k in range(len(ej)-len(b)+1)):
                found.add((min(ci,cj),max(ci,cj)))
    if len(found)!=1:raise BudgetContractError('intervention query has ambiguous route costs')
    xy=next(iter(found))
    if xy not in TARGET_QUERY_GRID:raise BudgetContractError('target used heldout query costs')
    return xy


def reconstruct(row,source,op,pair,*,include_candidate=False):
    book=SharedLabelBudget.from_snapshot(row['target_journal']);book.assert_complete()
    if book.purchased>4:raise BudgetContractError('target label cap violated')
    audit=audit_journal(book.snapshot(),lambda graph:independent_oracle(graph,pair,op))
    if audit['auditor_oracle_calls']!=row['target_labels'] or book.purchased!=row['target_labels']:
        raise BudgetContractError('purchased-target count mismatch')
    observations=[];used=set()
    for r in book.snapshot()['receipts']:
        xy=unpack_costs(r['query'],pair)
        if xy in used:raise BudgetContractError('multiple purchases of one query cost')
        used.add(xy);observations.append((xy,r['label']))
    selected=None;mode=row['mode']
    if mode in ('transfer-direct','transfer-verify2','sham-transfer'):
        idx=source['inferred_id']
        if idx is not None:
            if mode=='sham-transfer':idx=(idx+37)%len(grammar())
            if mode=='transfer-direct':
                if observations:raise BudgetContractError('direct transfer bought target labels')
                selected=('new',idx)
            else:
                if len(observations)!=2:raise BudgetContractError('target verification not exactly two labels')
                if all(grammar()[idx][2][GRID_INDEX[xy]]==y for xy,y in observations):
                    selected=('new',idx)
    elif mode in ('cold-new','cold-old'):
        ids=candidates(observations) if mode=='cold-new' else old_candidates(observations)
        if len(ids)==1 and len(observations)>=3:
            selected=('new' if mode=='cold-new' else 'old',ids[0])
    else:raise BudgetContractError('invalid audited policy')
    def value(xy):
        if selected is None:return None
        kind,i=selected
        return grammar()[i][2][GRID_INDEX[xy]] if kind=='new' else old_eval(old_library(5)[i],*xy)
    signature=tuple(value(x) for x in GRID) if selected is not None else None
    exact=selected is not None and signature==tuple(value_at(op,x) for x in GRID)
    errors=0
    if selected is not None:
        for g in heldout_probes({'id':row['world']},row['target_pair']):
            vals=unpack_costs_holdout(g,pair)
            pred=min((value(x) for x in vals),default=None)
            gold=independent_oracle(g,pair,op)
            errors+=int(pred!=gold)
    expected={'accepted':int(selected is not None),'exact':int(exact),
              'wrong_accepted':int(selected is not None and not exact),
              'abstain':int(selected is None),'target_labels':book.purchased,
              'target_replayed':audit['auditor_oracle_calls'],
              'accepted_probes':6*int(selected is not None),'probe_errors':errors}
    for key,v in expected.items():
        if type(row.get(key)) is not int or row[key]!=v:
            raise BudgetContractError(f'semantic or scoring tamper: {key}')
    return (expected,selected) if include_candidate else expected


def unpack_costs_holdout(graph,pair):
    routes=paths(graph);a,b=pair;found=set()
    for i,(ei,ci) in enumerate(routes):
        for j,(ej,cj) in enumerate(routes):
            if i!=j and any(tuple(ei[k:k+len(a)])==a for k in range(len(ei)-len(a)+1)) and any(
                tuple(ej[k:k+len(b)])==b for k in range(len(ej)-len(b)+1)):
                found.add((min(ci,cj),max(ci,cj)))
    return tuple(sorted(found))


def audit_files(paths):
    bank=build();all_rows=[];source_records=[];files=[];seen=set()
    for path in paths:
        report=json.loads(Path(path).read_bytes())
        record_hash=report.pop('sha256',None)
        if hashlib.sha256(canonical(report)).hexdigest()!=record_hash:
            raise BudgetContractError('tampered score report digest')
        if report['bank_sha256']!=digest(bank):
            raise BudgetContractError('wrong prescore bank')
        for row in report['rows']:
            key=(row['world'],row['target_pair'],row['mode'])
            if key in seen:raise BudgetContractError('duplicate target arm')
            seen.add(key)
        # Independently reconstruct batch summary from its rows.
        for mode in MODES:
            group=[r for r in report['rows'] if r['mode']==mode]
            old=report['summary'][mode]
            for field in ('accepted','exact','wrong_accepted','abstain','target_labels',
                          'target_replayed','accepted_probes','probe_errors'):
                if old[field]!=sum(r[field] for r in group):
                    raise BudgetContractError('score summary corruption')
        all_rows.extend(report['rows']);source_records.extend(report['sources'])
        files.append({'name':Path(path).name,'canonical_sha256':record_hash})
    expected_arms=len(bank['rows'])*len(bank['target_pair_indices'])*len(MODES)
    if len(all_rows)!=expected_arms or len(source_records)!=len(bank['rows']):
        raise BudgetContractError('incomplete 40-operator prescore bank coverage')
    total_target=0;source_count=0
    with tempfile.TemporaryDirectory(prefix='ace-e14y-audit-') as temp:
        tmp=Path(temp)
        for i,entry in enumerate(bank['rows']):
            matching=[s for s in source_records if s['id']==entry['id']]
            if len(matching)!=1:raise BudgetContractError('source repetition or missing')
            source=source_learn(entry,tmp)
            log=matching[0]
            if (source['source_purchased']!=log['source_labels'] or
                sum(r['replay'] for r in source['source'])!=log['source_replayed'] or
                int(source['inferred_id'] is not None)!=log['source_unique'] or
                [r['labels'] for r in source['source']]!=log['source_task_labels']):
                raise BudgetContractError('source acquisition mismatch')
            source_count+=source['source_purchased']
            op=truth_of(entry)
            for target_idx in bank['target_pair_indices']:
                pair=PAIR_SPACE[target_idx]
                for mode in MODES:
                    matches=[r for r in all_rows if r['world']==entry['id'] and
                             r['target_pair']==target_idx and r['mode']==mode]
                    if len(matches)!=1:raise BudgetContractError('missing arm')
                    row=matches[0]
                    if row['family']!=entry['family'] or row['source_label_cost']!=source['source_purchased']:
                        raise BudgetContractError('incorrect source lineage')
                    verified=reconstruct(row,source,op,pair)
                    total_target+=verified['target_labels']
    summary={mode:{k:sum(row[k] for row in all_rows if row['mode']==mode)
                   for k in ('accepted','exact','wrong_accepted','abstain','target_labels',
                             'target_replayed','accepted_probes','probe_errors')}
             for mode in MODES}
    return {'version':1,'status':'POSTSCORE_INDEPENDENT_ROUTE_AND_SEMANTIC_REPLAY',
            'scientific_decision':'NOT_ASSESSED','bank_sha256':digest(bank),
            'source_operators':len(bank['rows']),'arms':len(all_rows),'source_labels_recomputed':source_count,
            'target_labels_independently_replayed':total_target,
            'accepted_heldout_predictions_rechecked':sum(row['accepted_probes'] for row in all_rows),
            'summary':summary,'files':files,
            'limitations':['source raw purchased journals missing from first score; source independently rerun and aggregates compared',
                           'same author constructed bank and audit','not a sealed independent scientific benchmark']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('reports',nargs='+',type=Path)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    r=audit_files(a.reports)
    body=canonical(r);r['sha256']=hashlib.sha256(body).hexdigest()
    a.output.parent.mkdir(exist_ok=True,parents=True)
    a.output.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in r.items() if k!='files'},sort_keys=True))

if __name__=='__main__':main()
