"""S5 public diagnostic, predeclared before run: behavior-vs-parameter proxy falsification.
H0: a zero-output witness is a valid task-solution indicator for >=95% of proxy hits.
REJECT if >5% of zero-output hits disagree with a 256-input independent
behavioral specification. No parameter-identity assumption. 48 eval seeds,
4 predefined families, five methods, 64 proposals/arm. Public synthetic only.
No learning/novelty/generalization claim. No external labels.
"""
import json, time, random
FAMILIES=('xor','rotate','parity','threshold')
METHODS=('qd_archive','greedy','random','qd_no_archive','fixed_curriculum')

def task(family,seed):
    target=random.Random(42000+seed*1009+FAMILIES.index(family)*7919).randrange(256)
    def f(x):
        if family=='xor':return x^target
        if family=='rotate':return (((x<<3)|(x>>5))&255)^target
        if family=='parity':return ((x^target).bit_count()%2)*255
        return 255 if x>=target else 0
    return target,f

def arm(method,family,seed):
    rng=random.Random(777000+seed*991+FAMILIES.index(family)*3001)
    target,f=task(family,seed)
    archive={};champion=None;maxscore=-1;hits=[]
    for i in range(64):
        if method=='random' or method=='qd_no_archive':x=rng.randrange(256)
        elif method=='fixed_curriculum':x=(i*4)&255
        elif method=='greedy' and champion is not None:x=champion^(1<<rng.randrange(8))
        elif method=='qd_archive' and archive:x=rng.choice(list(archive.values()))[0]^(1<<rng.randrange(8))
        else:x=rng.randrange(256)
        b=f(x);score=8-b.bit_count();descriptor=b>>4
        if score==8:hits.append(x)
        if score>maxscore:maxscore=score;champion=x
        if method=='qd_archive' and (descriptor not in archive or score>archive[descriptor][1]):archive[descriptor]=(x,score)
    def response(parameter,probe):
        if family=='xor':return probe^parameter
        if family=='rotate':return (((probe<<3)|(probe>>5))&255)^parameter
        if family=='parity':return ((probe^parameter).bit_count()%2)*255
        return 255 if probe>=parameter else 0
    target_trace=tuple(response(target,j) for j in range(256))
    correct=sum(tuple(response(p,j) for j in range(256))==target_trace for p in hits)
    return len(hits),correct

def main():
    start=time.process_time();out={};hits=correct=0
    for family in FAMILIES:
        out[family]={}
        for method in METHODS:
            h=c=0
            for seed in range(100,148):
                hi,co=arm(method,family,seed);h+=hi;c+=co
            out[family][method]={'proxy_hits':h,'behaviorally_correct_hits':c}
            hits+=h;correct+=c
    false=hits-correct
    return {'hypothesis':'zero-output proxy is behaviorally correct on >=95% of hits',
      'criterion':'REJECT if >5% proxy hits fail full 256-probe behavioral oracle',
      'decision':'REJECT' if hits and false/hits>0.05 else 'NOT_REJECTED',
      'methods':METHODS,'families':FAMILIES,'evaluation_seeds':'100..147',
      'arms':48*len(FAMILIES)*len(METHODS),'proposals':48*len(FAMILIES)*len(METHODS)*64,
      'synthetic_selection_labels':48*len(FAMILIES)*len(METHODS)*64,
      'behavioral_oracle_comparisons':hits*256,
      'proxy_hits':hits,'behaviorally_correct_hits':correct,'false_proxy_hits':false,
      'false_proxy_rate':false/hits if hits else None,'by_family_method':out,
      'cpu_seconds':time.process_time()-start,
      'limitations':'public author-defined four families, not generator-disjoint; exhaustive oracle used only for diagnostic evaluation; same random and no-archive sampler remains a control limitation; does not test OAIE'}
if __name__=='__main__':print(json.dumps(main(),indent=2,sort_keys=True))
