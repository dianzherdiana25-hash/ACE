"""S4-v3 public synthetic nonstationary regime experiment. Standard-library only."""
import json, random, time
G,N,B=4,48,8
POLICIES=('successor','online_change','online_last','online_flip','fixed0','fixed1')

def worlds(seed, mode):
    r=random.Random(seed); typ=r.randrange(2); rows=[]
    for t in range(N):
        stay=(.85 if ((t//12)%2)==0 else .15) if mode=='alternating' else (.15 if ((t//12)%2)==0 else .85)
        if t and r.random()>stay: typ=1-typ
        rows.append((typ,[(r.random(),r.random()) for _ in range(B)]))
    return rows

def evaluate(rows,policy,learned=None):
    last=None; inferred=[]; success=0
    for t,(typ,draws) in enumerate(rows):
        if policy=='fixed0': pref=0
        elif policy=='fixed1': pref=1
        elif last is None: pref=0
        elif policy=='online_flip': pref=1-last
        elif policy=='online_last': pref=last
        else:
            window=inferred[max(0,len(inferred)-8):]
            same=sum(a==b for a,b in zip(window,window[1:]))
            flip=(len(window)-1)-same
            if policy=='online_change': flip_now=flip>same
            else:
                # Learned complexity-penalized transition offset from development;
                # bounded scalar, not new source or architecture.
                flip_now=(flip-same)>learned
            pref=(1-last) if flip_now else last
        counts=[0,0]; wins=[0,0]
        for j,draw in enumerate(draws):
            arm=pref if j==0 else (1-pref if j==1 else max((0,1),key=lambda k:((wins[k]+1)/(counts[k]+2),k==pref)))
            reward=int(draw[arm] < (.8 if arm==typ else .2))
            wins[arm]+=reward; counts[arm]+=1; success+=reward
        last=max((0,1),key=lambda k:(wins[k]/counts[k],k==pref)); inferred.append(last)
    return success

def run():
    start=time.process_time(); rec=[]; chosen=[]
    for g in range(G):
        dev=worlds(20264106+g,'alternating')
        # Development budget: one full task sequence for each of 5 candidates.
        candidate_offsets=(-4,-2,0,2,4)
        scores={str(k):evaluate(dev,'successor',k) for k in candidate_offsets}
        # Complexity penalty 1 point per abs offset, tie prefers zero.
        best=max(candidate_offsets,key=lambda k:(scores[str(k)]-abs(k),-abs(k),-k))
        chosen.append({'generation':g,'offset':best,'development_scores':scores})
        row={'generation':g}
        for split,mode,seed in (('future','alternating',20265106+g),('negative','reversed',20266106+g)):
            w=worlds(seed,mode)
            row[split]={p:evaluate(w,p,best) for p in POLICIES}
        rec.append(row)
    totals={split:{p:sum(r[split][p] for r in rec) for p in POLICIES} for split in ('future','negative')}
    controls=POLICIES[1:]
    gain=totals['future']['successor']-max(totals['future'][p] for p in controls)
    neg=totals['negative']['successor']-max(totals['negative'][p] for p in controls)
    threshold=.05*G*N*B
    return {'protocol':'S4-v3','generations':G,'tasks_per_generation':N,'labels_per_task':B,'candidate_offsets':[-4,-2,0,2,4],
            'development_labels':G*N*B*5,'future_labels':G*N*B*len(POLICIES),
            'negative_labels':G*N*B*len(POLICIES),'total_labels':G*N*B*(5+2*len(POLICIES)),
            'selected':chosen,'records':rec,'totals':totals,'future_gain':gain,'negative_gap':neg,
            'accept':gain>=threshold and neg>=-threshold,'threshold_successes':threshold,
            'cpu_seconds':time.process_time()-start}
if __name__=='__main__':print(json.dumps(run(),sort_keys=True,indent=2))
