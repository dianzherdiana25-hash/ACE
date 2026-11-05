"""S4-v2: public synthetic transition-policy experiment. No external labels."""
import json, random, time
G=4; N=32; B=6
POLICIES=("successor","online_last","online_flip","fixed0","fixed1")
def worlds(seed,stay):
    r=random.Random(seed); typ=r.randrange(2); out=[]
    for j in range(N):
        if j and r.random()>stay: typ=1-typ
        out.append((typ,[(r.random(),r.random()) for _ in range(B)]))
    return out
def evaluate(world,mode):
    previous=None; successes=0; labels=0; inferred=[]
    for typ,draws in world:
        if mode=="fixed0": pref=0
        elif mode=="fixed1": pref=1
        elif previous is None: pref=0
        elif mode in ("online_flip","flip"): pref=1-previous
        else: pref=previous
        counts=[0,0]; wins=[0,0]
        for j in range(B):
            if j==0: a=pref
            elif j==1: a=1-pref
            else: a=max((0,1),key=lambda k:((wins[k]+1)/(counts[k]+2),k==pref))
            reward=int(draws[j][a] < (.8 if a==typ else .2))
            wins[a]+=reward;counts[a]+=1;successes+=reward;labels+=1
        frac=[wins[k]/counts[k] for k in (0,1)]
        previous=max((0,1),key=lambda k:(frac[k],k==pref))
        inferred.append(previous)
    return successes,labels,inferred
def run():
    start=time.process_time(); records=[]; learned=[]
    for g in range(G):
        dev=worlds(20261106+g,.85)
        future=worlds(20262106+g,.85)
        negative=worlds(20263106+g,.15)
        _,_,inferred=evaluate(dev,"online_last")
        same=sum(a==b for a,b in zip(inferred,inferred[1:]))
        posterior=(same+1)/(len(inferred)+1)
        bit="same" if posterior>=.5 else "flip"
        learned.append({"generation":g,"same_inferred":same,"transition_pairs":len(inferred)-1,"posterior_stay":posterior,"mode":bit})
        mode="last" if bit=="same" else "flip"
        scores={}
        for split,world in (("future",future),("negative",negative)):
            scores[split]={}
            for policy in POLICIES:
                actual=mode if policy=="successor" else policy
                score,labels,_=evaluate(world,actual)
                scores[split][policy]={"success":score,"labels":labels}
        records.append({"generation":g,**scores})
    totals={split:{p:sum(row[split][p]["success"] for row in records) for p in POLICIES} for split in ("future","negative")}
    base=tuple(p for p in POLICIES if p!="successor")
    gain=totals["future"]["successor"]-max(totals["future"][p] for p in base)
    neg=totals["negative"]["successor"]-max(totals["negative"][p] for p in base)
    development_labels=G*N*B
    split_labels=G*N*B*len(POLICIES)
    return {"protocol":"S4-v2","generations":G,"tasks_per_gen":N,"labels_per_task":B,"policies":POLICIES,
            "development_labels":development_labels,"future_labels":split_labels,"negative_labels":split_labels,
            "total_simulated_labels":development_labels+2*split_labels,"future_gain":gain,"negative_gap":neg,
            "accepted":gain>=.05*G*N*B and neg>=-.05*G*N*B,
            "learned":learned,"totals":totals,"records":records,
            "cpu_seconds":time.process_time()-start}
if __name__=="__main__": print(json.dumps(run(),indent=2,sort_keys=True))
