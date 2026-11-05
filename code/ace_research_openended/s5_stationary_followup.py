"""S5 follow-up: stationary target, distinct public generator families, bounded search."""
import json,random,statistics,time
METHODS=('qd_archive','greedy','random','qd_no_archive','fixed_curriculum')
FAMILIES=('xor','rotate','parity','threshold')

def task(family,seed):
    rng=random.Random(42000+seed*1009+FAMILIES.index(family)*7919)
    target=rng.randrange(256)
    def behavior(x):
        if family=='xor': return x^target
        if family=='rotate': return ((x<<3)|(x>>5))&255 ^ target
        if family=='parity': return ((x^target).bit_count()%2)*255
        return 255 if x>=target else 0
    return target,behavior

def arm(method,family,seed,steps=64):
    rng=random.Random(777000+seed*991+FAMILIES.index(family)*3001)
    target,behavior=task(family,seed)
    archive={}; champion=None; solved=set(); seen=set(); maxscore=-1
    for i in range(steps):
        if method=='random': x=rng.randrange(256)
        elif method=='fixed_curriculum': x=(i*4)&255
        elif method=='greedy' and champion is not None: x=champion^(1<<rng.randrange(8))
        elif method=='qd_archive' and archive: x=rng.choice(list(archive.values()))[0]^(1<<rng.randrange(8))
        else: x=rng.randrange(256)
        b=behavior(x); score=8-(b.bit_count()); descriptor=b>>4
        seen.add(descriptor)
        if score==8: solved.add(family)
        if score>maxscore: maxscore=score;champion=x
        if method=='qd_archive' and (descriptor not in archive or score>archive[descriptor][1]):archive[descriptor]=(x,score)
    return dict(solved=int(bool(solved)),best=maxscore,descriptors=len(seen),id_novelty=steps,labels=steps,trials=steps)

def main():
    start=time.process_time(); rows=[]
    for split,seeds in [('development',range(12)),('evaluation',range(100,112))]:
        for family in FAMILIES:
            for seed in seeds:
                for method in METHODS:
                    rows.append(dict(split=split,family=family,seed=seed,method=method,**arm(method,family,seed)))
    ev=[r for r in rows if r['split']=='evaluation']
    means={m:{k:round(statistics.mean(r[k] for r in ev if r['method']==m),5) for k in ('solved','best','descriptors')} for m in METHODS}
    q=means['qd_archive']['solved'];g=means['greedy']['solved'];r=means['random']['solved']
    decision='ACCEPT' if q>=1.1*max(g,r) and q>max(g,r) else 'REJECT'
    return dict(decision=decision,criterion='QD solved rate >=1.10x both greedy and random, and strictly higher',means=means,rows=rows,total_trials=sum(x['trials'] for x in rows),total_labels=sum(x['labels'] for x in rows),cpu_seconds=time.process_time()-start,warning='all task families predefined; evaluation seeds distinct but public and author-designed')
if __name__=='__main__':print(json.dumps(main(),sort_keys=True,indent=2))
