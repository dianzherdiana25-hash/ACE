"""Fail-closed archive integrity and exact deterministic replay for public R5 ACQ1."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
import zlib
from . import acq1

ARCHIVE = Path(__file__).with_name('acq1_results.json.zlib.b64')
EXPECTED_SHA256 = '3a0dd2d04d3737377f5f9e50fa9df4f77534747c8ef01c0a2b12171721e9d4d8'


def read_archive():
    raw = zlib.decompress(base64.b64decode(ARCHIVE.read_text().strip(), validate=True))
    if hashlib.sha256(raw).hexdigest() != EXPECTED_SHA256:
        raise ValueError('ACQ1 result SHA-256 mismatch')
    result = json.loads(raw)
    if result['protocol']['worlds_per_cohort'] != 100 or set(result['cohorts']) != set(acq1.COHORTS):
        raise ValueError('ACQ1 protocol or cohort mismatch')
    return raw, result


def audit(result):
    for name, cohort in result['cohorts'].items():
        means = cohort['means']
        if set(means) != set(acq1.POLICIES):
            raise ValueError('missing acquisition policy')
        if means['disagreement32']['total_direct_rows'] != means['random_matched32']['total_direct_rows']:
            raise ValueError('random control lacks matched query budget')
        if means['no_buy']['total_direct_rows'] != 0 or means['always32']['total_direct_rows'] != 3200:
            raise ValueError('oracle acquisition accounting mismatch')
        for policy, stats in means.items():
            if not math.isclose(stats['net_regret'], stats['action_regret'] + stats['query_cost'], abs_tol=1e-5):
                raise ValueError('net regret omits purchase cost')
            if not math.isclose(stats['total_purchase_cost'], stats['total_direct_rows'] * .0125, abs_tol=1e-5):
                raise ValueError('purchase cost/account mismatch')
            if stats['accepted_count'] == 0:
                if stats['conditional_wrong_rate'] is not None:
                    raise ValueError('undefined accepted-case error rate is not null')
            elif not math.isclose(stats['conditional_wrong_rate'],
                                  stats['wrong_accepted_count'] / stats['accepted_count'],abs_tol=1e-5):
                raise ValueError('conditional wrong sign rate mismatch')
    return acq1.gates(result)


def verify(replay=True):
    raw, result = read_archive()
    flags = audit(result)
    if replay:
        rerun = (json.dumps(acq1.experiment(100), sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
        if rerun != raw:
            raise ValueError('ACQ1 full replay byte mismatch')
    return {'raw_sha256':EXPECTED_SHA256, 'raw_bytes':len(raw),
            'replayed':replay, 'gates':flags}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--archive-only',action='store_true')
    args=p.parse_args()
    print(json.dumps(verify(not args.archive_only),indent=2,sort_keys=True))

if __name__ == '__main__':
    main()
