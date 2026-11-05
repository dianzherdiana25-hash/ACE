"""E1.4w predecessor acquisition: expanded non-target-aware MAX queries.

Compares a fixed original 70-graph source pool with cost-diverse variants.
All source labels come from the distinct MAX task, not the successor formula.
Candidate vocabulary is provided and bounded to 28 motif pairs.
"""
from __future__ import annotations
from functools import lru_cache
from itertools import combinations
from collections import Counter
from .e14u_primitive import PAIR_WORDS,PAIR_SPACE,graph_from_routes,program
from .e14_integrated_graph import DurableGraphBudget,purchase,audit_journal
from .e14p_graph import paths
from .e14_shared_budget import BudgetContractError

COSTS=((0,2,5,9),(9,5,2,0),(0,9,2,5),(5,0,9,2),(2,5,9,0),(9,0,5,2))

@lru_cache(maxsize=1)
def offers():
    rows=[]
    for words in combinations(PAIR_WORDS,4):
        for tolls in COSTS:
            graph=graph_from_routes(words,tolls)
            table={w:4+t for w,t in zip(words,tolls,strict=True)}
            outputs=tuple(max(table[a],table[b]) if a in table and b in table else None
                          for a,b in PAIR_SPACE)
            rows.append((graph,outputs))
    return tuple(rows)


def query(candidates,known,*,mode='expanded'):
    if mode not in ('expanded','original'):
        raise BudgetContractError('invalid predecessor query strategy')
    ordered=offers() if mode=='expanded' else tuple(offers()[6*i+(i%2)] for i in range(70))
    used={tuple(sorted(map(tuple,g['edges']))) for g,y in known}
    choices=[]
    for pos,(graph,pred) in enumerate(ordered):
        if tuple(sorted(map(tuple,graph['edges']))) in used:continue
        groups=Counter(pred[i] for i in candidates)
        if len(groups)<=1:continue
        choices.append(((sum(v*v for v in groups.values()),max(groups.values()),pos),graph))
    return min(choices)[1] if choices else None


def source_truth(graph,pair):
    measures={}
    for events,cost in paths(graph):
        measures.setdefault(events,[]).append(cost)
    a,b=pair
    return min((max(x,y) for x in measures.get(a,()) for y in measures.get(b,())),default=None)


def learn(index,journal_path,mode='expanded',cap=4):
    if type(index) is not int or not 0<=index<len(PAIR_SPACE):
        raise BudgetContractError('invalid predecessor world')
    if type(cap) is not int or not 1<=cap<=4:
        raise BudgetContractError('invalid source cap')
    truth=PAIR_SPACE[index]
    active=tuple(range(len(PAIR_SPACE)))
    known=[]
    journal=DurableGraphBudget(journal_path,f'e14w-source:{index}:{mode}')
    for step in range(cap):
        if len(active)==1:break
        graph=query(active,known,mode=mode)
        if graph is None:break
        _,label=purchase(journal,'diagnosis' if step==0 else 'repair',graph,
                         lambda q:source_truth(q,truth))
        known.append((graph,label))
        pred=dict((tuple(sorted(map(tuple,g['edges']))),o) for g,o in offers())
        # Exactly the same legal graph and label vector is evaluated pre-oracle.
        key=tuple(sorted(map(tuple,graph['edges'])))
        outputs=pred[key]
        active=tuple(i for i in active if outputs[i]==label)
    snapshot=journal.snapshot()
    audit=audit_journal(snapshot,lambda q:source_truth(q,truth))
    learned=PAIR_SPACE[active[0]] if len(active)==1 else None
    return {'world':index,'mode':mode,'labels':len(known),
            'replay':audit['auditor_oracle_calls'],'survivors':len(active),
            'learned':learned,'correct':learned==truth,
            'source_journal':snapshot}
