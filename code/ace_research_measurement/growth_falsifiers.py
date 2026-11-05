"""Public synthetic null calibration for R8 family-cluster capability gate.

This is a method canary, not a real ACE benchmark or independent evaluator.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random

from .growth_gate import screen_growth
from .lineage import Lineage
from .measurement import Record


def _sha(message):
    return hashlib.sha256(message.encode('ascii')).hexdigest()


def calibrated_null(*, seed=8492, runs=512, families=8, cases=12):
    if type(seed) is not int or type(runs) is not int or not 1 <= runs <= 4096:
        raise ValueError('invalid bounded null simulation')
    rng = random.Random(seed)
    counts = Counter()
    hold_reasons = Counter()
    diagnostics = []
    for run in range(runs):
        rows, lineage = [], []
        for split in ('development','evaluation'):
            for family_index in range(families):
                family = ('fit' if split == 'development' else 'new') + str(family_index)
                for j in range(cases):
                    cid = f'{run}/{split}/{family_index}/{j}'
                    semantic = _sha(cid)
                    novelty = split == 'evaluation'
                    base_correct = bool(rng.getrandbits(1)) if novelty else False
                    candidate_correct = bool(rng.getrandbits(1)) if novelty else False
                    rows.append(Record(cid,split,family,semantic,family,novelty,novelty,
                                       base_correct,candidate_correct,base_correct,candidate_correct,
                                       10,10,0,0))
                    lineage.append(Lineage(cid,split,semantic,_sha('gen'+family),
                                           _sha('mech'+family),_sha('world'+cid),
                                           split != 'evaluation'))
        selected = [x for x in rows if x.split == 'evaluation']
        observed = sum(int(x.candidate_correct)-int(x.baseline_correct) for x in selected)/len(selected)
        if observed >= 0.10:
            counts['naive_delta_at_least_10pp'] += 1
        assessed = screen_growth(rows,lineage)
        if assessed['diagnostic_status'] == 'PASS_PUBLIC_SCREEN_ONLY':
            counts['public_screen_pass'] += 1
        else:
            hold_reasons.update(assessed['reasons'])
        diagnostics.append(observed)
    return {'schema':'ace.r8.growth-null.v1',
            'design':{'seed':seed,'runs':runs,'families':families,'cases_per_family':cases,
                      'known_true_delta':0,'all_generator_specs_public':True},
            'counts':{'naive_delta_at_least_10pp':counts['naive_delta_at_least_10pp'],
                      'public_screen_pass':counts['public_screen_pass']},
            'mean_observed_micro_delta':sum(diagnostics)/len(diagnostics),
            'top_hold_reasons':[list(item) for item in hold_reasons.most_common()],
            'claim':'PUBLIC_NULL_DIAGNOSTIC_ONLY_NO_REAL_ACE',
            'limitations':['Exact p-value is family sign-flip nominal, not adjusted for selection.',
                           'Synthetic independent Bernoulli clusters do not represent all real task correlations.',
                           'No authentication of evaluator lineage by the module.']}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output', type=Path)
    args=p.parse_args()
    body=json.dumps(calibrated_null(), indent=2, sort_keys=True)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body,encoding='utf-8')
    else:print(body,end='')


if __name__=='__main__': main()
