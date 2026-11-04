"""Fresh five-event source/target tasks; all query pools reserved before words.

Public-development evaluator. Never import it inside the candidate selector.
"""
from __future__ import annotations
import hashlib
import random
from dataclasses import dataclass
from e13.contract import canonical_json
from e13.evaluator.selection import input_key
from .cross_episode_bank import _raw, _random_events, _contains
from .cross_episode_bank_v2 import _prior_inputs
from .query_bank import oracle
from .e14d_policy import grammar5

PAIR_SEED=141801
POOL_SEED=141802
DEMO_SEED=141803
FAMILIES=('S','G')
REGIMES=('related','unrelated')

@dataclass(frozen=True)
class Episode:
    family:str
    regime:str
    role:str
    slot:int
    word:tuple[int,...]  # evaluator custody only, not sent to policy learner
    task_id:str
    demos:tuple[dict,...]
    pool:tuple
    probes:tuple[dict,...]
    probe_types:tuple[str,...]


def pairs(family):
    r=random.Random(PAIR_SEED+(family=='G'))
    words=list(grammar5(family));r.shuffle(words)
    selected=[];used=set()
    for regime in ('related','unrelated'):
        for _ in range(3):
            match=next(((a,b) for a in words if a not in used for b in words
                       if b not in used and a!=b and
                       (sum(x!=y for x,y in zip(a,b))==1 if regime=='related'
                        else sum(x!=y for x,y in zip(a,b))>=3)),None)
            if not match:raise ValueError('not enough fresh five-event motifs')
            used.update(match);selected.append((regime,*match))
    return tuple(selected)


def pools(used):
    # Completely fixed role/family/slot coordinates; no hidden rule or oracle.
    result={}
    for fam in FAMILIES:
        for slot in range(6):
            for role in ('source','target'):
                r=random.Random(POOL_SEED+100*(fam=='G')+2*slot+(role=='target'))
                result[(fam,slot,role)]=tuple(_raw(fam,_random_events(fam,r,r.randint(9,14)),r,used[fam])
                                              for _ in range(8))
    return result


def positive_events(fam,word,r):
    if fam=='G':
        return (*((0,) if word[0]!=0 else ()),*word,*((1,) if r.randrange(2) else ()))
    return (*_random_events(fam,r,r.randint(1,3)),*word)


def negative_events(fam,word,r):
    for _ in range(2048):
        events=_random_events(fam,r,r.randint(8,12))
        if not _contains(events,word):return events
    raise ValueError('cannot generate negative events')


def make_episode(fam,regime,role,slot,word,pool,used):
    r=random.Random(DEMO_SEED+100*(fam=='G')+2*slot+(role=='target'))
    # Demo hardness controls are preallocated by slot/role, not by target outcomes.
    demo_kinds=('negative','positive') if slot%2 else ('negative','negative')
    demos=[]
    for kind in demo_kinds:
        events=positive_events(fam,word,r) if kind=='positive' else negative_events(fam,word,r)
        value=_raw(fam,events,r,used[fam]);demos.append({'input':value,'output':oracle(fam,word,value)})
    probes=[];kinds=[]
    # 4 natural random probes, then 4 diagnostic probes (2 positive, 2 negative).
    # Disclose both strata; synthetic diagnostic distribution is not natural prevalence.
    for i in range(8):
        if i<4:
            events=_random_events(fam,r,r.randint(9,14));kind='natural'
        else:
            kind='diagnostic';events=(positive_events(fam,word,r) if i in (4,6)
                                      else negative_events(fam,word,r))
        value=_raw(fam,events,r,used[fam]);probes.append({'input':value,'output':oracle(fam,word,value)})
        kinds.append(kind)
    tid=hashlib.sha256(canonical_json([fam,regime,role,slot,word])).hexdigest()[:32]
    return Episode(fam,regime,role,slot,word,tid,tuple(demos),pool,tuple(probes),tuple(kinds))


def bank():
    used=_prior_inputs() # includes historical E1.4 public, v1 and v2 inventories
    pp=pools(used)        # allocation is entirely before any rule-conditioned demos
    result=[]
    for fam in FAMILIES:
        for slot,(regime,sw,tw) in enumerate(pairs(fam)):
            result.append((make_episode(fam,regime,'source',slot,sw,pp[(fam,slot,'source')],used),
                           make_episode(fam,regime,'target',slot,tw,pp[(fam,slot,'target')],used)))
    return tuple(result)


def digest(pairs_):
    return hashlib.sha256(canonical_json([[{'family':t.family,'regime':t.regime,
     'role':t.role,'slot':t.slot,'word':t.word,'task_id':t.task_id,
     'demos':t.demos,'pool':t.pool,'probes':t.probes,'probe_types':t.probe_types}
     for t in pair]for pair in pairs_])).hexdigest()
