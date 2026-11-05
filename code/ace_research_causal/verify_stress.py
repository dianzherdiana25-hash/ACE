"""Replay and audit R5 stress evidence without network or paid evaluators."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import zlib

from . import stress

EXPECTED_SHA256 = '95f0ce45cf6a53692cd95ff81ff9ab4e15dcb6863c8a396306c7ae4ce39ed1f7'
ARCHIVE = Path(__file__).with_name('stress_results.json.zlib.b64')


def verified_archive():
    raw = zlib.decompress(base64.b64decode(ARCHIVE.read_text().strip(), validate=True))
    if hashlib.sha256(raw).hexdigest() != EXPECTED_SHA256:
        raise RuntimeError('archived report digest mismatch')
    data = json.loads(raw)
    if data.get('protocol', {}).get('worlds_per_cohort') != 80:
        raise RuntimeError('archived world count changed')
    if len(data.get('cohorts', {})) != 5:
        raise RuntimeError('archived cohort count changed')
    return raw, data


def descriptive_gates(result):
    cohorts=result['cohorts']
    def val(group, arm, key): return cohorts[group]['means'][arm][key]
    strong=val('strong_linear','obs_cubic','regret')-val('strong_linear','iv_cubic','regret')
    weak_coverage=1-val('weak_compliance','iv_cubic_gated','abstain')
    near_null_abstain=val('near_null_effect','iv_cubic_gated','abstain')
    nonlinear=val('nonlinear_transport','iv_linear','regret')-val('nonlinear_transport','iv_cubic','regret')
    tr=cohorts['confounder_shift']['means']['transport']
    # H2's second criterion is undefined when the gate accepts zero actions.
    h2='INDETERMINATE_ZERO_ACCEPTANCE' if weak_coverage==0 else (
        'PASS' if (val('weak_compliance','iv_cubic_gated','incorrect_accepted') /
                    weak_coverage<=.1 and weak_coverage<=.25) else 'FAIL')
    return {'H1_strong_regret_gain_ge_0_10': 'PASS' if strong>=.10 else 'FAIL',
            'H2_weak_accepted_wrong_rate':h2,
            'H3_nonlinear_regret_gain_ge_0_10':'PASS' if nonlinear>=.10 else 'FAIL',
            'H4_transport_iv_drift_below_observed': 'PASS' if tr['iv_coefficient_drift']<tr['observational_coefficient_drift'] else 'FAIL',
            'H5_near_null_abstention_ge_0_75': 'PASS' if near_null_abstain>=.75 else 'FAIL',
            'scientific_acceptance': 'NOT_ASSESSED'}


def verify(replay=True):
    raw,archive=verified_archive()
    if replay:
        fresh=json.dumps(stress.experiment(80),sort_keys=True,indent=2,allow_nan=False)+'\n'
        if fresh.encode() != raw:
            raise RuntimeError('fresh scientific replay disagrees byte-for-byte')
    return {'sha256':EXPECTED_SHA256,'bytes':len(raw),
            'replayed':replay,'gates':descriptive_gates(archive)}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--archive-only',action='store_true')
    args=parser.parse_args()
    print(json.dumps(verify(replay=not args.archive_only),indent=2,sort_keys=True))


if __name__=='__main__':
    main()
