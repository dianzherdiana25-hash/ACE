"""ACE R7.6: self-contained bounded candidate discovery and fresh e-value certification.

Public synthetic development only. Decision logic gets observations, never latent
probabilities or scorer-only samples. IID Bernoulli assumption excludes correlated.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import random

P0, P1, LIMIT, GROUPS = .80, .99, 10., 6
TRAIN_SEED = 20261111
SEEDS = (20261112, 20261113, 20261114, 20261115)
CAPS = (0, 6, 12, 18, 24)
METHODS = ('narrow6', 'full12', 'broad6', 'adaptive10', 'random6', 'abstain6')
BASES = {
    'stable': (.18,.42,.63,.78,.91,.97),
    'swap': (.91,.19,.36,.54,.33,.72),
    'reverse': (.90,.79,.29,.39,.17,.12),
    'new01': (.86,.94,.22,.68,.14,.24),
    'new23': (.21,.34,.96,.91,.27,.11),
    'all_null': (.55,.62,.70,.73,.75,.77),
    'correlated': (.18,.42,.63,.78,.91,.97),
    'near_boundary': (.77,.79,.80,.81,.82,.78),
}

def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def rng(*x):
    return random.Random(int(digest(x),16))

@dataclass(frozen=True)
class World:
    uid: str
    family: str
    probabilities: tuple[float,...]

def worlds(split, family, seed, n):
    if split not in ('train','validation','test') or family not in BASES or type(n) is not int or not 1<=n<=1000:
        raise ValueError('invalid bank')
    if split in ('train','validation') and (family != 'stable' or seed != TRAIN_SEED):
        raise ValueError('source isolation violated')
    if split == 'test' and seed not in SEEDS:
        raise ValueError('unknown final seed')
    out=[]
    for i in range(n):
        r=rng('r76-new-world',split,family,seed,i)
        p=tuple(min(.99,max(.01,v+r.uniform(-.09,.09))) for v in BASES[family])
        if family=='all_null': p=tuple(min(.799,v) for v in p)
        out.append(World(f'r76:{split}:{family}:{seed}:{i}',family,p))
    return tuple(out)

@lru_cache(maxsize=1000)
def score_draws(uid, probabilities):
    return tuple(int(rng('r76-score',uid,g,j).random() < probabilities[g]) for g in range(GROUPS) for j in range(64))

class Evaluator:
    def __init__(self,world,cap):
        if cap not in CAPS: raise ValueError('invalid cap')
        self.__world=world
        self.__cap=cap
        self.__counts=[0]*GROUPS
        self.purchases=0
    def buy(self,group):
        if type(group) is not int or not 0<=group<GROUPS: raise ValueError('invalid group')
        if self.purchases>=self.__cap: raise RuntimeError('label budget exceeded')
        i=self.__counts[group]
        self.__counts[group]+=1
        self.purchases+=1
        if self.__world.family=='correlated': i//=2
        return int(rng('r76-purchase',self.__world.uid,group,i).random()<self.__world.probabilities[group])
    def grade(self,chosen,estimates):
        if chosen is not None and (type(chosen) is not int or not 0<=chosen<GROUPS): raise ValueError('invalid decision')
        if len(estimates)!=GROUPS or any(not (0<=p<=1) for p in estimates): raise ValueError('invalid estimates')
        good=int(chosen is not None and self.__world.probabilities[chosen]>=P0)
        wrong=int(chosen is not None and self.__world.probabilities[chosen]<P0)
        labels=score_draws(self.__world.uid,self.__world.probabilities)
        bins=[[0.,0.,0] for _ in range(10)]
        sq=0.
        for i,y in enumerate(labels):
            p=estimates[i//64]
            b=min(9,int(p*10))
            bins[b][0]+=p
            bins[b][1]+=y
            bins[b][2]+=1
            sq+=(p-y)**2
        return dict(true_accepts=good,false_accepts=wrong,abstentions=GROUPS-good-wrong,
                    purchases=self.purchases,brier_sum=sq,bins=bins,scoring_probes=len(labels))
    def oracle_ceiling(self):
        return sum(p>=P0 for p in self.__world.probabilities)

def train_prior():
    success=[1]*GROUPS
    count=[2]*GROUPS
    purchases=0
    for w in worlds('train','stable',TRAIN_SEED,18):
        e=Evaluator(w,24)
        # 18 worlds × 6 groups × 12 labels cannot fit a per-world 24 cap,
        # so source training uses six separate 24-cap acquisition sessions.
        for g in range(GROUPS):
            sess=Evaluator(w,24)
            for _ in range(12):
                success[g]+=sess.buy(g)
                count[g]+=1
                purchases+=1
    return tuple(s/c for s,c in zip(success,count)),purchases

def sequence(method,prior,observations):
    """Pure selector; only acquired diagnostic replies and source prior used."""
    if method not in METHODS or len(prior)!=GROUPS or any(not 0<p<1 for p in prior):
        raise ValueError('invalid selector input')
    if method=='narrow6': return (0,4,5,0,4,5)
    return (0,1,2,3,4,5) if method!='full12' else tuple(range(GROUPS))*2

def shortlist(first,prior):
    if len(first)!=6 or any(type(y) is not int or y not in (0,1) for y in first):
        raise ValueError('requires exactly six purchased diagnostics')
    return tuple(sorted(range(GROUPS),key=lambda g:(first[g],prior[g],-g),reverse=True)[:2])

def candidate(method,obs,prior,short=None,uid=None):
    if method=='random6': return rng('r76-random-pick',uid).randrange(GROUPS)
    eligible=(0,4,5) if method=='narrow6' else tuple(range(GROUPS))
    if method=='adaptive10': eligible=short
    if method=='abstain6': return None
    counts={g:0 for g in eligible};total={g:0 for g in eligible}
    for g,y in obs:
        if g in counts:
            counts[g]+=1
            total[g]+=y
    return max(eligible,key=lambda g:(total[g]/counts[g],prior[g],-g))

@dataclass(frozen=True)
class Trace:
    result:dict
    candidate:int|None
    diagnostics:int
    certificates:int
    certified:bool


def play(world,prior,method,cap):
    if method not in METHODS or cap not in CAPS: raise ValueError('invalid method or cap')
    ev=Evaluator(world,cap)
    hits=[0]*GROUPS;counts=[0]*GROUPS;obs=[]
    fixed=sequence(method,prior,())
    for g in fixed[:cap]:
        y=ev.buy(g); hits[g]+=y;counts[g]+=1;obs.append((g,y))
    short=None
    needed=len(fixed)
    if method=='adaptive10' and len(obs)==6 and cap>6:
        short=shortlist(tuple(hits),prior)
        # Both shortlist groups receive two additional diagnostics, round-robin.
        extra=(short[0],short[1],short[0],short[1])
        for g in extra[:cap-6]:
            y=ev.buy(g);hits[g]+=y;counts[g]+=1;obs.append((g,y))
        needed=10
    elif method=='adaptive10': needed=10
    chosen=None
    if len(obs)>=needed and method!='abstain6':
        chosen=candidate(method,obs,prior,short=short,uid=world.uid)
    evalue=1.;cert=0;accepted=False
    if chosen is not None:
        while ev.purchases<cap:
            y=ev.buy(chosen);hits[chosen]+=y;counts[chosen]+=1
            cert+=1
            evalue*= P1/P0 if y else (1-P1)/(1-P0)
            if cert>=3 and evalue>=LIMIT:
                accepted=True
                break
    estimates=tuple((1+hits[g])/(2+counts[g]) for g in range(GROUPS))
    return Trace(ev.grade(chosen if accepted else None,estimates),chosen,len(obs),cert,accepted)

def aggregate(tasks,prior,method,cap):
    traces=[play(w,prior,method,cap) for w in tasks]
    bins=[[0.,0.,0] for _ in range(10)]
    for t in traces:
        for i,b in enumerate(t.result['bins']):
            for j in range(3): bins[i][j]+=b[j]
    n=sum(t.result['scoring_probes'] for t in traces)
    a={key:sum(t.result[key] for t in traces) for key in ('true_accepts','false_accepts','abstentions','purchases')}
    den=a['true_accepts']+a['false_accepts']
    a.update(tasks=len(tasks),cap=cap,diagnostic_labels=sum(t.diagnostics for t in traces),
             certificate_labels=sum(t.certificates for t in traces),
             selected_groups={str(g):sum(t.candidate==g for t in traces) for g in range(GROUPS)},
             certified_tasks=sum(t.certified for t in traces),
             ece=round(sum(abs(p-y) for p,y,c in bins if c)/n,6),
             brier=round(sum(t.result['brier_sum'] for t in traces)/n,6),
             false_acceptance_rate=round(a['false_accepts']/den,6) if den else None,
             correct_per_100_labels=round(100*a['true_accepts']/a['purchases'],6) if a['purchases'] else None)
    a['utility']=20*a['true_accepts']-60*a['false_accepts']-2*a['abstentions']-a['purchases']
    return a

def validation():
    prior,cost=train_prior()
    bank=worlds('validation','stable',TRAIN_SEED,12)
    return {'phase':'validation','offline_train_labels':cost,'prior':prior,
            'results':{method:aggregate(bank,prior,method,24) for method in METHODS}}

def final_once():
    prior,cost=train_prior()
    out={};manifests={};limits=[]
    for family in BASES:
        out[family]={};manifests[family]={}
        for seed in SEEDS:
            ts=worlds('test',family,seed,20)
            manifests[family][str(seed)]=digest([w.uid for w in ts])
            out[family][str(seed)]={str(cap):{method:aggregate(ts,prior,method,cap) for method in METHODS} for cap in CAPS}
            limits.append((family,seed,sum(w.probabilities[g]>=P0 for w in ts for g in range(GROUPS))))
    def get(f,m,k): return sum(out[f][str(seed)]['24'][m][k] for seed in SEEDS)
    core=('stable','swap','reverse','new01','new23')
    risk=('stable','swap','reverse','new01','new23','all_null','near_boundary')
    gate={
        'new23_exceeds_narrow':get('new23','adaptive10','true_accepts')>get('new23','narrow6','true_accepts'),
        'stable_coverage_and_safety':get('stable','adaptive10','true_accepts')>=.8*get('stable','full12','true_accepts') and get('stable','adaptive10','false_accepts')<=get('stable','full12','false_accepts'),
        'risk_not_higher':sum(get(f,'adaptive10','false_accepts') for f in risk)<=sum(get(f,'full12','false_accepts') for f in risk),
        'utility_at_least_full':sum(get(f,'adaptive10','utility') for f in core)>=sum(get(f,'full12','utility') for f in core),
        'utility_at_least_broad':sum(get(f,'adaptive10','utility') for f in core)>=sum(get(f,'broad6','utility') for f in core),
        'budget_and_certificate':all(out[f][str(s)][str(cap)][m]['purchases']<=20*cap and out[f][str(s)][str(cap)][m]['certified_tasks']<=20 for f in BASES for s in SEEDS for cap in CAPS for m in METHODS),
    }
    return {'classification':'PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY','protocol':'R76_PROTOCOL.md',
            'seeds':SEEDS,'source_prior':prior,'offline_train_labels':cost,'split_id_hashes':manifests,
            'oracle_ceiling_eval_only':{f:{str(s):n for fam,s,n in limits if fam==f} for f in BASES},
            'results':out,'gate':gate,'gate_pass':all(gate.values()),
            'scientific_decision':'HOLD_PENDING_INDEPENDENT_CONFIRMATION',
            'limits':['author-visible public mechanism families','single world Bernoulli null only','correlation breaks e-test validity',
                      'source training labels not part of online utility','final bank cannot be reused as fresh test']}

def main():
    a=argparse.ArgumentParser()
    a.add_argument('--phase',choices=('validation','final'),required=True)
    options=a.parse_args()
    result=validation() if options.phase=='validation' else final_once()
    print(json.dumps(result,indent=2,sort_keys=True,allow_nan=False))

if __name__=='__main__': main()
