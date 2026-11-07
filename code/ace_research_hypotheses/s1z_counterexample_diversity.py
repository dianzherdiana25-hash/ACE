"""S1-Z public synthetic falsification probe selection; stdlib only."""
import hashlib, json, random, time
from pathlib import Path

METHODS=('diversity','novelty','static','random')
SCENARIOS=('valid','clustered','scattered','random_label')

def bit(x): return x.bit_count() & 1

def world(seed, scenario):
    rng=random.Random(seed*101+SCENARIOS.index(scenario)*1000003)
    mask=rng.randrange(1,64); intercept=rng.randrange(2)
    truth=[bit(x&mask)^intercept for x in range(64)]
    hypothesis=truth.copy()
    if scenario=='clustered':
        start=rng.randrange(57)
        for x in range(start,start+8): hypothesis[x]^=1
    elif scenario=='scattered':
        for x in rng.sample(range(64),8): hypothesis[x]^=1
    if scenario=='random_label':
        truth=[rng.randrange(2) for _ in range(64)]
    return hypothesis,truth

def choose(method, selected, rng):
    remain=[x for x in range(64) if x not in selected]
    if method=='static': return remain[0]
    if method=='random': return rng.choice(remain)
    if not selected: return 0
    if method=='novelty':
        return max(remain,key=lambda x:(sum((x^y).bit_count() for y in selected),-x))
    if method=='diversity':
        return max(remain,key=lambda x:(min((x^y).bit_count() for y in selected),-x))
    raise ValueError(method)

def run():
    cpu=time.process_time()
    outcomes={scenario:{m:{'accepted':0,'mismatches':0} for m in METHODS} for scenario in SCENARIOS}
    ops=0
    for seed in range(2100,2356):
        for scenario in SCENARIOS:
            h,g=world(seed,scenario)
            for method in METHODS:
                selected=[]; rng=random.Random(seed*53+METHODS.index(method)*1009)
                mismatch=0
                for _ in range(8):
                    if method in ('novelty','diversity'):
                        ops+=sum(len(selected) for x in range(64) if x not in selected)
                    x=choose(method,selected,rng)
                    selected.append(x)
                    mismatch+=(h[x]!=g[x])
                outcomes[scenario][method]['accepted']+=(mismatch==0)
                outcomes[scenario][method]['mismatches']+=mismatch
    pooled={}
    for method in METHODS:
        pooled[method]=sum(outcomes[s][method]['accepted'] for s in ('clustered','scattered'))/512
    relative={m:(pooled[m]-pooled['diversity'])/pooled[m] if pooled[m] else None for m in METHODS if m!='diversity'}
    accept=all(v is not None and v>=.20 for v in relative.values()) and outcomes['valid']['diversity']['accepted']>=outcomes['valid']['static']['accepted']-12.8
    return {'status':'ACCEPT_EXPLORATORY_NOT_ASSESSED' if accept else 'REJECT_EXPLORATORY_NOT_ASSESSED','protocol_commit':'83b99ca351dec652212b75b97c76bb539a572cc9','main_sha_at_prereg':'80104ce50ecbcea21080bed8c0eabce88d47ccb5','methods':METHODS,'scenarios':SCENARIOS,'eval_seeds':[2100,2355],'dev_seeds':[1100,1131],'outcomes':outcomes,'pooled_invalid_false_acceptance':pooled,'relative_reduction_vs_controls':relative,'trials':256*4*4,'labels':256*4*4*8,'selection_distance_operations':ops,'cpu_process_seconds':time.process_time()-cpu,'limits':['public synthetic evaluation, no sealed heldout','no independent replay yet','CPU not matched','mismatch rate is not Shannon information gain','no new hypothesis generation']}

if __name__=='__main__':
    result=run()
    src=Path(__file__).read_bytes()
    result['code_sha256']=hashlib.sha256(src).hexdigest()
    print(json.dumps(result,indent=2))
