"""Public synthetic OOD transfer; deterministic, no external data or dependencies."""
import json, random, time
SEED=3157
def cases(n,topology,shift,seed):
    r=random.Random(seed); rows=[]
    for _ in range(n):
        bits=[r.randrange(2) for _ in range(5)]
        label=sum(bits)%2
        edges={'chain':[(0,1),(1,2),(2,3),(3,4)],'star':[(0,1),(0,2),(0,3),(0,4)],'branch':[(0,1),(0,2),(1,3),(2,4)]}[topology]
        edge_parity=sum(bits[a]*bits[b] for a,b in edges)%2
        marker=label if r.random()<shift else 1-label
        rows.append((bits,label,marker,edge_parity))
    return rows
def pred(name,row):
    b,y,s,e=row
    return {'invariant':sum(b)%2,'spurious':s,'edge':e,'constant':0}[name]
def err(name,rows):return sum(pred(name,x)!=x[1] for x in rows)
def run():
    start=time.process_time();names=['invariant','spurious','edge','constant']
    train=cases(32,'chain',.95,SEED)
    validation=cases(32,'star',.95,SEED+1)
    test=cases(128,'branch',.10,SEED+2)
    def choose(rows):return min(names,key=lambda k:(err(k,rows),names.index(k)))
    baseline=choose(train)
    eligible=[k for k in names if err(k,train)<=3 and err(k,validation)<=3]
    robust=min(eligible,key=lambda k:(err(k,train)+err(k,validation),names.index(k))) if eligible else None
    shuffled=[(b,1-y,s,e) for b,y,s,e in validation]
    neg=[k for k in names if err(k,train)<=3 and err(k,shuffled)<=3]
    counter=next((i for i,x in enumerate(test) if pred('spurious',x)!=x[1]),None)
    results={k:{'train_errors':err(k,train),'validation_errors':err(k,validation),'test_errors':err(k,test)} for k in names}
    result={'seed':SEED,'splits':{'train':32,'validation':32,'test':128},'topologies':['chain','star','branch'],'train_marker_fidelity':.95,'test_marker_fidelity':.10,'distinct_candidate_split_scores':16,'label_budget_selection':64,'test_labels_reporting_only':128,'baseline':baseline,'robust':robust,'negative_control_eligible':neg,'counterexample_test_index':counter,'results':results,'baseline_test_error':err(baseline,test),'robust_test_error':err(robust,test) if robust else None,'baseline_false_accept':int(err(baseline,test)>12),'robust_false_accept':int(robust is not None and err(robust,test)>12),'robust_abstention':int(robust is None),'robust_regret_vs_invariant':(err(robust,test)-err('invariant',test)) if robust else None,'cpu_seconds':round(time.process_time()-start,6)}
    assert len({SEED,SEED+1,SEED+2,SEED+3})==4
    assert counter is not None
    return result
if __name__=='__main__':print(json.dumps(run(),indent=2,sort_keys=True))
