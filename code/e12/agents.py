"""Bounded inducer and target search. No imports of oracle or access to hidden labels."""
import hashlib,random
from itertools import product
COEFFS=(1,2,3)
SIDES=(-1,1)
OFFSETS=(0,1,2,3)
WRAPPERS=('id','inc','dec','rol','ror','rev')
ALL_PRIMITIVES=tuple((a,b,c,d,s) for a,b,c,d,s in product(COEFFS,COEFFS,COEFFS,OFFSETS,SIDES))
SOURCE_BUDGET=len(ALL_PRIMITIVES)
TARGET_BUDGET=64

def score(predictions,demos):
    exact=sum(p==ref for p,(_,ref) in zip(predictions,demos))
    elements=sum(sum(a==b for a,b in zip(p,ref)) for p,(_,ref) in zip(predictions,demos))
    return (exact,elements)

def discover(examples, primitive_executor):
    # Every condition performs the same 216 source candidate evaluations.
    scored=[]
    for p in ALL_PRIMITIVES:
        val=score([primitive_executor(p,x) for x,_ in examples],examples)
        scored.append((val,p))
    # prefer deterministic smaller lexicographic parameter on ties
    return max(scored,key=lambda item:(item[0],tuple(-n for n in item[1])))[1],max(scored)[0]

def mutate(p,r):
    k=r.randrange(5)
    choices=(COEFFS,COEFFS,COEFFS,OFFSETS,SIDES)[k]
    new=r.choice([v for v in choices if v!=p[k]])
    return p[:k]+(new,)+p[k+1:]

def invert_wrap(w, y):
    y=list(y)
    if w=='id':return tuple(y)
    if w=='inc':return tuple((z-1)%17 for z in y)
    if w=='dec':return tuple((z+1)%17 for z in y)
    if w=='rol':return tuple(y[-1:]+y[:-1])
    if w=='ror':return tuple(y[1:]+y[:1])
    if w=='rev':return tuple(y[::-1])
    raise ValueError(w)

def solve_linear_mod17(rows):
    mat=[list(z) for z in rows];rank=0;pivots=[]
    for col in range(4):
        idx=next((i for i in range(rank,len(mat)) if mat[i][col]%17),None)
        if idx is None:continue
        mat[rank],mat[idx]=mat[idx],mat[rank]
        scale=pow(mat[rank][col]%17,-1,17)
        mat[rank]=[(z*scale)%17 for z in mat[rank]]
        for j in range(len(mat)):
            if j!=rank:
                factor=mat[j][col]
                mat[j]=[(u-factor*v)%17 for u,v in zip(mat[j],mat[rank])]
        pivots.append(col);rank+=1
        if rank==4:break
    if rank<4:return None
    if any(row[:4]==[0,0,0,0] and row[4]!=0 for row in mat):return None
    answer=[0]*4
    for i,k in enumerate(pivots):answer[k]=mat[i][4]
    return tuple(answer)

def decompose_targets(demos):
    for w in WRAPPERS:
        for side in SIDES:
            rows=[]
            for x,y in demos:
                z=invert_wrap(w,y);n=len(x)
                for i in range(n):
                    rows.append((x[i],x[(i+side)%n],i%2,1,z[i]))
            sol=solve_linear_mod17(rows)
            if sol is None:continue
            a,b,c,d=sol
            if (a in COEFFS and b in COEFFS and c in COEFFS and d in OFFSETS):
                yield (a,b,c,d,side),w

def find_target(policy,source_primitive,demos,executor,seed):
    r=random.Random(int(hashlib.sha256(str(('target',seed)).encode()).hexdigest()[:16],16))
    history=[];best=None;best_score=(-1,-1)
    common=[(r.choice(ALL_PRIMITIVES),r.choice(WRAPPERS)) for _ in range(12)]
    archive=[]
    for k in range(TARGET_BUDGET):
        if k<12: p,w=common[k]
        elif policy in ('REUSE','SHAM','WRONG'):
            if k<18: p,w=source_primitive,WRAPPERS[k-12]
            elif r.random()<.78:
                p=mutate(source_primitive,r);w=r.choice(WRAPPERS)
            else: p,w=r.choice(ALL_PRIMITIVES),r.choice(WRAPPERS)
        elif policy=='STRUCTURED':
            inferred=list(decompose_targets(demos))
            if k>=12 and inferred and k<12+len(inferred): p,w=inferred[k-12]
            elif archive and r.random()<.82:
                base=archive[r.randrange(min(6,len(archive)))][1]
                p,w=base
                if r.random()<.8:p=mutate(p,r)
                else:w=r.choice([q for q in WRAPPERS if q!=w])
            else:p,w=r.choice(ALL_PRIMITIVES),r.choice(WRAPPERS)
        elif policy=='TARGET_ONLY':
            if archive and r.random()<.82:
                base=archive[r.randrange(min(6,len(archive)))][1]
                p,w=base
                if r.random()<.80:p=mutate(p,r)
                else:w=r.choice([q for q in WRAPPERS if q!=w])
            else:p,w=r.choice(ALL_PRIMITIVES),r.choice(WRAPPERS)
        else:raise ValueError(policy)
        val=score([executor(p,w,x) for x,_ in demos],demos)
        history.append((p,w))
        if val>best_score:best_score=val;best=(p,w)
        archive.append((val,(p,w)));archive.sort(key=lambda z:z[0],reverse=True)
        archive=archive[:10]
    digest=hashlib.sha256(repr(history).encode()).hexdigest()
    init=hashlib.sha256(repr(history[:12]).encode()).hexdigest()
    return {'selected':best,'score':best_score,'evaluations':TARGET_BUDGET,
            'proposal_sha256':digest,'common_initial_sha256':init}
