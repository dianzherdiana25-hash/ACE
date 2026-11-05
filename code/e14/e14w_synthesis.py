"""ACE E1.4w: bounded bottom-up program *structure* synthesis.

Searches syntax trees, not a predefined list of named MAX/MIN/SUM operators.
The DSL, constants, search depth, and motif pair are *provided* by the
researcher; only tree composition and selection are induced from evidence.
No claims of open-ended operator invention or out-of-grammar completeness.
"""
from __future__ import annotations
from collections import Counter
from functools import lru_cache
from itertools import product
import random
from .e14_shared_budget import BudgetContractError
from .e14u_primitive import PAIR_SPACE, graph_from_routes
from .e14v_operator import pairs_of
from .e14_integrated_graph import graph_routes

GRID = tuple((lo,hi) for lo in range(4,19) for hi in range(lo,19))
LIMIT = 960
OPS = ('add','mul','min','max')
QUERIES = tuple((a,b) for a in range(15) for b in range(15))


def evaluate(tree,lo,hi):
    name=tree[0]
    if name=='lo':return lo
    if name=='hi':return hi
    if name=='const':return tree[1]
    x=evaluate(tree[1],lo,hi)
    y=evaluate(tree[2],lo,hi)
    if name=='add':return x+y
    if name=='mul':return x*y
    if name=='min':return min(x,y)
    if name=='max':return max(x,y)
    raise BudgetContractError('unknown DSL constructor')


def render(tree):
    if tree[0] in ('lo','hi'):return tree[0]
    if tree[0]=='const':return str(tree[1])
    symbol={'add':'+','mul':'*','min':'min','max':'max'}[tree[0]]
    return '('+render(tree[1])+symbol+render(tree[2])+')'


@lru_cache(maxsize=2)
def library(max_nodes=5):
    """Enumerate commutative binary ASTs; hash-cons semantic signatures.

    Equivalence is defined on the bounded graph-cost domain GRID only;
    distinct expressions can coincide there. Minimal tree wins each signature.
    """
    if max_nodes not in (3,5):raise BudgetContractError('unsupported search limit')
    levels={1:{}}
    terminals=(('lo',),('hi',),('const',0),('const',1),('const',2))
    for t in terminals:
        signature=tuple(evaluate(t,*x) for x in GRID)
        levels[1].setdefault(signature,t)
    for size in range(3,max_nodes+1,2):
        found={}
        for left_size in range(1,size-1,2):
            right_size=size-left_size-1
            if left_size>right_size:continue
            for sa,ta in levels[left_size].items():
                for sb,tb in levels[right_size].items():
                    if left_size==right_size and render(ta)>render(tb):continue
                    for name in OPS:
                        if name=='add': sig=tuple(a+b for a,b in zip(sa,sb))
                        elif name=='mul':sig=tuple(a*b for a,b in zip(sa,sb))
                        elif name=='min':sig=tuple(min(a,b) for a,b in zip(sa,sb))
                        else:sig=tuple(max(a,b) for a,b in zip(sa,sb))
                        if max(sig)>LIMIT:continue
                        if any(sig in prior for prior in levels.values()):continue
                        found.setdefault(sig,(name,ta,tb))
        levels[size]=found
    expressions=tuple(tree for size in sorted(levels) for tree in levels[size].values())
    return expressions


@lru_cache(maxsize=2)
def signatures(max_nodes=5):
    return tuple(tuple(evaluate(t,*costs) for costs in GRID) for t in library(max_nodes))


def candidate_ids(observed,max_nodes=5):
    if type(observed) is not list or len(observed)>8:raise BudgetContractError('invalid observations')
    programs=library(max_nodes)
    for costs,y in observed:
        if (type(costs) is not tuple or len(costs)!=2 or
            any(type(v) is not int or not 4<=v<=18 for v in costs) or
            type(y) is not int or not 0<=y<=960):
            raise BudgetContractError('invalid observation')
    return tuple(i for i,p in enumerate(programs) if all(evaluate(p,*v)==y for v,y in observed))


def select_question(ids,observed,max_nodes=5,mode='active',seed=0):
    if mode not in ('active','random','fixed'):raise BudgetContractError('unknown policy')
    if not ids:return None
    programs=library(max_nodes)
    if any(type(i) is not int or not 0<=i<len(programs) for i in ids):
        raise BudgetContractError('invalid candidate IDs')
    used=set(v for v,_ in observed)
    options=[]
    for a,b in QUERIES:
        costs=(4+min(a,b),4+max(a,b))
        if costs in used:continue
        responses=Counter(evaluate(programs[i],*costs) for i in ids)
        if len(responses)<2:continue
        score=(sum(n*n for n in responses.values()),max(responses.values()),a+b,a,b)
        options.append((score,(a,b),costs))
    if not options:return None
    if mode=='active':return min(options)[1]
    if mode=='fixed':return min(options,key=lambda row:(row[1][0],row[1][1]))[1]
    return random.Random(seed).choice(options)[1]


def target_for(pair,program):
    if pair not in PAIR_SPACE:raise BudgetContractError('unexpected motif pair')
    if type(program) is not tuple:raise BudgetContractError('invalid DSL program')
    def oracle(graph):
        routes=graph_routes(graph)[0]
        candidates=pairs_of(routes,pair)
        return min((evaluate(program,lo,hi) for lo,hi in candidates),default=None)
    return oracle


def out_of_basis(kind):
    if kind=='difference':return lambda lo,hi:hi-lo
    if kind=='offset-3':return lambda lo,hi:lo+hi+3
    if kind=='saturated-difference':return lambda lo,hi:min(7,hi-lo)
    if kind=='half-hi':return lambda lo,hi:lo+hi//2
    if kind=='three-lo-two-hi':return lambda lo,hi:3*lo+2*hi
    if kind=='two-lo-three-hi':return lambda lo,hi:2*lo+3*hi
    if kind=='square-sum':return lambda lo,hi:lo*lo+hi*hi
    if kind=='floor-mean':return lambda lo,hi:(lo+hi)//2
    if kind=='gap-parity':return lambda lo,hi:lo+hi+((hi-lo)%2)
    if kind=='switch-gap':return lambda lo,hi:(lo+hi if hi-lo<5 else hi)
    if kind=='quadratic-mix':return lambda lo,hi:lo*hi+lo*lo+1
    if kind=='clamped-sum':return lambda lo,hi:min(24,lo+hi)
    if kind=='gap-mod3':return lambda lo,hi:lo+hi+((hi-lo)%3)
    if kind=='lo-parity':return lambda lo,hi:lo+hi+(lo%2)
    if kind=='hi-parity':return lambda lo,hi:lo+hi+(hi%2)
    if kind=='upper-threshold':return lambda lo,hi:lo+hi+int(hi>=15)
    if kind=='gap-mod4':return lambda lo,hi:lo+hi+((hi-lo)%4)
    if kind=='clamped-product':return lambda lo,hi:min(lo*hi,200)
    if kind=='odd-weighted':return lambda lo,hi:lo*(1+(hi%2))+hi
    if kind=='piecewise-product':return lambda lo,hi:(lo*hi if hi-lo<=4 else lo+hi)
    raise BudgetContractError('unknown stress target')


def outsider_for(pair,kind):
    fn=out_of_basis(kind)
    def oracle(graph):
        routes=graph_routes(graph)[0]
        candidates=pairs_of(routes,pair)
        return min((fn(lo,hi) for lo,hi in candidates),default=None)
    return oracle


def motif_query(pair,a,b):
    return graph_from_routes(pair,(a,b))

@lru_cache(maxsize=2)
def _question_table(max_nodes=5):
    lookup={cost:i for i,cost in enumerate(GRID)}
    signatureset=signatures(max_nodes)
    return tuple((ab, (4+min(ab),4+max(ab)),
                  tuple(sig[lookup[(4+min(ab),4+max(ab))]] for sig in signatureset))
                 for ab in QUERIES)


def select_fast(ids,observed,max_nodes=5,mode='active',seed=0):
    if mode not in ('active','random','fixed'):raise BudgetContractError('unknown policy')
    used=set(v for v,_ in observed)
    options=[]
    for ab,costs,outputs in _question_table(max_nodes):
        if costs in used:continue
        groups=Counter(outputs[i] for i in ids)
        if len(groups)<2:continue
        score=(sum(v*v for v in groups.values()),max(groups.values()),ab[0]+ab[1],*ab)
        options.append((score,ab))
    if not options:return None
    if mode=='active':return min(options)[1]
    if mode=='fixed':return min(options,key=lambda row:row[1])[1]
    return random.Random(seed).choice(options)[1]
