"""E1.4v: bounded compositional operator *parameter* induction on graph routes.

This program family is deliberately specified by its author: single-motif
cost, or a pair of motif witnesses with cost a*min(route tolls) + b*max(...).
A and B are INFERRED from observed numeric labels; they are not chosen from
an enumeration of MAX/MIN/SUM function names. This is not open-ended grammar
invention and cannot guarantee safety for unrepresented semantic programs.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
from itertools import combinations, product

from .e14_integrated_graph import graph_routes
from .e14_shared_budget import BudgetContractError
from .e14u_primitive import PAIR_SPACE, SINGLE_SPACE, _matches, query_pool

BOUND = 3
PARAMETERS = tuple((a, b) for a in range(BOUND+1)
                   for b in range(BOUND+1) if a or b)
ALL = tuple(("single",(w,),None) for w in SINGLE_SPACE) + tuple(
    ("pair-affine",pair,(a,b)) for pair in PAIR_SPACE for a,b in PARAMETERS)
LEGACY = tuple(c for c in ALL if c[0] == "single" or c[2] in ((0,1),(1,0),(1,1)))
INDEX = {candidate:i for i,candidate in enumerate(ALL)}


def pairs_of(routes, pair):
    a,b = pair
    found = set()
    for i,(ei,ci) in enumerate(routes):
        for j,(ej,cj) in enumerate(routes):
            if i!=j and _matches(ei,a) and _matches(ej,b):
                found.add((min(ci,cj),max(ci,cj)))
    return tuple(sorted(found))


def predict(routes, candidate):
    kind,words,weights=candidate
    if kind == "single":
        if weights is not None or len(words)!=1:
            raise BudgetContractError("invalid single representation")
        return min((c for ev,c in routes if _matches(ev,words[0])),default=None)
    if kind != "pair-affine" or type(weights) is not tuple or weights not in PARAMETERS:
        raise BudgetContractError("invalid operator representation")
    measures=pairs_of(routes,words)
    a,b=weights
    return min((a*u+b*v for u,v in measures),default=None)


def graph_score(graph,candidate):
    return predict(graph_routes(graph)[0],candidate)


@lru_cache(maxsize=1)
def pool():
    """Trusted public feature table for source acquisition and query design."""
    graphs=query_pool()
    routes=[graph_routes(g)[0] for g in graphs]
    outputs=tuple(tuple(predict(r,c) for c in ALL) for r in routes)
    keys=tuple(tuple(sorted(map(tuple,g['edges']))) for g in graphs)
    return graphs,outputs,keys


def survivor_ids(observed,allowed=None):
    """Fit exact version space from purchased evidence only."""
    ids=range(len(ALL)) if allowed is None else allowed
    _graphs,table,keys=pool()
    known={key:i for i,key in enumerate(keys)}
    rows=[]
    for graph,label in observed:
        key=tuple(sorted(map(tuple,graph["edges"])))
        if key in known:
            rows.append((table[known[key]],label))
        else:
            rows.append((tuple(graph_score(graph,c) for c in ALL),label))
    return tuple(i for i in ids if all(row[i]==label for row,label in rows))


def select(ids, forbidden, *, mode='active', seed=0):
    if mode not in ('active','fixed') or type(seed) is not int:
        raise BudgetContractError('invalid selector mode')
    if not ids or len(ids)<=1:
        return None
    graphs, outputs, keys=pool()
    used={tuple(sorted(map(tuple,g['edges']))) for g in forbidden}
    offers=[]
    for k,(graph,row,key) in enumerate(zip(graphs,outputs,keys,strict=True)):
        if key in used:continue
        counts=Counter(row[i] for i in ids)
        if len(counts)<2:continue
        score=(sum(v*v for v in counts.values()), max(counts.values()), k)
        offers.append((score,k))
    if not offers:return None
    _,chosen=min(offers,key=lambda item:item[0] if mode=='active' else (item[1],))
    return graphs[chosen]


def infer_weights(pair,observed):
    """Solve a,b algebraically from full-rank single-witness equations.

    Does not need candidate operator labels MAX/MIN/SUM or a grid search.
    Returns None if evidence cannot identify unique parameters or they fail
    a required observation, even if a finite list would have one survivor.
    """
    equations=[]
    for graph,label in observed:
        if label is None:continue
        route_measurements=pairs_of(graph_routes(graph)[0],pair)
        if len(route_measurements)==1:
            u,v=route_measurements[0]
            equations.append((u,v,label))
    solutions=set()
    for u,v,y in equations:
        for x,z,q in equations:
            determinant=u*z-v*x
            if determinant==0:continue
            anum=y*z-v*q
            bnum=u*q-y*x
            if anum % determinant or bnum % determinant:continue
            a,b=anum//determinant,bnum//determinant
            if (a,b) not in PARAMETERS:continue
            model=('pair-affine',pair,(a,b))
            if all(graph_score(g,model)==label for g,label in observed):
                solutions.add((a,b))
    return next(iter(solutions)) if len(solutions)==1 else None


def proof(candidate,observed):
    if candidate[0]=='single':
        return {'status':'single-supported','coefficients':None}
    learned=infer_weights(candidate[1],observed)
    return {'status':'rank-verified' if learned==candidate[2] else 'underidentified',
            'coefficients':None if learned is None else list(learned)}
