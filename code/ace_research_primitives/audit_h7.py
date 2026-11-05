"""R1 H7 independent replay: no import of learner or experiment runner."""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import random
from pathlib import Path

SEED = 20261106
BASES = ('equal_counts', 'a_mod3', 'contains_ab', 'dyck')
FROZEN = ('aaaaa', 'aaabb', 'ababa', 'bbbaa', 'bbbbb')


def words(lo, hi):
    return [''.join(v) for n in range(lo, hi+1) for v in itertools.product('ab', repeat=n)]


def hash_obj(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def base_truth(name, s):
    if name == 'equal_counts':
        return s.count('a') == s.count('b')
    if name == 'a_mod3':
        return s.count('a') % 3 == 0
    if name == 'contains_ab':
        return 'ab' in s
    if name == 'dyck':
        counter = 0
        for char in s:
            counter += 1 if char == 'a' else -1
            if counter < 0:
                return False
        return counter == 0
    raise AssertionError('unexpected base')


def truth(name, s, pattern, kind):
    if kind == 'pattern':
        change = len(s) >= 6 and pattern in s
    elif kind == 'late':
        change = len(s) >= 14 and 'abba' in s
    elif kind == 'non_substring':
        change = len(s) >= 6 and s.count('a') % 2 == 0
    else:
        raise AssertionError('unexpected kind')
    return base_truth(name, s) ^ change


def verify(evidence):
    assert evidence['schema'] == 'r1-h7-1'
    assert evidence['scientific_status'] == 'NOT_ASSESSED'
    assert evidence['protocol_commit'] == '9e7e810952a39a1003e28fb0005037ffe62db0fd'
    assert len(evidence['main']) == 64 and len(evidence['controls']) == 8
    pool = words(6, 10)
    holdpool = words(11, 13)
    scores = []
    for idx, row in enumerate(evidence['main'] + evidence['controls']):
        assert row['index'] == idx
        assert row['base'] == (BASES[idx//16] if idx < 64 else BASES[(idx-64)%4])
        kind = 'pattern' if idx < 64 else ('late' if idx < 68 else 'non_substring')
        assert row['kind'] == kind
        target = [''.join(t) for t in itertools.product('ab', repeat=4)][idx%16] if idx < 64 else ('abba' if kind == 'late' else None)
        assert row['target'] == (target if kind == 'pattern' else kind)
        tr = random.Random(SEED + 30000 + idx).sample(pool, 128)
        rest = sorted(set(pool) - set(tr), key=lambda s: (len(s),s))
        val = random.Random(SEED + 40000 + idx).sample(rest, 128)
        if kind == 'late':
            hold = random.Random(SEED + 70000 + idx-64).sample(words(14,17),256)
        else:
            hold = random.Random(SEED + 50000 + idx).sample(holdpool, 256)
        assert (row['queries_sha256'],row['validation_sha256'],row['holdout_sha256']) == (hash_obj(tr),hash_obj(val),hash_obj(hold))
        positive = [s for s in tr if truth(row['base'],s,target,kind) != base_truth(row['base'],s)]
        vpositive = [s for s in val if truth(row['base'],s,target,kind) != base_truth(row['base'],s)]
        assert row['train_residual_positive'] == len(positive)
        assert row['validation_residual_positive'] == len(vpositive)
        candidates = set()
        for s in positive:
            for n in (2,3,4,5):
                candidates.update(s[t:t+n] for t in range(len(s)-n+1))
        assert len(candidates) <= 100
        candidates = sorted(candidates,key=lambda s:(len(s),s))
        def residual_error(pattern, arr):
            return sum(((len(s)>=6 and pattern in s) !=
                        (truth(row['base'],s,target,kind) != base_truth(row['base'],s))) for s in arr)
        good = next((p for p in candidates if len(positive)>=2 and len(vpositive)>=2 and
                     residual_error(p,tr) == 0 and residual_error(p,val) == 0),None)
        representation = {'accepted':good is not None, 'pattern':good, 'candidates':len(candidates),
                          'reason':'validated_exact_fit' if good is not None else 'no_validated_residual_feature'}
        assert row['representation'] == representation, f'candidate drift {idx}'
        best = min(FROZEN,key=lambda p:(residual_error(p,tr),FROZEN.index(p)))
        fixed = best if (len(positive)>=2 and len(vpositive)>=2 and
                         residual_error(best,tr)==0 and residual_error(best,val)==0) else None
        assert row['baseline_fixed_pattern'] == fixed
        def score(pattern):
            guesses = [base_truth(row['base'],s) ^ bool(pattern and len(s)>=6 and pattern in s) for s in hold]
            actuals = [truth(row['base'],s,target,kind) for s in hold]
            failures = next(([s,int(y),int(x)] for s,x,y in zip(hold,guesses,actuals) if x!=y),None)
            return {'correct':sum(x==y for x,y in zip(guesses,actuals)),'total':256,'first_error':failures}
        assert row['score'] == score(good), f'score {idx}'
        assert row['fixed_score'] == score(fixed)
        assert row['base_score'] == score(None)
        assert row['control_oracle_correct'] == max(score(p)['correct'] for p in (None,)+FROZEN)
        assert row['query_label_count'] == 256
        scores.append(row)
    main = scores[:64]
    neg = scores[64:]
    accepted = sum(r['representation']['accepted'] for r in main)
    got = sum(r['score']['correct'] for r in main)
    base_oracle = sum(r['control_oracle_correct'] for r in main)
    abstained = sum(not r['representation']['accepted'] for r in neg)
    ga = accepted >=56 and got >= .95*16384 and (got-base_oracle)>=.10*16384
    gb = abstained>=7
    expected = {'accepted':accepted,'out_of':64,'holdout_correct':got,'holdout_total':16384,
                'oracle_fixed_correct':base_oracle,'oracle_gain':round((got-base_oracle)/16384,6),
                'negative_abstentions':abstained,'negative_total':8,
                'train_validation_oracle_labels':18432,
                'gates':{'h7a':ga,'h7b':gb,'overall_go':ga and gb}}
    assert evidence['summary'] == expected, 'tampered aggregate'
    return {'worlds_replayed':72,'query_validation_labels_replayed':18432,
            'terminal_predictions_replayed':72*256,'evidence_matches':True,
            'computed_gates':expected['gates']}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('evidence',type=Path)
    a=p.parse_args()
    raw=a.evidence.read_bytes()
    result=verify(json.loads(raw))
    result['evidence_sha256']=hashlib.sha256(raw).hexdigest()
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    main()
