"""Independent H6 receipt auditor: rederive oracle, candidate models and holdouts.

Does not import the tested experiment runner and does not use model decisions
as authority. It is an independent within-team implementation, not third-party.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
from pathlib import Path

SEED = 20261106
BASES = ('equal_counts', 'a_mod3', 'contains_ab', 'dyck', 'ends_ba',
         'avoids_bb', 'odd_length', 'first_equals_last')
TRIGGERS = ('aaaaa', 'aaabb', 'ababa', 'bbbaa', 'bbbbb')


def check(ok, reason):
    if not ok:
        raise AssertionError(reason)


def bank(lo, hi):
    return [''.join(bits) for n in range(lo, hi + 1)
            for bits in itertools.product('ab', repeat=n)]


def sha(values):
    return hashlib.sha256(json.dumps(values, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def oracle_base(kind, s):
    n_a = s.count('a')
    n_b = s.count('b')
    match kind:
        case 'equal_counts': return n_a == n_b
        case 'a_mod3': return n_a % 3 == 0
        case 'contains_ab': return 'ab' in s
        case 'ends_ba': return s.endswith('ba')
        case 'avoids_bb': return 'bb' not in s
        case 'odd_length': return len(s) % 2 == 1
        case 'first_equals_last': return len(s) > 0 and s[0] == s[-1]
        case 'dyck':
            bal = 0
            for c in s:
                bal += 1 if c == 'a' else -1
                if bal < 0: return False
            return bal == 0
        case _: raise AssertionError('invalid base')


def candidate(kind, s, marker, start=6):
    return bool(oracle_base(kind, s)) != bool(marker and len(s) >= start and marker in s)


def holdout(task):
    return sorted(random.Random(SEED+100000+task).sample(bank(11, 13), 256),
                  key=lambda w: (len(w), w))


def audit(report):
    check(report['schema']=='r1-h6-1' and report['scientific_status']=='NOT_ASSESSED', 'schema')
    queries=bank(6, 10)
    train=bank(0, 5)
    check(len(queries)==1984 and report['query_pool_size']==len(queries), 'query pool count')
    check(report['query_pool_sha256']==sha(queries), 'query pool sha')
    check(report['additional_query_oracle_labels']==256, 'oracle budget')
    check(report['training_labels_per_world']==63, 'train budget')
    check(len(report['worlds'])==80, 'world count')
    collected={k:{'correct_identification':0,'abstentions':0,'oracle_queries':0,
                  'decided_holdout_correct':0,'decided_holdout_total':0}
               for k in ('active','uniform','random_disagreement')}
    scored=0
    for idx,row in enumerate(report['worlds']):
        base=BASES[idx//10]
        trigger=TRIGGERS[(idx//2)%5]
        actual=('H0','H1')[idx%2]
        check(row['task_index']==idx and row['base']==base and row['trigger']==trigger
              and row['true_hypothesis']==actual,'task identity')
        check(row['training_sha256']==sha([int(oracle_base(base,s)) for s in train]),'training hash')
        hold=holdout(idx)
        check(row['holdout_sha256']==sha(hold),'holdout hash')
        disagreements=[j for j,s in enumerate(queries)
                       if candidate(base,s,None)!=candidate(base,s,trigger)]
        check(len(disagreements)>0,'missing disagreement for in-class pair')
        for method in collected:
            item=row['trials'][method]
            rng=random.Random(SEED+idx)
            if method=='active': intended=disagreements[0]
            elif method=='uniform': intended=rng.randrange(len(queries))
            else: intended=disagreements[rng.randrange(len(disagreements))]
            word=queries[intended]
            check(item['query_index']==intended and item['query']==word,'query mismatch')
            check(item['candidate_disagreements']==len(disagreements),'disagreement count')
            a=candidate(base,word,None)
            b=candidate(base,word,trigger)
            y=candidate(base,word,trigger if actual=='H1' else None)
            check((item['h0_label'],item['h1_label'],item['oracle_label'])==(int(a),int(b),int(y)),
                  'query predictions or oracle tampered')
            decision='H0' if a!=b and y==a else 'H1' if a!=b and y==b else None
            check(item['decision']==decision and item['abstained']==(decision is None),
                  'decision drift')
            check(item['correct_identification']==(decision==actual),'identification drift')
            expected_hold=None
            if decision is not None:
                expected_hold=sum(candidate(base,w,trigger if decision=='H1' else None)==
                                  candidate(base,w,trigger if actual=='H1' else None)
                                  for w in hold)
            check(item['holdout_correct_if_decided']==expected_hold, 'terminal score altered')
            agg=collected[method]
            agg['correct_identification']+=decision==actual
            agg['abstentions']+=decision is None
            agg['oracle_queries']+=1
            agg['decided_holdout_correct']+=expected_hold or 0
            agg['decided_holdout_total']+=256*(decision is not None)
            scored+=1
    check(report['scores']==collected,'aggregate drift')
    controls=report['controls']
    check(len(controls['late_indistinguishable'])==len(controls['misspecified_open_world'])==8,
          'control counts')
    for i,base in enumerate(BASES):
        ctrl=controls['late_indistinguishable'][i]
        check(ctrl['base']==base and ctrl['query']==queries[0] and ctrl['candidate_disagreements']==0,
              'late pool mismatch')
        check(ctrl['oracle_label']==int(candidate(base,queries[0],'aaaaa',14))
              and ctrl['decision'] is None and ctrl['abstained'] is True,'late false claim')
        miss=controls['misspecified_open_world'][i]
        first=next(word for word in queries if candidate(base,word,None)!=candidate(base,word,'aaaaa'))
        check(miss['base']==base and miss['query']==first,'misspecified query')
        check(miss['oracle_label']==int(candidate(base,first,'bbbbb')),'misspecified label')
        check(miss['decision']=='H0' and miss['false_acceptance'] and not miss['abstained'],
              'misspecified false acceptance')
    h6a=collected['active']['correct_identification']/80>=.95 and (
        collected['active']['correct_identification']-collected['uniform']['correct_identification'])/80>=.4
    h6b=all(t['abstained'] for t in controls['late_indistinguishable'])
    h6c=sum(t['abstained'] for t in controls['misspecified_open_world'])>=6
    check(report['gates']=={'H6a_identification':h6a,'H6b_late_abstention':h6b,
                           'H6c_open_world_abstention':h6c,'overall_go':h6a and h6b and h6c},
          'gate re-evaluation mismatch')
    return {'worlds':80,'queries':256,'world_method_score_cells':scored,
            'terminal_labels_recomputed_per_decided_model':sum(v['decided_holdout_total'] for v in collected.values()),
            'H6a':h6a,'H6b':h6b,'H6c':h6c,'overall_go':h6a and h6b and h6c}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('report',type=Path)
    a=p.parse_args()
    raw=a.report.read_bytes()
    out=audit(json.loads(raw))
    out['evidence_sha256']=hashlib.sha256(raw).hexdigest()
    print(json.dumps(out, sort_keys=True))


if __name__=='__main__':
    main()
