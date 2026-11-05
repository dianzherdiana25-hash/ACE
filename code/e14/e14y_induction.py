"""ACE E1.4y: bounded AST-form transfer via independent source tasks.

The *grammar primitives* (integer arithmetic, modulo, equality, threshold)
are authored; syntax trees, period, residue, threshold and signed amplitudes
are searched/induced from purchased demonstrations. This is not open-ended
semantic invention. Search is deliberately finite and inspectable.
"""
from __future__ import annotations
from collections import Counter
from functools import lru_cache

from .e14_shared_budget import BudgetContractError
from .e14w_synthesis import GRID, library, evaluate as old_eval

MAX_LABEL = 960


def ast_eval(ast, lo, hi):
    if type(ast) is not tuple or not ast:raise BudgetContractError('invalid AST')
    op = ast[0]
    if op == 'lo' and len(ast)==1:return lo
    if op == 'hi' and len(ast)==1:return hi
    if op == 'const' and len(ast)==2 and type(ast[1]) is int and -10<=ast[1]<=10:return ast[1]
    if len(ast)!=3:raise BudgetContractError('invalid AST arity')
    a,b=ast_eval(ast[1],lo,hi),ast_eval(ast[2],lo,hi)
    if op=='add':return a+b
    if op=='sub':return a-b
    if op=='mul':return a*b
    if op=='mod' and b>0:return a % b
    if op=='eq':return int(a==b)
    if op=='ge':return int(a>=b)
    raise BudgetContractError('unsupported AST operation')


def base_ast():
    return ('add',('lo',),('hi',))


def residue_ast(period,residue,amplitude):
    # Derived compositional expression; does not carry a named operator.
    test=('eq',('mod',('sub',('hi',),('lo',)),('const',period)),('const',residue))
    return ('add',base_ast(),('mul',('const',amplitude),test))


def threshold_ast(threshold,amplitude):
    test=('ge',('sub',('hi',),('lo',)),('const',threshold))
    return ('add',base_ast(),('mul',('const',amplitude),test))


@lru_cache(maxsize=1)
def grammar():
    """Collapse programs to semantic signatures on the entire legal grid."""
    syntax=[('base',base_ast())]
    for p in range(2,7):
        for r in range(p):
            for a in (-3,-2,-1,1,2,3):
                syntax.append(('residual',residue_ast(p,r,a)))
    for t in range(2,11):
        for a in (-3,-2,-1,1,2,3):
            syntax.append(('threshold',threshold_ast(t,a)))
    signatures={}
    for template,ast in syntax:
        sig=tuple(ast_eval(ast,*xy) for xy in GRID)
        if any(type(y) is not int or not 0<=y<=MAX_LABEL for y in sig):continue
        signatures.setdefault(sig,(template,ast))
    return tuple((name,ast,sig) for sig,(name,ast) in signatures.items())


@lru_cache(maxsize=1)
def old_signatures():
    return {tuple(old_eval(ast,*xy) for xy in GRID) for ast in library(5)}


def value_at(form, costs):
    if type(costs) is not tuple or len(costs)!=2 or any(type(x) is not int for x in costs):
        raise BudgetContractError('invalid cost coordinates')
    if costs not in GRID:raise BudgetContractError('out-of-domain cost query')
    if form[0] == 'unknown':
        name=form[1];lo,hi=costs
        if name=='gap-mod-7':return lo+hi+((hi-lo)%7)
        if name=='floor-half':return lo+hi//2
        if name=='square-gap':return lo+hi+(hi-lo)**2
        if name=='parity-lo':return lo+hi+(lo%2)
        if name=='mod-11':return lo+hi+((hi-lo)%11)
        if name=='odd-hi-times-two':return lo+hi+2*(hi%2)
        raise BudgetContractError('unknown stress formula')
    return ast_eval(form[1],*costs)


OUTSIDERS=('gap-mod-7','floor-half','square-gap','parity-lo','mod-11','odd-hi-times-two')


def candidates(observations):
    if type(observations) is not list or len(observations)>16:
        raise BudgetContractError('invalid evidence history')
    for xy,label in observations:
        if (type(xy) is not tuple or xy not in GRID or type(label) is not int or
            not 0<=label<=MAX_LABEL):
            raise BudgetContractError('invalid purchased evidence')
    return tuple(i for i,item in enumerate(grammar())
                 if all(item[2][GRID_INDEX[xy]]==label for xy,label in observations))


GRID_INDEX={xy:i for i,xy in enumerate(GRID)}


def choose_query(ids,observations,*,strategy='active',seed=0,allowed=None):
    if strategy not in ('active','fixed','random'):
        raise BudgetContractError('unknown query strategy')
    if type(ids) not in (tuple,list) or any(type(i) is not int or not 0<=i<len(grammar()) for i in ids):
        raise BudgetContractError('invalid candidate set')
    if len(ids)<2:return None
    used={xy for xy,_ in observations};offers=[]
    if allowed is None:allowed=GRID
    if any(xy not in GRID for xy in allowed):raise BudgetContractError('invalid query domain')
    for xy in allowed:
        if xy in used:continue
        groups=Counter(grammar()[i][2][GRID_INDEX[xy]] for i in ids)
        if len(groups)<2:continue
        score=(sum(n*n for n in groups.values()),max(groups.values()),xy[1]-xy[0],xy)
        offers.append((score,xy))
    if not offers:return None
    if strategy=='active':return min(offers)[1]
    if strategy=='fixed':return min(offers,key=lambda r:r[1])[1]
    import random
    return random.Random(seed).choice(offers)[1]


def information_state(observed):
    ids=candidates(observed)
    return {'survivors':len(ids),'unique':len(ids)==1,'operator':grammar()[ids[0]][0] if len(ids)==1 else None}
