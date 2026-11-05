"""S4-v1 public synthetic recursive policy transfer; no self-authored code."""
import json,random,time
SEED=20261105
GENERATIONS=4
TASKS_PER_GEN=24
BUDGET=6
def tasks(seed):
    r=random.Random(seed)
    return [(r.randrange(2),[r.random() for _ in range(BUDGET*2)]) for _ in range(TASKS_PER_GEN)]
def evaluate(policy,bank,regime,prior):
    successes=0; labels=0; actions=[]
    for typ,draws in bank:
        counts=[0,0]; wins=[0,0]
        for j in range(BUDGET):
            if policy=='fixedA': a=0
            elif policy=='fixedB': a=1
            elif policy=='uniform': a=j%2
            else:
                pref=prior if policy=='adaptive' else int(policy[-1])
                a=j if j<2 else max(range(2),key=lambda z:((wins[z]+1)/(counts[z]+2),z==pref))
            p=(.8 if a==typ else .2) if regime=='stable' else (.8 if a!=typ else .2)
            outcome=int(draws[j*2+a]<p)
            counts[a]+=1; wins[a]+=outcome; successes+=outcome;labels+=1;actions.append((a,outcome))
    return successes,labels,actions
def run():
    started=time.process_time()
    policies=('fixedA','fixedB','uniform','adaptive0','adaptive1','adaptive')
    prior=0; records=[]
    for g in range(GENERATIONS):
        dev=tasks(SEED+g); future=tasks(SEED+1000+g); negative=tasks(SEED+2000+g)
        dev_scores={k:evaluate(k,dev,'stable',prior) for k in policies}
        successor=max((0,1),key=lambda a:(sum(o for arm,o in dev_scores['adaptive'][2] if arm==a),-a))
        future_scores={k:evaluate(k,future,'stable',successor)[:2] for k in policies}
        negative_scores={k:evaluate(k,negative,'flip',successor)[:2] for k in policies}
        records.append({'generation':g,'prior':prior,'successor':successor,'development':{k:list(v[:2]) for k,v in dev_scores.items()},'future':{k:list(v) for k,v in future_scores.items()},'negative_flip':{k:list(v) for k,v in negative_scores.items()}})
        prior=successor
    summary={k:sum(row['future'][k][0] for row in records) for k in policies}
    neg={k:sum(row['negative_flip'][k][0] for row in records) for k in policies}
    total=GENERATIONS*TASKS_PER_GEN*BUDGET
    controls=tuple(k for k in policies if k!='adaptive')
    delta=summary['adaptive']-max(summary[k] for k in controls)
    neg_delta=neg['adaptive']-max(neg[k] for k in controls)
    return {'protocol':'S4-v1','seed':SEED,'generations':GENERATIONS,'tasks_per_generation':TASKS_PER_GEN,'labels_per_task':BUDGET,'development_labels':total*len(policies),'future_labels':total*len(policies),'negative_labels':total*len(policies),'total_labels_all_policies':total*len(policies)*3,'cpu_seconds':time.process_time()-started,'future_success':summary,'negative_success':neg,'future_gain_vs_best_control':delta,'negative_gap_vs_best_control':neg_delta,'accepted':delta>=.05*total and neg_delta>=-.05*total,'generation_records':records}
if __name__=='__main__': print(json.dumps(run(),sort_keys=True,indent=2))
