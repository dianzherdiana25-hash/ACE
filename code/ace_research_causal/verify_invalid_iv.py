"""Fail-closed archive SHA-256 and full deterministic replay for R5 IV falsification."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
from pathlib import Path
import zlib
from . import invalid_iv

RAW_SHA256='fe50505bbb126f5ce32f609baef3e51df1c1aab42cd364f9af3385353864c3d9'
ARCHIVE=Path(__file__).with_name('invalid_iv_results.json.zlib.b64')


def read_archive():
    content=base64.b64decode(ARCHIVE.read_text().strip(),validate=True)
    raw=zlib.decompress(content)
    if hashlib.sha256(raw).hexdigest()!=RAW_SHA256:
        raise ValueError('result archive SHA-256 mismatch')
    obj=json.loads(raw)
    if obj['protocol']['worlds_per_group']!=100 or len(obj['results'])!=5:
        raise ValueError('unexpected result cohorts or sample count')
    return raw,obj


def gates(data):
    r=data['results']
    def metric(group,policy,key):
        return r[group]['0.5']['policies'][policy][key]
    positive={
        'F1_valid_iv_vs_observational_regret':
          (metric('valid','obs_point_cost','regret')-metric('valid','iv_point_cost','regret'))>=.1,
        'F2_direct_exclusion_breaks_iv_mse':
          metric('direct_exclusion','iv_point_cost','tau_squared_error') >=
          2*metric('valid','iv_point_cost','tau_squared_error'),
        'F3_selection_iv_worse_than_direct_do_regret':
          (metric('selected_compliance','iv_point_cost','regret')-
           metric('selected_compliance','direct_do_point_cost','regret'))>=.1,
        'F4_boot_less_regret_than_always_in_all_invalid':
          all(metric(group,'iv_boot_cost','regret')<metric(group,'iv_always','regret')
              for group in ('direct_exclusion','selected_compliance','both_invalid')),
        'F5_direct_do_lower_mse_than_iv_both_invalid':
          metric('both_invalid','direct_do_point_cost','tau_squared_error')<
          metric('both_invalid','iv_point_cost','tau_squared_error')}
    return {'exploratory_descriptive_criteria':positive,
            'accepted_case_error_warning':{
                group:{key:r[group]['0.5']['policies']['iv_boot_cost'][key]
                       for key in ('accepted_count','wrong_accepted_count','conditional_wrong_rate')}
                for group in r},
            'scientific_acceptance':'NOT_ASSESSED'}


def verify(replay=True):
    raw,data=read_archive()
    if replay:
        expected=(json.dumps(invalid_iv.experiment(100),sort_keys=True,indent=2,
                             allow_nan=False)+'\n').encode()
        if expected!=raw:
            raise ValueError('byte-level replay mismatch')
    return {'sha256':RAW_SHA256, 'bytes':len(raw), 'replayed':replay, 'gates':gates(data)}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--archive-only',action='store_true')
    options=p.parse_args()
    print(json.dumps(verify(not options.archive_only),indent=2,sort_keys=True))


if __name__=='__main__':
    main()
