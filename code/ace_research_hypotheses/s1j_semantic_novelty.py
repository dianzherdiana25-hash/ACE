"""S1-J synthetic diagnostic. Standalone, no frozen ACE data."""
import json,random,time
N=64
def run(start_seed,worlds=100):
    counts={p:{'tp':0,'fp':0,'fn':0,'tn':0} for p in ('random8','static8','full64','syntax')}
    presentations=0
    for s in range(start_seed,start_seed+worlds):
        rng=random.Random(s)
        for k in range(64):
            axis=rng.randrange(6)
            base=tuple((i>>axis)&1 for i in range(N))
            if k<32: candidate=base;novel=False
            else:
                at=rng.randrange(N)
                candidate=tuple(v^(i==at) for i,v in enumerate(base));novel=True
            for p,c in counts.items():
                if p=='syntax':pred=True
                else:
                    ids=range(8) if p=='static8' else range(N) if p=='full64' else rng.sample(range(N),8)
                    pred=any(candidate[i]!=base[i] for i in ids)
                    presentations+=2*len(ids)
                c['tp' if pred and novel else 'fp' if pred else 'fn' if novel else 'tn']+=1
    for c in counts.values():
        c['precision']=c['tp']/max(1,c['tp']+c['fp'])
        c['recall']=c['tp']/max(1,c['tp']+c['fn'])
    return counts,presentations
if __name__=='__main__':
    start=time.process_time();dev,dl=run(0);ev,el=run(10000)
    print(json.dumps({'dev':dev,'evaluation':ev,'presentations':{'dev':dl,'evaluation':el},'cpu_seconds':time.process_time()-start},indent=2))
