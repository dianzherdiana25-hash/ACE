"""REAL E1.4y grammar/unknown-operator adapter for bounded E1.5 search.

The evaluator gives candidates only acquired labels. Validation/test scoring
is inside this evaluator and never handed to the candidate/query selector.
The dataset is deterministic *public development*, not sealed confirmation.
"""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
import random
import hashlib
from pathlib import Path
import e14.e14y_induction as original_grammar

from .engine import Policy, ResearchIntegrityError, _metrics, digest
from e14.e14y_induction import grammar, OUTSIDERS, candidates, choose_query, value_at, GRID, GRID_INDEX


@dataclass(frozen=True)
class World:
    key: str
    family: str
    index: int | None = None
    outsider: str | None = None

    def descriptor(self):
        return {'key':self.key,'family':self.family,'index':self.index,
                'outsider':self.outsider}


class OperatorAdapter:
    """Three disjoint world-ID splits, one heldout evaluation after selection."""
    def __init__(self,*,seed=20261105, sizes=(24,12,18), outsiders_per_split=2):
        if type(seed) is not int or type(sizes) is not tuple or len(sizes)!=3 or any(
                type(n) is not int or n<4 for n in sizes):
            raise ResearchIntegrityError('invalid bank configuration')
        if type(outsiders_per_split) is not int or not 0<=outsiders_per_split<=2:
            raise ResearchIntegrityError('invalid outsider fraction')
        g=grammar();rng=random.Random(seed)
        if sum(sizes)>len(g)+len(OUTSIDERS):
            raise ResearchIntegrityError('not enough independent operator worlds')
        sample=[World('grammar:'+str(i),g[i][0],i) for i in range(len(g))]
        sample.extend(World('outside:'+name,'unrepresented',outsider=name) for name in OUTSIDERS)
        rng.shuffle(sample)
        # Guarantee each split receives an out-of-grammar stress example when possible.
        outsiders=[x for x in sample if x.family=='unrepresented']
        inside=[x for x in sample if x.family!='unrepresented']
        rng.shuffle(outsiders);rng.shuffle(inside)
        sets=[]
        for i,n in enumerate(sizes):
            extra=outsiders[i*outsiders_per_split:(i+1)*outsiders_per_split]
            sets.append(tuple(inside[:n-len(extra)]+extra))
            inside=inside[n-len(extra):]
        self._sets=dict(zip(('train','validation','test'),sets))
        self.seed=seed;self.sizes=sizes;self.outsiders_per_split=outsiders_per_split
        self._memo={}
        keys=[w.key for worlds in self._sets.values() for w in worlds]
        if len(keys)!=len(set(keys)):
            raise ResearchIntegrityError('bank task identity collision')

    def bank_manifest(self):
        return {'version':1,'seed':self.seed,'sizes':list(self.sizes),'outsiders_per_split':self.outsiders_per_split,
                'split_worlds':{s:[w.descriptor() for w in v] for s,v in self._sets.items()},
                'grammar_signatures':len(grammar()),
                'grammar_semantics_sha256':digest([list(sig) for _,_,sig in grammar()]),
                'oracle_module_sha256':hashlib.sha256(Path(original_grammar.__file__).read_bytes()).hexdigest(),
                'outside_names':list(OUTSIDERS),
                'scoring':'finite_grid_exact_check','source_information':'NONE',
                'nature':'PUBLIC_SYNTHETIC_DEVELOPMENT'}

    def task_ids(self,split):
        if split not in self._sets:raise ResearchIntegrityError('unknown split')
        return tuple(w.key for w in self._sets[split])

    def _truth(self,w,xy):
        if w.family=='unrepresented':return value_at(('unknown',w.outsider),xy)
        return value_at(('known',grammar()[w.index][1]),xy)

    def _one(self,w,policy):
        observations=[];picked=set()
        for turn in range(policy.label_cap):
            ids=candidates(observations)
            if len(ids)==1:break
            xy=choose_query(ids,observations,strategy=policy.selector,
                            seed=self.seed+turn*7919+sum(ord(z) for z in w.key))
            if xy is None:break
            if xy in picked:
                raise ResearchIntegrityError('duplicate paid query')
            picked.add(xy)
            observations.append((xy,self._truth(w,xy)))
        ids=candidates(observations)
        accepted=len(ids)==1 and len(observations)>=policy.min_evidence
        if not accepted:
            return {'accepted_correct':0,'accepted_wrong':0,'abstained':1,
                    'logical_labels':len(observations),'probe_errors':0}
        predicted=grammar()[ids[0]][2]
        # Scorer-only independent finite-domain comparison. Unqueried labels
        # are NOT returned to the policy, candidate search or selector.
        target=tuple(self._truth(w,xy) for xy in GRID)
        wrong=sum(a!=b for a,b in zip(predicted,target))
        return {'accepted_correct':int(wrong==0),'accepted_wrong':int(wrong>0),
                'abstained':0,'logical_labels':len(observations),'probe_errors':wrong}

    def evaluate(self,policy,split):
        if type(policy) is not Policy:
            raise ResearchIntegrityError('typed policy required')
        if split not in self._sets:raise ResearchIntegrityError('unknown split')
        key=(policy,split)
        if key not in self._memo:
            self._memo[key]=_metrics([self._one(w,policy) for w in self._sets[split]])
        return dict(self._memo[key])
