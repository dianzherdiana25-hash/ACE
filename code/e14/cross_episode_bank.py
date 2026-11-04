"""Fresh E1.4c source/target rule blocks; evaluator side only.

Every task uses a new length-4 motif, distinct from the previously exercised
length-3 E1.4b motifs. Pool construction does not inspect true labels or
candidate predictions. Source tasks teach policies; target tasks test transfer.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from itertools import product

from e13.contract import canonical_json, parse_fit_request
from e13.evaluator.selection import input_key
from e14.query_bank import _used_public, oracle, bank as prior_query_bank
from e14.query_replication import bank as previous_replication
from .cross_episode_candidate import inventory

SEED = 141701
FAMILIES = ("S", "G")
REGIMES = ("related", "unrelated")


@dataclass(frozen=True)
class Task:
    family: str
    regime: str
    role: str
    pair_id: int
    word: tuple[int, ...]  # evaluator-only; never forwarded into candidate fit
    task_id: str
    demos: tuple[dict, ...]
    pool: tuple[dict, ...]
    probes: tuple[dict, ...]


def _distance(a,b):
    return sum(x != y for x,y in zip(a,b,strict=True))


def _pairs(family):
    """Six disjoint pairs: three one-edit related and three >=3-edit unrelated."""
    earlier = {case.word for case in (*prior_query_bank(), *previous_replication())
               if case.episode.family == family}
    available = [word for word in inventory(family) if word not in earlier]
    random.Random(SEED + (0 if family == "S" else 1)).shuffle(available)
    used, result = set(), []
    for regime in REGIMES:
        for _ in range(3):
            match = next(((a,b) for a in available if a not in used for b in available
                          if b not in used and b != a and
                          (_distance(a,b) == 1 if regime == "related" else _distance(a,b) >= 3)), None)
            if match is None:
                raise ValueError("insufficient disjoint grammar motifs")
            a,b = match
            used.update(match)
            result.append((regime,a,b))
    return tuple(result)


def _make_input(family, events, rng):
    if family == "S":
        vals=[0]
        for event in events:
            vals.append(vals[-1]+(1,0,-1)[event])
        lo,hi=-min(vals),15-max(vals)
        if lo>hi:
            raise ValueError("symbol trace exceeds byte-token range")
        off=rng.randint(lo,hi)
        return [v+off for v in vals]
    if not events or events[0]!=0 or any(x not in (1,2) for x in events[1:]):
        raise ValueError("invalid graph event chain")
    labels=[rng.randrange(4)]
    for event in events[1:]:
        labels.append(labels[-1] if event==1 else (labels[-1]+rng.randint(1,3))%4)
    costs=[rng.randint(1,7) for _ in labels]
    return {"nodes":len(labels)+1,"start":0,"goal":len(labels),
            "edges":[[i,i+1,labels[i],costs[i]] for i in range(len(labels))]}


def _random_events(family,rng,length):
    return tuple(rng.randrange(3) for _ in range(length)) if family=="S" else (
        0, *(rng.choice((1,2)) for _ in range(length-1))
    )


def _contains(events,word):
    return any(events[i:i+len(word)]==word for i in range(len(events)-len(word)+1))


def _raw(family,events,rng,used):
    for _ in range(256):
        value=_make_input(family,events,rng)
        key=input_key(family,value)
        if key not in used:
            used.add(key)
            return json.loads(key)
    raise ValueError("fresh-input space exhausted")


def _task(family,regime,role,pair_id,word,rng,used):
    demos=[]
    # Weak but correctly labeled demonstrations: two word-avoiding random traces.
    # Source/target learn query usefulness, not the true motif ID.
    attempts=0
    while len(demos)<2 and attempts<1000:
        attempts+=1
        events=_random_events(family,rng,rng.randint(5,8))
        if _contains(events,word):
            continue
        val=_raw(family,events,rng,used)
        demos.append({"input":val,"output":oracle(family,word,val)})
    if len(demos)!=2:
        raise ValueError("could not create negative-only demonstrations")
    # Unlabeled pool is generated without consulting the hidden target word.
    pool=tuple(_raw(family,_random_events(family,rng,rng.randint(8,14)),rng,used)
               for _ in range(8))
    probes=[]
    for i in range(8):
        if i%2==0:
            if family=="S":
                events=(*_random_events(family,rng,rng.randint(1,3)),*word)
            else:
                events=word if word[0]==0 else (0,*word)
                events=(*events,*((1,) if i>=4 else ()))
        else:
            for _ in range(256):
                events=_random_events(family,rng,rng.randint(6,12))
                if not _contains(events,word):
                    break
            else:
                raise ValueError("unable to create negative probe")
        val=_raw(family,events,rng,used)
        probes.append({"input":val,"output":oracle(family,word,val)})
    task_id=f"{rng.getrandbits(128):032x}"
    parse_fit_request(canonical_json({"version":1,"task_id":task_id,"family":family,
        "seed":rng.getrandbits(32),"fuel":75000,"source":demos[:1],"target":demos}))
    return Task(family,regime,role,pair_id,word,task_id,tuple(demos),pool,tuple(probes))


def bank():
    rng=random.Random(SEED)
    used=_used_public()
    for prior in previous_replication():
        fam=prior.episode.family
        request=json.loads(prior.episode.fit_request)
        used[fam].update(input_key(fam,d["input"]) for d in request["target"])
        used[fam].update(prior.pool)
        used[fam].update(p.input for p in (*prior.episode.in_distribution,*prior.episode.extrapolation))
    result=[]
    for family in FAMILIES:
        for i,(regime,source,target) in enumerate(_pairs(family)):
            result.append((_task(family,regime,"source",i,source,rng,used[family]),
                           _task(family,regime,"target",i,target,rng,used[family])))
    return tuple(result)


def digest(pairs):
    return hashlib.sha256(canonical_json([
        [{"family":t.family,"regime":t.regime,"role":t.role,"pair":t.pair_id,
          "word":t.word,"task_id":t.task_id,"demos":t.demos,"pool":t.pool,"probes":t.probes}
         for t in pair] for pair in pairs])).hexdigest()
