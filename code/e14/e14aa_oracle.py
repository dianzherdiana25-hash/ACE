"""Independent arithmetic and graph-label oracle for E1.4aa development.

This module imports no learner, grammar, candidate interpreter or study code.
Specs are evaluator data: lo+hi plus at most two supplied predicate terms and
an optional explicitly labeled outside-family perturbation. Its independence
is implementation independence within one session, not blind scientific custody.
"""
from .e14_shared_budget import BudgetContractError


def _integer(x,lo,hi,name):
    if type(x) is not int or not lo<=x<=hi:
        raise BudgetContractError('independent oracle invalid '+name)
    return x


def value(spec,xy):
    """Evaluate the public truth schema using direct arithmetic, without ASTs."""
    if type(spec) is not dict or set(spec)-{'terms','outsider'}:
        raise BudgetContractError('independent oracle invalid spec fields')
    if type(xy) not in (tuple,list) or len(xy)!=2:
        raise BudgetContractError('independent oracle invalid cost coordinates')
    lo=_integer(xy[0],4,18,'lo');hi=_integer(xy[1],lo,18,'hi')
    terms=spec.get('terms',[])
    if type(terms) not in (tuple,list) or len(terms)>2:
        raise BudgetContractError('independent oracle invalid terms')
    answer=lo+hi;gap=hi-lo
    for term in terms:
        if type(term) is not dict:raise BudgetContractError('independent oracle invalid term')
        amplitude=_integer(term.get('a'),-10,10,'amplitude')
        if term.get('kind')=='periodic' and set(term)=={'kind','p','r','a'}:
            period=_integer(term['p'],1,32,'period')
            residue=_integer(term['r'],0,period-1,'residue')
            # Divmod implements remainder separately from the learner AST.
            active=divmod(gap,period)[1]==residue
        elif term.get('kind')=='threshold' and set(term)=={'kind','t','a'}:
            threshold=_integer(term['t'],0,18,'threshold')
            active=gap>=threshold
        else:raise BudgetContractError('independent oracle unknown predicate')
        if active:answer+=amplitude
    outsider=spec.get('outsider')
    if outsider is not None:
        if type(outsider) is not dict:raise BudgetContractError('independent oracle invalid outsider')
        amplitude=_integer(outsider.get('a',1),-10,10,'outsider amplitude')
        kind=outsider.get('kind')
        if kind=='needle' and not set(outsider)-{'kind','lo','hi','a'}:
            needle_lo=_integer(outsider.get('lo'),4,18,'needle lo')
            needle_hi=_integer(outsider.get('hi'),needle_lo,18,'needle hi')
            if (lo,hi)==(needle_lo,needle_hi):answer+=amplitude
        elif kind=='squared_gap' and not set(outsider)-{'kind','a'}:
            answer+=amplitude*gap*gap
        elif kind=='lo_parity' and not set(outsider)-{'kind','a'}:
            if lo & 1:answer+=amplitude
        else:raise BudgetContractError('independent oracle unknown outsider')
    return _integer(answer,0,960,'answer')


def _routes(graph):
    """Bounded recursive DFS; independent of the production graph walker."""
    if type(graph) is not dict or set(graph)!={'nodes','start','goal','edges'}:
        raise BudgetContractError('independent oracle invalid graph')
    n=_integer(graph['nodes'],2,16,'nodes')
    start=_integer(graph['start'],0,n-1,'start')
    goal=_integer(graph['goal'],start+1,n-1,'goal')
    edges=graph['edges']
    if type(edges) is not list or not 1<=len(edges)<=16:
        raise BudgetContractError('independent oracle invalid edges')
    adjacency={i:[] for i in range(n)};keys=set()
    for edge in edges:
        if type(edge) is not list or len(edge)!=4:
            raise BudgetContractError('independent oracle invalid edge')
        a=_integer(edge[0],start,goal-1,'edge source')
        b=_integer(edge[1],a+1,goal,'edge destination')
        color=_integer(edge[2],0,3,'color')
        cost=_integer(edge[3],0,15,'edge cost')
        key=(a,b,color,cost)
        if key in keys:raise BudgetContractError('independent oracle duplicate edge')
        keys.add(key);adjacency[a].append(key)
    routes=[];used=set()
    def visit(node,colors,total,traversed):
        if node==goal:
            events=tuple(1 if colors[i]==colors[i+1] else 2 for i in range(len(colors)-1))
            routes.append((events,total));used.update(traversed)
            if len(routes)>16:raise BudgetContractError('independent oracle route cap')
            return
        for edge in adjacency[node]:
            visit(edge[1],colors+[edge[2]],total+edge[3],traversed+[edge])
    visit(start,[],0,[])
    if not routes or used!=keys or sum(len(x[0]) for x in routes)>256:
        raise BudgetContractError('independent oracle disconnected or oversized graph')
    return routes


def graph_label(graph,pair,spec):
    """Minimum operator value over distinct routes satisfying the motif pair."""
    if type(pair) not in (list,tuple) or len(pair)!=2:
        raise BudgetContractError('independent oracle invalid motif pair')
    motifs=[]
    for motif in pair:
        if type(motif) not in (list,tuple) or len(motif)!=3 or any(
            type(x) is not int or x not in (1,2) for x in motif):
            raise BudgetContractError('independent oracle invalid motif')
        motifs.append(tuple(motif))
    if motifs[0]==motifs[1]:raise BudgetContractError('independent oracle duplicate motif')
    routes=_routes(graph);answers=[]
    for i,(events_a,cost_a) in enumerate(routes):
        if not any(events_a[k:k+3]==motifs[0] for k in range(len(events_a)-2)):continue
        for j,(events_b,cost_b) in enumerate(routes):
            if i==j:continue
            if any(events_b[k:k+3]==motifs[1] for k in range(len(events_b)-2)):
                answers.append(value(spec,sorted((cost_a,cost_b))))
    return min(answers) if answers else None
