"""R5 stress study: weak instruments, near-null effects and transport limits.

Public deterministic synthetic environments, stdlib only. This is a *fixed*
SCM-family intervention-effect estimator, not general causal discovery.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import random

TRAIN_ROWS = 160
EVAL_DO = 2.0
SETTINGS = (-1.5, -0.5, 0.5, 1.5)
BOOT_REPS = 32


@dataclass(frozen=True)
class World:
    a: float
    b: float
    c: float
    d: float
    gamma: float
    compliance: float

    @property
    def tau(self) -> float:
        return self.b + self.a * self.c


def make_world(seed: int, cohort: str) -> World:
    rng = random.Random(491721 + seed)
    a = rng.choice((-1, 1)) * rng.uniform(.3, .9)
    c = rng.choice((-1, 1)) * rng.uniform(.4, 1.0)
    target = rng.choice((-1, 1)) * rng.uniform(.7, 1.2)
    compliance = .7
    gamma = 0.0
    if cohort == 'weak_compliance':
        compliance = .06
    elif cohort == 'near_null_effect':
        a = rng.choice((-1., 0., 1.)) * rng.uniform(0.0, .04)
        target = rng.uniform(-.035, .035)
    elif cohort == 'nonlinear_transport':
        # Simpler linear-IV extrapolation can reverse the preferred action.
        gamma = -math.copysign(rng.uniform(.40, .54), target)
        target = math.copysign(rng.uniform(.80, 1.0), target)
    elif cohort not in ('strong_linear', 'confounder_shift'):
        raise ValueError('invalid cohort')
    return World(a, target - a*c, c,
                 rng.choice((-1, 1)) * rng.uniform(1.0, 2.0), gamma, compliance)


def do_mean(w: World, x: float) -> float:
    return w.tau * x + w.gamma*x**3


def generate(w: World, rng: random.Random, *, setting: float | None) -> tuple[float, float, float, float]:
    """Return (assigned, actual X, observed Y, observed M); U never exposed."""
    u = rng.gauss(0, 1)
    x0 = u + rng.gauss(0, .30)
    if setting is not None and rng.random() < w.compliance:
        x = setting
    else:
        x = x0
    m = w.a*x + rng.gauss(0, .3)
    y = w.b*x + w.c*m + w.gamma*x**3 + w.d*u + rng.gauss(0, .5)
    return (0.0 if setting is None else setting, x, y, m)


def sample(w: World, seed: int, randomized: bool, n: int = TRAIN_ROWS):
    if n != TRAIN_ROWS:
        raise ValueError('precommitted evaluator budget is 160 rows')
    rng = random.Random(seed)
    assignments = list(SETTINGS) * (n//len(SETTINGS))
    rng.shuffle(assignments)
    rows = [generate(w, rng, setting=assignments[i] if randomized else None)
            for i in range(n)]
    assert len(rows) == n
    return rows


def ols(xs, ys):
    if not xs or len(xs) != len(ys):
        raise ValueError('invalid rows')
    k = len(xs[0])
    if len(xs) < k or any(len(row) != k for row in xs):
        raise ValueError('underdetermined regression')
    aug = []
    for i in range(k):
        aug.append([math.fsum(row[i]*row[j] for row in xs) +
                    (1.e-9 if i == j else 0.0) for j in range(k)] +
                   [math.fsum(row[i]*y for row,y in zip(xs,ys))])
    for i in range(k):
        pivot = max(range(i,k),key=lambda j:abs(aug[j][i]))
        aug[i],aug[pivot]=aug[pivot],aug[i]
        if abs(aug[i][i])<1.e-9:
            raise ValueError('singular design')
        scale=aug[i][i]
        aug[i]=[v/scale for v in aug[i]]
        for j in range(k):
            if j==i: continue
            q=aug[j][i]
            aug[j]=[a-q*b for a,b in zip(aug[j],aug[i])]
    return tuple(row[-1] for row in aug)


@dataclass(frozen=True)
class Fit:
    slope: float
    cubic: float
    compliance: float
    # A negative compliance signal indicates that a finite-sample IV denominator
    # has flipped sign. It is *not* silently truncated to a favorable value.

    def contrast(self) -> float:
        return 2*(self.slope*EVAL_DO+self.cubic*EVAL_DO**3)


def estimate(rows, arm: str) -> Fit:
    if arm == 'random':
        raise ValueError('random control requires seeded independent generator')
    randomized=arm in ('itt_linear','iv_linear','iv_cubic','iv_cubic_gated')
    if randomized:
        zs=[row[0] for row in rows]
        xs=[row[1] for row in rows]
        ys=[row[2] for row in rows]
        p=ols([(1.,z) for z in zs],xs)[1]
        if arm in ('itt_linear','iv_linear'):
            reduced=ols([(1.,z) for z in zs],ys)
            beta,gamma=reduced[1],0.
        else:
            reduced=ols([(1.,z,z**3) for z in zs],ys)
            beta,gamma=reduced[1:]
        if arm=='itt_linear':
            return Fit(beta,gamma,p)
        if abs(p)<1.e-8:
            return Fit(math.nan,math.nan,p)
        return Fit(beta/p,gamma/p,p)
    if arm in ('obs_linear','obs_cubic'):
        xs=[row[1] for row in rows]
        ys=[row[2] for row in rows]
        if arm=='obs_linear':
            beta=ols([(1.,x) for x in xs],ys)
            return Fit(beta[1],0.,0.)
        beta=ols([(1.,x,x**3) for x in xs],ys)
        return Fit(beta[1],beta[2],0.)
    raise ValueError('invalid estimator')


def random_fit(seed: int) -> Fit:
    rng = random.Random(seed+305000)
    return Fit(rng.choice((-1.,1.)),0.,0.)


def gated_action(rows, seed: int, fit: Fit) -> int:
    """Heuristic abstention: strong first-stage + bootstrap sign consensus.

    This is not a calibrated confidence interval. A 0 denotes abstention.
    """
    if not math.isfinite(fit.contrast()) or fit.compliance < .12:
        return 0
    rng = random.Random(seed+81000)
    signs=[]
    n=len(rows)
    for _ in range(BOOT_REPS):
        subset=[rows[rng.randrange(n)] for _ in range(n)]
        candidate=estimate(subset,'iv_cubic')
        if not math.isfinite(candidate.contrast()) or candidate.compliance < .12:
            return 0
        signs.append(1 if candidate.contrast()>0 else -1)
    direction = 1 if fit.contrast()>0 else -1
    if sum(z==direction for z in signs)/len(signs) < .94:
        return 0
    return direction


def evaluate(w: World, fit: Fit, action: int | None=None):
    actual = do_mean(w,EVAL_DO)-do_mean(w,-EVAL_DO)
    if action is None:
        contrast=fit.contrast()
        action = 0 if not math.isfinite(contrast) else (1 if contrast>0 else -1)
    assert action in (-1,0,1)
    # No intervention returns a zero mean policy reward; decisions are +/-do(X).
    gain=action*actual/2
    return {'contrast_squared_error':(actual-fit.contrast())**2 if math.isfinite(fit.contrast()) else 1.e9,
            'regret':abs(actual)/2-gain,
            'correct_action':float(action==(1 if actual>0 else -1)),
            'abstain':float(action==0),
            'incorrect_accepted':float(action!=0 and action!=(1 if actual>0 else -1)),
            'absolute_true_contrast':abs(actual)}


def run_world(seed: int, cohort: str):
    w=make_world(seed,cohort)
    base=seed*19+17
    randomized=sample(w,base,True)
    observed=sample(w,base+1,False)
    fits={arm:estimate(randomized,arm) for arm in ('iv_cubic','iv_linear','itt_linear')}
    fits.update({arm:estimate(observed,arm) for arm in ('obs_linear','obs_cubic')})
    fits['random']=random_fit(seed)
    metrics={arm:evaluate(w,fit) for arm,fit in fits.items()}
    direction=gated_action(randomized,seed,fits['iv_cubic'])
    metrics['iv_cubic_gated']=evaluate(w,fits['iv_cubic'],direction)
    metrics['iv_cubic_gated']['policy_query_count']=TRAIN_ROWS
    # Confounder-change transport: the true do-contrast is unchanged.
    changed=replace(w,d=-w.d)
    adapted_obs=estimate(sample(changed,base+2,False),'obs_cubic')
    adapted_iv=estimate(sample(changed,base+3,True),'iv_cubic')
    metrics['transport']={
        'true_effect_drift':abs(2*do_mean(w,EVAL_DO)-2*do_mean(changed,EVAL_DO)),
        'observational_coefficient_drift':abs(fits['obs_cubic'].contrast()-adapted_obs.contrast()),
        'iv_coefficient_drift':abs(fits['iv_cubic'].contrast()-adapted_iv.contrast())
    }
    return metrics


def aggregate(rows):
    return {arm:{key:round(math.fsum(r[arm][key] for r in rows)/len(rows),6)
                 for key in rows[0][arm]}
            for arm in rows[0]}


def bootstrap(rows, lhs, rhs, metric):
    values=[r[lhs][metric]-r[rhs][metric] for r in rows]
    rng=random.Random(1262026)
    samples=sorted(math.fsum(values[rng.randrange(len(values))]
                             for _ in values)/len(values) for _ in range(1200))
    return {'mean':round(math.fsum(values)/len(values),6),
            'ci95':[round(samples[29],6),round(samples[1169],6)]}


def experiment(n=80):
    if not (2<=n<=300): raise ValueError('world count out of declared bounds')
    groups={'strong_linear':410000,'weak_compliance':420000,
            'near_null_effect':430000,'nonlinear_transport':440000,
            'confounder_shift':450000}
    output={}
    for cohort,begin in groups.items():
        rows=[run_world(begin+i,cohort) for i in range(n)]
        output[cohort]={
            'means':aggregate(rows),
            'iv_cubic_minus_observational_cubic_regret':bootstrap(
                rows,'iv_cubic','obs_cubic','regret'),
            'gated_minus_ungated_iv_regret':bootstrap(
                rows,'iv_cubic_gated','iv_cubic','regret'),
            'iv_cubic_minus_iv_linear_regret':bootstrap(
                rows,'iv_cubic','iv_linear','regret')}
    return {'classification':'EXPLORATORY_NOT_INDEPENDENTLY_ACCEPTED',
            'protocol':{'worlds_per_cohort':n,'samples_per_learned_arm':TRAIN_ROWS,
                        'independent_obs_samples':TRAIN_ROWS,
                        'assignment_levels':SETTINGS,'do_evaluation':EVAL_DO,
                        'bootstrap_repetitions':1200,'uncertainty_bootstrap_repetitions':BOOT_REPS,
                        'random_training_queries':0,
                        'additional_shift_probe_samples_per_learning_arm':TRAIN_ROWS,
                        'evaluation_target_hidden_from_learners':True,
                        'known_family_linear_plus_cubic':True},
            'cohorts':output}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--worlds',type=int,default=80)
    p.add_argument('--output',type=Path,default=Path('stress_results.json'))
    a=p.parse_args()
    result=experiment(a.worlds)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    data=a.output.read_bytes()
    print('Saved',a.output,'SHA256',hashlib.sha256(data).hexdigest(),
          'cohorts',len(result['cohorts']))


if __name__=='__main__':
    main()
