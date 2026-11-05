"""ACE E1.4t public-development candidate: bounded representation-length extension.

Worker side ONLY. The trusted evaluator must never stage the hidden truth, oracle,
held-out probes, bank generator or evaluator-side budget code with this file.
The algorithm learns a *bounded* longer motif from labeled graph examples;
it does not invent a new semantic primitive or claim open-ended evolution.
"""
import json
import sys
from collections import defaultdict
from itertools import pairwise, product

BASE = (5, 6, 7)
EXTENDED = (8, 9)
MAX_PACKET = 131072


def bounded_graph_routes(graph):
    if type(graph) is not dict or set(graph) != {'nodes','start','goal','edges'}:
        raise ValueError('invalid graph packet')
    n = graph['nodes']
    if type(n) is not int or not 2 <= n <= 16:
        raise ValueError('node cap')
    start,goal=graph['start'],graph['goal']
    if type(start) is not int or type(goal) is not int or not 0 <= start < goal < n:
        raise ValueError('invalid vertices')
    edges=graph['edges']
    if type(edges) is not list or not 1 <= len(edges) <= 16:
        raise ValueError('edge cap')
    adj=defaultdict(list)
    for e in edges:
        if type(e) is not list or len(e)!=4 or any(type(v) is not int for v in e):
            raise ValueError('typed edge')
        a,b,c,w=e
        if not start <= a < b <= goal or not 0 <= c <= 3 or not 0 <= w <= 15:
            raise ValueError('edge range')
        adj[a].append((b,c,w))
    stack=[(start,(),0)]; paths=[]
    while stack:
        node,colors,cost=stack.pop()
        if node==goal:
            events=tuple(1 if a==b else 2 for a,b in pairwise(colors))
            paths.append((events,cost))
            if len(paths)>16:
                raise ValueError('path cap')
            continue
        for b,c,w in adj[node]:
            stack.append((b,colors+(c,),cost+w))
        if len(stack)>512:
            raise ValueError('path exploration cap')
    if not paths:
        raise ValueError('disconnected graph')
    return paths


def match(routes,word):
    l=len(word)
    return min((cost for events,cost in routes if any(events[i:i+l]==word for i in range(len(events)-l+1))),default=None)


def make_chain(word, extra=()):
    word=tuple(extra)+tuple(word)
    if not word or len(word)>14 or any(type(x) is not int or x not in (1,2) for x in word):
        raise ValueError('bad chain word')
    color=0; edges=[[0,1,color,1]]
    for i,event in enumerate(word,1):
        color ^= event==2
        edges.append([i,i+1,color,1])
    return {'nodes':len(word)+2,'start':0,'goal':len(word)+1,'edges':edges}


def admitted(packet):
    if type(packet) is not dict or set(packet)!={'mode','demos','receipts','remaining','source_word'}:
        raise ValueError('invalid packet fields')
    if packet['mode'] not in ('integrated','fixed','no-inheritance','sham','exhaustive'):
        raise ValueError('invalid candidate arm')
    remaining=packet['remaining']
    if type(remaining) is not int or not 0 <= remaining <= 4:
        raise ValueError('invalid remaining')
    rows=packet['demos']
    if type(rows) is not list or not 1 <= len(rows) <= 16:
        raise ValueError('invalid demos')
    receipts=packet['receipts']
    if type(receipts) is not list or len(receipts)>4:
        raise ValueError('invalid receipts')
    source=packet['source_word']
    if source is not None and (type(source) is not list or len(source)!=7 or any(type(x) is not int or x not in (1,2) for x in source)):
        raise ValueError('invalid source')
    samples=[]
    for r in rows:
        if type(r) is not dict or set(r)!={'input','output'}:
            raise ValueError('invalid demo')
        if r['output'] is not None and (type(r['output']) is not int or not 0 <= r['output'] <= 960):
            raise ValueError('invalid label')
        samples.append((bounded_graph_routes(r['input']),r['output']))
    for r in receipts:
        if type(r) is not dict or set(r) != {'id','stage','query','label','status','reused_in'}:
            raise ValueError('invalid receipt data')
        if r['status']!='settled' or type(r['id']) is not str or type(r['reused_in']) is not list:
            raise ValueError('unsettled receipt exposed')
        if r['label'] is not None and (type(r['label']) is not int or not 0 <= r['label'] <= 960):
            raise ValueError('invalid purchase label')
        samples.append((bounded_graph_routes(r['query']),r['label']))
    return samples,receipts,source


def candidate_pool(samples,lengths):
    positive=[(routes,y) for routes,y in samples if y is not None]
    if not positive:
        return set()
    # Ground candidates in positive observed graphs; no hidden target is read.
    route_examples=positive[0][0]
    hypotheses=set()
    for length in lengths:
        for route,_ in route_examples:
            hypotheses.update(route[i:i+length] for i in range(len(route)-length+1))
    return hypotheses


def candidates(samples,lengths):
    return sorted(w for w in candidate_pool(samples,lengths)
                  if all(match(routes,w)==y for routes,y in samples))


def propose(packet):
    samples, receipts, source=admitted(packet)
    old=candidates(samples,BASE)
    trigger=not old
    if packet['mode']=='fixed':
        space=old
    elif packet['mode']=='exhaustive':
        space=candidates(samples,BASE+EXTENDED)
    else:
        space=candidates(samples,EXTENDED) if trigger else old
    diagnostic={'trigger': trigger, 'base_survivors':len(old),
                'extended_survivors':len(space) if trigger else 0,
                'candidate_fits':len(candidate_pool(samples,BASE if packet['mode']=='fixed' else BASE+EXTENDED)),'representation':'extended' if trigger else 'base'}
    if not space:
        return {**diagnostic,'action':'abstain','reason':'no-consistent-representation'}
    if len(space)>32:
        return {**diagnostic,'action':'abstain','reason':'version-space-too-large'}
    prior=source if packet['mode'] in ('integrated','sham') else None
    if packet['mode']=='sham' and prior is not None:
        prior=[3-prior[0],*prior[1:]]
    # Artifact is only a search-order prior, NOT proof or a filter. No target leak.
    ranked=sorted(space,key=lambda w:(0 if prior is not None and list(w[:7])==prior else 1,w))
    first=receipts[0] if receipts else None
    if first is not None and first['stage']=='diagnosis' and 'repair' not in first['reused_in']:
        return {**diagnostic,'action':'reuse','receipt_id':first['id'],'stage':'repair'}
    if first is not None and first['stage']=='diagnosis' and 'inheritance' not in first['reused_in'] and packet['mode'] in ('integrated','sham'):
        return {**diagnostic,'action':'reuse','receipt_id':first['id'],'stage':'inheritance'}
    if len(space)==1:
        chosen=space[0]
        if packet['mode']=='fixed' and not trigger:
            # Fixed grammar must independently verify just as the new grammar does.
            pass
        # Independent held-out short-chain confirmation; not equal to diagnosis graph.
        if not any(r['stage']=='qualification' for r in receipts):
            if packet['remaining']<1:
                return {**diagnostic,'action':'abstain','reason':'no-qualification-budget'}
            query=make_chain(chosen, extra=(2,))
            if any(r['query']==query for r in receipts):
                return {**diagnostic,'action':'abstain','reason':'duplicate-qualification-query'}
            return {**diagnostic,'action':'query','stage':'qualification','graph':query}
        qualifiers=[r for r in receipts if r['stage']=='qualification']
        if any(r['label'] is None for r in qualifiers):
            return {**diagnostic,'action':'abstain','reason':'qualification-falsified'}
        return {**diagnostic,'action':'accept','word':list(chosen)}
    if packet['remaining']==0:
        return {**diagnostic,'action':'abstain','reason':'budget-exhausted'}
    # Query a candidate chain: split admitted predictions into positive / blank.
    offers=[]
    for w in ranked[:16]:
        graph=make_chain(w)
        if any(r['query']==graph for r in receipts):
            continue
        route=bounded_graph_routes(graph)
        votes=[match(route,x) for x in space]
        a=sum(v is not None for v in votes); b=len(space)-a
        if a==0 or b==0:
            continue
        offers.append((-min(a,b),abs(a-b),0 if w==ranked[0] else 1,len(w),w,graph))
    if not offers:
        return {**diagnostic,'action':'abstain','reason':'no-discriminating-query'}
    chosen=min(offers)
    return {**diagnostic,'action':'query','stage':'diagnosis' if first is None else 'repair','graph':chosen[-1]}


def main():
    raw=sys.stdin.buffer.read(MAX_PACKET+1)
    if len(raw)>MAX_PACKET:
        raise ValueError('candidate input size cap')
    packet=json.loads(raw)
    result=propose(packet)
    print(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False))


if __name__=='__main__':
    main()
