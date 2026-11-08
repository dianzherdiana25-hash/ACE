"""PAC-Bayesian Generalization Bound Estimation for Synthesized DSL Programs.

Mathematical Foundation:
1. McAllester's PAC-Bayesian Theorem (McAllester, 1999, 2003):
   With probability >= 1 - delta over training sample draws S ~ D^m:
     R(Q) <= R_hat(Q) + sqrt((KL(Q || P) + ln(2*sqrt(m) / delta)) / (2m))

2. Seeger & Maurer PAC-Bayes-kl Bound (Seeger, 2002; Maurer, 2004):
   With probability >= 1 - delta:
     kl(R_hat(Q) || R(Q)) <= (KL(Q || P) + ln(2*sqrt(m) / delta)) / m
   where kl(q || p) = q * ln(q/p) + (1-q) * ln((1-q)/(1-p)).
   Inverting kl(q || p) <= epsilon via bisection yields a strictly tighter upper bound,
   converging at rate O(1/m) for zero empirical risk (realizable setting).

3. Catoni's PAC-Bayesian Bound (Catoni, 2007):
   For any tuning parameter c in (0, 2):
     R(Q) <= R_hat(Q) / (1 - c/2) + (KL(Q || P) + ln(1/delta)) / (c * (1 - c/2) * m)

4. Program Ensemble Distribution:
   - Prior P(h): Complexity-weighted prior P(h) ∝ 2^{-depth(h)} (Minimum Description Length).
   - Posterior Q(h): Gibbs posterior Q(h) ∝ P(h) * exp(-beta * m * R_hat(h)).
   - KL(Q || P) = ∑_h Q(h) * ln(Q(h) / P(h)).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


def binary_kl(q: float, p: float, eps: float = 1e-12) -> float:
    """Computes binary relative entropy (Kullback-Leibler divergence) kl(q || p) in nats.
    kl(q || p) = q * ln(q/p) + (1-q) * ln((1-q)/(1-p)).
    """
    q = min(max(q, 0.0), 1.0)
    p = min(max(p, eps), 1.0 - eps)

    term1 = q * math.log(q / p) if q > 0 else 0.0
    term2 = (1.0 - q) * math.log((1.0 - q) / (1.0 - p)) if q < 1.0 else 0.0
    return max(0.0, term1 + term2)


def invert_binary_kl(q: float, epsilon: float, max_iter: int = 50, tol: float = 1e-8) -> float:
    """Finds sup { p in [q, 1] : kl(q || p) <= epsilon } via bisection.
    Since kl(q || p) is strictly convex and increasing on [q, 1], bisection is guaranteed
    to converge to the unique root.
    """
    q = min(max(q, 0.0), 1.0)
    if epsilon <= 0.0:
        return q
    if q >= 1.0 - 1e-12:
        return 1.0

    low = q
    high = 1.0 - 1e-12

    # If even high has kl <= epsilon, upper bound is 1.0
    if binary_kl(q, high) <= epsilon:
        return 1.0

    for _ in range(max_iter):
        mid = (low + high) / 2.0
        val = binary_kl(q, mid)
        if val <= epsilon:
            low = mid
        else:
            high = mid
        if (high - low) < tol:
            break

    return (low + high) / 2.0


def mcallester_bound(
    empirical_risk: float,
    kl_div: float,
    m: int,
    delta: float = 0.05,
) -> float:
    """Computes McAllester's PAC-Bayesian bound on true risk R(Q).
    R(Q) <= R_hat(Q) + sqrt((KL(Q || P) + ln(2*sqrt(m) / delta)) / (2m)).
    """
    if m <= 0:
        raise ValueError(f"Sample size m must be positive, got {m}")
    empirical_risk = min(max(empirical_risk, 0.0), 1.0)
    kl_div = max(kl_div, 0.0)
    delta = min(max(delta, 1e-12), 1.0)

    complexity = (kl_div + math.log(2.0 * math.sqrt(m) / delta)) / (2.0 * m)
    bound = empirical_risk + math.sqrt(max(0.0, complexity))
    return min(1.0, max(0.0, bound))


def seeger_maurer_bound(
    empirical_risk: float,
    kl_div: float,
    m: int,
    delta: float = 0.05,
) -> float:
    """Computes Seeger & Maurer's PAC-Bayes-kl bound on true risk R(Q).
    kl(R_hat(Q) || R(Q)) <= (KL(Q || P) + ln(2*sqrt(m) / delta)) / m.
    Returns the inverted root p >= R_hat(Q).
    """
    if m <= 0:
        raise ValueError(f"Sample size m must be positive, got {m}")
    empirical_risk = min(max(empirical_risk, 0.0), 1.0)
    kl_div = max(kl_div, 0.0)
    delta = min(max(delta, 1e-12), 1.0)

    epsilon = (kl_div + math.log(2.0 * math.sqrt(m) / delta)) / m
    return invert_binary_kl(empirical_risk, epsilon)


def catoni_bound(
    empirical_risk: float,
    kl_div: float,
    m: int,
    delta: float = 0.05,
    c: Optional[float] = None,
) -> float:
    """Computes Catoni's PAC-Bayesian bound on true risk R(Q).
    If c is not specified, optimizes c in (0, 2) via grid search to find the tightest bound.
    """
    if m <= 0:
        raise ValueError(f"Sample size m must be positive, got {m}")
    empirical_risk = min(max(empirical_risk, 0.0), 1.0)
    kl_div = max(kl_div, 0.0)
    delta = min(max(delta, 1e-12), 1.0)

    def eval_c(val_c: float) -> float:
        denom = 1.0 - val_c / 2.0
        return (empirical_risk / denom) + (kl_div + math.log(1.0 / delta)) / (val_c * denom * m)

    if c is not None:
        if not (0.0 < c < 2.0):
            raise ValueError(f"Catoni parameter c must be in (0, 2), got {c}")
        return min(1.0, max(0.0, eval_c(c)))

    # Grid search for optimal c in (0.05, 1.95)
    best_bound = 1.0
    for step in range(1, 40):
        grid_c = step * 0.05
        cand = eval_c(grid_c)
        if cand < best_bound:
            best_bound = cand

    return min(1.0, max(0.0, best_bound))


@dataclass
class ProgramEnsembleDistribution:
    """Represents a prior P and posterior Q distribution over synthesized program hypotheses."""
    program_ids: List[str]
    programs: List[Callable[[Any], Any]]
    prior_weights: List[float]
    posterior_weights: List[float] = field(default_factory=list)

    def __post_init__(self):
        # Normalize prior
        total_p = sum(self.prior_weights)
        if total_p <= 0:
            uniform = 1.0 / len(self.program_ids)
            self.prior_weights = [uniform] * len(self.program_ids)
        else:
            self.prior_weights = [w / total_p for w in self.prior_weights]

        if not self.posterior_weights:
            self.posterior_weights = list(self.prior_weights)
        else:
            total_q = sum(self.posterior_weights)
            if total_q <= 0:
                self.posterior_weights = list(self.prior_weights)
            else:
                self.posterior_weights = [w / total_q for w in self.posterior_weights]

    def compute_kl_divergence(self, eps: float = 1e-12) -> float:
        """Computes KL(Q || P) in nats."""
        kl = 0.0
        for q, p in zip(self.posterior_weights, self.prior_weights):
            if q > 0:
                p_safe = max(p, eps)
                kl += q * math.log(q / p_safe)
        return max(0.0, kl)

    def evaluate_empirical_risks(
        self,
        dataset: Sequence[Tuple[Any, Any]],
        loss_fn: Optional[Callable[[Any, Any], float]] = None,
    ) -> List[float]:
        """Evaluates 0-1 loss (or custom loss) for each individual program."""
        if not dataset:
            return [0.0] * len(self.programs)

        if loss_fn is None:
            loss_fn = lambda pred, actual: 0.0 if pred == actual else 1.0

        risks: List[float] = []
        for fn in self.programs:
            total_loss = sum(loss_fn(fn(x), y) for x, y in dataset)
            risks.append(total_loss / len(dataset))
        return risks

    def compute_expected_empirical_risk(self, individual_risks: List[float]) -> float:
        """Computes expected risk under posterior Q: R_hat(Q) = ∑_i Q(h_i) * R_hat(h_i)."""
        return sum(q * r for q, r in zip(self.posterior_weights, individual_risks))

    def update_to_gibbs_posterior(
        self,
        individual_risks: List[float],
        m: int,
        temperature: float = 1.0,
    ) -> None:
        """Updates Q to the optimal Gibbs posterior: Q(h) ∝ P(h) * exp(-temperature * m * R_hat(h))."""
        unnorm = []
        for p, r in zip(self.prior_weights, individual_risks):
            # Scale risk by m and temperature
            exponent = -temperature * m * r
            # Clip exponent for numerical stability
            exponent = max(-100.0, min(100.0, exponent))
            unnorm.append(p * math.exp(exponent))

        total = sum(unnorm)
        if total > 0:
            self.posterior_weights = [w / total for w in unnorm]
        else:
            self.posterior_weights = list(self.prior_weights)


class PACBayesCertifier:
    """Computes PAC-Bayesian generalization certificates for program synthesis pipelines."""

    def __init__(self, delta: float = 0.05):
        self.delta = delta

    def certify(
        self,
        ensemble: ProgramEnsembleDistribution,
        dataset: Sequence[Tuple[Any, Any]],
        temperature: Optional[float] = None,
    ) -> Dict[str, float]:
        """Computes sound upper bounds on the true generalization risk of the program distribution."""
        m = len(dataset)
        if m == 0:
            raise ValueError("Cannot certify generalization with empty dataset (m=0).")

        indiv_risks = ensemble.evaluate_empirical_risks(dataset)

        if temperature is not None:
            ensemble.update_to_gibbs_posterior(indiv_risks, m, temperature)

        r_hat = ensemble.compute_expected_empirical_risk(indiv_risks)
        kl = ensemble.compute_kl_divergence()

        b_mcallester = mcallester_bound(r_hat, kl, m, self.delta)
        b_seeger = seeger_maurer_bound(r_hat, kl, m, self.delta)
        b_catoni = catoni_bound(r_hat, kl, m, self.delta)

        return {
            "m_samples": float(m),
            "delta": self.delta,
            "kl_divergence": kl,
            "empirical_risk_R_hat": r_hat,
            "mcallester_bound": b_mcallester,
            "seeger_maurer_bound": b_seeger,
            "catoni_bound": b_catoni,
            "certified_bound": min(b_mcallester, b_seeger, b_catoni),
            "seeger_strictly_tighter": b_seeger <= b_mcallester,
        }
