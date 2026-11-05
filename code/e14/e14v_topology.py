"""E1.4v post-development graph-topology counterfactuals.

New structural distribution: shared-prefix branching DAG, unlike the disjoint
path graphs used by the original public query pool. Any positive generalization
is to this authored invariant only; not evidence of unseen natural semantics.
"""
from __future__ import annotations

import random

from .e14_integrated_graph import graph_routes
from .e14_shared_budget import BudgetContractError
from .e14u_primitive import PAIR_WORDS, graph_from_routes


def fork(words,tolls):
    if type(words) not in (list,tuple) or not 2 <= len(words) <= 4:
        raise BudgetContractError('fork needs two to four routes')
    if type(tolls) not in (list,tuple) or len(tolls)!=len(words):
        raise BudgetContractError('invalid fork tolls')
    goal=2*len(words)+2
    edges=[[0,1,0,1]]
    for idx,(word,toll) in enumerate(zip(words,tolls,strict=True)):
        if type(word) not in (list,tuple) or len(word)!=3 or any(type(x) is not int or x not in (1,2) for x in word):
            raise BudgetContractError('invalid fork motif')
        if type(toll) is not int or not 0 <= toll <= 14:
            raise BudgetContractError('invalid fork toll')
        x=2+2*idx;y=x+1
        color=[0]
        for e in word:color.append(color[-1]^int(e==2))
        edges.extend([[1,x,color[1],1],[x,y,color[2],1],[y,goal,color[3],1+toll]])
    graph={'nodes':goal+1,'start':0,'goal':goal,'edges':edges}
    graph_routes(graph)
    return graph


def structurally_new_probes(seed,count=6):
    if type(seed) is not int or type(count) is not int or not 1 <= count <= 32:
        raise BudgetContractError('invalid probe seed/count')
    rng=random.Random(seed)
    graphs=[];seen=set()
    while len(graphs)<count:
        n=rng.choice((2,3,4))
        motifs=rng.sample(PAIR_WORDS,n)
        tolls=[rng.randrange(12) for _ in range(n)]
        graph=fork(motifs,tolls)
        identity=tuple(sorted(map(tuple,graph['edges'])))
        if identity not in seen:seen.add(identity);graphs.append(graph)
    return graphs


def expected_equivalent_graphs(words,tolls):
    """Share-prefix and disjoint-fork graphs with the same labeled routes/costs."""
    left=fork(words,tolls)
    right=graph_from_routes(words,tolls)
    assert sorted(graph_routes(left)[0])==sorted(graph_routes(right)[0])
    return left,right
