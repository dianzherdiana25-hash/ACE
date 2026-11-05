"""Researcher-authored public E1.4y development bank; separate from frozen E1.4t.

The deterministic program list is written and hashed before the study run.
It is NOT a blinded or independently held-out scientific benchmark.
"""
from __future__ import annotations
import hashlib
import json
import random
from .e14y_induction import grammar, OUTSIDERS

SEED=202611051617
SOURCE_PAIRS=(0,5,10)
TARGET_PAIRS=(18,22)

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def build():
    g=grammar();rng=random.Random(SEED)
    by_kind={name:[i for i,(kind,_,__) in enumerate(g) if kind==name]
             for name in ('residual','threshold')}
    # Do not construct operators in response to experimental outcomes.
    chosen=sorted(rng.sample(by_kind['residual'],20))+sorted(rng.sample(by_kind['threshold'],14))
    rows=[{'id':f'y:{i:03d}','family':g[k][0], 'program_id':k, 'outsider':None}
          for i,k in enumerate(chosen)]
    rows.extend({'id':f'y:{len(rows)+j:03d}','family':'unrepresented',
                 'program_id':None,'outsider':name}
                for j,name in enumerate(OUTSIDERS))
    return {'version':1,'seed':SEED,'candidate_count':len(g),
            'source_pair_indices':SOURCE_PAIRS,
            'target_pair_indices':TARGET_PAIRS,
            'strata_counts':{'residual':20,'threshold':14,'unrepresented':6},
            'rows':rows, 'status':'PUBLIC_DEVELOPMENT_PRE-SCORE_DESIGN'}
