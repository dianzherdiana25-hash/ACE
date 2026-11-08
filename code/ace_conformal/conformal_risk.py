"""Conformal Risk Control & Distribution-Free Prediction Sets.

Mathematical Foundation:
1. Split Conformal Prediction (Vovk et al., 2005):
   Given exchangeable calibration samples (X_1, Y_1), ..., (X_n, Y_n) and significance level alpha in (0, 1):
   Let nonconformity scores be s_i = S(X_i, Y_i).
   Compute empirical adjusted quantile:
     q_hat = Quantile({s_1, ..., s_n}, ceil((n + 1) * (1 - alpha)) / n)
   For a new test point X_{n+1}, the prediction set:
     C_{1-alpha}(X_{n+1}) = { y : S(X_{n+1}, y) <= q_hat }
   guarantees exact finite-sample coverage:
     P(Y_{n+1} in C_{1-alpha}(X_{n+1})) >= 1 - alpha

2. Conformal Risk Control (Bates et al., 2021; Angelopoulos et al., 2021):
   For any monotonic bounded loss function l(C_lambda(X), Y) in [0, B]:
   The finite-sample risk-controlling threshold lambda_hat satisfies:
     (n / (n + 1)) * R_hat_n(lambda_hat) + (B / (n + 1)) <= alpha
   guaranteeing expected risk control:
     E[ l(C_{lambda_hat}(X_{test}), Y_{test}) ] <= alpha
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple


def compute_conformal_quantile(scores: Sequence[float], alpha: float) -> float:
    """Computes the exact finite-sample conformal quantile:
    q_hat = sorted_scores[ceil((n + 1) * (1 - alpha)) - 1].
    """
    n = len(scores)
    if n == 0:
        raise ValueError("Cannot compute conformal quantile on empty scores array.")
    alpha = min(max(alpha, 1e-6), 1.0 - 1e-6)

    # 1-indexed target index
    k = math.ceil((n + 1) * (1.0 - alpha))
    if k > n:
        return float("inf")

    sorted_scores = sorted(scores)
    return sorted_scores[k - 1]


@dataclass
class ConformalIntervalPredictor:
    """Split conformal predictor for continuous numerical outputs (e.g. program execution cost)."""
    point_predictor: Callable[[Any], float]
    alpha: float = 0.10
    q_hat: Optional[float] = None
    calibration_size: int = 0

    def calibrate(self, calibration_set: Sequence[Tuple[Any, float]]) -> float:
        """Calibrates prediction interval width on held-out calibration samples."""
        residuals = []
        for x, y in calibration_set:
            pred = self.point_predictor(x)
            residuals.append(abs(float(y) - float(pred)))

        self.calibration_size = len(residuals)
        self.q_hat = compute_conformal_quantile(residuals, self.alpha)
        return self.q_hat

    def predict_interval(self, x: Any) -> Tuple[float, float]:
        """Returns distribution-free (1 - alpha) prediction interval [y_low, y_high]."""
        if self.q_hat is None:
            raise RuntimeError("Predictor must be calibrated before generating intervals.")
        pred = self.point_predictor(x)
        return (pred - self.q_hat, pred + self.q_hat)


@dataclass
class ConformalSetPredictor:
    """Split conformal predictor for discrete candidate sets / classification labels."""
    score_model: Callable[[Any], Dict[Any, float]]
    alpha: float = 0.10
    q_hat: Optional[float] = None
    calibration_size: int = 0

    def calibrate(self, calibration_set: Sequence[Tuple[Any, Any]]) -> float:
        """Calibrates nonconformity threshold using 1 - p(y | x)."""
        scores = []
        for x, true_label in calibration_set:
            dist = self.score_model(x)
            prob = dist.get(true_label, 0.0)
            # Nonconformity score: higher when model assigns lower probability to true label
            scores.append(1.0 - prob)

        self.calibration_size = len(scores)
        self.q_hat = compute_conformal_quantile(scores, self.alpha)
        return self.q_hat

    def predict_set(self, x: Any) -> Set[Any]:
        """Returns the distribution-free prediction set C_{1-alpha}(x)."""
        if self.q_hat is None:
            raise RuntimeError("Predictor must be calibrated before generating prediction sets.")
        dist = self.score_model(x)
        return {label for label, prob in dist.items() if (1.0 - prob) <= self.q_hat}


class ConformalRiskController:
    """Controls general bounded loss E[l(C_lambda(X), Y)] <= alpha (Bates et al., 2021)."""

    def __init__(
        self,
        set_generator: Callable[[Any, float], Any],
        loss_fn: Callable[[Any, Any], float],
        loss_bound_B: float = 1.0,
        target_risk_alpha: float = 0.10,
    ):
        self.set_generator = set_generator
        self.loss_fn = loss_fn
        self.loss_bound_B = loss_bound_B
        self.target_risk_alpha = target_risk_alpha
        self.calibrated_lambda: Optional[float] = None

    def calibrate(
        self,
        calibration_set: Sequence[Tuple[Any, Any]],
        lambda_candidates: Sequence[float],
    ) -> float:
        """Finds the optimal parameter lambda_hat guaranteeing finite-sample risk <= alpha."""
        n = len(calibration_set)
        if n == 0:
            raise ValueError("Calibration set must be non-empty.")

        # Sort candidate parameters in increasing order of set size / decreasing loss
        sorted_lambdas = sorted(lambda_candidates)

        chosen_lambda = sorted_lambdas[-1]
        for lam in sorted_lambdas:
            losses = [
                self.loss_fn(self.set_generator(x, lam), y)
                for x, y in calibration_set
            ]
            r_hat = sum(losses) / n
            # Bates et al. (2021) finite-sample corrected empirical risk bound
            inflated_risk = (n / (n + 1.0)) * r_hat + (self.loss_bound_B / (n + 1.0))
            if inflated_risk <= self.target_risk_alpha:
                chosen_lambda = lam
                break

        self.calibrated_lambda = chosen_lambda
        return self.calibrated_lambda

    def predict(self, x: Any) -> Any:
        if self.calibrated_lambda is None:
            raise RuntimeError("ConformalRiskController must be calibrated before prediction.")
        return self.set_generator(x, self.calibrated_lambda)


def evaluate_coverage(
    set_predictor: Callable[[Any], Any],
    test_set: Sequence[Tuple[Any, Any]],
    is_interval: bool = False,
) -> Dict[str, float]:
    """Empirically evaluates marginal coverage and average set efficiency over a test set."""
    if not test_set:
        return {"coverage": 1.0, "average_size": 0.0}

    covered_count = 0
    total_size = 0.0

    for x, y in test_set:
        c = set_predictor(x)
        if is_interval:
            low, high = c
            if low <= y <= high:
                covered_count += 1
            total_size += max(0.0, high - low)
        else:
            if y in c:
                covered_count += 1
            total_size += len(c)

    n = len(test_set)
    return {
        "coverage": covered_count / n,
        "average_size": total_size / n,
        "test_samples": float(n),
    }
