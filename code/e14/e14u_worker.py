"""Standalone E1.4u candidate worker (no evaluator, labels oracle or repository imports).

The evaluator supplies only purchased examples and the policy/seed.  This
script models the public *hypothesis grammar* but never receives target truth,
held-out probes, or a callable oracle.  Intended for a read-only isolated mount.
"""
import json
import resource
import sys
from collections import Counter
from itertools import combinations, product

PATTERNS = tuple(product((1,2),repeat=3))
SINGLES = tuple(w for n in (3,4,5) for w in product((1,2),repeat=n))
PAIRS = tuple(combinations(PATTERNS,2))


def graph_routes(g):
    if type(g) is not dict or set(g) != {'nodes','start','goal','edges'}:
        raise ValueError('invalid graph shape')
    n, start, goal, rows = g['nodes'],g['start'],g['goal'],g['edges']
    if (type(n) is not int or not 2 <= n <= 16 or type(start) is not int
            or type(goal) is not int or not 0 <= start < goal < n
            or type(rows) is not list or not 1 <= len(rows) <= 16):
        raise ValueError('invalid graph bounds')
    by = {i:[] for i in range(n)}
    seen = set()
    for e in rows:
        if type(e) is not list or len(e)!=4 or any(type(x) is not int for x in e):
            raise ValueError('invalid edge')
        a,b,label,cost=e
        if not start <= a < b <= goal or not 0 <= label <= 3 or not 0 <= cost <= 15:
            raise ValueError('out-of-bounds edge')
        if tuple(e) in seen:
            raise ValueError('duplicate edge')
        seen.add(tuple(e));by[a].append(tuple(e))
    stack=[(start,(),0,())]; routes=[]; used=set()
    while stack:
        node, labels, cost, walked=stack.pop()
        if node==goal:
            routes.append((tuple(1 if a==b else 2 for a,b in zip(labels,labels[1:])),cost))
            used.update(walked)
            if len(routes)>16:raise ValueError('too many routes')
        else:
            for e in by[node]:
                stack.append((e[1],labels+(e[2],),cost+e[3],walked+(e,)))
            if len(stack)>512:raise ValueError('graph stack exceeded')
    if not routes or used!=seen or sum(len(e) for e,_ in routes)>256:
        raise ValueError('invalid route coverage')
    return routes


def match(events, word):
    return any(events[i:i+len(word)]==word for i in range(len(events)-len(word)+1))


def score(routes, candidate):
    kind, words=candidate
    if kind=='single-path':
        return min((v for e,v in routes if match(e,words[0])),default=None)
    if kind=='branch-pair':
        a,b=words
        return min((max(c,d) for i,(e,c) in enumerate(routes)
                    for j,(f,d) in enumerate(routes)
                    if i!=j and match(e,a) and match(f,b)),default=None)
    raise ValueError('invalid candidate')


def graph(words,tolls):
    count=len(words); depth=len(words[0]);goal=count*depth+1
    edges=[]
    for branch,(word,toll) in enumerate(zip(words,tolls)):
        vertices=[0,*range(1+branch*depth,1+(branch+1)*depth),goal]
        colors=[0]
        for event in word:colors.append(colors[-1]^int(event==2))
        edges.extend([[a,b,colors[i],1+toll if i==depth else 1]
                      for i,(a,b) in enumerate(zip(vertices,vertices[1:]))])
    return {'nodes':goal+1,'start':0,'goal':goal,'edges':edges}


def select(candidates, purchased, mode, seed):
    seen={tuple(sorted(map(tuple,x['edges']))) for x in purchased}
    feasible=[]
    for i,words in enumerate(combinations(PATTERNS,4)):
        g=graph(words,(0,2,5,9) if i%2==0 else (9,5,2,0))
        if tuple(sorted(map(tuple,g['edges']))) in seen:continue
        tally=Counter(score(graph_routes(g),c) for c in candidates)
        if len(tally)>1:feasible.append((g,tally))
    if not feasible:return None
    if mode in ('fixed','base-only'):return feasible[0][0]
    if mode=='random':return feasible[seed%len(feasible)][0]
    return min(feasible,key=lambda x:(sum(v*v for v in x[1].values()),
                                      max(x[1].values()),len(x[0]['edges']),x[0]['edges']))[0]


def solve(packet):
    if type(packet) is not dict or set(packet)!={'mode','seed','demos','purchased'}:
        raise ValueError('unexpected worker packet')
    mode,seed,demos,purchased=(packet[k] for k in ('mode','seed','demos','purchased'))
    if mode not in ('active','fixed','random','base-only') or type(seed) is not int or seed<0:
        raise ValueError('invalid worker policy')
    if type(demos) is not list or not 1<=len(demos)<=8 or type(purchased) is not list or len(purchased)>4:
        raise ValueError('invalid worker observation')
    observations=[]
    for row in demos:
        if type(row) is not dict or set(row)!={'input','output'}:
            raise ValueError('worker received unexpected observation')
        y=row['output']
        if y is not None and (type(y) is not int or not 0<=y<=960):
            raise ValueError('bad label')
        observations.append((graph_routes(row['input']),y))
    base=[('single-path',(w,)) for w in SINGLES]
    known=[c for c in base if all(score(r,c)==y for r,y in observations)]
    trigger=not known
    if trigger and mode!='base-only':
        all_pairs=[('branch-pair',p) for p in PAIRS]
        known=[c for c in all_pairs if all(score(r,c)==y for r,y in observations)]
    if len(known)==1:
        action={'action':'accept','candidate':{'kind':known[0][0],
                        'words':[list(w) for w in known[0][1]]}}
    elif not known or len(purchased)>=4:
        action={'action':'abstain'}
    else:
        chosen=select(known,purchased,mode,seed)
        action={'action':'query','graph':chosen} if chosen is not None else {'action':'abstain'}
    return {'trigger':trigger,'survivors':len(known),'action':action}


def main():
    payload=sys.stdin.buffer.read(131073)
    if len(payload)>131072:raise ValueError('oversized packet')
    result=solve(json.loads(payload))
    usage=resource.getrusage(resource.RUSAGE_SELF)
    result['cpu_us']=round(1_000_000*(usage.ru_utime+usage.ru_stime))
    result['rss_kib']=usage.ru_maxrss
    sys.stdout.buffer.write(json.dumps(result,allow_nan=False,sort_keys=True,separators=(',',':')).encode())

if __name__=='__main__':main()
