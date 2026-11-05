"""Independent-from-worker E1.4u *development* report auditor.

Uses the frozen E1.4t graph route algorithm as a separate implementation of
path enumeration; reconstructs every program cost and purchased receipt.
Not an independent scientist, blind evaluator, or trusted isolation review.
"""
from __future__ import annotations

import hashlib
import json
from itertools import permutations

from .e14_shared_budget import SharedLabelBudget, BudgetContractError
from .e14_integrated_graph import graph_cost
from .e14p_graph import paths
from .e14u_dev import MODES, TRIPLE_WORDS, make_world
from .e14u_primitive import PAIR_SPACE, PAIR_WORDS, fit, diagnose


def _contains(events, motif):
    return tuple(motif) in (events[i:i+len(motif)] for i in range(len(events)-len(motif)+1))


def independent_label(graph, truth):
    graph_cost(graph)  # independent topology invariants; must be paid for auditor
    routes=paths(graph)
    kind, words=truth
    if kind=="single-path":
        return min((cost for word,cost in routes if _contains(word,words[0])),default=None)
    if kind=="branch-pair":
        a,b=words
        return min((max(ci,cj) for i,(ei,ci) in enumerate(routes)
                    for j,(ej,cj) in enumerate(routes)
                    if i!=j and _contains(ei,a) and _contains(ej,b)),default=None)
    if kind=="branch-triple-hidden":
        a,b,c=words
        return min((max(ci,cj,ck) for i,(ei,ci) in enumerate(routes)
                    for j,(ej,cj) in enumerate(routes)
                    for k,(ek,ck) in enumerate(routes)
                    if len({i,j,k})==3 and _contains(ei,a)
                    and _contains(ej,b) and _contains(ek,c)),default=None)
    raise BudgetContractError("unrecognized audit truth")


def audit_row(row):
    if type(row) is not dict:
        raise BudgetContractError("invalid report row")
    if type(row.get('world')) is not str or row.get('arm') not in MODES:
        raise BudgetContractError("invalid world or arm")
    try:
        kind,idx=row['world'].split(':')
        if kind not in ('pair','single','triple') or not idx.isdigit() or str(int(idx))!=idx:
            raise ValueError('malformed world id')
        limit={'pair':len(PAIR_SPACE),'single':len(PAIR_WORDS),'triple':len(TRIPLE_WORDS)}[kind]
        if not 0<=int(idx)<limit:raise ValueError('out of range')
    except (ValueError,KeyError,IndexError) as exc:
        raise BudgetContractError("unknown world in report") from exc
    world=make_world(kind,int(idx))
    if row['kind']!=kind or row['demos']!=len(world['demonstrations']):
        raise BudgetContractError("world metadata differs")
    budget=SharedLabelBudget.from_snapshot(row['journal'])
    budget.assert_complete()
    if budget.purchased>4:
        raise BudgetContractError("shared label cap violated")
    if row['purchased']!=budget.purchased or row['audit_calls']!=budget.purchased:
        raise BudgetContractError("wrong purchase or replay accounting")
    known=list(world['demonstrations'])
    previous=diagnose(known)
    expanded=previous['trigger'] and row['arm']!='base-only'
    if row['trigger']!=previous['trigger'] or row['expanded']!=expanded:
        raise BudgetContractError("contradiction trigger mismatch")
    if row['base_fits']!=previous['base']['candidate_fits']:
        raise BudgetContractError("candidate fit accounting mismatch")
    if row['extension_fits']!=(previous['extended']['candidate_fits'] if expanded else 0):
        raise BudgetContractError("extension fit cost mismatch")
    initial=(previous['extended'] if expanded else previous['base'])['candidates']
    if len(initial)!=row['initial_candidates']:
        raise BudgetContractError("initial version space mismatch")
    if len(row['trace'])!=budget.purchased:
        raise BudgetContractError("purchase trace length mismatch")
    for i,(receipt,step) in enumerate(zip(budget.snapshot()['receipts'],row['trace'])):
        required='diagnosis' if i==0 else 'qualification'
        if receipt['stage']!=required or (i==0 and 'repair' not in receipt['reused_in']):
            raise BudgetContractError("receipt stage or reuse missing")
        if any(step[k]!=v for k,v in (('receipt',receipt['id']),('label',receipt['label']),('stage',required))):
            raise BudgetContractError("trace receipt mismatch")
        y=independent_label(receipt['query'],world['truth'])
        if y!=receipt['label'] or type(y) is not type(receipt['label']):
            raise BudgetContractError("independent oracle replay mismatch")
        known.append({'input':receipt['query'],'output':y})
        candidates=fit(known,extended=expanded)['candidates']
        if step['survivors']!=len(candidates):
            raise BudgetContractError("trace version-space mismatch")
    candidates=fit(known,extended=expanded)['candidates']
    accepted=len(candidates)==1
    exact=accepted and candidates[0]==world['truth']
    covered=errors=0
    from .e14u_primitive import guarded_predict
    for g in world['probes']:
        pred=guarded_predict(candidates,g)
        gold=independent_label(g,world['truth'])
        if pred['covered']:
            covered+=1
            errors+=int(pred['prediction']!=gold)
    expected={'accepted':int(accepted),'exact':int(exact),
              'wrong_accepted':int(accepted and not exact),
              'covered':covered,'probe_errors':errors,
              'remaining_candidates':len(candidates),
              'query_cost':budget.snapshot()['query_cost_totals']}
    if any(row.get(k)!=v for k,v in expected.items()):
        raise BudgetContractError("reported outcome or resource cost disagrees with audit")
    return {'purchased':budget.purchased,'oracle_replay_calls':budget.purchased,
            'initial_demo_calls':len(world['demonstrations']),
            'heldout_probe_calls':len(world['probes'])}


def audit_report(report):
    if type(report) is not dict or report.get('version')!=1 or type(report.get('rows')) is not list:
        raise BudgetContractError("invalid report structure")
    rows=report['rows']
    expected={(f'{kind}:{i}',mode) for kind,n in (('pair',len(PAIR_SPACE)),
               ('single',len(PAIR_WORDS)),('triple',len(TRIPLE_WORDS)))
               for i in range(n) for mode in MODES}
    if len(rows)!=len(expected) or len({(r.get('world'),r.get('arm')) for r in rows})!=len(expected):
        raise BudgetContractError("missing or duplicate scored arms")
    if {(r['world'],r['arm']) for r in rows}!=expected:
        raise BudgetContractError("wrong scoring coverage")
    audit=[audit_row(row) for row in rows]
    summary={kind:{mode:{k:sum(r[k] for r in rows if r['kind']==kind and r['arm']==mode)
                for k in ('purchased','audit_calls','accepted','exact','wrong_accepted',
                          'covered','probe_errors')}
                for mode in MODES} for kind in ('pair','single','triple')}
    for kind in summary:
        for mode in MODES:
            summary[kind][mode]['worlds']=sum(r['kind']==kind and r['arm']==mode for r in rows)
    if summary!=report['summary']:
        raise BudgetContractError("summary arithmetic differs")
    return {'status':'PUBLIC_DEVELOPMENT_AUDIT_PASS',
            'arms':len(rows),'purchased_labels':sum(r['purchased'] for r in audit),
            'oracle_audit_calls':sum(r['oracle_replay_calls'] for r in audit),
            'initial_demo_labels':sum(r['initial_demo_calls'] for r in audit),
            'heldout_probe_labels':sum(r['heldout_probe_calls'] for r in audit)}


def main():
    import argparse
    from pathlib import Path
    p=argparse.ArgumentParser();p.add_argument('report',type=Path)
    a=p.parse_args()
    raw=json.loads(a.report.read_text())
    print(json.dumps(audit_report(raw),sort_keys=True))

if __name__=='__main__':main()
