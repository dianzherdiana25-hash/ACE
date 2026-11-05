"""ACE E1.4x typed epistemic scope for bounded symbolic-program claims.

A unique version-space fit means 'unique inside this stated grammar', not
'uniquely true'. Open-world claims abstain in the absence of an externally
justified grammar-completeness assumption. This module does not read truth,
secrets, held-out probes or evaluator score fields.
"""
from __future__ import annotations
import hashlib
import json
from .e14_shared_budget import BudgetContractError,SharedLabelBudget
from .e14_integrated_graph import graph_cost
from .e14u_primitive import PAIR_SPACE
from .e14w_synthesis import GRID,library,render,candidate_ids
from .e14x_identifiability import measured_costs

SCOPES=('bounded-dsl-assumed','open-world-unrestricted')


def scoped_claim(snapshot,pair,accepted_expr,*,scope='bounded-dsl-assumed'):
    if scope not in SCOPES:raise BudgetContractError('unknown semantic claim scope')
    if (type(pair) is not tuple or len(pair)!=2 or
        any(type(w) is not tuple or len(w)!=3 or
            any(type(v) is not int or v not in (1,2) for v in w)
            for w in pair) or pair not in PAIR_SPACE):
        raise BudgetContractError('unknown canonical inherited motif pair')
    if accepted_expr is not None and (type(accepted_expr) is not str or len(accepted_expr)>512):
        raise BudgetContractError('invalid expression attestation')
    book=SharedLabelBudget.from_snapshot(snapshot);book.assert_complete()
    points=set();observed=[]
    for receipt in snapshot['receipts']:
        graph=receipt['query']
        if receipt['cost']!=graph_cost(graph):
            raise BudgetContractError('untrusted topology resource cost')
        current=measured_costs(graph,pair)
        points.update(current)
        label=receipt['label']
        if label is None:
            # The accepted expression family expects a positive pair witness.
            observed.append(None)
            continue
        if len(current)!=1:
            raise BudgetContractError('cannot infer DSL evidence from multiplexed costs')
        only=next(iter(current))
        observed.append((only,label))
    supported=all(row is not None for row in observed)
    candidates=candidate_ids(observed) if supported else ()
    program=next((render(library(5)[i]) for i in candidates),None) if len(candidates)==1 else None
    fits=(program is not None and accepted_expr==program and book.purchased>=3)
    # Open-world confidence is NEVER inferred from finite inside-DSL uniqueness.
    accepted=bool(fits and scope=='bounded-dsl-assumed')
    reason=('UNRESTRICTED_OPERATOR_NOT_IDENTIFIABLE' if scope=='open-world-unrestricted'
            else 'UNIQUE_WITHIN_FINITE_DSL' if fits
            else 'INSUFFICIENT_OR_CONFLICTING_EVIDENCE')
    report={'version':1,'scope':scope,'decision':'accept_conditional' if accepted else 'abstain',
            'reason':reason,'expression':accepted_expr if fits else None,
            'purchased':book.purchased,'remaining_labels':book.remaining,
            'distinct_measured_points':len(points),'unmeasured_domain_points':len(GRID)-len(points),
            'candidate_count':len(candidates),
            'assumptions':{'grammar_complete':scope=='bounded-dsl-assumed',
                           'predecessor_pair_identity':'assumed_from_typed_artifact',
                           'deterministic_exact_oracle':True},
            'not_a_probability':True}
    return report


def compare_archived(rows,sources):
    lineage={s['index']:s for s in sources}
    cells={'bounded-dsl-assumed':{'accepted':0,'abstain':0},
           'open-world-unrestricted':{'accepted':0,'abstain':0}}
    for row in rows:
        if row['mode']!='synthesis-safe':continue
        i=int(row['id'].split(':',2)[1])
        learned=lineage[i].get('pair_learned')
        if learned is None:
            # Missing predecessor proof must not become an invented target claim.
            if row['accepted']!=0:raise BudgetContractError('missing predecessor but accepted')
            for c in cells.values():c['abstain']+=1
            continue
        pair=tuple(tuple(int(x) for x in w) for w in learned)
        for scope in SCOPES:
            output=scoped_claim(row['target_journal'],pair,row['selected_expr'],scope=scope)
            cells[scope]['accepted']+=int(output['decision']=='accept_conditional')
            cells[scope]['abstain']+=int(output['decision']=='abstain')
    return cells
