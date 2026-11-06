"""R5 falsification: IV assumption violations and cost-sensitive abstention.

Author-visible synthetic public experiment, stdlib only. Instruments are not
assumed valid by the evaluator. No claims of generic causal identification.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import random
from .stress import ols

ROWS = 160
BOOT = 64
COSTS = (0.0, 0.5, 1.0)
GROUPS = {"valid": 610000, "direct_exclusion": 620000,
          "selected_compliance": 630000, "both_invalid": 640000,
          "weak_first_stage": 650000}


@dataclass(frozen=True)
class World:
    tau: float
    confounding: float
    heterogeneity: float
    direct_z: float
    selection_slope: float
    compliance: float


def world(seed: int, group: str) -> World:
    if group not in GROUPS:
        raise ValueError("unknown group")
    rng = random.Random(621000 + seed)
    sign = rng.choice((-1.0, 1.0))
    tau = sign*rng.uniform(.35, .85)
    d = rng.choice((-1.0, 1.0))*rng.uniform(.8, 1.6)
    h = 0.0
    direct = 0.0
    selection = 0.0
    compliance = .75
    if group in ("direct_exclusion", "both_invalid"):
        # Magnitude sometimes exceeds treatment effect after IV division.
        direct = -sign*rng.uniform(.55, 1.05)
    if group in ("selected_compliance", "both_invalid"):
        h = rng.choice((-1.0, 1.0))*rng.uniform(1.0, 1.8)
        selection = rng.choice((-1.0, 1.0))*rng.uniform(1.8, 3.0)
    if group == "weak_first_stage":
        compliance = .08
    return World(tau, d, h, direct, selection, compliance)


def probability(w: World, u: float) -> float:
    # More stable than naive exp(-x) for bounded experimental inputs.
    t = math.log(w.compliance/(1.0-w.compliance)) + w.selection_slope*u
    return 1.0/(1.0+math.exp(-max(-100.,min(100.,t))))


def one(w: World, rng: random.Random, mode: str, assignment: float) -> tuple[float,float,float]:
    if mode not in ("encourage", "observe", "do"):
        raise ValueError("unknown sampling mode")
    u = rng.gauss(0,1)
    baseline = u+rng.gauss(0,.4)
    if mode == "encourage":
        x = assignment if rng.random() < probability(w,u) else baseline
        z = assignment
    elif mode == "do":
        x = assignment  # controlled intervention bypasses compliance
        z = 0.0
    else:
        x,z = baseline,0.0
    y = (w.tau+w.heterogeneity*u)*x + w.confounding*u + w.direct_z*z + rng.gauss(0,.45)
    return z,x,y


def sample(w: World, seed: int, mode: str, n: int=ROWS) -> list[tuple[float,float,float]]:
    if n != ROWS:
        raise ValueError("matched sample budget fixed at 160")
    rng = random.Random(seed)
    assignment = [-1.0,1.0]*(n//2)
    rng.shuffle(assignment)
    return [one(w,rng,mode,assignment[i]) for i in range(n)]


def regress(rows: list[tuple[float,float,float]], arm: str) -> tuple[float,float]:
    if arm == "iv":
        first = ols([(1.,z) for z,x,y in rows],[x for z,x,y in rows])[1]
        reduced = ols([(1.,z) for z,x,y in rows],[y for z,x,y in rows])[1]
        return (reduced/first if abs(first)>=1.e-6 else math.nan, first)
    if arm in ("obs", "direct_do"):
        return ols([(1.,x) for z,x,y in rows],[y for z,x,y in rows])[1], math.nan
    raise ValueError("unknown estimator")


def bootstrap_iv(rows: list[tuple[float,float,float]], seed: int) -> tuple[float, ...]:
    rng = random.Random(111333 + seed)
    n=len(rows)
    out=[]
    for _ in range(BOOT):
        batch=[rows[rng.randrange(n)] for _ in range(n)]
        slope,first=regress(batch,'iv')
        out.append(slope if math.isfinite(slope) and first>.12 else math.nan)
    return tuple(out)


def act(estimate: float, cost: float, rule: str, boots: tuple[float,...] = (),
        first: float = math.nan) -> int:
    if cost not in COSTS:
        raise ValueError("undeclared action cost")
    if not math.isfinite(estimate):
        return 0
    sign = 1 if estimate>0 else -1
    if rule == 'always':
        return sign
    if rule == 'point_cost':
        return sign if abs(estimate)>cost else 0
    if rule == 'boot_cost':
        if first<=.12 or not boots or any(not math.isfinite(b) for b in boots):
            return 0
        # A lower empirical 10th percentile is *heuristic*, not calibrated.
        lower = sorted(b*sign for b in boots)[max(0,int(.1*len(boots))-1)]
        return sign if lower>cost else 0
    raise ValueError("unknown policy")


def score(w: World, estimate: float, action: int, cost: float) -> dict[str,float]:
    if action not in (-1,0,1):
        raise ValueError("invalid action")
    true=w.tau  # E[U]=0 under do(X), even with heterogeneous effects
    best=max(0.0,abs(true)-cost)
    gain=(action*true-cost) if action else 0.0
    return {'regret':best-gain,
            'accepted':float(action!=0),
            'incorrect_accepted':float(action!=0 and action*true<0),
            'optimal_policy':float(best-gain<1.e-12),
            'tau_squared_error':(true-estimate)**2 if math.isfinite(estimate) else 1.e9}


def run_world(seed: int, group: str) -> dict[str,dict[str,dict[str,float]]]:
    w=world(seed,group)
    rng=sample(w,seed*17+1,'encourage')
    obs=sample(w,seed*17+2,'observe')
    direct=sample(w,seed*17+3,'do')
    iv,first=regress(rng,'iv')
    oe,_=regress(obs,'obs')
    de,_=regress(direct,'direct_do')
    boot=bootstrap_iv(rng,seed)
    rng_control=random.Random(800000 + seed)
    random_action=rng_control.choice((-1,1))
    answer={}
    for cost in COSTS:
        label=str(cost)
        policies={
            'iv_always':(iv,act(iv,cost,'always')),
            'iv_point_cost':(iv,act(iv,cost,'point_cost')),
            'iv_boot_cost':(iv,act(iv,cost,'boot_cost',boot,first)),
            'obs_point_cost':(oe,act(oe,cost,'point_cost')),
            'direct_do_point_cost':(de,act(de,cost,'point_cost')),
            'random':(0.0,random_action),
            'always_abstain':(0.0,0),
        }
        answer[label]={name:score(w,est,a,cost) for name,(est,a) in policies.items()}
    return answer


def mean(a):
    return round(math.fsum(a)/len(a),6)


def paired_interval(rows, cost, a, b, metric):
    diffs=[r[str(cost)][a][metric]-r[str(cost)][b][metric] for r in rows]
    rng=random.Random(893344)
    n=len(diffs)
    bs=sorted(math.fsum(diffs[rng.randrange(n)] for _ in range(n))/n
              for _ in range(1200))
    return {'mean':mean(diffs), 'ci95':[round(bs[29],6),round(bs[1169],6)]}


def summarize(rows):
    result={}
    for cost in COSTS:
        group={}
        for policy in rows[0][str(cost)]:
            scores=[r[str(cost)][policy] for r in rows]
            aggregate={key:mean([s[key] for s in scores]) for key in scores[0]}
            accepted=sum(s['accepted'] for s in scores)
            wrong=sum(s['incorrect_accepted'] for s in scores)
            aggregate.update({'accepted_count':int(accepted),'wrong_accepted_count':int(wrong),
                              'conditional_wrong_rate':round(wrong/accepted,6) if accepted else None})
            group[policy]=aggregate
        result[str(cost)]={'policies':group,
            'iv_boot_minus_iv_point_regret':paired_interval(rows,cost,'iv_boot_cost','iv_point_cost','regret'),
            'iv_boot_minus_direct_do_regret':paired_interval(rows,cost,'iv_boot_cost','direct_do_point_cost','regret')}
    return result


def experiment(n=100):
    if not (2<=n<=250):
        raise ValueError('world count out of protocol bounds')
    return {'status':'EXPLORATORY_NOT_INDEPENDENTLY_ACCEPTED',
        'protocol':{'worlds_per_group':n,'rows_per_learned_arm':ROWS,
            'causal_access_different_for_do_control':True,
            'costs':COSTS,'bootstrap_per_iv_world':BOOT,
            'random_policy_rows':0,
            'groups':{group:[start,start+n-1] for group,start in GROUPS.items()}},
        'results':{group:summarize([run_world(start+i,group) for i in range(n)])
                    for group,start in GROUPS.items()}}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--worlds',type=int,default=100)
    p.add_argument('--output',type=Path,default=Path('invalid_iv_results.json'))
    args=p.parse_args()
    output=experiment(args.worlds)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(output,sort_keys=True,indent=2,allow_nan=False)+'\n')
    print('SHA256',hashlib.sha256(args.output.read_bytes()).hexdigest(), 'worlds/group',args.worlds)


if __name__=='__main__':
    main()
