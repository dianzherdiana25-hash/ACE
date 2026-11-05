"""ACE E1.4x: constructive indistinguishability after bounded target queries.

For any accepted bounded-DSL pair task with fewer than 120 distinct measured
cost pairs, construct an adversarial *out-of-family* operator that agrees with
all purchased labels yet differs on an unseen legal query. This is a finite
no-free-lunch certificate, not an active capability or an accepted scientific GO.

An adaptive deterministic learner cannot distinguish the two tasks from the
same complete purchased transcript: response equality at each round implies
the next query is identical (induction on the interaction steps). The witness
is chosen *after* scoring solely for falsification, never used to change the
original E1.4w results.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from .e14_integrated_graph import graph_routes
from .e14_shared_budget import SharedLabelBudget, BudgetContractError
from .e14u_primitive import PAIR_SPACE
from .e14v_operator import pairs_of
from .e14w_synthesis import GRID, evaluate, library, signatures, render, motif_query


def measured_costs(graph, pair):
    """All matching two-route cost pairs, not just a worker's claim."""
    return frozenset(pairs_of(graph_routes(graph)[0], pair))


def build_certificate(row, pair):
    if type(row) is not dict or row.get('accepted') != 1 or row.get('semantic_exact') != 1:
        raise BudgetContractError('certificate requires originally correct accepted model')
    if (type(pair) is not tuple or len(pair) != 2 or
        any(type(w) is not tuple or len(w) != 3 or
            any(type(x) is not int or x not in (1, 2) for x in w)
            for w in pair) or pair not in PAIR_SPACE):
        raise BudgetContractError('noncanonical motif pair')
    book = SharedLabelBudget.from_snapshot(row['target_journal'])
    book.assert_complete()
    if book.purchased > 4:
        raise BudgetContractError('four-label budget exceeded')
    original_expr = row['selected_expr']
    ast = next((tree for tree in library(5) if render(tree) == original_expr), None)
    if ast is None:
        raise BudgetContractError('unknown accepted DSL program')
    used = set()
    for r in row['target_journal']['receipts']:
        if r['status']!='settled':
            raise BudgetContractError('unsettled receipt')
        used.update(measured_costs(r['query'], pair))
    choices = set(GRID) - used
    if not choices:
        raise BudgetContractError('no unqueried counterexample')
    # Predeclare a witness choice independent of the true hidden operator.
    # Prefer a legal cost tuple far from all purchased examples, as an audit.
    ordered = sorted(choices, key=lambda x: (
        min((abs(x[0]-y[0])+abs(x[1]-y[1]) for y in used),default=999), x[1], x[0]),
        reverse=True)
    witness = next((x for x in ordered if evaluate(ast,*x) < 960),None)
    if witness is None:raise BudgetContractError('no bounded-cost witness')
    patched_signature=tuple(evaluate(ast,*c)+int(c==witness) for c in GRID)
    if patched_signature in signatures(5):
        raise BudgetContractError('countermodel unexpectedly represented in bounded grammar')
    witness_graph = motif_query(pair,witness[0]-4,witness[1]-4)
    wroute = measured_costs(witness_graph,pair)
    if wroute != frozenset((witness,)):
        raise BudgetContractError('witness graph has wrong typed route measurements')

    def base(g):
        v = measured_costs(g,pair)
        return min((evaluate(ast,*c) for c in v),default=None)
    def adversary(g):
        v = measured_costs(g,pair)
        return min((evaluate(ast,*c)+(1 if c == witness else 0) for c in v),default=None)

    for r in row['target_journal']['receipts']:
        b,a=base(r['query']),adversary(r['query'])
        if b != a or a != r['label']:
            raise BudgetContractError('candidate and countermodel do not share purchased transcript')
    b,a=base(witness_graph),adversary(witness_graph)
    if b is None or a != b+1:
        raise BudgetContractError('counterexample does not distinguish models')
    return {
        'world':row['id'],'mode':row['mode'],'accepted_expression':original_expr,
        'source_lineage_succeeded':bool(row['source_success']),
        'target_label_purchases':book.purchased,
        'distinct_measured_cost_pairs':len(used),
        'unmeasured_domain_points':len(choices),
        'total_cost_domain_points':len(GRID),
        'witness_route_costs':list(witness),
        'witness_graph':witness_graph,
        'original_cost':b,'adversarial_cost':a,'delta':1,
        'observed_labels_unchanged':True,
        'hypothesis_class':'single-point correction to finite bounded DSL',
        'countermodel_outside_5_node_DSL':True,
        'outcome':'INDISTINGUISHABLE_WITHIN_PURCHASED_INTERVENTIONS'
    }


def audit_reports(paths,*,modes=('synthesis-safe',)):
    certs=[];reports=[];scanned=0
    seen=set()
    for path in paths:
        raw=json.loads(Path(path).read_text())
        digest=raw.pop('sha256',None)
        encoding=json.dumps(raw,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        if hashlib.sha256(encoding).hexdigest()!=digest:
            raise BudgetContractError('input report digest mismatch')
        for row in raw['rows']:
            if row['mode'] not in modes:continue
            scanned+=1
            if row['accepted'] != 1 or row['semantic_exact'] != 1:continue
            key=(row['id'],row['mode'])
            if key in seen:raise BudgetContractError('duplicate accepted report arm')
            seen.add(key)
            idx=int(row['id'].split(':',2)[1])
            pair=PAIR_SPACE[idx]
            certs.append(build_certificate(row,pair))
        reports.append({'file':Path(path).name,'canonical_sha256':digest})
    return {'version':1,'status':'POSTSCORE_CONSTRUCTIVE_NONIDENTIFIABILITY',
            'scientific_decision':'NOT_ASSESSED',
            'pair_model_family':'author-supplied symbolic DSL',
            'worlds_independent':False,
            'scanned_arms':scanned,'certificates':len(certs),
            'worst_case_unknown_semantic_operators':'NO_FINITE_QUERY_GUARANTEE',
            'proof_scope':'legal 120-point route-cost grid, deterministic policies, arbitrary unseen cost operators',
            'reports':reports,'cases':certs}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('reports',nargs='+')
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    report=audit_reports(a.reports)
    text=json.dumps(report,sort_keys=True,separators=(',',':'),allow_nan=False)
    digest=hashlib.sha256(text.encode()).hexdigest()
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps({**report,'sha256':digest},sort_keys=True,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'scanned_arms':report['scanned_arms'],
                      'certificates':report['certificates'],'sha256':digest},sort_keys=True))

if __name__ == '__main__':main()
