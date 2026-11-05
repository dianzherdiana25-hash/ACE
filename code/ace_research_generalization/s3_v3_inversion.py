"""S3 v3 public selection-label inversion; no heldout access, stdlib only."""
import hashlib, json, random, time
NAMES=('marker','edge','bit0','constant')
EDGES={'chain':((0,1),(1,2),(2,3),(3,4)),'star':((0,1),(0,2),(0,3),(0,4))}
def cases(n,topology,fidelity,seed):
    r=random.Random(seed); out=[]
    for _ in range(n):
        bits=tuple(r.randrange(2) for _ in range(5)); y=sum(bits)%2
        m=y if r.random()<fidelity else 1-y
        e=sum(bits[a]*bits[b] for a,b in EDGES[topology])%2
        out.append((bits,y,m,e))
    return out
def errors(name,rows):
    return sum({'marker':row[2],'edge':row[3],'bit0':row[0][0],'constant':0}[name]!=row[1] for row in rows)
def select(a,b):
    eligible=[n for n in NAMES if errors(n,a)<=12 and errors(n,b)<=12]
    return min(eligible,key=lambda n:(errors(n,a)+errors(n,b),NAMES.index(n))) if eligible else None
def invert(rows):return [(bits,1-y,m,e) for bits,y,m,e in rows]
def run():
    t=time.process_time(); trials=[]
    for i in range(24):
        s=51000+11*i; a=cases(32,'chain',.95,s+1); b=cases(32,'star',.05,s+2)
        original=select(a,b); dual=select(invert(a),invert(b)); chain=select(invert(a),b); star=select(a,invert(b))
        assert original==select(list(a),list(b))
        trials.append(dict(trial=i,seed=s,original=original,dual=dual,chain_only=chain,star_only=star,
                           dual_changed=original!=dual,chain_changed=original!=chain,star_changed=original!=star))
    summary={k:sum(row[k] for row in trials) for k in ('dual_changed','chain_changed','star_changed')}
    summary.update(original_abstain=sum(row['original'] is None for row in trials),dual_abstain=sum(row['dual'] is None for row in trials))
    return dict(protocol='s3_v3_inversion_precommitted',status='PUBLIC_DEVELOPMENT_NOT_CONFIRMATORY',
                hypothesis_accepted=summary['dual_changed']>=18,summary=summary,trials=trials,
                unique_source_labels=1536,label_presentations=6144,candidate_example_comparisons=24576,
                cpu_seconds=round(time.process_time()-t,6))
if __name__=='__main__':print(json.dumps(run(),sort_keys=True,indent=2))
