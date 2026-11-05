"""Cold stdlib-only E1.4w grammar-search worker.

Mount this file alone in a fresh chroot namespace for each action. No imports
from ACE evaluator, no oracle, target truth, bank or probe data in its packet.
The grammar is explicitly bounded to five tree nodes; no new DSL primitives.
"""
from __future__ import annotations
from collections import Counter
from functools import lru_cache
import json
import random
import resource
import sys

GRID=tuple((a,b) for a in range(4,19) for b in range(a,19))
TERMINALS=(('lo',),('hi',),('const',0),('const',1),('const',2))
OPERATORS=('add','mul','min','max')


def value(t,a,b):
    if t[0]=='lo':return a
    if t[0]=='hi':return b
    if t[0]=='const':return t[1]
    x=value(t[1],a,b);y=value(t[2],a,b)
    if t[0]=='add':return x+y
    if t[0]=='mul':return x*y
    if t[0]=='min':return min(x,y)
    if t[0]=='max':return max(x,y)
    raise ValueError('unknown syntax')


def name(t):
    if t[0] in ('lo','hi'):return t[0]
    if t[0]=='const':return str(t[1])
    return '('+name(t[1])+{'add':'+','mul':'*','min':'min','max':'max'}[t[0]]+name(t[2])+')'


@lru_cache(maxsize=2)
def library(max_nodes):
    if max_nodes not in (3,5):raise ValueError('invalid grammar size')
    levels={1:{}}
    for t in TERMINALS:levels[1].setdefault(tuple(value(t,*v) for v in GRID),t)
    for size in range(3,max_nodes+1,2):
        stage={}
        for na in range(1,size-1,2):
            nb=size-1-na
            if na>nb:continue
            for va,ta in levels[na].items():
                for vb,tb in levels[nb].items():
                    if na==nb and name(ta)>name(tb):continue
                    for op in OPERATORS:
                        if op=='add':sig=tuple(x+y for x,y in zip(va,vb))
                        elif op=='mul':sig=tuple(x*y for x,y in zip(va,vb))
                        elif op=='min':sig=tuple(min(x,y) for x,y in zip(va,vb))
                        else:sig=tuple(max(x,y) for x,y in zip(va,vb))
                        if max(sig)>960 or any(sig in p for p in levels.values()):continue
                        stage.setdefault(sig,(op,ta,tb))
        levels[size]=stage
    return tuple(t for size in sorted(levels) for t in levels[size].values())


def validate_packet(packet):
    if type(packet) is not dict or set(packet)!= {'pair','observations','remaining','mode','seed'}:
        raise ValueError('invalid packet fields')
    pair=packet['pair']
    if (type(pair) is not list or len(pair)!=2 or
        any(type(w) is not list or len(w)!=3 or any(type(x) is not int or x not in (1,2) for x in w) for w in pair)):
        raise ValueError('invalid inert predecessor artifact')
    remaining=packet['remaining']
    if type(remaining) is not int or not 0<=remaining<=4:
        raise ValueError('invalid remaining labels')
    mode=packet['mode']
    if mode not in ('synthesis-safe','synthesis-eager','random-safe','compact-safe'):
        raise ValueError('unsupported worker strategy')
    seed=packet['seed']
    if type(seed) is not int or not 0<=seed<2**63:
        raise ValueError('invalid deterministic seed')
    observed=packet['observations']
    if type(observed) is not list or len(observed)!=4-remaining:
        raise ValueError('mismatched purchased observation count')
    out=[]
    for r in observed:
        if type(r) is not dict or set(r)!= {'costs','label'}:
            raise ValueError('invalid receipt fields')
        c=r['costs']; y=r['label']
        if type(c) is not list or len(c)!=2 or any(type(x) is not int or not 4<=x<=18 for x in c) or c[0]>c[1]:
            raise ValueError('invalid purchased route costs')
        if y is not None and (type(y) is not int or not 0<=y<=960):
            raise ValueError('invalid purchased label')
        out.append((tuple(c),y))
    return mode,seed,out,remaining


def decision(packet):
    mode,seed,observed,remaining=validate_packet(packet)
    size=3 if mode=='compact-safe' else 5
    expressions=library(size)
    # Graph with wrong source artifact yields None: never pretend it is numeric zero.
    if any(y is None for c,y in observed):return {'action':'abstain'}
    ids=tuple(i for i,t in enumerate(expressions) if all(value(t,*v)==y for v,y in observed))
    if not ids:return {'action':'abstain'}
    min_labels=1 if mode=='synthesis-eager' else 3
    if len(ids)==1 and len(observed)>=min_labels:
        return {'action':'accept','expression':name(expressions[ids[0]])}
    if remaining<=0:return {'action':'abstain'}
    used={c for c,y in observed}
    if len(ids)==1:
        controls=((0,14),(14,0),(1,9),(6,13),(8,2))
        ab=next((ab for ab in controls if (4+min(ab),4+max(ab)) not in used),None)
    else:
        offers=[]
        for a in range(15):
            for b in range(15):
                v=(4+min(a,b),4+max(a,b))
                if v in used:continue
                counts=Counter(value(expressions[i],*v) for i in ids)
                if len(counts)<2:continue
                score=(sum(n*n for n in counts.values()),max(counts.values()),a+b,a,b)
                offers.append((score,(a,b)))
        if not offers:ab=None
        elif mode=='random-safe':ab=random.Random(seed).choice(offers)[1]
        else:ab=min(offers)[1]
    if ab is None:return {'action':'abstain'}
    return {'action':'query','tolls':list(ab)}


def main():
    raw=sys.stdin.buffer.read(65_537)
    if len(raw)>65_536:raise ValueError('packet too long')
    packet=json.loads(raw.decode('utf-8'))
    result=decision(packet)
    u=resource.getrusage(resource.RUSAGE_SELF)
    result.update(cpu_us=round(1_000_000*(u.ru_utime+u.ru_stime)),rss_kib=u.ru_maxrss)
    sys.stdout.buffer.write(json.dumps(result,sort_keys=True,separators=(',',':')).encode())

if __name__=='__main__':main()
