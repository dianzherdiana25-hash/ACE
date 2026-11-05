"""S1-B public synthetic diagnostic grammar expansion; no ACE frozen data."""
import json,random,time
from itertools import product
X=list(product((0,1),repeat=4))
def family(max_degree):
    return sorted({tuple((sum(x[j] for j in range(4) if mask>>j&1)+bias)%2 for x in X)
                   for mask in range(1,16) if mask.bit_count()<=max_degree for bias in (0,1)})
BASE=family(3);EXT=family(4)
def run(truth,policy,seed,budget=6):
    rng=random.Random(seed);ids=list(range(16));rng.shuffle(ids);train=ids[:12];test=ids[12:]
    live=BASE[:];used=[];repaired=False
    for _ in range(budget):
        avail=[i for i in train if i not in used]
        if policy=='random':q=rng.choice(avail)
        elif policy=='static':q=avail[0]
        else:q=max(avail,key=lambda i:(sum(h[i] for h in live)*(len(live)-sum(h[i] for h in live)),-i)) if live else avail[0]
        used.append(q);label=truth[q];live=[h for h in live if h[q]==label]
        if not live and policy=='repair':
            repaired=True;live=[h for h in EXT if all(h[i]==truth[i] for i in used)]
    if not live:return {'acc':0.0,'labels':len(used),'repair':repaired,'remaining':0}
    acc=sum((2*sum(h[i] for h in live)>len(live))==bool(truth[i]) for i in test)/len(test)
    return {'acc':acc,'labels':len(used),'repair':repaired,'remaining':len(live)}
def study():
    start=time.process_time();results={};n=100
    for world in ('parity4','in_grammar','noisy'):
        results[world]={}
        for policy in ('random','static','adaptive','repair'):
            rows=[]
            for k in range(n):
                rng=random.Random(32000+k)
                if world=='parity4':truth=tuple(sum(x)%2 for x in X)
                elif world=='in_grammar':truth=BASE[(k*17+5)%len(BASE)]
                else:
                    truth=list(BASE[(k*17+5)%len(BASE)]);truth[rng.randrange(16)]^=1;truth=tuple(truth)
                rows.append(run(truth,policy,32000+k))
            results[world][policy]={'accuracy':round(sum(r['acc'] for r in rows)/n,5),
              'labels':sum(r['labels'] for r in rows),'repair_triggered':sum(r['repair'] for r in rows),
              'zero_posterior':sum(r['remaining']==0 for r in rows)}
    results['meta']={'worlds_per_stratum':n,'labels_per_arm':6,'train_points':12,'test_points':4,
      'base_hypotheses':len(BASE),'expanded_hypotheses':len(EXT),
      'total_train_labels':3*4*n*6,'cpu_seconds':round(time.process_time()-start,6)}
    return results
if __name__=='__main__':print(json.dumps(study(),indent=2,sort_keys=True))
