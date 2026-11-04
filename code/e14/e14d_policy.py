"""Source-trained context selector: never imports oracle, bank, or evaluator.

Fixed five-event candidate grammar; it is *not* novel architecture invention.
"""
from __future__ import annotations
from itertools import product
from collections import Counter
from .cross_episode_candidate import choose, predict, POLICIES

def grammar5(family):
    if family == "S":
        return tuple(product(range(3), repeat=5))
    if family == "G":
        return tuple((0,*tail) for tail in product((1,2),repeat=4))+tuple(product((1,2),repeat=5))
    raise ValueError("unknown family")


ABSTAIN='ABSTAIN'
PENALTY=1 # one correct probe equivalent per oracle label in source utility


def fit5(family,demos):
    words=grammar5(family)
    scores=[(sum(predict(family,w,d['input'])==d['output'] for d in demos),w) for w in words]
    m=max(s for s,_ in scores)
    return tuple(w for s,w in scores if s==m)


def context(family,candidates,pool):
    if len(candidates)<=1:return 'resolved'
    disagreements=0
    for item in pool:
        outs={predict(family,w,item) for w in candidates}
        disagreements+=len(outs)>1
    if not disagreements:return 'no_disagreement'
    if len(candidates)>40:return 'high_ambiguity'
    return 'low_ambiguity'



def minimax_index(family,candidates,pool):
    """Class-informed minimax split, using only unlabeled hypothesis predictions."""
    if not candidates or len(pool)!=8:raise ValueError('bad minimax input')
    values=[]
    for i,raw in enumerate(pool):
        groups=Counter(predict(family,w,raw) for w in candidates)
        values.append((max(groups.values()),-len(groups),i))
    return min(range(8), key=lambda i:values[i])


def choose_context(family,candidates,pool,model,seed):
    key=context(family,candidates,pool)
    action=model.get(key,model.get('fallback',ABSTAIN))
    if key in ('resolved','no_disagreement') or action==ABSTAIN:
        return {'policy':ABSTAIN,'index':None,'reason':key,'bucket':key,'labels':0}
    i,reason=choose(action,family,candidates,pool,seed=seed)
    return {'policy':action,'index':i,'reason':reason,'bucket':key,'labels':1}


def learn(source_records,family):
    """Learn a source-only mapping; penalize label and prefer abstention in ties."""
    rows=[s for s in source_records if s['family']==family]
    if len(rows)!=6:raise ValueError('six source episodes per family required')
    model={}
    for bucket in ('high_ambiguity','low_ambiguity'):
        group=[s for s in rows if s['bucket']==bucket]
        if not group:continue
        # Utility is probe correct minus one correct-probe-equivalent per label.
        totals={p:sum(s['policy_scores'][p]-PENALTY for s in group) for p in POLICIES}
        abstain=sum(s['no_label'] for s in group)
        best=max(POLICIES,key=lambda p:(totals[p],-POLICIES.index(p)))
        model[bucket]=best if totals[best]>abstain else ABSTAIN
    model['fallback']=ABSTAIN
    return {'family':family,'mapping':model,'source_episodes':6,'source_labels':48,
            'training_rule':'max net source accuracy minus one probe point per acquired label'}
