"""Evaluator-owned deterministic E1.4t public-development bank.

Four explicitly distinct strata, with no target or probe ever sent to workers.
This is a new bounded extension task, not a redesign of frozen E1.4o/s.
"""
from __future__ import annotations

import hashlib
import json
import random

from .e14_integrated_graph import graph_oracle
from .e14t_worker import make_chain

SEED = 2026110513
STRATA = ('reachable', 'natural', 'rare', 'out-of-grammar')


def sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def packed(words):
    """Exactly two word paths, same toll, shared prefix then independent tails."""
    if type(words) not in (tuple,list) or len(words)!=2:
        raise ValueError('need two words')
    a,b=[tuple(w) for w in words]
    length=len(a)
    if length!=len(b) or not 8<=length<=10 or a==b or a[:length-2]!=b[:length-2]:
        raise ValueError('words must share a long prefix and differ in last two events')
    base_len=length-1  # common *edge* colors before a branch
    goal=base_len+3
    edges=[]
    colors=[]
    for word in (a,b):
        seq=[0]
        for event in word:
            seq.append(seq[-1] ^ (event==2))
        colors.append(seq)
    for i in range(base_len):
        edges.append([i,i+1,colors[0][i],1])
    for branch,seq in enumerate(colors):
        via=base_len+1+branch
        edges.extend([[base_len,via,seq[base_len],1],
                      [via,goal,seq[base_len+1],1]])
    return {'nodes':goal+1,'start':0,'goal':goal,'edges':edges}


def _word(rng,n):
    return tuple(rng.choice((1,2)) for _ in range(n))


def _pair(rng,length):
    prefix=_word(rng,length-2)
    tails=[(1,1),(1,2),(2,1),(2,2)]
    u,v=rng.sample(tails,2)
    return prefix+u,prefix+v


def _negative_coverage(pair, length):
    # Every shorter motif (<=length-1) in the ambiguous positive query occurs
    # in a length-(length-1) window. Negative windows eliminate old grammars.
    windows=sorted({tuple(w[i:i+length-1]) for w in pair for i in range(2)})
    return [make_chain(w) for w in windows]


def _reprice(graph,ticket):
    # Distinct public graph identities across all world/role/split positions;
    # modifying common-prefix edges preserves equal toll for packed branches.
    out=json.loads(json.dumps(graph))
    for i in range(3):
        out['edges'][i][3]=(ticket//(15**i))%15
    return out


def _probes(rng, pair, target, stratum):
    probes=[]
    for w in pair:
        for prefix in ((1,),(2,)):
            probes.append(make_chain(w,extra=prefix))
    negative=[(2,)*len(target), (1,)*len(target)]
    probes.extend(make_chain(w) for w in negative)
    # The score data is public-development but always evaluator-only at runtime.
    rng.shuffle(probes)
    return probes


def build(seed=SEED, per_stratum=12):
    if type(seed) is not int or not 0<=seed<2**32:
        raise ValueError('seed out of bounds')
    if type(per_stratum) is not int or not 1<=per_stratum<=48:
        raise ValueError('invalid sample count')
    rng=random.Random(seed)
    worlds=[]
    used=set()
    for stratum in STRATA:
        for slot in range(per_stratum):
            length=10 if stratum=='out-of-grammar' else 8+slot%2
            pair=_pair(rng,length)
            target=pair[rng.randrange(2)]
            positive=packed(pair)
            negatives=_negative_coverage(pair,length)
            if stratum=='reachable' or stratum=='out-of-grammar':
                selected=negatives
            elif stratum=='rare':
                selected=negatives[:1]
            else:
                selected=[]
            index=STRATA.index(stratum)*per_stratum+slot
            rawprobes=_probes(rng,pair,target,stratum)
            rawinputs=[positive,*selected]
            if len(rawinputs)+len(rawprobes)>32:
                raise ValueError('graph roles exceed collision-free ticket range')
            demos=[{'input':_reprice(g,index*32+i),
                    'output':None} for i,g in enumerate(rawinputs)]
            for row in demos:
                row['output']=graph_oracle(row['input'],target)
            probes=[_reprice(g,index*32+len(demos)+j) for j,g in enumerate(rawprobes)]
            for g in [x['input'] for x in demos]+probes:
                d=sha(g)
                if d in used:
                    raise ValueError('cross-split or cross-world graph collision')
                used.add(d)
            worlds.append({'id':f'{stratum}:{slot:02d}', 'stratum':stratum,
                           'source_word':list(target[:7]),
                           'demos':demos, 'probes':probes,
                           'target':list(target), 'source_label_calls':0,
                           'source_origin':'synthetic-aligned-prior-untrained'})
    return {'version':1,'seed':seed,'per_stratum':per_stratum,'worlds':worlds,
            'domain':'typed-branching-weighted-DAG',
            'status':'public-development-not-confirmatory'}


def public_packet(world,mode):
    if type(world) is not dict or type(mode) is not str:
        raise ValueError('invalid worker packet')
    # Source-word is a synthetic predecessor artifact, not the target.
    source=world['source_word'] if mode!='no-inheritance' else None
    return {'mode':mode,'source_word':source,'demos':world['demos']}


def audit_bank(bank):
    if len(bank['worlds'])!=len(STRATA)*bank['per_stratum']:
        raise ValueError('incorrect bank size')
    seen_worlds=set(); seen_graphs=set(); counts={s:0 for s in STRATA}; ngraphs=0
    for w in bank['worlds']:
        if w['id'] in seen_worlds or w['stratum'] not in STRATA:
            raise ValueError('duplicate/malformed world')
        seen_worlds.add(w['id']);counts[w['stratum']]+=1
        truth=tuple(w['target'])
        if w['source_word']!=list(truth[:7]):
            raise ValueError('invalid public source artifact')
        for row in w['demos']:
            if graph_oracle(row['input'],truth)!=row['output']:
                raise ValueError('incorrect seeded example')
        all_graphs=[x['input'] for x in w['demos']]+w['probes']
        for g in all_graphs:
            graph_oracle(g,truth)
            digest=sha(g)
            if digest in seen_graphs:
                raise ValueError('train-probe or interworld graph collision')
            seen_graphs.add(digest)
        ngraphs+=len(w['demos'])+len(w['probes'])
    if any(n!=bank['per_stratum'] for n in counts.values()):
        raise ValueError('wrong stratum counts')
    return {'worlds':len(bank['worlds']),'graphs_checked':ngraphs,
            'strata':counts,'bank_sha256':sha(bank)}
