"""Independent task generator & execution oracle. Policy receives examples only, never truth."""
import hashlib, random
from dataclasses import dataclass
MOD=17
COEFFS=(1,2,3)
SIDES=(-1,1)
OFFSETS=(0,1,2,3)
WRAPPERS=('id','inc','dec','rol','ror','rev')

def rng(*tags):
    digest=hashlib.sha256(repr(('ACE-E1.2',)+tags).encode()).digest()
    return random.Random(int.from_bytes(digest[:16],'big'))

def apply_primitive(p, x):
    a,b,c,d,side=p;n=len(x)
    return tuple((a*x[i]+b*x[(i+side)%n]+c*(i%2)+d)%MOD for i in range(n))

def wrap(w,y):
    if w=='id':return tuple(y)
    if w=='inc':return tuple((z+1)%MOD for z in y)
    if w=='dec':return tuple((z-1)%MOD for z in y)
    if w=='rol':return tuple(y[1:]+y[:1])
    if w=='ror':return tuple(y[-1:]+y[:-1])
    if w=='rev':return tuple(y[::-1])
    raise ValueError(w)

def apply_program(p,w,x):
    return wrap(w,apply_primitive(p,x))

def sample_vectors(seed,kind,n,length):
    r=rng(seed,kind,'vectors',length)
    out=[];seen=set()
    while len(out)<n:
        x=tuple(r.randrange(MOD) for _ in range(length))
        if x not in seen:seen.add(x);out.append(x)
    return tuple(out)

def choose_primitive(seed,kind):
    r=rng(seed,kind,'teacher')
    return (r.choice(COEFFS),r.choice(COEFFS),r.choice(COEFFS),r.choice(OFFSETS),r.choice(SIDES))

@dataclass(frozen=True)
class Episode:
    episode_id: str
    source_examples: tuple
    sham_examples: tuple
    wrong_source_examples: tuple
    targets: tuple
    truths: tuple

def make_episode(seed):
    p=choose_primitive(seed,'source')
    wrong=choose_primitive(seed,'wrong')
    # Prevent coincidental identical parameterized operators in negative control
    if wrong==p: wrong=choose_primitive(seed,'wrong2')
    xs=sample_vectors(seed,'source',5,6)
    source=tuple((x,apply_primitive(p,x)) for x in xs)
    wrong_examples=tuple((x,apply_primitive(wrong,x)) for x in xs)
    s=rng(seed,'sham-labels'); shift=s.randrange(1,len(xs));perm=list(range(shift,len(xs)))+list(range(shift))  # derangement
    sham=tuple((x,source[perm[i]][1]) for i,x in enumerate(xs))
    targets=[];truths=[]
    for category in ('related','related','unrelated','unrelated'):
        k=sum(1 for z in targets if z['category']==category)
        tag=f'{category}-{k}'
        q=p if category=='related' else choose_primitive(seed,tag)
        if category=='unrelated' and q==p:q=choose_primitive(seed,tag+'-distinct')
        w=rng(seed,tag,'wrapper').choice(WRAPPERS)
        demos=sample_vectors(seed,tag+'-demo',4,7)
        h9=sample_vectors(seed,tag+'-hidden9',8,9)
        h13=sample_vectors(seed,tag+'-hidden13',8,13)
        targets.append({'task_id':f'{seed}-{tag}','category':category,
           'demos':tuple((x,apply_program(q,w,x)) for x in demos),
           'h9':tuple((x,apply_program(q,w,x)) for x in h9),
           'h13':tuple((x,apply_program(q,w,x)) for x in h13)})
        truths.append({'task_id':f'{seed}-{tag}','primitive':q,'wrapper':w})
    return Episode(str(seed),source,sham,wrong_examples,tuple(targets),tuple(truths))
