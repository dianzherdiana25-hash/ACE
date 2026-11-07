import random,json,time,statistics
from collections import defaultdict
N=6
pairs=[(a,b) for a in range(N) for b in range(a+1,N)]
ops=[(op,a,b) for op in ('xor','and') for a,b in pairs]
def predict(c,x):
 op,a,b=c;u=(x>>a)&1;v=(x>>b)&1
 return u^v if op=='xor' else u&v
def run():
 t=time.process_time();out=defaultdict(lambda:defaultdict(list));checks=labels=trials=0
 for family in ('xor','and','parity3'):
  for seed in list(range(64))+list(range(10000,10256)):
   rng=random.Random(seed+{'xor':0,'and':100000,'parity3':200000}[family]);train=rng.sample(range(64),32);test=[i for i in range(64) if i not in train]
   a,b=rng.choice(pairs);third=rng.choice([i for i in range(N) if i not in (a,b)])
   y=lambda x:(predict(('xor' if family=='parity3' else family,a,b),x)^((x>>third)&1)) if family=='parity3' else predict((family,a,b),x)
   yy={x:y(x) for x in train};labels+=32;trials+=1
   associations=[]
   for i in range(N):
    p=sum(yy[x] for x in train)/32;q=sum((x>>i)&1 for x in train)/32
    cov=abs(sum((yy[x]-p)*(((x>>i)&1)-q) for x in train)/32)
    associations.append((cov,i))
   checks+=6*32
   rank=[i for _,i in sorted(associations,key=lambda z:(-z[0],z[1]))]
   order=sorted(ops,key=lambda c:(max(rank.index(c[1]),rank.index(c[2])),rank.index(c[1])+rank.index(c[2]),c[0],c[1],c[2]))
   random_order=ops.copy();rng.shuffle(random_order)
   for method,candidates in [('guided',order),('random',random_order),('static',ops)]:
    cand=candidates[:12]
    errors=[sum(predict(c,x)!=yy[x] for x in train) for c in cand];checks+=12*32
    best=min(range(len(cand)),key=lambda j:(errors[j],cand[j]));chosen=cand[best]
    acc=sum(predict(chosen,x)==y(x) for x in test)/32
    out[('dev' if seed<10000 else 'evaluation',family)][method].append(acc)
 result={split+'_'+family:{m:round(statistics.mean(v),6) for m,v in d.items()} for (split,family),d in out.items()}
 return {'metrics':result,'worlds':trials,'unique_train_labels_per_arm':labels,'candidate_scores_per_arm':trials*12,'candidate_example_checks_total':checks,'cpu_seconds':time.process_time()-t,'development_seeds':64,'evaluation_seeds':256,'notes':'Train and terminal input sets disjoint; development and evaluation seeds separate. No predictive entropy information gain calculated. Guided arm has 192 extra association checks per world; compute NOT matched.'}
if __name__=='__main__':print(json.dumps(run(),indent=2))
