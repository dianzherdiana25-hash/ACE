"""Fail-closed, deterministic ACQ2 evidence replay and accounting audit."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import math
import zlib
from pathlib import Path
from . import acq2

ARCHIVE=Path(__file__).with_name('acq2_results.json.zlib.b64')
EXPECTED_SHA256='c5cc9245aae3d7017adafef526eae2cb4d0d41c5ef4d98ad6573817819ebea84'


def read_archive(path=ARCHIVE):
    raw=zlib.decompress(base64.b64decode(Path(path).read_text().strip(),validate=True))
    if hashlib.sha256(raw).hexdigest()!=EXPECTED_SHA256:
        raise ValueError('ACQ2 archive digest mismatch')
    data=json.loads(raw)
    if data['protocol']['worlds_per_cohort']!=100 or set(data['cohorts'])!=set(acq2.COHORTS):
        raise ValueError('ACQ2 unexpected cohorts or size')
    return raw,data


def audit(data):
    for cohort,prices in data['cohorts'].items():
        counts=[]
        for price in acq2.PRICES:
            block=prices[str(price)]
            means=block['means']
            if set(means)!=set(acq2.POLICIES):
                raise ValueError('missing policy')
            if means['evpi32']['total_direct_rows']!=means['random_matched32']['total_direct_rows']:
                raise ValueError('random control unmatched')
            if means['evpi32']['total_direct_rows']!=32*block['evpi32_purchase_count']:
                raise ValueError('EVPI count mismatch')
            if means['iv_no_buy']['total_direct_rows']!=0 or means['always32']['total_direct_rows']!=3200:
                raise ValueError('acquisition count mismatch')
            counts.append(block['evpi32_purchase_count'])
            for name,stats in means.items():
                if not math.isclose(stats['net_regret'],stats['action_regret']+stats['purchase_cost'],abs_tol=3e-6):
                    raise ValueError('cost omitted from net regret')
                if not math.isclose(stats['purchase_cost'],stats['direct_rows']*price,abs_tol=3e-6):
                    raise ValueError('sample cost accounting mismatch')
                if not (0<=stats['total_direct_rows']<=3200):
                    raise ValueError('direct label budget violated')
                accepted=stats['accepted_count'];wrong=stats['wrong_accepted_count']
                if wrong>accepted or accepted>100:
                    raise ValueError('accepted cases invalid')
                rate=stats['conditional_wrong_rate']
                if (rate is None)!=(accepted==0):
                    raise ValueError('undefined error rate not preserved')
                if accepted and not math.isclose(rate,wrong/accepted,abs_tol=3e-6):
                    raise ValueError('conditional rate mismatch')
        if counts!=sorted(counts,reverse=True):
            raise ValueError('higher prices increase purchase count')
    return acq2.gates(data)


def verify(replay=True,path=ARCHIVE):
    raw,document=read_archive(path)
    flags=audit(document)
    if replay:
        result=acq2.experiment(100)
        actual=(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
        if actual!=raw:
            raise ValueError('ACQ2 fresh replay mismatch')
    return {'sha256':EXPECTED_SHA256,'bytes':len(raw),'replay':replay,'falsifiers':flags}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--archive-only',action='store_true')
    opt=parser.parse_args()
    print(json.dumps(verify(not opt.archive_only),sort_keys=True,indent=2))

if __name__=='__main__':
    main()
