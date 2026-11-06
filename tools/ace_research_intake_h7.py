"""Cross-lane coordinator H7 transfer test; protocol precommitted at e4280bb.

This module does not modify R1's representation learner or selection logic.
All task generation and reporting are public and purely deterministic.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import random

BASES = ('equal_counts', 'a_mod3', 'contains_ab', 'dyck')
LENGTHS = (5, 6, 7)
SEED_TARGET = 2026110601
TRAIN_SEED = 43000000
VALID_SEED = 44000000
NATURAL_SEED = 45000000
BALANCED_SEED = 46000000
MAX_ATTEMPTS = 200000


def words(start, stop):
    return [''.join(cs) for n in range(start, stop+1)
            for cs in itertools.product('ab', repeat=n)]


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def targets():
    chosen = []
    for base_index, base in enumerate(BASES):
        for length in LENGTHS:
            observed = set()
            for pair in range(2):
                rng = random.Random(SEED_TARGET+100000*base_index+1000*length+pair)
                for draw in range(10000):
                    pattern = ''.join('ab'[rng.randrange(2)] for _ in range(length))
                    if pattern.count('a') >= 2 and pattern.count('b') >= 2 and pattern not in observed:
                        observed.add(pattern)
                        chosen.append({'id': len(chosen), 'base': base, 'pattern': pattern,
                                       'length': length, 'draw': draw})
                        break
                else:
                    raise RuntimeError('HALT_TARGET_GENERATION')
    if len(chosen) != 24:
        raise AssertionError('wrong number of worlds')
    return chosen


def splits(index, pattern):
    query_pool = words(6, 12)
    train = random.Random(TRAIN_SEED+index).sample(query_pool, 128)
    complement = sorted(set(query_pool)-set(train), key=lambda s:(len(s),s))
    validation = random.Random(VALID_SEED+index).sample(complement, 128)
    natural = random.Random(NATURAL_SEED+index).sample(words(13, 16), 256)
    selected = set(natural)
    positives, negatives = [], []
    rng = random.Random(BALANCED_SEED+index)
    attempts = 0
    for attempts in range(1, MAX_ATTEMPTS+1):
        if len(positives) == 128 and len(negatives) == 128:
            break
        n = rng.randrange(13, 21)
        word = ''.join('ab'[rng.randrange(2)] for _ in range(n))
        if word in selected:
            continue
        hit = pattern in word
        if hit and len(positives) < 128:
            positives.append(word)
            selected.add(word)
        elif not hit and len(negatives) < 128:
            negatives.append(word)
            selected.add(word)
    if len(positives) != 128 or len(negatives) != 128:
        raise RuntimeError('HALT_BALANCED_TERMINAL_GENERATION')
    balanced = sorted(positives+negatives, key=lambda s:(len(s),s))
    if (len(set(train+validation+natural+balanced)) != 768 or
            not all(6<=len(w)<=12 for w in train+validation) or
            not all(13<=len(w)<=20 for w in natural+balanced)):
        raise RuntimeError('HALT_SPLIT_DISJOINTNESS')
    if sum(pattern in w for w in balanced) != 128:
        raise RuntimeError('HALT_BALANCED_LABELS')
    return train,validation,natural,balanced,attempts


def residual_rows(source, base, pattern, strings):
    # The base predictor is privileged background given to all methods.
    # Source.truth_base output cancels when converting oracle truth to XOR residual.
    return [(w, bool((source.truth_base(base,w) ^ (pattern in w)) ^
                     source.truth_base(base,w))) for w in strings]


def _err(pattern, rows):
    return sum((pattern in word)!=correct for word,correct in rows)


def expanded_fit(train, validation):
    positives = [w for w,bit in train if bit]
    proposals = sorted({word[i:i+n] for word in positives for n in range(2,8)
                        for i in range(len(word)-n+1)}, key=lambda s:(len(s),s))
    if len(proposals) > 254:
        raise RuntimeError('HALT_EXPANDED_CANDIDATE_LIMIT')
    comparisons = 0
    fit = None
    if sum(bit for _,bit in train) >= 2 and sum(bit for _,bit in validation) >= 2:
        for candidate in proposals:
            comparisons += len(train)
            if _err(candidate, train):
                continue
            comparisons += len(validation)
            if _err(candidate, validation)==0:
                fit=candidate
                break
    return {'pattern':fit,'accepted':fit is not None,'candidates':len(proposals),
            'comparisons_upper_bound':len(proposals)*(len(train)+len(validation)),
            'comparisons_charged':comparisons}


def score_pattern(pattern, strings, target):
    correct = sum(bool(pattern and pattern in w)==(target in w) for w in strings)
    first = next(({'word':w, 'expected_residual':int(target in w),
                   'predicted_residual':int(bool(pattern and pattern in w))}
                  for w in strings if bool(pattern and pattern in w)!=(target in w)), None)
    return {'correct':correct,'total':len(strings),'first_error':first}


def world(source, spec):
    i,base,target=spec['id'],spec['base'],spec['pattern']
    train,val,natural,balanced,draws=splits(i,target)
    tr=residual_rows(source,base,target,train)
    va=residual_rows(source,base,target,val)
    learned=source.discover(tr,va)
    fixed=source.frozen_selection(tr,va)
    expanded=expanded_fit(tr,va)
    pattern=learned['pattern'] if learned['accepted'] else None
    methods={'h7':pattern,'base':None,'fixed5':fixed,'expanded2to7':expanded['pattern']}
    scores={name:{'natural':score_pattern(p,natural,target),
                  'balanced':score_pattern(p,balanced,target)}
            for name,p in methods.items()}
    # Training and validation are the only input to feature selection; scores are reporting-only.
    return {'id':i,'base':base,'length':spec['length'],'target':target,
            'target_draw_attempt':spec['draw'],
            'query_sha256':digest(train),'validation_sha256':digest(val),
            'natural_sha256':digest(natural),'balanced_sha256':digest(balanced),
            'train_residual_positives':sum(y for _,y in tr),
            'validation_residual_positives':sum(y for _,y in va),
            'balanced_sampling_attempts':draws,
            'h7_representation':learned,'fixed_h6':fixed,'expanded':expanded,
            'methods':scores,'forced_final_predictions':512,
            'semantic_final_abstentions':0,
            'false_accepted_feature':bool(learned['accepted'] and
                                           scores['h7']['balanced']['correct']<231)}


def aggregate(rows):
    out={}
    for length in LENGTHS:
        sub=[x for x in rows if x['length']==length]
        methods={}
        for name in ('h7','base','fixed5','expanded2to7'):
            methods[name]={'balanced_correct':sum(x['methods'][name]['balanced']['correct'] for x in sub),
                           'natural_correct':sum(x['methods'][name]['natural']['correct'] for x in sub)}
            methods[name]['balanced_accuracy']=round(methods[name]['balanced_correct']/(len(sub)*256),6)
            methods[name]['natural_accuracy']=round(methods[name]['natural_correct']/(len(sub)*256),6)
        out[str(length)]={'tasks':len(sub),'h7_accept':sum(x['h7_representation']['accepted'] for x in sub),
                         'expanded_accept':sum(x['expanded']['accepted'] for x in sub),
                         'h7_false_accepted':sum(x['false_accepted_feature'] for x in sub),
                         'h7_tasks_at_90':sum(x['methods']['h7']['balanced']['correct']>=231 for x in sub),
                         'expanded_tasks_at_90':sum(x['methods']['expanded2to7']['balanced']['correct']>=231 for x in sub),
                         'methods':methods}
    outclass=[x for x in rows if x['length'] in (6,7)]
    g1=(out['5']['h7_accept']>=6 and out['5']['methods']['h7']['balanced_accuracy']>=.90
        and out['5']['methods']['h7']['balanced_accuracy']-.5>=.15)
    g2=(sum(not x['h7_representation']['accepted'] for x in outclass)>=14
        and all(not x['false_accepted_feature'] for x in outclass))
    g3=(sum(x['expanded']['accepted'] and x['methods']['expanded2to7']['balanced']['correct']>=231
            for x in outclass)>=12)
    return {'by_length':out,'precommitted_gates':{'G1_inclass_fivegram':g1,
                 'G2_outclass_abstain_from_feature_and_no_false_accept':g2,
                 'G3_expanded_grammar_diagnostic':g3,
                 'G4_open_world_safe_to_deploy':False},
            'open_world_status':'OPEN_WORLD_HOLD_FORCED_PREDICTIONS',
            'total_h7_false_accepted_features':sum(x['false_accepted_feature'] for x in rows),
            'total_balanced_positives':24*128,
            'total_balanced_negatives':24*128,
            'total_forced_final_predictions':24*512}


def evaluate(source):
    rows=[world(source,spec) for spec in targets()]
    return {'schema':'ace.coordinator.h7.crossclass.public.v1',
            'r1_source_head':'8952c8ac55613e61b362841f4722c66a5aa990b3',
            'protocol_commit':'e4280bb3ebf4372a4ee69834e55dd0c8085b68b6',
            'label_budget':{'tasks':24,'per_task_train':128,'per_task_validation':128,
                 'per_task_natural':256,'per_task_balanced':256,
                 'total_task_specific_judgments':18432,
                 'query_and_validation':24*256,'terminal_reporting':24*512,
                 'selection_uses_terminal_labels':False},
            'rows':rows,'summary':aggregate(rows),
            'scientific_decision':'NOT_ASSESSED_NO_PROMOTION'}


def canonical(report):
    return (json.dumps(report, sort_keys=True, indent=2, allow_nan=False)+'\n').encode('utf-8')


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args(argv)
    from ace_research_primitives import h7_residual_memory as source
    report=evaluate(source)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    data=canonical(report)
    a.output.write_bytes(data)
    print(json.dumps({'sha256':hashlib.sha256(data).hexdigest(),
          'summary':report['summary'],'decision':report['scientific_decision']},sort_keys=True))


if __name__=='__main__':
    main()
