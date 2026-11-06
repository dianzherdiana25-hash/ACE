"""Bounded public synthetic anti-stagnation negative control; stdlib only."""
import json,random,statistics,time
METHODS=("greedy","random","qd_archive","qd_no_archive","fixed_curriculum")
def trial(method,seed,phase,steps=40):
    rng=random.Random(seed+phase*100000)
    targets=[rng.getrandbits(16) for _ in range(4)]
    seen=set();archive={};candidates=[];scores=[]
    for t in range(steps):
        if method=="random": x=rng.getrandbits(16)
        elif method=="fixed_curriculum": x=(1<<((t//10+1)*4))-1
        else:
            if method=="greedy" and candidates: base=max(candidates,key=lambda p:p[1])[0]
            elif method=="qd_archive" and archive: base=rng.choice(list(archive.values()))[0]
            else: base=rng.getrandbits(16)
            x=base^(1<<rng.randrange(16))
        mask=15<<((t//10)*4)
        train=sum(16-((x^y)&mask).bit_count() for y in targets)
        # Posthoc evaluation only. Never used to choose candidates.
        evaluation=sum(16-((x^y)&(~mask&65535)).bit_count() for y in targets)
        descriptor=x&15
        seen.add(descriptor)
        if method=="qd_archive" and (descriptor not in archive or train>archive[descriptor][1]):
            archive[descriptor]=(x,train)
        candidates.append((x,train));scores.append(evaluation)
    return {"best_test":max(scores),"mean_test":statistics.mean(scores),
            "behavior_novelty":len(seen),"id_novelty":steps,
            "train_max":max(p[1] for p in candidates),"labels":4*steps,"trials":steps}
def main():
    start=time.process_time();rows=[]
    for phase in (0,1):
        for seed in range(8):
            for method in METHODS:
                rows.append({"phase":"development" if phase==0 else "evaluation",
                             "seed":seed,"method":method,**trial(method,seed,phase)})
    metrics=("best_test","mean_test","behavior_novelty","id_novelty","train_max")
    summary={p:{m:{k:round(statistics.mean(row[k] for row in rows if row["phase"]==p and row["method"]==m),3) for k in metrics} for m in METHODS} for p in ("development","evaluation")}
    ev=summary["evaluation"]; dg=round(ev["qd_archive"]["best_test"]-ev["greedy"]["best_test"],3);dr=round(ev["qd_archive"]["best_test"]-ev["random"]["best_test"],3)
    return {"hypothesis":"QD archive gains >=2.0 evaluation best_test over BOTH greedy and random","acceptance":"Both gains >=2.0; otherwise REJECT","decision":"ACCEPT" if min(dg,dr)>=2 else "REJECT","delta_greedy":dg,"delta_random":dr,"summary":summary,"rows":rows,"total_trials":len(rows)*40,"total_labels":sum(r["labels"] for r in rows),"cpu_seconds":time.process_time()-start}
if __name__=="__main__":print(json.dumps(main(),sort_keys=True,indent=2))
