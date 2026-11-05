"""S4-v4: bounded inherited Beta transition prior; public synthetic only."""
import json, random, time
G,N,B=4,48,8
POLICIES=('successor','reset','online_last','online_flip','fixed0','fixed1')

def worlds(seed, reversed_regime=False):
    rng=random.Random(seed); typ=rng.randrange(2); rows=[]
    for t in range(N):
        stay=(.85 if t//12%2==0 else .15)
        if reversed_regime: stay=1-stay
        if t and rng.random()>stay: typ=1-typ
        rows.append((typ,tuple((rng.random(),rng.random()) for _ in range(B))))
    return rows

def evaluate(rows, policy, prior):
    last=None; inferred=[]; reward_sum=0
    for typ,draws in rows:
        if policy=='fixed0': pref=0
        elif policy=='fixed1': pref=1
        elif last is None: pref=0
        elif policy=='online_flip': pref=1-last
        elif policy=='online_last': pref=last
        else: pref=last if prior[0]>=prior[1] else 1-last
        counts=[0,0]; wins=[0,0]
        for j,draw in enumerate(draws):
            if j==0: arm=pref
            elif j==1: arm=1-pref
            else: arm=max((0,1),key=lambda k:((wins[k]+1)/(counts[k]+2),k==pref))
            success=int(draw[arm] < (.8 if arm==typ else .2))
            counts[arm]+=1; wins[arm]+=success; reward_sum+=success
        last=max((0,1),key=lambda k:(wins[k]/counts[k],k==pref))
        inferred.append(last)
    same=sum(a==b for a,b in zip(inferred,inferred[1:]))
    return reward_sum,(same,len(inferred)-1-same)

def run():
    start=time.process_time(); inherited=[1,1]; records=[]
    for g in range(G):
        dev=worlds(20267106+g)
        dev_results={p:evaluate(dev,p,tuple(inherited)) for p in POLICIES}
        same,flip=dev_results['successor'][1]
        before=tuple(inherited); inherited[0]+=same; inherited[1]+=flip
        reset=(1+same,1+flip)
        future=worlds(20268106+g); negative=worlds(20269106+g,True)
        row={'generation':g,'prior_before':before,'prior_after':tuple(inherited),'reset_prior':reset,'dev_inferred_transitions':(same,flip)}
        for split,world in (('future',future),('negative',negative)):
            row[split]={}
            for p in POLICIES:
                prior=tuple(inherited) if p=='successor' else reset
                row[split][p]=evaluate(world,p,prior)[0]
        records.append(row)
    totals={s:{p:sum(r[s][p] for r in records) for p in POLICIES} for s in ('future','negative')}
    controls=POLICIES[1:]
    gain=totals['future']['successor']-max(totals['future'][p] for p in controls)
    neg=totals['negative']['successor']-max(totals['negative'][p] for p in controls)
    return {'protocol':'S4-v4','records':records,'totals':totals,'future_gain':gain,'negative_gap':neg,'accepted':gain>=77 and neg>=-76,'development_labels':9216,'future_labels':9216,'negative_labels':9216,'total_labels':27648,'cpu_seconds':time.process_time()-start}
if __name__=='__main__': print(json.dumps(run(),indent=2,sort_keys=True))
