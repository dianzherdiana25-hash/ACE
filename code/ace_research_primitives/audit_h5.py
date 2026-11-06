"""R1 H5 independent receipt auditor. No imports from H5 implementation/learner.

Reconstructs holdouts and all task truth separately; checks each serialized
predictor and train-only selection rule, plus aggregate gates. Stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

try:
    from . import audit_h3 as base
except ImportError:
    import audit_h3 as base

SEED=20261105
ALPHABET='ab'
COUNTER_FAMILIES=('equal_counts','a_twice_b','b_twice_a','a_three_b','dyck','reverse_dyck','a_block_b_block','b_block_a_block')
DRIFT_FAMILIES=('equal_counts','a_twice_b','dyck','a_block_b_block')


def assert_true(cond, message):
    if not cond:
        raise AssertionError(message)


def judge(name, word):
    a,b=word.count('a'),word.count('b')
    if name=='equal_counts':return a==b
    if name=='a_twice_b':return a==2*b
    if name=='b_twice_a':return b==2*a
    if name=='a_three_b':return a==3*b
    if name=='dyck':
        balance=0
        for c in word:
            balance+= 1 if c=='a' else -1
            if balance<0:return False
        return balance==0
    if name=='reverse_dyck':
        balance=0
        for c in word:
            balance+=1 if c=='b' else -1
            if balance<0:return False
        return balance==0
    if name=='a_block_b_block':return a==b and word=='a'*a+'b'*b
    if name=='b_block_a_block':return a==b and word=='b'*b+'a'*a
    raise ValueError('unexpected target name')


def finite_holdout(index):
    rng=random.Random(SEED+25000+index)
    words=set()
    for _ in range(100000):
        if len(words)==256:break
        n=rng.randrange(12,19)
        words.add(''.join('ab'[rng.randrange(2)] for _ in range(n)))
    assert_true(len(words)==256,'finite holdout exhausted')
    return sorted(words,key=lambda x:(len(x),x))


def block_holdout(name,index):
    positives=['a'*n+'b'*n if name=='a_block_b_block' else 'b'*n+'a'*n for n in range(28,52)]
    rand=random.Random(SEED+26000+index)
    observed=set(positives)
    negatives=[]
    for positive in positives:
        for _ in range(250000):
            chars=list(positive)
            rand.shuffle(chars)
            candidate=''.join(chars)
            if candidate not in observed and not judge(name,candidate):
                negatives.append(candidate)
                observed.add(candidate)
                break
        else:raise AssertionError('block bank exhausted')
    return sorted(positives+negatives,key=lambda x:(len(x),x))


def nonblock_holdout(name,index):
    rng=random.Random(SEED+14000+3000+index)
    positives=[]
    used=set()
    for _ in range(250000):
        if len(positives)==24:break
        n=rng.randrange(8,21)
        word=''.join('ab'[rng.randrange(2)] for _ in range(n))
        if word not in used and judge(name,word):
            positives.append(word)
            used.add(word)
    assert_true(len(positives)==24,'nonblock positive exhaustion')
    negatives=[]
    for positive in positives:
        for _ in range(250000):
            if name in ('dyck','reverse_dyck'):
                x=list(positive);rng.shuffle(x);candidate=''.join(x)
            elif name in ('equal_counts','a_twice_b','b_twice_a','a_three_b'):
                pos=rng.randrange(len(positive))
                inverse='b' if positive[pos]=='a' else 'a'
                candidate=positive[:pos]+inverse+positive[pos+1:]
            else:raise ValueError('unexpected nonblock target')
            if candidate not in used and not judge(name,candidate):
                negatives.append(candidate);used.add(candidate);break
        else:raise AssertionError('nonblock negative exhaustion')
    return sorted(positives+negatives,key=lambda x:(len(x),x))


def sample_holdout(name,index):
    return block_holdout(name,index) if name in ('a_block_b_block','b_block_a_block') else nonblock_holdout(name,index)


def eval_counter(model,word):
    if model is None:raise ValueError('cannot directly score absent counter')
    wa,wb,target=model['w_a'],model['w_b'],model['target']
    q=0;low=0;high=0
    for c in word:
        q+=wa if c=='a' else wb
        low=min(low,q);high=max(high,q)
    if q!=target:return False
    kind=model['guard_kind']; parameter=model['guard_parameter']
    if kind=='none':return True
    if kind=='min':return low>=parameter
    if kind=='max':return high<=parameter
    if kind=='forbid':return parameter not in word
    raise ValueError('invalid counter guard')


def independent_random_targets():
    seen=set(); result=[]
    train=base.strings_between(0,5)
    for n in (2,3,4,5):
        accepted=0
        for attempt in range(50000):
            rng=random.Random(SEED+24000+1000*n+attempt)
            moves=[[rng.randrange(n) for _ in range(2)] for _ in range(n)]
            flags=[rng.randrange(2) for _ in range(n)]
            reached={0};frontier=[0]
            while frontier:
                for dest in moves[frontier.pop()]:
                    if dest not in reached:reached.add(dest);frontier.append(dest)
            if len(reached)!=n:continue
            labels=tuple(base.independent_oracle((moves,flags),x) for x in train)
            if labels in seen or not .2<=sum(labels)/63<=.8:continue
            seen.add(labels)
            result.append((n,attempt,moves,flags))
            accepted+=1
            if accepted==3:break
        assert_true(accepted==3,'finite target gen exhausted')
    return result


def assert_metrics(a,b,context):
    assert_true(a==b, 'score drift '+context)


def verify(report):
    # Normalize JSON-native tuple/list equivalence for in-process or file replay.
    report=json.loads(json.dumps(report))
    assert_true(report['schema']=='r1-h5-1','schema')
    assert_true(report['protocol_commit']=='e53a98a95c1a5e26cebc65f23cdc6fc00086e84a','protocol lock')
    assert_true(report['scientific_status']=='NOT_ASSESSED','scientific status')
    assert_true([report[k] for k in ('training_labels','validation_labels','holdout_labels','total_oracle_labels')]==[1512,4608,3648,9768],'label budget')
    assert_true(len(report['tasks'])==24,'task count')
    train_words=base.strings_between(0,5)
    val_words=base.strings_between(6,7)
    assert_true(len(train_words)==63 and len(val_words)==192,'split sizes')
    finite_targets=independent_random_targets()
    library=base.reconstruct_frozen_library()
    checked=0
    for index,entry in enumerate(report['tasks']):
        assert_true(entry['id']==index,'task order')
        if index<12:
            n,attempt,moves,flags=finite_targets[index]
            assert_true(entry['group']=='finite' and entry['source']=={
                'states':n,'attempt':attempt,'transitions':moves,'acceptance':flags},'finite source')
            oracle=lambda s,moves=moves,flags=flags:base.independent_oracle((moves,flags),s)
            hold=finite_holdout(index)
        else:
            base_name=COUNTER_FAMILIES[index-12] if index<20 else DRIFT_FAMILIES[index-20]
            group='counter' if index<20 else 'drift'
            source={'family':base_name} if group=='counter' else {'base_family':base_name,'rule':'invert above length 7'}
            assert_true(entry['group']==group and entry['source']==source,'family source')
            oracle=(lambda s,name=base_name,group=group: judge(name,s) if group=='counter' or len(s)<=7 else not judge(name,s))
            hold=sample_holdout(base_name,index)
        training=[(s,oracle(s)) for s in train_words]
        validation=[(s,oracle(s)) for s in val_words]
        holding=[(s,oracle(s)) for s in hold]
        assert_true(not set(hold)&set(train_words+val_words),'split contamination')
        assert_true(entry['split_hashes']=={
            'train':base.label_digest(train_words),
            'validation':base.label_digest(val_words),
            'holdout':base.label_digest(hold)},'fingerprints')
        assert_true(entry['holdout_labels']==[int(y) for _,y in holding],'holdout truth')
        machine=entry['finite']['automaton']
        base.validate_machine(machine)
        assert_true(entry['finite']['states']==len(machine),'automaton complexity')
        assert_true(0<=entry['finite']['merges']<=10000,'finite budget')
        finite=lambda s,machine=machine:base.predict_canonical(machine,s)
        counter_model=entry['counter']['model']
        assert_true(entry['counter']['status'] in ('constructed','abstain'),'counter status')
        assert_true(entry['counter']['proposals']<=1000 and entry['counter']['guards']<=1000,'counter budget')
        if counter_model is None:
            assert_true(entry['counter']['status']=='abstain','fallback status')
        counter=(lambda s,c=counter_model:eval_counter(c,s)) if counter_model else finite
        chosen_fixed=min(library,key=lambda name:sum(base.eval_frozen(name,s)!=y for s,y in training))
        assert_true(entry['fixed_predicate']==chosen_fixed,'fixed-model training selection')
        errors_finite=sum(finite(s)!=y for s,y in validation)
        errors_counter=sum(counter(s)!=y for s,y in validation)
        selected_name='counter_or_fallback' if counter_model and errors_counter<errors_finite else 'finite'
        selected=counter if selected_name=='counter_or_fallback' else finite
        selection=entry['selection']
        assert_true(selection=={'chosen':selected_name,'finite_validation_errors':errors_finite,
                 'counter_validation_errors':errors_counter,'validation_margin':errors_finite-errors_counter,
                 'semantic_abstention':False},'selection integrity')
        predictors={
            'finite':finite,'counter_or_fallback':counter,
            'selected':selected,'fixed_library':lambda s,name=chosen_fixed:base.eval_frozen(name,s),
            'suffix3':lambda s,training=training:base.suffix3_prediction(training,s),
            'memorizer':lambda s,known=dict(training):known.get(s,False),
        }
        for method,predict in predictors.items():
            for split,cases in (('train',training),('validation',validation),('holdout',holding)):
                assert_metrics(entry['scores'][method][split],base.independent_metrics(predict,cases),f'{index}:{method}:{split}')
                checked+=1
        witness=[[s,int(y),int(selected(s))] for s,y in holding if selected(s)!=y]
        assert_true(entry['counterexamples']==witness[:3],'counterexample drift')
    primary=report['tasks'][:20]
    avg=lambda name:sum(r['scores'][name]['holdout']['accuracy'] for r in primary)/20
    selected_mean=avg('selected')
    fixed_mean=max(avg('finite'),avg('counter_or_fallback'))
    high=sum(r['scores']['selected']['holdout']['accuracy']>=.9 for r in primary)
    least=all(r['scores']['selected']['holdout']['correct']>=min(r['scores']['finite']['holdout']['correct'],
                     r['scores']['counter_or_fallback']['holdout']['correct']) for r in primary)
    abstain=sum(r['selection']['semantic_abstention'] for r in report['tasks'][20:])
    h5a=selected_mean-fixed_mean>=.05 and high>=16 and least
    h5b=abstain>=3
    expected={'selected_mean':round(selected_mean,6),'finite_mean':round(avg('finite'),6),
        'counter_mean':round(avg('counter_or_fallback'),6),'best_fixed_mean':round(fixed_mean,6),
        'improvement_vs_best_fixed':round(selected_mean-fixed_mean,6),
        'selected_tasks_at_90':high,'drift_semantic_abstentions':abstain,
        'h5a_pass':bool(h5a),'h5b_pass':bool(h5b),'combined_h5_go':bool(h5a and h5b)}
    assert_true(report['metrics']==expected,'aggregate/gate drift')
    return {'verified_tasks':len(report['tasks']),'verified_split_method_scores':checked,
            'oracle_labels_verified':9768,'h5a_pass':h5a,'h5b_pass':h5b,
            'drift_holdout_correct':[r['scores']['selected']['holdout']['correct'] for r in report['tasks'][20:]],
            'selected_mean':round(selected_mean,6),'best_fixed_mean':round(fixed_mean,6)}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('evidence',type=Path)
    args=parser.parse_args()
    raw=args.evidence.read_bytes()
    result=verify(json.loads(raw))
    result['evidence_sha256']=hashlib.sha256(raw).hexdigest()
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
