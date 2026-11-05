"""R5 extension: unknown mediator direction, nonlinear SCM, interventions.

Public author-visible synthetic experiments only. Does not imply general causal discovery.
Python >=3.10, standard library only. No external oracle or execution.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import json
import math
import random
from pathlib import Path

TRAIN_BUDGET = 120
INTERVENTION_RANGE = 1.2
TEST_VALUE = 1.5  # out of training intervention support


@dataclass(frozen=True)
class SCM:
    direction: int  # 0: X -> M; 1: M -> X
    a: float
    q: float
    h: float  # cubic mechanism, excluded from learner basis
    b: float
    c: float
    t: float  # X*M -> Y
    p: float  # X^2 -> Y
    r: float  # M^2 -> Y
    d: float  # latent U -> Y


@dataclass(frozen=True)
class Estimator:
    direction: int
    a: float
    q: float
    root_var: float
    child_var: float
    y_coef: tuple[float, ...]


def world(seed: int, *, confounded: bool, cubic: bool = False) -> SCM:
    rng = random.Random(1900000 + seed)
    signed = lambda lo, hi: rng.choice((-1.0, 1.0)) * rng.uniform(lo, hi)
    return SCM(direction=seed % 2, a=signed(.6, 1.2), q=signed(.2, .5),
               h=signed(.35, .55) if cubic else 0.0,
               b=signed(.4, 1.2), c=signed(.4, 1.2), t=signed(.15, .5),
               p=signed(.1, .3), r=signed(.1, .3),
               d=signed(1, 1.8) if confounded else 0.0)


def rewired(w: SCM) -> SCM:
    return replace(w, direction=1 - w.direction)


def mediator(w: SCM, root: float) -> float:
    return w.a * root + w.q * root**2 + w.h * root**3


def outcome(w: SCM, x: float, m: float, u: float, noise: float) -> float:
    return (w.b*x + w.c*m + w.t*x*m + w.p*x*x + w.r*m*m + w.d*u + noise)


def observe(w: SCM, mode: str, rng: random.Random) -> tuple[float, float, float]:
    if mode not in ('obs', 'x', 'm', 'joint'):
        raise ValueError('invalid intervention')
    u = rng.gauss(0, 1)
    root_noise = rng.gauss(0, .25)
    child_noise = rng.gauss(0, .2)
    y_noise = rng.gauss(0, .25)
    if w.direction == 0:  # X causes M
        x = u + root_noise
        if mode in ('x', 'joint'):
            x = rng.uniform(-INTERVENTION_RANGE, INTERVENTION_RANGE)
        m = mediator(w, x) + child_noise
        if mode in ('m', 'joint'):
            m = rng.uniform(-INTERVENTION_RANGE, INTERVENTION_RANGE)
    else:  # M causes X
        m = u + root_noise
        if mode in ('m', 'joint'):
            m = rng.uniform(-INTERVENTION_RANGE, INTERVENTION_RANGE)
        x = mediator(w, m) + child_noise
        if mode in ('x', 'joint'):
            x = rng.uniform(-INTERVENTION_RANGE, INTERVENTION_RANGE)
    return (x, m, outcome(w, x, m, u, y_noise))


class Budget:
    def __init__(self, w: SCM, seed: int, max_queries: int):
        self.w = w
        self.rng = random.Random(seed)
        self.max_queries = max_queries
        self.used = 0

    def ask(self, mode: str) -> tuple[float, float, float]:
        if self.used >= self.max_queries:
            raise RuntimeError('evaluator budget exhausted')
        self.used += 1
        return observe(self.w, mode, self.rng)


def ols(rows: list[tuple[float, ...]], targets: list[float]) -> tuple[float, ...]:
    if not rows or len(rows) != len(targets):
        raise ValueError('invalid least-squares shape')
    size = len(rows[0])
    if len(rows) < size or any(len(row) != size for row in rows):
        raise ValueError('insufficient rows')
    matrix = [
        [math.fsum(row[i]*row[j] for row in rows) + (1.e-7 if i == j else 0.0)
         for j in range(size)] + [math.fsum(row[i]*y for row,y in zip(rows,targets))]
        for i in range(size)
    ]
    for i in range(size):
        pivot = max(range(i, size), key=lambda k: abs(matrix[k][i]))
        if abs(matrix[pivot][i]) < 1.e-11:
            raise ValueError('ill-conditioned design')
        matrix[i], matrix[pivot] = matrix[pivot], matrix[i]
        denominator = matrix[i][i]
        matrix[i] = [value / denominator for value in matrix[i]]
        for k in range(size):
            if k != i:
                coeff = matrix[k][i]
                matrix[k] = [v - coeff*reference for v,reference in zip(matrix[k], matrix[i])]
    return tuple(row[-1] for row in matrix)


def fit_quad(points: list[tuple[float, float]]) -> tuple[float, float, float]:
    return ols([(1.0, x, x*x) for x,y in points], [y for x,y in points])


def variance(values: list[float]) -> float:
    if len(values) < 2:
        raise ValueError('insufficient variance samples')
    mu = math.fsum(values) / len(values)
    return math.fsum((v-mu)**2 for v in values) / len(values)


def y_features(x: float, m: float) -> tuple[float, ...]:
    return (1.0, x, m, x*m, x*x, m*m)


def fit_y(data: list[tuple[float,float,float]]) -> tuple[float, ...]:
    return ols([y_features(x,m) for x,m,y in data], [y for x,m,y in data])


def fitted_model(direction: int, data: list[tuple[float,float,float]],
                 y_data: list[tuple[float,float,float]]) -> Estimator:
    if direction == 0:
        pairs = [(x,m) for x,m,y in data]
        root = [x for x,m,y in data]
    else:
        pairs = [(m,x) for x,m,y in data]
        root = [m for x,m,y in data]
    intercept, a, q = fit_quad(pairs)
    residuals = [child - (intercept + a*parent + q*parent**2)
                 for parent,child in pairs]
    return Estimator(direction, a, q, variance(root), variance(residuals), fit_y(y_data))


def train(w: SCM, seed: int, arm: str, budget: int = TRAIN_BUDGET) -> tuple[Estimator, int]:
    if budget != TRAIN_BUDGET:
        raise ValueError('only declared, equal budget supported')
    sampler = Budget(w, seed, budget)
    if arm in ('causal', 'causal_joint_only'):
        do_x = [sampler.ask('x') for _ in range(30)]
        do_m = [sampler.ask('m') for _ in range(30)]
        do_joint = [sampler.ask('joint') for _ in range(60)]
        # Detect direction from responses to randomized interventions, not ground truth.
        fx = fit_quad([(x,m) for x,m,y in do_x])
        fm = fit_quad([(m,x) for x,m,y in do_m])
        # Squared change of fitted conditional mean on a centered symmetric grid.
        grid = (-1.2,-.6,0,.6,1.2)
        def strength(coeff):
            vals = [coeff[1]*v+coeff[2]*v*v for v in grid]
            return variance(vals)
        direction = 0 if strength(fx) >= strength(fm) else 1
        if direction == 0:
            # X->M: randomized do(X) estimates the mechanism; do(M) measures root X.
            pairs = do_x
            root = [x for x,m,y in do_m]
            p = [(x,m) for x,m,y in pairs]
        else:
            # M->X: randomized do(M) estimates the mechanism; do(X) measures root M.
            pairs = do_m
            root = [m for x,m,y in do_x]
            p = [(m,x) for x,m,y in pairs]
        intercept,a,q = fit_quad(p)
        residual = [child-(intercept+a*parent+q*parent*parent)
                    for parent,child in p]
        # In the inferred parent intervention, U is independent of BOTH
        # predictors, so its outcome rows are eligible for pooling.
        outcome_rows = do_joint if arm == 'causal_joint_only' else (
            do_joint + (do_x if direction == 0 else do_m))
        model = Estimator(direction,a,q,variance(root),variance(residual),fit_y(outcome_rows))
    elif arm in ('obs_oracle_direction', 'obs_fixed_direction'):
        data = [sampler.ask('obs') for _ in range(budget)]
        # oracle direction is deliberately generous to the observational baseline.
        model = fitted_model(w.direction if arm == 'obs_oracle_direction' else 0,
                             data, data)
    else:
        raise ValueError('invalid learner')
    assert sampler.used == budget
    return model, sampler.used


def truth(w: SCM, mode: str, x: float=0.0, m: float=0.0) -> float:
    if mode == 'joint':
        return outcome(w,x,m,0,0)
    if mode == 'x':
        if w.direction == 0:
            mu = mediator(w,x)
            return w.b*x + (w.c+w.t*x)*mu + w.p*x*x + w.r*(mu*mu+.2**2)
        return w.b*x + w.p*x*x + w.r*(1+.25**2)
    if mode == 'm':
        if w.direction == 1:
            mu = mediator(w,m)
            return (w.b+w.t*m)*mu + w.c*m + w.p*(mu*mu+.2**2) + w.r*m*m
        return w.c*m + w.p*(1+.25**2) + w.r*m*m
    raise ValueError('invalid intervention')


def prediction(model: Estimator, mode: str, x: float=0.0, m: float=0.0) -> float:
    intercept,b,c,t,p,r = model.y_coef
    if mode == 'joint':
        return intercept+b*x+c*m+t*x*m+p*x*x+r*m*m
    if mode == 'x':
        if model.direction == 0:
            mu = model.a*x+model.q*x*x
            return intercept+b*x+(c+t*x)*mu+p*x*x+r*(mu*mu+model.child_var)
        return intercept+b*x+p*x*x+r*model.root_var
    if mode == 'm':
        if model.direction == 1:
            mu = model.a*m+model.q*m*m
            return intercept+(b+t*m)*mu+c*m+p*(mu*mu+model.child_var)+r*m*m
        return intercept+c*m+p*model.root_var+r*m*m
    raise ValueError('invalid intervention')


def random_model(seed: int) -> Estimator:
    rng = random.Random(400000 + seed)
    return Estimator(rng.randrange(2),rng.uniform(-1,1),rng.uniform(-.5,.5),
                     1.,.04, tuple(rng.uniform(-1,1) for _ in range(6)))


def metrics(w: SCM, model: Estimator) -> dict[str,float]:
    test = TEST_VALUE
    actions = [('x',v,0.0) for v in (-test,test)] + [('m',0.0,v) for v in (-test,test)]
    interventions = actions + [('joint', x,m) for x in (-test,test) for m in (-test,test)]
    y_true = [truth(w,k,x,m) for k,x,m in interventions]
    y_pred = [prediction(model,k,x,m) for k,x,m in interventions]
    target_errors = [(v-p)**2 for v,p in zip(y_true,y_pred)]
    best = max(range(len(actions)), key=lambda idx:y_pred[idx])
    regret = max(y_true[:4]) - y_true[best]
    return {'mse':math.fsum(target_errors)/len(target_errors),
            'single_intervention_mse':math.fsum(target_errors[:4])/4,
            'planning_regret':max(0.0,regret),
            'direction_correct':float(w.direction == model.direction),
            'ate_x_delta_sq_error':((y_true[1]-y_true[0])-(y_pred[1]-y_pred[0]))**2}


def run_one(seed: int, confounded: bool, cubic: bool) -> dict[str, dict[str,float]]:
    w = world(seed,confounded=confounded,cubic=cubic)
    c, cc = train(w, seed*37+1, 'causal')
    joint_only, jc = train(w, seed*37+1, 'causal_joint_only')
    o, oc = train(w, seed*37+2, 'obs_oracle_direction')
    fixed,fc = train(w, seed*37+3,'obs_fixed_direction')
    assert cc==oc==fc==jc==TRAIN_BUDGET
    random_baseline = random_model(seed)
    return {'causal':metrics(w,c), 'causal_joint_only':metrics(w,joint_only),
            'observational_oracle_direction':metrics(w,o),
            'observational_fixed_direction':metrics(w,fixed),
            'random':metrics(w,random_baseline),
            'causal_shift_static':metrics(rewired(w),c),
            'observational_shift_static':metrics(rewired(w),o),
            'causal_shift_adapt':metrics(rewired(w),train(rewired(w),seed*37+4,'causal')[0]),
            'observational_shift_adapt':metrics(rewired(w),train(rewired(w),seed*37+5,'obs_oracle_direction')[0])}


def aggregate(rows: list[dict[str,dict[str,float]]]) -> dict[str,dict[str,float]]:
    return {arm:{metric:round(math.fsum(row[arm][metric] for row in rows)/len(rows),6)
                 for metric in rows[0][arm]} for arm in rows[0]}


def bootstrap_diff(rows, lhs, rhs, metric):
    diffs = [row[lhs][metric]-row[rhs][metric] for row in rows]
    rng = random.Random(201105)
    n = len(diffs)
    boot = sorted(math.fsum(diffs[rng.randrange(n)] for _ in range(n))/n
                  for _ in range(1600))
    return {'mean':round(math.fsum(diffs)/n,6),
            'ci95':[round(boot[39],6),round(boot[1559],6)]}


def experiment(n: int=80):
    if n<2 or n>1000:
        raise ValueError('worlds must be in [2,1000]')
    groups = {'nonlinear_confounder':(600000,True,False),
              'nonlinear_unconfounded':(700000,False,False),
              'cubic_misspecification':(800000,True,True)}
    all_results = {}
    for key,(start,confounded,cubic) in groups.items():
        cases = [run_one(start+i,confounded,cubic) for i in range(n)]
        all_results[key] = {'means':aggregate(cases),
                            'causal_minus_oracle_observation_mse':bootstrap_diff(
                                cases,'causal','observational_oracle_direction','mse'),
                            'causal_minus_oracle_observation_regret':bootstrap_diff(
                                cases,'causal','observational_oracle_direction','planning_regret'),
                            'causal_minus_oracle_obs_shift_adapt_mse':bootstrap_diff(
                                cases,'causal_shift_adapt','observational_shift_adapt','mse')}
    return {'status':'EXPLORATORY_AUTHOR_VISIBLE_NOT_SCIENTIFICALLY_ACCEPTED',
            'protocol':{'worlds_per_cohort':n,'train_rows_per_learned_arm':TRAIN_BUDGET,
                        'adapt_rows_per_learned_arm':TRAIN_BUDGET,
                        'causal_train_rows':{'do(X)':30,'do(M)':30,'do(X,M)':60},
                        'intervention_train_range':[-INTERVENTION_RANGE,INTERVENTION_RANGE],
                        'eval_values':[-TEST_VALUE,TEST_VALUE],
                        'orientation_unknown_to_causal_learner':True,
                        'observational_oracle_receives_true_orientation':True,
                        'cubic_absent_from_fitted_mechanism':True,
                        'baseline_random_training_queries':0,'bootstrap_resamples':1600},
            'cohorts':all_results}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--worlds',type=int,default=80)
    parser.add_argument('--output',type=Path,default=Path('extension_results.json'))
    args=parser.parse_args()
    result=experiment(args.worlds)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(f'Finished: {args.worlds} worlds/cohort -> {args.output}')


if __name__ == '__main__':
    main()
