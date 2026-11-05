"""R5 ACQ2: EVPI is an upper bound, not a promise of profitable samples.

Public synthetic exploratory research. No real-world causal identification claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path

from . import acq1, invalid_iv

PRICES = (0.0025, 0.0125, 0.025)
COST = 0.5
PRIOR = (-1.5, 1.5)
COHORTS = {"valid": 810000, "direct_exclusion": 820000,
           "selected_compliance": 830000, "both_invalid": 840000,
           "weak_first_stage": 850000}
POLICIES = ("iv_no_buy", "bayes_no_buy", "robust_no_buy", "evpi32", "evpi8",
            "always32", "disagreement32", "random_matched32", "abstain")


def candidate_interval(signal: acq1.Signal) -> tuple[float, float]:
    iv, first = signal.iv_effect, signal.first_stage
    if not math.isfinite(iv) or not math.isfinite(first) or abs(first) < .12:
        return PRIOR
    radius = 1.2 / abs(first)
    low, high = max(PRIOR[0], iv - radius), min(PRIOR[1], iv + radius)
    if not (math.isfinite(low) and math.isfinite(high) and low < high):
        return PRIOR
    return low, high


def expected_perfect_value(interval: tuple[float, float]) -> float:
    lo, hi = interval
    if not (-1.5 <= lo < hi <= 1.5):
        raise ValueError('invalid interval')
    hinge = lambda x: max(x, 0.)**2 / 2
    length = hi - lo
    return (hinge(hi-COST) - hinge(lo-COST) +
            hinge(-lo-COST) - hinge(-hi-COST)) / length


def bayes_value(interval: tuple[float, float]) -> float:
    mid = sum(interval)/2
    return max(0., abs(mid) - COST)


def evpi(interval: tuple[float, float]) -> float:
    return max(0., expected_perfect_value(interval) - bayes_value(interval))


def belief_action(interval: tuple[float, float]) -> int:
    return acq1.action(sum(interval)/2)


def robust_action(interval: tuple[float, float]) -> int:
    lo, hi = interval
    if lo > COST:
        return 1
    if hi < -COST:
        return -1
    return 0


def triggers(signal: acq1.Signal, price: float) -> dict[str, bool]:
    if price not in PRICES:
        raise ValueError('undeclared price')
    value = evpi(candidate_interval(signal))
    return {'evpi32': value > 32*price,
            'evpi8': value > 8*price,
            'disagreement32': acq1.disagreement(signal)}


def choose(name: str, signal: acq1.Signal, price: float,
           oracle: acq1.DirectOracle, random_flag: bool=False) -> int:
    if name not in POLICIES:
        raise ValueError('unknown policy')
    if price not in PRICES:
        raise ValueError('unknown price')
    interval = candidate_interval(signal)
    if name == 'abstain':
        return 0
    if name == 'iv_no_buy':
        return acq1.action(signal.iv_effect)
    if name == 'bayes_no_buy':
        return belief_action(interval)
    if name == 'robust_no_buy':
        return robust_action(interval)
    buy = ({'evpi32':triggers(signal,price)['evpi32'],
            'evpi8':triggers(signal,price)['evpi8'],
            'always32':True, 'disagreement32':acq1.disagreement(signal),
            'random_matched32':bool(random_flag)})[name]
    if not buy:
        return belief_action(interval) if name.startswith('evpi') else acq1.action(signal.iv_effect)
    return acq1.action(acq1.direct_estimate(oracle.buy(8 if name=='evpi8' else 32)))


def score(world: invalid_iv.World, action: int, rows: int, price: float) -> dict:
    if action not in (-1,0,1) or rows not in (0,8,32) or price not in PRICES:
        raise ValueError('invalid action, direct-row count or price')
    optimum = max(0., abs(world.tau)-COST)
    realized = action*world.tau-COST if action else 0.
    regret = max(0.,optimum-realized)
    query_cost = rows*price
    return {'net_regret':regret+query_cost, 'action_regret':regret,
            'purchase_cost':query_cost, 'direct_rows':rows,
            'accepted':int(action!=0),
            'wrong_accepted':int(action!=0 and action*world.tau<0),
            'optimal_action':int(regret<1e-10)}


def paired_interval(rows: list[dict], left: str, right: str) -> dict:
    differences = [r[left]['net_regret']-r[right]['net_regret'] for r in rows]
    rng = random.Random(720206)
    n = len(rows)
    bs=sorted(math.fsum(differences[rng.randrange(n)] for _ in range(n))/n
              for _ in range(1000))
    return {'mean':round(math.fsum(differences)/n,6),
            'percentile_95':[round(bs[24],6),round(bs[974],6)]}


def mean(values):
    return round(math.fsum(values)/len(values),6)


def aggregate(rows):
    out={}
    for name in POLICIES:
        rr=[r[name] for r in rows]
        accepted=sum(r['accepted'] for r in rr)
        wrong=sum(r['wrong_accepted'] for r in rr)
        out[name]={key:mean([r[key] for r in rr]) for key in
                   ('net_regret','action_regret','purchase_cost','direct_rows','accepted','optimal_action')}
        out[name].update(total_direct_rows=sum(r['direct_rows'] for r in rr),
                         accepted_count=accepted,wrong_accepted_count=wrong,
                         conditional_wrong_rate=round(wrong/accepted,6) if accepted else None)
    return out


def experiment(n: int=100) -> dict:
    if type(n) is not int or n < 2 or n > 200:
        raise ValueError('invalid world count')
    cohorts={}
    for cohort,begin in COHORTS.items():
        # Initial observables are sampled once and reused by every policy/price.
        states=[]
        for i in range(n):
            seed=begin+i
            w=invalid_iv.world(seed,cohort)
            encouragement, observation=acq1.initial_rows(w,seed)
            signal=acq1.signal_from_rows(encouragement,observation)
            states.append((w,seed,signal))
        prices={}
        for price in PRICES:
            count=sum(triggers(s,price)['evpi32'] for _,_,s in states)
            random_set=set(random.Random(9000000+begin+int(price*100000)).sample(range(n),count))
            records=[]
            coverage=0
            for i,(w,seed,s) in enumerate(states):
                interval=candidate_interval(s)
                coverage+=int(interval[0]<=w.tau<=interval[1])
                record={}
                for policy in POLICIES:
                    oracle=acq1.DirectOracle(w,seed)
                    a=choose(policy,s,price,oracle,i in random_set)
                    record[policy]=score(w,a,oracle.used,price)
                records.append(record)
            means=aggregate(records)
            if means['evpi32']['total_direct_rows']!=means['random_matched32']['total_direct_rows']:
                raise RuntimeError('matched-random budget mismatch')
            prices[str(price)]={'means':means,'evpi32_purchase_count':count,
                'candidate_interval_truth_coverage':round(coverage/n,6),
                'paired_net_regret':{
                    'evpi32_minus_random':paired_interval(records,'evpi32','random_matched32'),
                    'evpi32_minus_iv':paired_interval(records,'evpi32','iv_no_buy'),
                    'evpi32_minus_always32':paired_interval(records,'evpi32','always32'),
                    'evpi8_minus_evpi32':paired_interval(records,'evpi8','evpi32')}}
        cohorts[cohort]=prices
    return {'status':'EXPLORATORY_NO_SCIENTIFIC_ACCEPTANCE',
       'protocol':{'worlds_per_cohort':n,'action_cost':COST,'prices':PRICES,
                   'baseline_encouragement_rows':80,'baseline_observation_rows':80,
                   'max_direct_rows':32,'prior_tau_interval':PRIOR,
                   'structural_assumption_direct_exclusion_bound':1.0,
                   'statistical_interval_is_calibrated':False,
                   'random_control_is_offline':True,
                   'cohort_seeds':{k:[s,s+n-1] for k,s in COHORTS.items()}},
       'cohorts':cohorts}


def gates(r:dict)->dict:
    c=r['cohorts']
    def m(group,price,arm):return c[group][str(price)]['means'][arm]['net_regret']
    return {'F1_cost_accounting':all(
          abs(m['net_regret']-m['action_regret']-m['purchase_cost'])<0.000003
          and abs(m['purchase_cost']-m['direct_rows']*float(price))<0.000003
          for groups in c.values() for price,block in groups.items()
          for m in block['means'].values()),
      'F2_exact_random_budget_match':all(
         entry['means']['evpi32']['total_direct_rows']==entry['means']['random_matched32']['total_direct_rows']
         for groups in c.values() for entry in groups.values()),
      'F3_superior_targeting_to_random_at_cheap_price':all(
         m(g,.0025,'random_matched32')-m(g,.0025,'evpi32')>=.02
         for g in ('direct_exclusion','both_invalid')),
      'F4_valid_world_penalty_within_point05':(
         m('valid',.0125,'evpi32')-m('valid',.0125,'iv_no_buy')<=.05),
      'F5_monotone_evpi32_purchase_by_price':all(
         c[g]['0.0025']['evpi32_purchase_count']>=c[g]['0.0125']['evpi32_purchase_count']>=c[g]['0.025']['evpi32_purchase_count']
         for g in c),
      'F6_general_causal_intelligence':'REJECTED_NOT_IDENTIFIED',
      'scientific_acceptance':'NOT_ASSESSED'}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--worlds',type=int,default=100)
    p.add_argument('--output',type=Path,default=Path('acq2_results.json'))
    a=p.parse_args()
    report=experiment(a.worlds)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+'\n')
    print(json.dumps(gates(report),indent=2))
    print('sha256',hashlib.sha256(a.output.read_bytes()).hexdigest())

if __name__=='__main__':
    main()
