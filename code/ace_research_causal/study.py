"""ACE R5 causal study: bounded, deterministic, synthetic, stdlib-only."""
from __future__ import annotations
import argparse
from dataclasses import dataclass, replace
import json
import random
from pathlib import Path

TRAIN = 80
ADAPT = 32
THRESHOLD = 0.45

@dataclass(frozen=True)
class World:
    a: float  # X -> M
    b: float  # X -> Y
    c: float  # M -> Y
    d: float  # latent U -> Y, and U -> X

@dataclass(frozen=True)
class Model:
    a: float
    b: float
    c: float
    intercept: float = 0.0

def make_world(seed, confounded=True):
    rng = random.Random(900000 + seed)
    def edge():
        return 0.0 if rng.random() < .28 else rng.choice((-1,1))*rng.uniform(.8,1.6)
    return World(edge(),edge(),edge(),rng.choice((-1,1))*rng.uniform(1.3,2) if confounded else 0)

def shift(w, seed):
    rng = random.Random(700000+seed)
    key = rng.choice(('a','b','c'))
    old = getattr(w,key)
    return replace(w,**{key: -old if old else rng.choice((-1.3,1.3))})

def sample(w, mode, rng):
    if mode not in ('obs','x','joint'):
        raise ValueError('unknown mode')
    u = rng.gauss(0,1)
    x = u + rng.gauss(0,.25)
    if mode in ('x','joint'):
        x = rng.uniform(-1.7,1.7)
    m = w.a*x + rng.gauss(0,.25)
    if mode == 'joint':
        m = rng.uniform(-1.7,1.7)
    y = w.b*x + w.c*m + w.d*u + rng.gauss(0,.3)
    return x,m,y

class Sampler:
    def __init__(self,w,seed,budget):
        self._w=w
        self._rng=random.Random(seed)
        self.budget=budget
        self.used=0
    def query(self,mode):
        if self.used>=self.budget:
            raise RuntimeError('sample budget exceeded')
        self.used+=1
        return sample(self._w,mode,self._rng)

def ls(rows,targets):
    p=len(rows[0])
    g=[[sum(r[i]*r[j] for r in rows)+(1e-8 if i==j else 0)
        for j in range(p)]+[sum(r[i]*t for r,t in zip(rows,targets))] for i in range(p)]
    for i in range(p):
        k=max(range(i,p),key=lambda j:abs(g[j][i]))
        g[i],g[k]=g[k],g[i]
        if abs(g[i][i])<1e-12:
            raise ValueError('ill-conditioned')
        z=g[i][i]
        g[i]=[v/z for v in g[i]]
        for j in range(p):
            if j!=i:
                z=g[j][i]
                g[j]=[a-z*b for a,b in zip(g[j],g[i])]
    return [g[i][-1] for i in range(p)]

def fit(outcome_rows,mediator_rows=None):
    if len(outcome_rows)<3:
        raise ValueError('insufficient outcomes')
    mediator_rows=mediator_rows if mediator_rows is not None else outcome_rows
    intercept,b,c=ls([(1,x,m) for x,m,y in outcome_rows],[y for x,m,y in outcome_rows])
    a=ls([(1,x) for x,m,y in mediator_rows],[m for x,m,y in mediator_rows])[1]
    return Model(a,b,c,intercept)

def train(w,seed,arm,n):
    sampler=Sampler(w,seed,n)
    if arm=='obs':
        model=fit([sampler.query('obs') for _ in range(n)])
    elif arm=='causal' and n%2==0:
        do_x=[sampler.query('x') for _ in range(n//2)]
        do_joint=[sampler.query('joint') for _ in range(n//2)]
        model=fit(do_joint,do_x)
    else:
        raise ValueError('invalid arm or odd budget')
    assert sampler.used==n
    return model,sampler.used

def random_model(seed):
    rng=random.Random(333+seed)
    return Model(*(rng.uniform(-1.6,1.6) for _ in range(3)))

def mean_do(w,kind,x,m):
    if kind=='x': return (w.b+w.c*w.a)*x
    if kind=='m': return w.c*m
    if kind=='joint': return w.b*x+w.c*m
    raise ValueError('bad intervention')

def predict(model,kind,x,m):
    return model.intercept+mean_do(model,kind,x,m)

def evaluate(w,model):
    a=1.25
    qs=[('x',-a,0),('x',a,0),('m',0,-a),('m',0,a)]+[
        ('joint',x,m) for x in (-a,a) for m in (-a,a)]
    e=[(mean_do(w,k,x,m)-predict(model,k,x,m))**2 for k,x,m in qs]
    real=w.b+w.c*w.a
    estimated=model.b+model.c*model.a
    action=1 if estimated>=0 else -1
    true_edges=[abs(v)>0 for v in (w.a,w.b,w.c)]
    inferred=[abs(v)>=THRESHOLD for v in (model.a,model.b,model.c)]
    tp=sum(t and p for t,p in zip(true_edges,inferred))
    fp=sum(not t and p for t,p in zip(true_edges,inferred))
    fn=sum(t and not p for t,p in zip(true_edges,inferred))
    return {'mse':sum(e)/len(e),'unseen_do_m_mse':sum(e[2:4])/2,
            'plan_regret':max(0,abs(real)-action*real),
            'plan_accuracy':float(action*real>=0),
            'cf_delta_mse':(2*(real-estimated))**2,
            'edge_f1':2*tp/(2*tp+fp+fn) if tp+fp+fn else 1.0}

def run_world(seed,confounded):
    w=make_world(seed,confounded)
    newer=shift(w,seed)
    obs,o_cost=train(w,17*seed+1,'obs',TRAIN)
    causal,c_cost=train(w,17*seed+2,'causal',TRAIN)
    random=random_model(seed)
    obs_new,oa_cost=train(newer,17*seed+3,'obs',ADAPT)
    causal_new,ca_cost=train(newer,17*seed+4,'causal',ADAPT)
    assert o_cost==c_cost==TRAIN and oa_cost==ca_cost==ADAPT
    return {'obs_stationary':evaluate(w,obs),'causal_stationary':evaluate(w,causal),
            'random_stationary':evaluate(w,random),
            'obs_shift_static':evaluate(newer,obs),
            'causal_shift_static':evaluate(newer,causal),
            'random_shift_static':evaluate(newer,random),
            'obs_shift_adapt':evaluate(newer,obs_new),
            'causal_shift_adapt':evaluate(newer,causal_new)}

def average(cases):
    return {arm:{metric:round(sum(case[arm][metric] for case in cases)/len(cases),6)
                 for metric in cases[0][arm]} for arm in cases[0]}

def paired_ci(cases,left,right,metric):
    values=[case[left][metric]-case[right][metric] for case in cases]
    rng=random.Random(20261105)
    boot=sorted(sum(values[rng.randrange(len(values))] for _ in values)/len(values)
                for _ in range(2000))
    return {'mean':round(sum(values)/len(values),6),
            'ci95':[round(boot[50],6),round(boot[1949],6)]}

def experiment(n=100):
    if n<2:
        raise ValueError('at least two worlds')
    conf=[run_world(50000+i,True) for i in range(n)]
    clean=[run_world(90000+i,False) for i in range(n)]
    # Observation-equivalent SCMs: (X=U,Y=X) vs (X=U,Y=U).
    # Both yield the same joint distribution X=Y=U, but do(X=1)
    # gives mean Y=1 vs mean Y=0, respectively.
    witness={'same_observations':True,'do_x_1_mean_A':1,'do_x_1_mean_B':0}
    return {'protocol':{'worlds_per_cohort':n,'train_samples_per_arm':TRAIN,
                        'adapt_samples_per_arm':ADAPT,'random_samples_used':0,
                        'training_interventions':['do(X)','do(X,M)'],
                        'evaluation_interventions':['do(X)','do(M)','do(X,M)'],
                        'seed_confounded':[50000,50000+n-1],
                        'seed_unconfounded':[90000,90000+n-1],
                        'edge_threshold':THRESHOLD,'bootstrap_draws':2000},
            'confounded':average(conf),
            'unconfounded_negative_control':average(clean),
            'contrasts':{
                'stationary_mse_causal_minus_obs':paired_ci(conf,'causal_stationary','obs_stationary','mse'),
                'stationary_plan_regret_causal_minus_obs':paired_ci(conf,'causal_stationary','obs_stationary','plan_regret'),
                'shift_adapt_mse_causal_minus_obs':paired_ci(conf,'causal_shift_adapt','obs_shift_adapt','mse'),
                'no_confounder_mse_causal_minus_obs':paired_ci(clean,'causal_stationary','obs_stationary','mse')},
            'nonidentifiability_witness':witness,
            'scientific_status':'EXPLORATORY_NOT_INDEPENDENTLY_ACCEPTED'}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--worlds',type=int,default=100)
    parser.add_argument('--output',type=Path,default=Path('causal_results.json'))
    args=parser.parse_args()
    result=experiment(args.worlds)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+'
')
    print('Wrote',args.output,'worlds/cohort:',args.worlds)

if __name__=='__main__':
    main()
