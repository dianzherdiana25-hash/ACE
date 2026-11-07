# S1-W public synthetic experiment. Deterministic single-spike query counterexample.
import random, math, time, json
N=64; K=8; WORLDS=4096
prior=[.75/8 if i<8 else .25/56 for i in range(N)]
def entropy(p): return -sum(v*math.log2(v) for v in p if v>0)
def draw(rng,shift=False):
    if rng.random()<.75: return rng.randrange(56,64) if shift else rng.randrange(8)
    return rng.randrange(56) if shift else rng.randrange(8,64)
def choose(method,rng):
    if method=='static': return list(range(8))
    if method=='random': return rng.sample(range(N),8)
    if method=='hedged': return list(range(4))+rng.sample(list(range(8,64)),4)
    return None
def run():
    start=time.process_time();results={};total_ops=0;labels=0
    for scenario,seed in [('normal',1073),('adversarial',2073),('no_change',3073),('random_labels',4073)]:
        rng=random.Random(seed)
        worlds=[draw(rng,scenario=='adversarial') if scenario in ('normal','adversarial') else None for _ in range(WORLDS)]
        results[scenario]={}
        for method in ['bayesian','static','random','hedged']:
            hit=0;gains=[];method_ops=0
            mrng=random.Random(seed+{'bayesian':11,'static':17,'random':23,'hedged':29}[method])
            for j in worlds:
                p=prior.copy();selected=choose(method,mrng);positive=False;initial=entropy(p)
                for step in range(K):
                    if method=='bayesian':
                        i=max(range(N),key=lambda i:(p[i],-i));method_ops+=N
                    else:i=selected[step]
                    y=mrng.randrange(2) if scenario=='random_labels' else int(j==i)
                    labels+=1
                    if y:positive=True
                    if y:p=[float(k==i) for k in range(N)]
                    else:
                        p[i]=0;s=sum(p)
                        if s:p=[x/s for x in p]
                    if method=='bayesian':p[i]=-1 if y else p[i]
                hit+=positive
                pp=[max(0,x) for x in p];ss=sum(pp)
                if ss:
                    pp=[x/ss for x in pp]
                    gains.append((initial-entropy(pp))/K)
            results[scenario][method]={'detection_rate':hit/WORLDS,'positive_worlds':hit,'entropy_gain_bits_per_label_model_proxy':sum(gains)/len(gains) if gains else None,'ranking_comparisons':method_ops}
            total_ops+=method_ops
    return {'status':'REJECT_EXPLORATORY_NOT_ASSESSED','protocol_commit':'20c589fa60526f48d053a032d9bc263d0ceccfc8','main_sha_at_start':'80104ce50ecbcea21080bed8c0eabce88d47ccb5','worlds_per_scenario':WORLDS,'methods':4,'scenarios':4,'trials':WORLDS*4*4,'labels_presented':labels,'ranking_comparisons':total_ops,'cpu_seconds_process':time.process_time()-start,'results':results,'caveats':['Single-spike oracle labels and known prior, not autonomous hypothesis discovery','Random-label control invalidates Bayesian likelihood; entropy reduction is not empirical information gain','CPU budgets not equal because Bayesian ranks 64 options at each step','Public synthetic exploratory only; no independent exact-SHA replay']}
if __name__=='__main__': print(json.dumps(run(),indent=2))
