"""ACE R1 H4 independent score auditor.

Re-derives public synthetic task labels and sample words. Uses independent
reference implementation to replay counter/guards and preexisting H3 auditor
for frozen-library baselines. Does NOT import H4 synthesis/training runner.
"""
from __future__ import annotations

import argparse
import json
import hashlib
import itertools
import random

try:
    from . import audit_h3 as ref
except ImportError:
    import audit_h3 as ref

NAMES = ('equal_counts','a_twice_b','b_twice_a','a_three_b',
         'dyck','reverse_dyck','a_block_b_block','b_block_a_block',
         'a_odd','avoids_aba','palindrome','late_flip_equal')


def truth(name, s):
    a,b=s.count('a'),s.count('b')
    if name=='equal_counts': return a==b
    if name=='a_twice_b': return a==2*b
    if name=='b_twice_a': return b==2*a
    if name=='a_three_b': return a==3*b
    if name=='dyck':
        current=0
        for c in s:
            current+=1 if c=='a' else -1
            if current<0:return False
        return current==0
    if name=='reverse_dyck':
        current=0
        for c in s:
            current+=1 if c=='b' else -1
            if current<0:return False
        return current==0
    if name=='a_block_b_block': return s=='a'*a+'b'*b and a==b
    if name=='b_block_a_block': return s=='b'*b+'a'*a and a==b
    if name=='a_odd':return bool(a%2)
    if name=='avoids_aba':return 'aba' not in s
    if name=='palindrome':return s==s[::-1]
    if name=='late_flip_equal':return (a==b) if len(s)<=5 else a!=b
    raise ValueError('bad task')


def reference_holdout(name, index):
    rng=random.Random(20261105+14000+index)
    if name in ('a_block_b_block','b_block_a_block'):
        positives=[('a'*n+'b'*n) if name.startswith('a_') else ('b'*n+'a'*n)
                   for n in range(4,28)]
    else:
        positives=[]; seen=set()
        for attempt in range(250000):
            if len(positives)>=24:break
            length=rng.randrange(8,21)
            candidate=''.join('ab'[rng.randrange(2)] for _ in range(length))
            if name=='late_flip_equal' and length%2:continue
            if candidate not in seen and truth(name,candidate):
                positives.append(candidate);seen.add(candidate)
        ref.insist(len(positives)==24,'positive sampler exhaustion')
    selected=set(positives)
    negatives=[]
    for positive in positives:
        choice=None
        for _ in range(250000):
            if name in ('a_block_b_block','b_block_a_block','dyck','reverse_dyck'):
                temp=list(positive);rng.shuffle(temp);candidate=''.join(temp)
            elif name in ('equal_counts','a_twice_b','b_twice_a','a_three_b'):
                at=rng.randrange(len(positive))
                candidate=positive[:at] + ('b' if positive[at]=='a' else 'a') + positive[at+1:]
            else:
                candidate=''.join('ab'[rng.randrange(2)] for _ in range(len(positive)))
            if candidate not in selected and not truth(name,candidate):
                choice=candidate;break
        ref.insist(choice is not None,'negative sampler exhausted')
        selected.add(choice);negatives.append(choice)
    hold=sorted(positives+negatives,key=lambda s:(len(s),s))
    ref.insist(len(hold)==48 and len(set(hold))==48,'holdout size')
    ref.insist(sum(truth(name,s) for s in hold)==24,'holdout class balance')
    return hold


def register_predict(spec,s):
    if spec is None:return False
    w_a,w_b=spec['w_a'],spec['w_b']
    value=0;low=0;high=0
    for c in s:
        value+=w_a if c=='a' else w_b
        low=min(low,value);high=max(high,value)
    if value!=spec['target']:return False
    kind=spec['guard_kind'];p=spec['guard_parameter']
    if kind=='none':return True
    if kind=='min':return low>=p
    if kind=='max':return high<=p
    if kind=='forbid':return p not in s
    raise AssertionError('unknown guard')


def sha_sample(words):
    return hashlib.sha256(json.dumps(words,separators=(',',':')).encode()).hexdigest()


def check(report):
    ref.insist(report['schema']=='r1-h4-v1','schema mismatch')
    ref.insist(report['status']=='NOT_ASSESSED','scientific status')
    ref.insist(report['protocol_commit']=='85515f6c91c18b898c8e51d1d2ed75b3df755ef0','protocol reference')
    ref.insist(report['synthetic_label_evaluations']==3636,'oracle budget')
    ref.insist(len(report['tasks'])==12,'world count')
    train_words=ref.strings_between(0,5)
    val_words=ref.strings_between(6,7)
    library=ref.reconstruct_frozen_library()
    audited_scores=0
    for idx,(name,case) in enumerate(zip(NAMES,report['tasks'])):
        ref.insist(case['task']==name and case['kind']==('primary' if idx<8 else ('specificity' if idx<11 else 'adversarial')),'order')
        hold_words=reference_holdout(name,idx)
        ref.insist(case['data_hash']=={'train':sha_sample(train_words),'validation':sha_sample(val_words),'holdout':sha_sample(hold_words)},'data fingerprints')
        train=[(s,truth(name,s)) for s in train_words]
        val=[(s,truth(name,s)) for s in val_words]
        hold=[(s,truth(name,s)) for s in hold_words]
        ref.validate_machine(case['rpni_automaton'])
        ref.insist(len(case['rpni_automaton'])==case['rpni_states'],'rpni state count')
        ref.insist(0<=case['proposal_attempts']<=1000 and 0<=case['guard_attempts']<=1000,'feature budget')
        ref.insist(0<=case['rpni_merge_attempts']<=10000,'DFA budget')
        fit_fixed=min(library,key=lambda fname: sum(ref.eval_frozen(fname,s)!=y for s,y in train))
        ref.insist(fit_fixed==case['fixed_predicate'],'fixed library selection')
        is_constructed=case['feature'] is not None
        ref.insist(is_constructed==case['constructed'],'construction flag')
        if case['feature'] is not None:
            ref.insist(case['feature']['w_a']>0 and case['feature']['w_b']<0,'signed feature normal')
            ref.insist(case['feature']['guard_kind'] in ('none','min','max','forbid'),'guard class')
            ref.insist(all(register_predict(case['feature'],s) for s,y in train if y),'positive consistency')
            ref.insist(all(not register_predict(case['feature'],s) for s,y in train if not y),'negative consistency')
        methods={
            'constructed_or_fallback':(lambda s,sp=case['feature'],machine=case['rpni_automaton']:
                                      register_predict(sp,s) if sp is not None else ref.predict_canonical(machine,s)),
            'raw_counter':lambda s,sp=case['raw_feature']:register_predict(sp,s),
            'guarded_counter':lambda s,sp=case['guarded_feature']:register_predict(sp,s),
            'rpni':lambda s,machine=case['rpni_automaton']:ref.predict_canonical(machine,s),
            'prefix_memorizer':lambda s,known=dict(train):known.get(s,False),
            'suffix3':lambda s,observed=train:ref.suffix3_prediction(observed,s),
            'fixed_library':lambda s,fname=fit_fixed:ref.eval_frozen(fname,s),
        }
        for method,predict in methods.items():
            for split,rows in (('train',train),('validation',val),('holdout',hold)):
                expected=ref.independent_metrics(predict,rows)
                ref.insist(case['scores'][method][split]==expected, f'score mismatch: {name}, {method}, {split}')
                audited_scores+=1
        errs=[[s,int(y),int(methods['constructed_or_fallback'](s))] for s,y in hold
              if methods['constructed_or_fallback'](s)!=y]
        ref.insist(case['counterexamples']==errs[:4],f'counterexamples mismatch: {name}')
    primary=report['tasks'][:8]
    mean_induced=sum(c['scores']['constructed_or_fallback']['holdout']['correct'] for c in primary)/384
    oracle=sum(max(c['scores'][m]['holdout']['correct'] for m in ('rpni','prefix_memorizer','suffix3','fixed_library')) for c in primary)/384
    good=sum(c['scores']['constructed_or_fallback']['holdout']['correct']>=44 for c in primary)
    proposals=sum(c['constructed'] for c in report['tasks'][8:11])
    expected={'mean_induced':round(mean_induced,6),'best_per_task_oracle_control':round(oracle,6),
              'gain':round(mean_induced-oracle,6),'primary_at_least_90_percent':good,
              'h4a_pass':bool(mean_induced>=.85 and mean_induced-oracle>=.10 and good>=6),
              'specificity_counter_proposals':proposals,'h4b_pass':proposals<=1,
              'adversarial_correct':report['tasks'][-1]['scores']['constructed_or_fallback']['holdout']['correct']}
    ref.insist(report['primary']==expected,'primary gate mismatch')
    ref.insist(report['tasks'][0]['scores']['constructed_or_fallback']['train']==
               report['tasks'][-1]['scores']['constructed_or_fallback']['train'],
               'length-switch control not training-indistinguishable')
    return {'audited_tasks':len(NAMES),'scored_cells':audited_scores,
            'source_labels_recomputed':3636,'primary':expected}


def main():
    p=argparse.ArgumentParser();p.add_argument('evidence');args=p.parse_args()
    raw=open(args.evidence,'rb').read();report=json.loads(raw)
    result=check(report);result['evidence_sha256']=hashlib.sha256(raw).hexdigest()
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
